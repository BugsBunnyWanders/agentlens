"""Pydantic v2 data models for AgentLens traces and spans."""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_serializer


class SpanKind(str, Enum):
    LLM = "llm"
    TOOL = "tool"
    RETRIEVAL = "retrieval"
    CHAIN = "chain"
    AGENT = "agent"
    CUSTOM = "custom"


class ReplayMode(str, Enum):
    DETERMINISTIC = "deterministic"
    LIVE = "live"
    HYBRID = "hybrid"


class Span(BaseModel):
    """A single step within a trace."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    trace_id: str
    parent_span_id: str | None = None
    kind: SpanKind
    name: str
    started_at: datetime
    ended_at: datetime | None = None
    status: Literal["running", "completed", "failed", "cancelled"] = "running"

    input: Any = None
    output: Any = None
    error: str | None = None

    model: str | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost_usd: float | None = None

    sequence: int
    is_mutated: bool = False
    is_stale: bool = False  # True if upstream span was mutated; output may be outdated
    is_reexecuted: bool = False  # True if this span was actually re-executed during live replay

    @field_serializer("input", "output")
    @classmethod
    def safe_serialize(cls, v: Any) -> Any:
        if v is None:
            return None
        try:
            json.dumps(v)
            return v
        except (TypeError, ValueError):
            return repr(v)


class Trace(BaseModel):
    """A single end-to-end agent execution."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    started_at: datetime
    ended_at: datetime | None = None
    status: Literal["running", "completed", "failed"] = "running"
    metadata: dict[str, Any] = Field(default_factory=dict)
    spans: list[Span] = Field(default_factory=list)
    total_tokens: int | None = None
    total_cost_usd: float | None = None
    total_duration_ms: float | None = None
    parent_trace_id: str | None = None


class SpanMutation(BaseModel):
    """A single edit to a span for replay."""

    span_id: str
    new_output: Any


class ReplayRequest(BaseModel):
    """Request to fork & replay a trace from a mutation point."""

    trace_id: str
    mutations: list[SpanMutation]
    mode: ReplayMode = ReplayMode.DETERMINISTIC


class ReplayResult(BaseModel):
    """Result of a fork & replay."""

    original_trace_id: str
    replay_trace: Trace
    mutated_span_ids: list[str]
    diverged_at_span_id: str
    mode: ReplayMode = ReplayMode.DETERMINISTIC
