"""Span-level replay — re-executes individual LLM spans with modified inputs.

Works for ALL trace types (decorator, LangChain, client-wrapped) because it
calls the LLM API directly using the recorded input, not the user's function.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import uuid4

from agentlens.sdk.models import (
    ReplayMode,
    ReplayRequest,
    ReplayResult,
    Span,
    SpanKind,
    Trace,
)

logger = logging.getLogger("agentlens")


def _deep_replace(obj: Any, old_val: Any, new_val: Any) -> Any:
    """Deep find-and-replace in a JSON-like structure.

    Replaces occurrences of old_val with new_val anywhere in the structure.
    Handles dicts, lists, and string containment.
    """
    if obj == old_val:
        return new_val

    if isinstance(obj, dict):
        return {k: _deep_replace(v, old_val, new_val) for k, v in obj.items()}

    if isinstance(obj, (list, tuple)):
        return [_deep_replace(item, old_val, new_val) for item in obj]

    # String containment for structured old values
    if isinstance(obj, str) and isinstance(old_val, (dict, list)):
        old_json = json.dumps(old_val, sort_keys=True)
        new_json = json.dumps(new_val, sort_keys=True)
        if old_json in obj:
            return obj.replace(old_json, new_json)

    # String-in-string replacement
    if isinstance(obj, str) and isinstance(old_val, str) and old_val in obj:
        new_str = json.dumps(new_val) if not isinstance(new_val, str) else new_val
        return obj.replace(old_val, new_str)

    return obj


def _extract_messages(span_input: Any) -> list[dict] | None:
    """Extract chat messages from a span's recorded input."""
    if not span_input:
        return None

    # Client-wrapped traces: {"model": "...", "messages": [...]}
    if isinstance(span_input, dict) and "messages" in span_input:
        return span_input["messages"]

    # LangChain: may be a list of message dicts directly
    if isinstance(span_input, list) and len(span_input) > 0:
        first = span_input[0]
        if isinstance(first, dict) and ("role" in first or "type" in first):
            return span_input
        # LangChain sometimes passes list of strings (prompts)
        if isinstance(first, str):
            return [{"role": "user", "content": first}]

    # Decorator traces: may have messages nested in args
    if isinstance(span_input, dict):
        for key in ("messages", "prompt", "input"):
            if key in span_input:
                val = span_input[key]
                if isinstance(val, list):
                    return val
                if isinstance(val, str):
                    return [{"role": "user", "content": val}]

    return None


def _extract_model(span: Span) -> str | None:
    """Get the model name from a span."""
    if span.model:
        return span.model
    if isinstance(span.input, dict):
        return span.input.get("model")
    return None


def _is_anthropic_model(model: str) -> bool:
    return "claude" in model.lower()


async def _call_llm(model: str, messages: list[dict], original_input: Any) -> dict:
    """Call an LLM API and return the result as a serializable dict."""
    if _is_anthropic_model(model):
        return await _call_anthropic(model, messages, original_input)
    else:
        return await _call_openai(model, messages, original_input)


