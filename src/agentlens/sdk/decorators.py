"""Decorators for tracing agent functions: @trace, @wrap_tool, @wrap_llm."""

from __future__ import annotations

import asyncio
import functools
import inspect
import logging
from typing import Any, Callable

from agentlens.sdk.models import SpanKind
from agentlens.sdk.tracer import (
    _is_enabled,
    get_current_trace,
    start_trace,
    start_trace_async,
)

logger = logging.getLogger("agentlens")


def _capture_input(fn: Callable, args: tuple, kwargs: dict) -> Any:
    """Capture function arguments as a serializable dict."""
    try:
        sig = inspect.signature(fn)
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        return dict(bound.arguments)
    except Exception:
        return {"args": repr(args), "kwargs": repr(kwargs)}


def _extract_tokens(result: Any) -> tuple[int | None, int | None]:
    """Try to extract token counts from common LLM response shapes."""
    if result is None:
        return None, None
    try:
        # Anthropic response
        if hasattr(result, "usage"):
            usage = result.usage
            if hasattr(usage, "input_tokens") and hasattr(usage, "output_tokens"):
                return usage.input_tokens, usage.output_tokens
        # OpenAI response
        if hasattr(result, "usage"):
            usage = result.usage
            if hasattr(usage, "prompt_tokens") and hasattr(usage, "completion_tokens"):
                return usage.prompt_tokens, usage.completion_tokens
        # Dict-based response
        if isinstance(result, dict) and "usage" in result:
            usage = result["usage"]
            if "input_tokens" in usage:
                return usage.get("input_tokens"), usage.get("output_tokens")
            if "prompt_tokens" in usage:
                return usage.get("prompt_tokens"), usage.get("completion_tokens")
    except Exception:
        pass
    return None, None


def trace(
    name: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Callable:
    """Decorator that creates a new trace for the wrapped function."""

    def decorator(fn: Callable) -> Callable:
        _name = name or fn.__name__

        @functools.wraps(fn)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            if not _is_enabled():
                return await fn(*args, **kwargs)
            async with start_trace_async(_name, metadata):
                return await fn(*args, **kwargs)

        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            if not _is_enabled():
                return fn(*args, **kwargs)
            with start_trace(_name, metadata):
                return fn(*args, **kwargs)

        if asyncio.iscoroutinefunction(fn):
            return async_wrapper
        return sync_wrapper

    return decorator


def wrap_tool(
    name: str | None = None,
) -> Callable:
    """Decorator that creates a TOOL span within the active trace."""

    def decorator(fn: Callable) -> Callable:
        _name = name or fn.__name__

        @functools.wraps(fn)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            trace_ctx = get_current_trace()
            if not _is_enabled() or trace_ctx is None:
                return await fn(*args, **kwargs)
            try:
                with trace_ctx.span(_name, SpanKind.TOOL) as span:
                    span.record_input(_capture_input(fn, args, kwargs))
                    result = await fn(*args, **kwargs)
                    span.record_output(result)
                    return result
            except Exception:
                raise

        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            trace_ctx = get_current_trace()
            if not _is_enabled() or trace_ctx is None:
                return fn(*args, **kwargs)
            try:
                with trace_ctx.span(_name, SpanKind.TOOL) as span:
                    span.record_input(_capture_input(fn, args, kwargs))
                    result = fn(*args, **kwargs)
                    span.record_output(result)
                    return result
            except Exception:
                raise

        if asyncio.iscoroutinefunction(fn):
            return async_wrapper
        return sync_wrapper

    return decorator


def wrap_llm(
    name: str | None = None,
    model: str | None = None,
    cost_usd: float | None = None,
) -> Callable:
    """Decorator that creates an LLM span within the active trace."""

    def decorator(fn: Callable) -> Callable:
        _name = name or fn.__name__

        @functools.wraps(fn)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            trace_ctx = get_current_trace()
            if not _is_enabled() or trace_ctx is None:
                return await fn(*args, **kwargs)
            try:
                with trace_ctx.span(_name, SpanKind.LLM, model=model) as span:
                    span.record_input(_capture_input(fn, args, kwargs))
                    result = await fn(*args, **kwargs)
                    span.record_output(result)
                    tokens_in, tokens_out = _extract_tokens(result)
                    if tokens_in is not None:
                        span.record_tokens(tokens_in, tokens_out or 0)
                    if cost_usd is not None:
                        span.record_cost(cost_usd)
                    return result
            except Exception:
                raise

        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            trace_ctx = get_current_trace()
            if not _is_enabled() or trace_ctx is None:
                return fn(*args, **kwargs)
            try:
                with trace_ctx.span(_name, SpanKind.LLM, model=model) as span:
                    span.record_input(_capture_input(fn, args, kwargs))
                    result = fn(*args, **kwargs)
                    span.record_output(result)
                    tokens_in, tokens_out = _extract_tokens(result)
                    if tokens_in is not None:
                        span.record_tokens(tokens_in, tokens_out or 0)
                    if cost_usd is not None:
                        span.record_cost(cost_usd)
                    return result
            except Exception:
                raise

        if asyncio.iscoroutinefunction(fn):
            return async_wrapper
        return sync_wrapper

    return decorator
