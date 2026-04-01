"""Deterministic replay engine — pure data transformation, no live API calls."""

from __future__ import annotations

from uuid import uuid4

from agentlens.sdk.models import ReplayRequest, ReplayResult, Trace


def replay_deterministic(original_trace: Trace, request: ReplayRequest) -> ReplayResult:
    """Fork a trace by applying mutations and producing a new trace.

    In deterministic mode, this is purely a data transformation:
    - Spans before the mutation point are copied as-is
    - Mutated spans get their output replaced and marked is_mutated=True
    - Spans after the mutation point are copied as-is but marked is_stale=True
      (their output was recorded with the OLD input and would differ if re-executed)
    """
    mutation_map = {m.span_id: m.new_output for m in request.mutations}

    # Find earliest mutation point
    earliest_seq = float("inf")
    earliest_span_id = ""
    for span in original_trace.spans:
        if span.id in mutation_map and span.sequence < earliest_seq:
            earliest_seq = span.sequence
            earliest_span_id = span.id

    # Build old->new ID mapping
    new_trace_id = str(uuid4())
    id_remap: dict[str, str] = {}
    new_spans = []

    for span in original_trace.spans:
        new_span = span.model_copy(deep=True)
        new_span_id = str(uuid4())
        id_remap[span.id] = new_span_id
        new_span.id = new_span_id
        new_span.trace_id = new_trace_id

        if span.id in mutation_map:
            new_span.output = mutation_map[span.id]
            new_span.is_mutated = True
        elif span.sequence > earliest_seq:
            # Downstream of the mutation — output is stale
            new_span.is_stale = True

        new_spans.append(new_span)

    # Remap parent_span_id references
    for new_span in new_spans:
        if new_span.parent_span_id and new_span.parent_span_id in id_remap:
            new_span.parent_span_id = id_remap[new_span.parent_span_id]

    replay_trace = Trace(
        id=new_trace_id,
        name=f"{original_trace.name} (replay)",
        started_at=original_trace.started_at,
        ended_at=original_trace.ended_at,
        status=original_trace.status,
        metadata={**original_trace.metadata, "replay_of": original_trace.id},
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
    )
