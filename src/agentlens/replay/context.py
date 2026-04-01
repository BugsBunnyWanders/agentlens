"""ReplayContext — runtime state that decorators consult during live/hybrid replay."""

from __future__ import annotations

from enum import Enum
from typing import Any

from agentlens.sdk.models import ReplayMode, Span, SpanKind


class SpanDisposition(str, Enum):
    RETURN_RECORDED = "return_recorded"
    RETURN_MUTATED = "return_mutated"
    EXECUTE = "execute"
    NEEDS_DECISION = "needs_decision"


class ReplayContext:
    """Holds replay state that decorators check at runtime.

    Spans are indexed by (name, occurrence_count) to handle repeated calls
    to the same function. Each call to lookup_span increments the counter
    for that name.
    """

    def __init__(
        self,
        mode: ReplayMode,
        original_spans: list[Span],
        mutations: dict[str, Any],
        mutation_sequence: int,
    ):
        self.mode = mode
        self.mutations = mutations
        self.mutation_sequence = mutation_sequence

        # Build index: (name, occurrence) -> Span
        self._span_index: dict[tuple[str, int], Span] = {}
        name_counters: dict[str, int] = {}
        for span in sorted(original_spans, key=lambda s: s.sequence):
            count = name_counters.get(span.name, 0)
            self._span_index[(span.name, count)] = span
            name_counters[span.name] = count + 1

        # Track per-name lookup count during replay execution
        self._lookup_counters: dict[str, int] = {}

    def lookup_span(self, name: str) -> tuple[Span | None, SpanDisposition]:
        """Look up the original span for the current call and decide what to do."""
        count = self._lookup_counters.get(name, 0)
        self._lookup_counters[name] = count + 1

        original = self._span_index.get((name, count))
        if original is None:
            return None, SpanDisposition.EXECUTE

        if original.id in self.mutations:
            return original, SpanDisposition.RETURN_MUTATED

        if original.sequence < self.mutation_sequence:
            # Before mutation: execute normally to preserve type fidelity.
            # The results will be the same as the original run, but we avoid
            # serialization mismatches (e.g., returning a dict instead of
            # a ChatCompletion object).
            return original, SpanDisposition.EXECUTE

        return original, SpanDisposition.NEEDS_DECISION

    def get_mutated_output(self, span_id: str) -> Any:
        return self.mutations[span_id]

    def should_execute(self, disposition: SpanDisposition, span_kind: SpanKind) -> bool:
        """Resolve NEEDS_DECISION based on mode and span kind."""
        if disposition == SpanDisposition.EXECUTE:
            return True
        if disposition in (SpanDisposition.RETURN_RECORDED, SpanDisposition.RETURN_MUTATED):
            return False
        # NEEDS_DECISION — downstream of mutation, depends on mode
        if self.mode == ReplayMode.LIVE:
            return True
        if self.mode == ReplayMode.HYBRID:
            return span_kind == SpanKind.LLM
        # DETERMINISTIC
        return False
