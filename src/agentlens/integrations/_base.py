"""Shared utilities for framework integrations."""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager, contextmanager
from typing import Any

from agentlens.sdk.tracer import get_current_trace, start_trace, start_trace_async

logger = logging.getLogger("agentlens")

# Cost per 1M tokens (input, output) for common models
_COST_TABLE: dict[str, tuple[float, float]] = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-4": (30.00, 60.00),
    "gpt-3.5-turbo": (0.50, 1.50),
    "claude-3-5-sonnet-20241022": (3.00, 15.00),
    "claude-sonnet-4-20250514": (3.00, 15.00),
    "claude-3-5-haiku-20241022": (0.80, 4.00),
    "claude-3-opus-20240229": (15.00, 75.00),
    "claude-opus-4-20250514": (15.00, 75.00),
}


@contextmanager
def ensure_trace(name: str, metadata: dict[str, Any] | None = None):
    """Yield the current active trace, or create a new one if none exists."""
    existing = get_current_trace()
    if existing:
        yield existing
    else:
        with start_trace(name, metadata) as ctx:
            yield ctx


@asynccontextmanager
async def ensure_trace_async(name: str, metadata: dict[str, Any] | None = None):
    """Async variant of ensure_trace."""
    existing = get_current_trace()
    if existing:
        yield existing
    else:
        async with start_trace_async(name, metadata) as ctx:
            yield ctx


def serialize_messages(messages: Any) -> list[dict[str, Any]]:
    """Convert various message formats to plain dicts."""
    if not messages:
        return []
    if not isinstance(messages, (list, tuple)):
        return [{"content": str(messages)}]

    result = []
    for msg in messages:
        if isinstance(msg, dict):
            result.append(msg)
        elif hasattr(msg, "type") and hasattr(msg, "content"):
            # LangChain BaseMessage
            d: dict[str, Any] = {"role": msg.type, "content": msg.content}
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                d["tool_calls"] = safe_serialize(msg.tool_calls)
            result.append(d)
        elif hasattr(msg, "role") and hasattr(msg, "content"):
            # OpenAI/Anthropic message object
            result.append({"role": msg.role, "content": str(msg.content)})
        else:
            result.append({"content": str(msg)})
    return result


def extract_model_name(serialized: dict[str, Any]) -> str | None:
    """Extract model name from a LangChain serialized dict."""
    kwargs = serialized.get("kwargs", {})
    for key in ("model_name", "model", "model_id"):
        if key in kwargs:
            return kwargs[key]
    # Fall back to the last element of the id list
    id_list = serialized.get("id", [])
    if id_list:
        return id_list[-1]
    return None


def estimate_cost(
    model: str | None, tokens_in: int | None, tokens_out: int | None
) -> float | None:
    """Estimate cost in USD from model name and token counts."""
    if not model or tokens_in is None or tokens_out is None:
        return None
    # Try exact match, then prefix match
    costs = _COST_TABLE.get(model)
    if not costs:
        for key, val in _COST_TABLE.items():
            if model.startswith(key) or key.startswith(model):
                costs = val
                break
    if not costs:
        return None
    input_cost, output_cost = costs
    return (tokens_in * input_cost + tokens_out * output_cost) / 1_000_000


def safe_serialize(obj: Any) -> Any:
    """Convert an object to a JSON-safe representation."""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (list, tuple)):
        return [safe_serialize(item) for item in obj]
    if isinstance(obj, dict):
        return {str(k): safe_serialize(v) for k, v in obj.items()}
    # Pydantic v2
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump()
        except Exception:
            pass
    # Pydantic v1 / LangChain objects
    if hasattr(obj, "dict"):
        try:
            return obj.dict()
        except Exception:
            pass
    # Dataclass
    if hasattr(obj, "__dataclass_fields__"):
        try:
            import dataclasses
            return dataclasses.asdict(obj)
        except Exception:
            pass
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return repr(obj)
