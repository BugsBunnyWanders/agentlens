"""Live replay engine — re-executes the user's traced function with replay context."""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import logging
import sys
from typing import Any

from agentlens.replay.context import ReplayContext
from agentlens.sdk.models import ReplayRequest, ReplayResult, Trace
from agentlens.sdk.tracer import set_replay_context, start_trace_async

logger = logging.getLogger("agentlens")


def _import_function(metadata: dict[str, Any]) -> Any:
    """Dynamically import the traced function, handling __main__ modules."""
    function_path = metadata.get("function_path", "")
    function_name = metadata.get("function_name", "")
    function_file = metadata.get("function_file")

    module_path, _, func_name = function_path.rpartition(".")
    if not func_name:
        func_name = function_name

    # Try normal import first
    if module_path != "__main__":
        try:
            module = importlib.import_module(module_path)
            return getattr(module, func_name)
        except (ModuleNotFoundError, AttributeError):
            pass  # fall through to file-based import

    # Fall back to importing from file path
    if function_file:
        spec = importlib.util.spec_from_file_location("_agentlens_replay_module", function_file)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules["_agentlens_replay_module"] = module
            spec.loader.exec_module(module)
            return getattr(module, func_name)

    raise ImportError(
        f"Cannot import function '{function_path}'. "
        f"Ensure the module is importable or function_file is set."
    )


async def replay_live(original_trace: Trace, request: ReplayRequest) -> ReplayResult:
    """Re-execute the traced function with mutations applied via ReplayContext."""
    function_path = original_trace.metadata.get("function_path")
    function_args = original_trace.metadata.get("function_args", {})

    if not function_path:
        raise ValueError(
            "Trace missing 'function_path' in metadata. "
            "Live replay requires traces captured with AgentLens >= 0.2."
        )

    # Build mutation map
    mutation_map: dict[str, Any] = {m.span_id: m.new_output for m in request.mutations}
    earliest_seq = float("inf")
    earliest_span_id = ""
    for span in original_trace.spans:
        if span.id in mutation_map and span.sequence < earliest_seq:
            earliest_seq = span.sequence
            earliest_span_id = span.id

    # Build replay context
    replay_ctx = ReplayContext(
        mode=request.mode,
        original_spans=original_trace.spans,
        mutations=mutation_map,
        mutation_sequence=int(earliest_seq) if earliest_seq != float("inf") else 0,
    )

    # Dynamic import
    func = _import_function(original_trace.metadata)

    # Set replay context and execute within a new trace scope
    token = set_replay_context(replay_ctx)
    trace_ctx = None
    try:
        async with start_trace_async(f"{original_trace.name} (replay)") as trace_ctx:
            trace_ctx.metadata = {
                **original_trace.metadata,
                "replay_of": original_trace.id,
                "replay_mode": request.mode.value,
            }
            # Call the function — decorators will check replay context
            if asyncio.iscoroutinefunction(func):
                await func(**function_args)
            else:
                func(**function_args)
    finally:
        from agentlens.sdk.tracer import _replay_context

        _replay_context.reset(token)

    # Build result
    replay_trace = trace_ctx.to_trace_model()
    replay_trace.parent_trace_id = original_trace.id

    return ReplayResult(
        original_trace_id=original_trace.id,
        replay_trace=replay_trace,
        mutated_span_ids=list(mutation_map.keys()),
        diverged_at_span_id=earliest_span_id,
        mode=request.mode,
    )
