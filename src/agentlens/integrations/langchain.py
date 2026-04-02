"""LangChain/LangGraph callback handler for automatic trace capture."""

from __future__ import annotations

import logging
import threading
from contextvars import Token
from typing import Any
from uuid import UUID

from agentlens.integrations._base import (
    extract_model_name,
    estimate_cost,
    safe_serialize,
    serialize_messages,
)
from agentlens.sdk.models import SpanKind
from agentlens.sdk.tracer import (
    SpanContext,
    TraceContext,
    _current_span,
    _current_trace,
    _now,
    _is_enabled,
    _schedule_flush,
)

logger = logging.getLogger("agentlens")

try:
    from langchain_core.callbacks import BaseCallbackHandler
except ImportError:
    raise ImportError(
        "LangChain integration requires 'langchain-core'. "
        "Install with: pip install agentlens-xray[langchain]"
    )


class AgentLensCallbackHandler(BaseCallbackHandler):
    """LangChain/LangGraph callback handler that captures traces into AgentLens.

    Usage:
        from agentlens.integrations.langchain import AgentLensCallbackHandler

        # As context manager (recommended)
        with AgentLensCallbackHandler(trace_name="my_agent") as handler:
            chain.invoke(input, config={"callbacks": [handler]})

        # Standalone (auto-creates and finalizes trace)
        handler = AgentLensCallbackHandler(trace_name="my_agent")
        chain.invoke(input, config={"callbacks": [handler]})
        # Trace is flushed when the last span completes
    """

    def __init__(
        self,
        trace_name: str = "langchain",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__()
        self._trace_name = trace_name
        self._metadata = {**(metadata or {}), "framework": "langchain"}
        self._trace_ctx: TraceContext | None = None
        self._trace_token: Token | None = None
        self._owns_trace = False
        self._run_to_span: dict[UUID, SpanContext] = {}
        self._restore_tokens: dict[UUID, Token] = {}
        self._active_runs = 0
        self._in_context_manager = False
        self._lock = threading.Lock()

    def __enter__(self) -> AgentLensCallbackHandler:
        if not _is_enabled():
            return self
        self._trace_ctx = TraceContext(self._trace_name, self._metadata)
        self._trace_token = _current_trace.set(self._trace_ctx)
        self._owns_trace = True
        self._in_context_manager = True
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._trace_ctx and self._owns_trace:
            self._trace_ctx.ended_at = _now()
            self._trace_ctx.status = "failed" if exc_type else "completed"
            if exc_val:
                self._trace_ctx.error = str(exc_val)
            if self._trace_token:
                _current_trace.reset(self._trace_token)
            _schedule_flush(self._trace_ctx)
            self._trace_ctx = None

    def _ensure_trace(self) -> TraceContext | None:
        """Get or create the trace context."""
        if not _is_enabled():
            return None
        if self._trace_ctx:
            return self._trace_ctx
        # Check if there's an external trace
        from agentlens.sdk.tracer import get_current_trace

        existing = get_current_trace()
        if existing:
            self._trace_ctx = existing
            self._owns_trace = False
            return existing
        # Auto-create a trace
        self._trace_ctx = TraceContext(self._trace_name, self._metadata)
        self._trace_token = _current_trace.set(self._trace_ctx)
        self._owns_trace = True
        return self._trace_ctx

    def _create_span(
        self,
        name: str,
        kind: SpanKind,
        run_id: UUID,
        parent_run_id: UUID | None,
        model: str | None = None,
    ) -> SpanContext | None:
        trace_ctx = self._ensure_trace()
        if not trace_ctx:
            return None

        with self._lock:
            # Ensure trace context is set in this thread (LangChain may call
            # sync handlers from a worker thread where the ContextVar is unset)
            _current_trace.set(trace_ctx)

            # Set parent context for correct nesting
            if parent_run_id and parent_run_id in self._run_to_span:
                parent = self._run_to_span[parent_run_id]
                restore_token = _current_span.set(parent)
            else:
                restore_token = _current_span.set(None)

            span = trace_ctx.span(name, kind, model=model)
            span.__enter__()
            self._run_to_span[run_id] = span
            self._restore_tokens[run_id] = restore_token
            self._active_runs += 1
            return span

    def _end_span(self, run_id: UUID, error: BaseException | None = None) -> None:
        with self._lock:
            span = self._run_to_span.pop(run_id, None)
            if not span:
                return
            if error:
                span.__exit__(type(error), error, None)
            else:
                span.__exit__(None, None, None)
            restore_token = self._restore_tokens.pop(run_id, None)
            if restore_token:
                _current_span.reset(restore_token)
            self._active_runs -= 1

            # Auto-finalize trace when all runs are done (not in context manager mode)
            if self._active_runs == 0 and self._owns_trace and self._trace_ctx and not self._in_context_manager:
                self._trace_ctx.ended_at = _now()
                self._trace_ctx.status = "completed"
                if self._trace_token:
                    _current_trace.reset(self._trace_token)
                _schedule_flush(self._trace_ctx)
                self._trace_ctx = None

    # --- Chain callbacks ---

    def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        name = serialized.get("name") or serialized.get("id", ["chain"])[-1]
        # Detect agent patterns
        id_list = serialized.get("id", [])
        kind = SpanKind.CHAIN
        if any("agent" in str(s).lower() for s in id_list):
            kind = SpanKind.AGENT
        span = self._create_span(str(name), kind, run_id, parent_run_id)
        if span:
            span.record_input(safe_serialize(inputs))

    def on_chain_end(
        self, outputs: dict[str, Any], *, run_id: UUID, **kwargs: Any
    ) -> None:
        with self._lock:
            span = self._run_to_span.get(run_id)
        if span:
            span.record_output(safe_serialize(outputs))
        self._end_span(run_id)

    def on_chain_error(
        self, error: BaseException, *, run_id: UUID, **kwargs: Any
    ) -> None:
        self._end_span(run_id, error)

    # --- LLM callbacks ---

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        model = extract_model_name(serialized)
        name = model or serialized.get("name", "llm")
        span = self._create_span(str(name), SpanKind.LLM, run_id, parent_run_id, model=model)
        if span:
            # Prefer messages (ChatModel) over prompts (LLM)
            messages = kwargs.get("messages")
            if messages:
                span.record_input(serialize_messages(messages))
            else:
                span.record_input(prompts)

    def on_llm_end(self, response: Any, *, run_id: UUID, **kwargs: Any) -> None:
        with self._lock:
            span = self._run_to_span.get(run_id)
        if span:
            # Extract output text
            try:
                output = response.generations[0][0].text
                if hasattr(response.generations[0][0], "message"):
                    msg = response.generations[0][0].message
                    output = safe_serialize(msg)
            except (IndexError, AttributeError):
                output = safe_serialize(response)
            span.record_output(output)

            # Extract tokens
            if hasattr(response, "llm_output") and response.llm_output:
                usage = response.llm_output.get("token_usage", {})
                tin = usage.get("prompt_tokens")
                tout = usage.get("completion_tokens")
                if tin is not None and tout is not None:
                    span.record_tokens(tin, tout)
                    cost = estimate_cost(span.model, tin, tout)
                    if cost:
                        span.record_cost(cost)
        self._end_span(run_id)

    def on_llm_error(
        self, error: BaseException, *, run_id: UUID, **kwargs: Any
    ) -> None:
        self._end_span(run_id, error)

    # --- Tool callbacks ---

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        name = serialized.get("name") or serialized.get("id", ["tool"])[-1]
        span = self._create_span(str(name), SpanKind.TOOL, run_id, parent_run_id)
        if span:
            span.record_input(input_str)

    def on_tool_end(self, output: str, *, run_id: UUID, **kwargs: Any) -> None:
        with self._lock:
            span = self._run_to_span.get(run_id)
        if span:
            span.record_output(str(output))
        self._end_span(run_id)

    def on_tool_error(
        self, error: BaseException, *, run_id: UUID, **kwargs: Any
    ) -> None:
        self._end_span(run_id, error)

    # --- Retriever callbacks ---

    def on_retriever_start(
        self,
        serialized: dict[str, Any],
        query: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        name = serialized.get("name", "retriever")
        span = self._create_span(str(name), SpanKind.RETRIEVAL, run_id, parent_run_id)
        if span:
            span.record_input({"query": query})

    def on_retriever_end(
        self, documents: Any, *, run_id: UUID, **kwargs: Any
    ) -> None:
        with self._lock:
            span = self._run_to_span.get(run_id)
        if span:
            try:
                docs = [
                    {"page_content": d.page_content, "metadata": d.metadata}
                    for d in documents
                ]
            except (AttributeError, TypeError):
                docs = safe_serialize(documents)
            span.record_output(docs)
        self._end_span(run_id)

    # --- Agent callbacks (informational) ---

    def on_agent_action(self, action: Any, *, run_id: UUID, **kwargs: Any) -> Any:
        pass  # Tool execution is captured by on_tool_start/end

    def on_agent_finish(self, finish: Any, *, run_id: UUID, **kwargs: Any) -> None:
        pass  # Chain end captures the final output
