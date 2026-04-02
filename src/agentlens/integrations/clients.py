"""Drop-in client wrappers for OpenAI and Anthropic SDKs."""

from __future__ import annotations

import logging
from typing import Any

from agentlens.integrations._base import (
    ensure_trace,
    ensure_trace_async,
    estimate_cost,
    safe_serialize,
    serialize_messages,
)
from agentlens.sdk.models import SpanKind

logger = logging.getLogger("agentlens")


# ---------------------------------------------------------------------------
# OpenAI wrappers
# ---------------------------------------------------------------------------


class _SyncWrappedCompletions:
    def __init__(self, completions: Any) -> None:
        self._completions = completions

    def create(self, **kwargs: Any) -> Any:
        if kwargs.get("stream"):
            return self._completions.create(**kwargs)
        model = kwargs.get("model", "unknown")
        messages = kwargs.get("messages", [])
        with ensure_trace(f"openai-{model}") as trace_ctx:
            with trace_ctx.span("chat.completions.create", SpanKind.LLM, model=model) as span:
                span.record_input({"model": model, "messages": serialize_messages(messages)})
                response = self._completions.create(**kwargs)
                span.record_output(safe_serialize(response))
                if hasattr(response, "usage") and response.usage:
                    tin = response.usage.prompt_tokens or 0
                    tout = response.usage.completion_tokens or 0
                    span.record_tokens(tin, tout)
                    cost = estimate_cost(model, tin, tout)
                    if cost:
                        span.record_cost(cost)
                return response

    def __getattr__(self, name: str) -> Any:
        return getattr(self._completions, name)


class _SyncWrappedChat:
    def __init__(self, chat: Any) -> None:
        self._chat = chat
        self.completions = _SyncWrappedCompletions(chat.completions)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._chat, name)


class _SyncWrappedOpenAI:
    def __init__(self, client: Any) -> None:
        self._client = client
        self.chat = _SyncWrappedChat(client.chat)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


class _AsyncWrappedCompletions:
    def __init__(self, completions: Any) -> None:
        self._completions = completions

    async def create(self, **kwargs: Any) -> Any:
        if kwargs.get("stream"):
            return await self._completions.create(**kwargs)
        model = kwargs.get("model", "unknown")
        messages = kwargs.get("messages", [])
        async with ensure_trace_async(f"openai-{model}") as trace_ctx:
            with trace_ctx.span("chat.completions.create", SpanKind.LLM, model=model) as span:
                span.record_input({"model": model, "messages": serialize_messages(messages)})
                response = await self._completions.create(**kwargs)
                span.record_output(safe_serialize(response))
                if hasattr(response, "usage") and response.usage:
                    tin = response.usage.prompt_tokens or 0
                    tout = response.usage.completion_tokens or 0
                    span.record_tokens(tin, tout)
                    cost = estimate_cost(model, tin, tout)
                    if cost:
                        span.record_cost(cost)
                return response

    def __getattr__(self, name: str) -> Any:
        return getattr(self._completions, name)


class _AsyncWrappedChat:
    def __init__(self, chat: Any) -> None:
        self._chat = chat
        self.completions = _AsyncWrappedCompletions(chat.completions)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._chat, name)


class _AsyncWrappedOpenAI:
    def __init__(self, client: Any) -> None:
        self._client = client
        self.chat = _AsyncWrappedChat(client.chat)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


def wrap_openai(client: Any) -> Any:
    """Wrap an OpenAI client to auto-trace chat completion calls.

    Usage:
        from openai import OpenAI
        from agentlens import wrap_openai

        client = wrap_openai(OpenAI())
        response = client.chat.completions.create(model="gpt-4o", messages=[...])
        # Trace captured automatically
    """
    try:
        import openai
    except ImportError:
        raise ImportError(
            "OpenAI client wrapping requires 'openai'. "
            "Install with: pip install agentlens-xray[openai]"
        )
    if isinstance(client, openai.AsyncOpenAI):
        return _AsyncWrappedOpenAI(client)
    if isinstance(client, openai.OpenAI):
        return _SyncWrappedOpenAI(client)
    raise TypeError(f"Expected OpenAI or AsyncOpenAI client, got {type(client)}")


