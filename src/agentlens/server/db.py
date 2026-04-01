"""SQLite database access for the API server (read-side + replay writes)."""

from __future__ import annotations

import json
from datetime import datetime

import aiosqlite

from agentlens.sdk.models import Span, SpanKind, Trace
from agentlens.sdk.recorder import SCHEMA_SQL, get_db_path


async def _get_connection() -> aiosqlite.Connection:
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(db_path), timeout=10.0)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    await db.executescript(SCHEMA_SQL)
    try:
        await db.execute(
            "ALTER TABLE spans ADD COLUMN is_stale INTEGER NOT NULL DEFAULT 0"
        )
    except Exception:
        pass  # column already exists
    await db.commit()
    return db


def _parse_datetime(s: str | None) -> datetime | None:
    if s is None:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _parse_json(s: str | None) -> any:
    if s is None:
        return None
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return s


def _row_to_trace(row: aiosqlite.Row, spans: list[Span] | None = None) -> Trace:
    return Trace(
        id=row["id"],
        name=row["name"],
        started_at=_parse_datetime(row["started_at"]),
        ended_at=_parse_datetime(row["ended_at"]),
        status=row["status"],
        metadata=_parse_json(row["metadata"]) or {},
        spans=spans or [],
        total_tokens=row["total_tokens"],
        total_cost_usd=row["total_cost_usd"],
        total_duration_ms=row["total_duration_ms"],
        parent_trace_id=row["parent_trace_id"],
    )


def _row_to_span(row: aiosqlite.Row) -> Span:
    return Span(
        id=row["id"],
        trace_id=row["trace_id"],
        parent_span_id=row["parent_span_id"],
        kind=SpanKind(row["kind"]),
        name=row["name"],
        started_at=_parse_datetime(row["started_at"]),
        ended_at=_parse_datetime(row["ended_at"]),
        status=row["status"],
        input=_parse_json(row["input"]),
        output=_parse_json(row["output"]),
        error=row["error"],
        model=row["model"],
        tokens_in=row["tokens_in"],
        tokens_out=row["tokens_out"],
        cost_usd=row["cost_usd"],
        sequence=row["sequence"],
        is_mutated=bool(row["is_mutated"]),
        is_stale=bool(row["is_stale"]) if "is_stale" in row.keys() else False,
    )


async def list_traces(
    limit: int = 50, offset: int = 0, status: str | None = None
) -> tuple[list[Trace], int]:
    db = await _get_connection()
    try:
        if status:
            count_row = await db.execute_fetchall(
                "SELECT COUNT(*) as cnt FROM traces WHERE status = ?", (status,)
            )
            total = count_row[0][0]
            rows = await db.execute_fetchall(
                "SELECT * FROM traces WHERE status = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (status, limit, offset),
            )
        else:
            count_row = await db.execute_fetchall("SELECT COUNT(*) as cnt FROM traces")
            total = count_row[0][0]
            rows = await db.execute_fetchall(
                "SELECT * FROM traces ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
        traces = [_row_to_trace(row) for row in rows]
        return traces, total
    finally:
        await db.close()


async def get_trace(trace_id: str) -> Trace | None:
    db = await _get_connection()
    try:
        rows = await db.execute_fetchall("SELECT * FROM traces WHERE id = ?", (trace_id,))
        if not rows:
            return None
        span_rows = await db.execute_fetchall(
            "SELECT * FROM spans WHERE trace_id = ? ORDER BY sequence", (trace_id,)
        )
        spans = [_row_to_span(row) for row in span_rows]
        return _row_to_trace(rows[0], spans)
    finally:
        await db.close()


async def delete_trace(trace_id: str) -> bool:
    db = await _get_connection()
    try:
        cursor = await db.execute("DELETE FROM spans WHERE trace_id = ?", (trace_id,))
        cursor2 = await db.execute("DELETE FROM traces WHERE id = ?", (trace_id,))
        await db.commit()
        return cursor2.rowcount > 0
    finally:
        await db.close()


async def save_trace(trace: Trace) -> None:
    """Save a trace (used for replay results)."""
    from agentlens.sdk.recorder import _safe_json_dumps

    db = await _get_connection()
    try:
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
                    cost_usd, sequence, is_mutated, is_stale)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                ),
            )
        await db.commit()
    finally:
        await db.close()


async def get_replays(trace_id: str) -> list[Trace]:
    """Get all replay traces that were forked from the given trace."""
    db = await _get_connection()
    try:
        rows = await db.execute_fetchall(
            "SELECT * FROM traces WHERE parent_trace_id = ? ORDER BY created_at DESC",
            (trace_id,),
        )
        return [_row_to_trace(row) for row in rows]
    finally:
        await db.close()


async def get_traces_count() -> int:
    db = await _get_connection()
    try:
        rows = await db.execute_fetchall("SELECT COUNT(*) FROM traces")
        return rows[0][0]
    finally:
        await db.close()