async def _call_openai(model: str, messages: list[dict], original_input: Any) -> dict:
    """Call OpenAI chat completions API."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI()

    # Extract additional params from original input if available
    kwargs: dict[str, Any] = {"model": model, "messages": messages}
    if isinstance(original_input, dict):
        for key in ("temperature", "max_tokens", "top_p", "tools", "tool_choice"):
            if key in original_input:
                kwargs[key] = original_input[key]

    response = await client.chat.completions.create(**kwargs)

    # Return serializable result
    return {
        "id": response.id,
        "model": response.model,
        "content": response.choices[0].message.content if response.choices else None,
        "tool_calls": [
            {"name": tc.function.name, "arguments": tc.function.arguments}
            for tc in (response.choices[0].message.tool_calls or [])
        ] if response.choices and response.choices[0].message.tool_calls else None,
        "usage": {
            "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
            "completion_tokens": response.usage.completion_tokens if response.usage else 0,
        },
    }


async def _call_anthropic(model: str, messages: list[dict], original_input: Any) -> dict:
    """Call Anthropic messages API."""
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic()

    # Separate system message from conversation
    system = None
    chat_messages = []
    for msg in messages:
        role = msg.get("role", msg.get("type", "user"))
        content = msg.get("content", "")
        if role == "system":
            system = content
        else:
            # Map LangChain roles to Anthropic roles
            if role in ("human", "user"):
                chat_messages.append({"role": "user", "content": content})
            elif role in ("ai", "assistant"):
                chat_messages.append({"role": "assistant", "content": content})
            else:
                chat_messages.append({"role": "user", "content": content})

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": chat_messages,
        "max_tokens": 4096,
    }
    if system:
        kwargs["system"] = system
    if isinstance(original_input, dict):
        for key in ("temperature", "max_tokens", "tools"):
            if key in original_input:
                kwargs[key] = original_input[key]

    response = await client.messages.create(**kwargs)

    return {
        "id": response.id,
        "model": response.model,
        "content": response.content[0].text if response.content else None,
        "usage": {
            "input_tokens": response.usage.input_tokens if response.usage else 0,
            "output_tokens": response.usage.output_tokens if response.usage else 0,
        },
    }


async def replay_span_level(
    original_trace: Trace, request: ReplayRequest
) -> ReplayResult:
    """Re-execute downstream LLM spans by calling the LLM API directly.

    Works for all trace types — doesn't require function_path metadata.
    Tool spans keep their recorded output (no user code to re-execute).
    """
    mutation_map = {m.span_id: m.new_output for m in request.mutations}

    # Find earliest mutation
    earliest_seq = float("inf")
    earliest_span_id = ""
    for span in original_trace.spans:
        if span.id in mutation_map and span.sequence < earliest_seq:
            earliest_seq = span.sequence
            earliest_span_id = span.id

    # Build old output → new output mapping for input substitution
    substitutions: list[tuple[Any, Any]] = []
    for span in original_trace.spans:
        if span.id in mutation_map:
            substitutions.append((span.output, mutation_map[span.id]))

    # Deep-copy trace with new IDs
    new_trace_id = str(uuid4())
    id_remap: dict[str, str] = {}
    new_spans: list[Span] = []

    for span in original_trace.spans:
        new_span = span.model_copy(deep=True)
        new_span_id = str(uuid4())
        id_remap[span.id] = new_span_id
        new_span.id = new_span_id
        new_span.trace_id = new_trace_id

        if span.id in mutation_map:
            # Mutated span — apply the edit
            new_span.output = mutation_map[span.id]
            new_span.is_mutated = True

        elif span.sequence > earliest_seq:
            # Downstream span — decide whether to re-execute
            should_reexec_llm = (
                span.kind == SpanKind.LLM
                and request.mode in (ReplayMode.LIVE, ReplayMode.HYBRID)
            )

            if should_reexec_llm:
                model = _extract_model(span)
                messages = _extract_messages(span.input)

                if model and messages:
                    # Apply substitutions to messages
                    modified_messages = messages
                    for old_val, new_val in substitutions:
                        modified_messages = _deep_replace(modified_messages, old_val, new_val)

                    try:
                        result = await _call_llm(model, modified_messages, span.input)
                        new_span.output = result
                        new_span.is_reexecuted = True

                        # Update tokens from new response
                        usage = result.get("usage", {})
                        tin = usage.get("prompt_tokens") or usage.get("input_tokens")
                        tout = usage.get("completion_tokens") or usage.get("output_tokens")
                        if tin is not None:
                            new_span.tokens_in = tin
                        if tout is not None:
                            new_span.tokens_out = tout

                        # Also add this result to substitutions so further
                        # downstream spans get the cascaded change
                        substitutions.append((span.output, result))
                    except Exception as e:
                        logger.warning("Failed to re-execute LLM span %s: %s", span.name, e)
                        new_span.is_stale = True
                        new_span.error = f"Replay re-execution failed: {e}"
                else:
                    new_span.is_stale = True
            else:
                # Tool/other spans in any mode, or LLM in deterministic
                new_span.is_stale = True

        new_spans.append(new_span)

    # Remap parent IDs
    for new_span in new_spans:
        if new_span.parent_span_id and new_span.parent_span_id in id_remap:
            new_span.parent_span_id = id_remap[new_span.parent_span_id]

    replay_trace = Trace(
        id=new_trace_id,
        name=f"{original_trace.name} (replay)",
        started_at=original_trace.started_at,
        ended_at=original_trace.ended_at,
        status=original_trace.status,
        metadata={
            **original_trace.metadata,
            "replay_of": original_trace.id,
            "replay_mode": request.mode.value,
        },
        spans=new_spans,
        total_tokens=original_trace.total_tokens,
        total_cost_usd=original_trace.total_cost_usd,
        total_duration_ms=original_trace.total_duration_ms,
        parent_trace_id=original_trace.id,
    )

    return ReplayResult(
        original_trace_id=original_trace.id,
        replay_trace=replay_trace,
        mutated_span_ids=list(mutation_map.keys()),
        diverged_at_span_id=earliest_span_id,
        mode=request.mode,
    )
