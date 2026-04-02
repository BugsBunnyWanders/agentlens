"""OpenAI Agents SDK tracing processor for automatic trace capture."""

from __future__ import annotations

import logging
import threading
from contextvars import Token
from typing import Any

from agentlens.integrations._base import estimate_cost, safe_serialize
from agentlens.sdk.models import SpanKind
from agentlens.sdk.tracer import (
    SpanContext,
    TraceContext,
    _current_span,
    _current_trace,
    _is_enabled,
    _now,
    _schedule_flush,
)

logger = logging.getLogger("agentlens")

try:
    from agents.tracing import TracingProcessor
    from agents.tracing.spans import Span as AgentsSpan

    HAS_OPENAI_AGENTS = True
except ImportError:
    HAS_OPENAI_AGENTS = False

# Span type detection via string matching on class names
# (avoids hard dependency on specific span_data imports)
_SPAN_KIND_MAP = {
    "AgentSpanData": SpanKind.AGENT,
    "GenerationSpanData": SpanKind.LLM,
    "FunctionSpanData": SpanKind.TOOL,
    "HandoffSpanData": SpanKind.AGENT,
    "GuardrailSpanData": SpanKind.CUSTOM,
    "CustomSpanData": SpanKind.CUSTOM,
}


class AgentLensTracingProcessor:
    """OpenAI Agents SDK tracing processor that captures traces into AgentLens.

    Usage:
        from agentlens.integrations.openai_agents import AgentLensTracingProcessor
        from agents import set_tracing_processor

        set_tracing_processor(AgentLensTracingProcessor())

        # All agent runs are now automatically traced
        result = await Runner.run(agent, input="Process this refund")
    """

    def __init__(self, default_trace_name: str = "openai-agents") -> None:
        if not HAS_OPENAI_AGENTS:
            raise ImportError(
                "OpenAI Agents SDK integration requires 'openai-agents'. "
                "Install with: pip install agentlens-xray[openai-agents]"
            )
        self._default_trace_name = default_trace_name
        self._trace_ctx: TraceContext | None = None
        self._trace_token: Token | None = None
        self._span_map: dict[str, SpanContext] = {}
        self._restore_tokens: dict[str, Token] = {}
        self._lock = threading.Lock()

    def on_trace_start(self, trace: Any) -> None:
        if not _is_enabled():
            return
        name = getattr(trace, "name", None) or self._default_trace_name
        self._trace_ctx = TraceContext(str(name), {"framework": "openai-agents"})
        self._trace_token = _current_trace.set(self._trace_ctx)

    def on_trace_end(self, trace: Any) -> None:
        if self._trace_ctx:
            self._trace_ctx.ended_at = _now()
            self._trace_ctx.status = "completed"
            if self._trace_token:
                _current_trace.reset(self._trace_token)
            _schedule_flush(self._trace_ctx)
            self._trace_ctx = None
            self._span_map.clear()
            self._restore_tokens.clear()

    def on_span_start(self, span: Any) -> None:
        if not self._trace_ctx:
            return

        # Determine span kind from span_data class name
        span_data = getattr(span, "span_data", None)
        data_type = type(span_data).__name__ if span_data else "CustomSpanData"
        kind = _SPAN_KIND_MAP.get(data_type, SpanKind.CUSTOM)

        # Get name
        name = getattr(span, "span_id", "span")
        if span_data:
            if hasattr(span_data, "name"):
                name = span_data.name or name
            elif data_type == "GenerationSpanData":
                name = getattr(span_data, "model", "llm") or "llm"
            elif data_type == "FunctionSpanData":
                name = getattr(span_data, "name", "function") or "function"

        # Get model for LLM spans
        model = None
        if data_type == "GenerationSpanData":
            model = getattr(span_data, "model", None)

        with self._lock:
            # Set parent context
            parent_id = getattr(span, "parent_id", None)
            if parent_id and parent_id in self._span_map:
                parent = self._span_map[parent_id]
                restore_token = _current_span.set(parent)
            else:
                restore_token = _current_span.set(None)

            al_span = self._trace_ctx.span(str(name), kind, model=model)
            al_span.__enter__()

            span_id = getattr(span, "span_id", str(id(span)))
            self._span_map[span_id] = al_span
            self._restore_tokens[span_id] = restore_token

        # Record input
        if span_data:
            if hasattr(span_data, "input"):
                al_span.record_input(safe_serialize(span_data.input))

    def on_span_end(self, span: Any) -> None:
        span_id = getattr(span, "span_id", str(id(span)))
        span_data = getattr(span, "span_data", None)

        with self._lock:
            al_span = self._span_map.pop(span_id, None)
            if not al_span:
                return

            # Record output and tokens
            if span_data:
                if hasattr(span_data, "output"):
                    al_span.record_output(safe_serialize(span_data.output))
                if hasattr(span_data, "usage") and span_data.usage:
                    usage = span_data.usage
                    tin = getattr(usage, "input_tokens", 0) or 0
                    tout = getattr(usage, "output_tokens", 0) or 0
                    al_span.record_tokens(tin, tout)
                    cost = estimate_cost(al_span.model, tin, tout)
                    if cost:
                        al_span.record_cost(cost)

            al_span.__exit__(None, None, None)
            restore_token = self._restore_tokens.pop(span_id, None)
            if restore_token:
                _current_span.reset(restore_token)


def install_agentlens_tracing(**kwargs: Any) -> AgentLensTracingProcessor:
    """One-liner to register AgentLens as the tracing processor.

    Usage:
        from agentlens.integrations.openai_agents import install_agentlens_tracing
        install_agentlens_tracing()
    """
    if not HAS_OPENAI_AGENTS:
        raise ImportError(
            "OpenAI Agents SDK integration requires 'openai-agents'. "
            "Install with: pip install agentlens-xray[openai-agents]"
        )
    from agents.tracing import set_tracing_processor

    processor = AgentLensTracingProcessor(**kwargs)
    set_tracing_processor(processor)
    return processor
