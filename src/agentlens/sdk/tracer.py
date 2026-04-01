"""Core tracing engine — context-based trace/span management using contextvars."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from agentlens.sdk.models import Span, SpanKind, Trace

logger = logging.getLogger("agentlens")

_current_trace: ContextVar[TraceContext | None] = ContextVar("_current_trace", default=None)
_current_span: ContextVar[SpanContext | None] = ContextVar("_current_span", default=None)
_replay_context: ContextVar[Any] = ContextVar("_replay_context", default=None)  # ReplayContext | None


def _is_enabled() -> bool:
    return os.environ.get("AGENTLENS_ENABLED", "true").lower() not in ("false", "0", "no")


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SpanContext:
    """Mutable runtime state for a single span."""

    def __init__(
        self,
        trace_ctx: TraceContext,
        name: str,
        kind: SpanKind,
        parent_span_id: str | None = None,
        model: str | None = None,
    ):
        self.span_id = str(uuid4())
        self.trace_id = trace_ctx.trace_id
        self.parent_span_id = parent_span_id
        self.kind = kind
        self.name = name
        self.sequence = trace_ctx.next_sequence()
        self.started_at = _now()
        self.ended_at: datetime | None = None
        self.status: str = "running"
        self.input: Any = None
        self.output: Any = None
        self.error: str | None = None
        self.model = model
        self.tokens_in: int | None = None
        self.tokens_out: int | None = None
        self.cost_usd: float | None = None
        self.is_reexecuted: bool = False
        self._trace_ctx = trace_ctx
        self._span_token: Token | None = None

    def record_input(self, data: Any) -> None:
        self.input = data

    def record_output(self, data: Any) -> None:
        self.output = data

    def record_tokens(self, tokens_in: int, tokens_out: int) -> None:
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out

    def record_cost(self, cost_usd: float) -> None:
        self.cost_usd = cost_usd

    def to_span_model(self) -> Span:
        return Span(
            id=self.span_id,
            trace_id=self.trace_id,
            parent_span_id=self.parent_span_id,
            kind=self.kind,
            name=self.name,
            started_at=self.started_at,
            ended_at=self.ended_at,
            status=self.status,
            input=self.input,
            output=self.output,
            error=self.error,
            model=self.model,
            tokens_in=self.tokens_in,
            tokens_out=self.tokens_out,
            cost_usd=self.cost_usd,
            sequence=self.sequence,
            is_reexecuted=self.is_reexecuted,
        )

    def __enter__(self) -> SpanContext:
        self._span_token = _current_span.set(self)
        return self

    def __exit__(self, exc_type: type | None, exc_val: BaseException | None, exc_tb: Any) -> None:
        self.ended_at = _now()
        if exc_type is not None:
            self.status = "failed"
            self.error = str(exc_val) if exc_val else str(exc_type)
        else:
            self.status = "completed"
        self._trace_ctx.spans.append(self)
        if self._span_token is not None:
            _current_span.reset(self._span_token)

    async def __aenter__(self) -> SpanContext:
        return self.__enter__()

    async def __aexit__(
        self, exc_type: type | None, exc_val: BaseException | None, exc_tb: Any
    ) -> None:
        self.__exit__(exc_type, exc_val, exc_tb)


class TraceContext:
    """Mutable runtime state for a trace."""

    def __init__(self, name: str, metadata: dict[str, Any] | None = None):
        self.trace_id = str(uuid4())
        self.name = name
        self.metadata = metadata or {}
        self.started_at = _now()
        self.ended_at: datetime | None = None
        self.status: str = "running"
        self.error: str | None = None
        self.spans: list[SpanContext] = []
        self._sequence_counter = 0
        self._trace_token: Token | None = None

    def next_sequence(self) -> int:
        seq = self._sequence_counter
        self._sequence_counter += 1
        return seq

    def span(
        self,
        name: str,
        kind: SpanKind | str = SpanKind.CUSTOM,
        model: str | None = None,
    ) -> SpanContext:
        if isinstance(kind, str):
            kind = SpanKind(kind)
        parent = _current_span.get()
        parent_id = parent.span_id if parent else None
        return SpanContext(self, name, kind, parent_span_id=parent_id, model=model)

    def to_trace_model(self) -> Trace:
        span_models = [s.to_span_model() for s in self.spans]
        total_tokens = None
        total_cost = None
        for s in span_models:
            if s.tokens_in is not None or s.tokens_out is not None:
                if total_tokens is None:
                    total_tokens = 0
                total_tokens += (s.tokens_in or 0) + (s.tokens_out or 0)
            if s.cost_usd is not None:
                if total_cost is None:
                    total_cost = 0.0
                total_cost += s.cost_usd

        duration_ms = None
        if self.ended_at and self.started_at:
            duration_ms = (self.ended_at - self.started_at).total_seconds() * 1000

        return Trace(
            id=self.trace_id,
            name=self.name,
            started_at=self.started_at,
            ended_at=self.ended_at,
            status=self.status,
            metadata=self.metadata,
            spans=span_models,
            total_tokens=total_tokens,
            total_cost_usd=total_cost,
            total_duration_ms=duration_ms,
        )


def get_current_trace() -> TraceContext | None:
    return _current_trace.get()


def get_current_span() -> SpanContext | None:
    return _current_span.get()


def get_replay_context() -> Any:
    """Get the active ReplayContext, or None."""
    return _replay_context.get()


def set_replay_context(ctx: Any) -> Token:
    """Set the active ReplayContext. Returns token for reset."""
    return _replay_context.set(ctx)


@contextmanager
def start_trace(name: str, metadata: dict[str, Any] | None = None):
    """Context manager to create a trace scope (sync)."""
    if not _is_enabled():
        yield _NoOpTraceContext()
        return

    ctx = TraceContext(name, metadata)
    token = _current_trace.set(ctx)
    try:
        yield ctx
    except Exception as e:
        ctx.status = "failed"
        ctx.error = str(e)
        raise
    finally:
        ctx.ended_at = _now()
        if ctx.status != "failed":
            ctx.status = "completed"
        _current_trace.reset(token)
        _schedule_flush(ctx)


@asynccontextmanager
async def start_trace_async(name: str, metadata: dict[str, Any] | None = None):
    """Context manager to create a trace scope (async)."""
    if not _is_enabled():
        yield _NoOpTraceContext()
        return

    ctx = TraceContext(name, metadata)
    token = _current_trace.set(ctx)
    try:
        yield ctx
    except Exception as e:
        ctx.status = "failed"
        ctx.error = str(e)
        raise
    finally:
        ctx.ended_at = _now()
        if ctx.status != "failed":
            ctx.status = "completed"
        _current_trace.reset(token)
        _schedule_flush(ctx)


class _NoOpTraceContext:
    """No-op stand-in when tracing is disabled."""

    def span(self, *args: Any, **kwargs: Any) -> _NoOpSpanContext:
        return _NoOpSpanContext()


class _NoOpSpanContext:
    def record_input(self, data: Any) -> None:
        pass

    def record_output(self, data: Any) -> None:
        pass

    def record_tokens(self, tokens_in: int, tokens_out: int) -> None:
        pass

    def record_cost(self, cost_usd: float) -> None:
        pass

    def __enter__(self) -> _NoOpSpanContext:
        return self

    def __exit__(self, *args: Any) -> None:
        pass

    async def __aenter__(self) -> _NoOpSpanContext:
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass


def _schedule_flush(ctx: TraceContext) -> None:
    """Schedule writing a completed trace to storage."""
    try:
        from agentlens.sdk.recorder import get_recorder

        trace_model = ctx.to_trace_model()
        recorder = get_recorder()
        recorder.schedule(trace_model)
    except Exception:
        logger.warning("Failed to schedule trace flush", exc_info=True)