# ---------------------------------------------------------------------------
# Anthropic wrappers
# ---------------------------------------------------------------------------


class _SyncWrappedMessages:
    def __init__(self, messages: Any) -> None:
        self._messages = messages

    def create(self, **kwargs: Any) -> Any:
        if kwargs.get("stream"):
            return self._messages.create(**kwargs)
        model = kwargs.get("model", "unknown")
        msgs = kwargs.get("messages", [])
        system = kwargs.get("system")
        with ensure_trace(f"anthropic-{model}") as trace_ctx:
            with trace_ctx.span("messages.create", SpanKind.LLM, model=model) as span:
                input_data: dict[str, Any] = {
                    "model": model,
                    "messages": serialize_messages(msgs),
                }
                if system:
                    input_data["system"] = system
                span.record_input(input_data)
                response = self._messages.create(**kwargs)
                span.record_output(safe_serialize(response))
                if hasattr(response, "usage"):
                    tin = getattr(response.usage, "input_tokens", 0) or 0
                    tout = getattr(response.usage, "output_tokens", 0) or 0
                    span.record_tokens(tin, tout)
                    cost = estimate_cost(model, tin, tout)
                    if cost:
                        span.record_cost(cost)
                return response

    def __getattr__(self, name: str) -> Any:
        return getattr(self._messages, name)


class _SyncWrappedAnthropic:
    def __init__(self, client: Any) -> None:
        self._client = client
        self.messages = _SyncWrappedMessages(client.messages)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


class _AsyncWrappedMessages:
    def __init__(self, messages: Any) -> None:
        self._messages = messages

    async def create(self, **kwargs: Any) -> Any:
        if kwargs.get("stream"):
            return await self._messages.create(**kwargs)
        model = kwargs.get("model", "unknown")
        msgs = kwargs.get("messages", [])
        system = kwargs.get("system")
        async with ensure_trace_async(f"anthropic-{model}") as trace_ctx:
            with trace_ctx.span("messages.create", SpanKind.LLM, model=model) as span:
                input_data: dict[str, Any] = {
                    "model": model,
                    "messages": serialize_messages(msgs),
                }
                if system:
                    input_data["system"] = system
                span.record_input(input_data)
                response = await self._messages.create(**kwargs)
                span.record_output(safe_serialize(response))
                if hasattr(response, "usage"):
                    tin = getattr(response.usage, "input_tokens", 0) or 0
                    tout = getattr(response.usage, "output_tokens", 0) or 0
                    span.record_tokens(tin, tout)
                    cost = estimate_cost(model, tin, tout)
                    if cost:
                        span.record_cost(cost)
                return response

    def __getattr__(self, name: str) -> Any:
        return getattr(self._messages, name)


class _AsyncWrappedAnthropic:
    def __init__(self, client: Any) -> None:
        self._client = client
        self.messages = _AsyncWrappedMessages(client.messages)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


def wrap_anthropic(client: Any) -> Any:
    """Wrap an Anthropic client to auto-trace message calls.

    Usage:
        from anthropic import Anthropic
        from agentlens import wrap_anthropic

        client = wrap_anthropic(Anthropic())
        response = client.messages.create(model="claude-sonnet-4-20250514", messages=[...])
        # Trace captured automatically
    """
    try:
        import anthropic
    except ImportError:
        raise ImportError(
            "Anthropic client wrapping requires 'anthropic'. "
            "Install with: pip install agentlens-xray[anthropic]"
        )
    if isinstance(client, anthropic.AsyncAnthropic):
        return _AsyncWrappedAnthropic(client)
    if isinstance(client, anthropic.Anthropic):
        return _SyncWrappedAnthropic(client)
    raise TypeError(f"Expected Anthropic or AsyncAnthropic client, got {type(client)}")
