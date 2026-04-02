"""Async SQLite writer — buffers completed traces and writes them asynchronously."""

from __future__ import annotations

import asyncio
import atexit
import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

import aiosqlite

from agentlens.sdk.models import Trace

logger = logging.getLogger("agentlens")

_SHUTDOWN = object()  # Sentinel to signal consumer loop to exit

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS traces (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    metadata TEXT DEFAULT '{}',
    total_tokens INTEGER,
    total_cost_usd REAL,
    total_duration_ms REAL,
    parent_trace_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS spans (
    id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL REFERENCES traces(id) ON DELETE CASCADE,
    parent_span_id TEXT,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    input TEXT,
    output TEXT,
    error TEXT,
    model TEXT,
    tokens_in INTEGER,
    tokens_out INTEGER,
    cost_usd REAL,
    sequence INTEGER NOT NULL,
    is_mutated INTEGER NOT NULL DEFAULT 0,
    is_stale INTEGER NOT NULL DEFAULT 0,
    is_reexecuted INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_spans_trace_id ON spans(trace_id);
CREATE INDEX IF NOT EXISTS idx_spans_sequence ON spans(trace_id, sequence);
CREATE INDEX IF NOT EXISTS idx_traces_created_at ON traces(created_at);

"""


def _safe_json_dumps(obj: Any) -> str | None:
    if obj is None:
        return None
    try:
        return json.dumps(obj)
    except (TypeError, ValueError):
        return json.dumps(repr(obj))


def get_db_path() -> Path:
    """Return the path to the SQLite traces database.

    Priority:
    1. AGENTLENS_DB_PATH env var (explicit override)
    2. .agentlens/traces.db in the current working directory (project-local)
    """
    env_path = os.environ.get("AGENTLENS_DB_PATH")
    if env_path:
        return Path(env_path)
    return Path.cwd() / ".agentlens" / "traces.db"


class Recorder:
    """Async trace writer with background event loop fallback for sync contexts."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue = asyncio.Queue()
        self._db: aiosqlite.Connection | None = None
        self._consumer_task: asyncio.Task | None = None
        self._bg_loop: asyncio.AbstractEventLoop | None = None
        self._bg_thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._shutting_down = False

    async def _ensure_db(self) -> aiosqlite.Connection:
        if self._db is None:
            db_path = get_db_path()
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self._db = await aiosqlite.connect(str(db_path), timeout=10.0)
            await self._db.execute("PRAGMA journal_mode=WAL")
            await self._db.execute("PRAGMA foreign_keys=ON")
            await self._db.executescript(SCHEMA_SQL)
            # Migrations: add columns if missing
            for col in ("is_stale", "is_reexecuted"):
                try:
                    await self._db.execute(
                        f"ALTER TABLE spans ADD COLUMN {col} INTEGER NOT NULL DEFAULT 0"
                    )
                except Exception:
                    pass  # column already exists
            await self._db.commit()
        return self._db

    async def _write_trace(self, trace: Trace) -> None:
        db = await self._ensure_db()
        await db.execute(
            """INSERT OR REPLACE INTO traces
               (id, name, started_at, ended_at, status, metadata,
                total_tokens, total_cost_usd, total_duration_ms, parent_trace_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                trace.id,
                trace.name,
                trace.started_at.isoformat(),
                trace.ended_at.isoformat() if trace.ended_at else None,
                trace.status,
                json.dumps(trace.metadata),
                trace.total_tokens,
                trace.total_cost_usd,
                trace.total_duration_ms,
                trace.parent_trace_id,
            ),
        )
        for span in trace.spans:
            await db.execute(
                """INSERT OR REPLACE INTO spans
                   (id, trace_id, parent_span_id, kind, name, started_at, ended_at,
                    status, input, output, error, model, tokens_in, tokens_out,
                    cost_usd, sequence, is_mutated, is_stale, is_reexecuted)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    span.id,
                    span.trace_id,
                    span.parent_span_id,
                    span.kind.value,
                    span.name,
                    span.started_at.isoformat(),
                    span.ended_at.isoformat() if span.ended_at else None,
                    span.status,
                    _safe_json_dumps(span.input),
                    _safe_json_dumps(span.output),
                    span.error,
                    span.model,
                    span.tokens_in,
                    span.tokens_out,
                    span.cost_usd,
                    span.sequence,
                    1 if span.is_mutated else 0,
                    1 if span.is_stale else 0,
                    1 if span.is_reexecuted else 0,
                ),
            )
        await db.commit()

    async def _consumer(self) -> None:
        while True:
            item = await self._queue.get()
            if item is _SHUTDOWN:
                self._queue.task_done()
                break
            try:
                await self._write_trace(item)
            except Exception:
                logger.warning("Failed to write trace %s", item.id, exc_info=True)
            finally:
                self._queue.task_done()

    async def enqueue(self, trace: Trace) -> None:
        if self._consumer_task is None or self._consumer_task.done():
            self._consumer_task = asyncio.create_task(self._consumer())
        await self._queue.put(trace)

    async def flush(self) -> None:
        if not self._queue.empty():
            await self._queue.join()

    def _ensure_bg_loop(self) -> asyncio.AbstractEventLoop:
        with self._lock:
            if self._bg_loop is None or self._bg_loop.is_closed():
                self._bg_loop = asyncio.new_event_loop()
                self._bg_thread = threading.Thread(
                    target=self._bg_loop.run_forever, daemon=True
                )
                self._bg_thread.start()
            return self._bg_loop

    def schedule(self, trace: Trace) -> None:
        """Schedule a trace for writing. Works from both sync and async contexts."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.enqueue(trace))
        except RuntimeError:
            bg_loop = self._ensure_bg_loop()
            asyncio.run_coroutine_threadsafe(self.enqueue(trace), bg_loop)

    async def shutdown(self) -> None:
        """Signal the consumer to stop after processing remaining items."""
        await self._queue.put(_SHUTDOWN)

    def flush_sync(self, timeout: float = 5.0) -> None:
        """Synchronously flush all pending traces (for atexit)."""
        self._shutting_down = True
        try:
            if self._bg_loop and not self._bg_loop.is_closed():
                asyncio.run_coroutine_threadsafe(self.shutdown(), self._bg_loop)
                future = asyncio.run_coroutine_threadsafe(self.flush(), self._bg_loop)
                future.result(timeout=timeout)
            else:
                try:
                    loop = asyncio.get_running_loop()
                    loop.run_until_complete(self.flush())
                except RuntimeError:
                    pass
        except Exception:
            logger.warning("Failed to flush traces on exit", exc_info=True)


_recorder: Recorder | None = None
_recorder_lock = threading.Lock()


def get_recorder() -> Recorder:
    global _recorder
    if _recorder is None:
        with _recorder_lock:
            if _recorder is None:
                _recorder = Recorder()
                atexit.register(_recorder.flush_sync)
    return _recorder
