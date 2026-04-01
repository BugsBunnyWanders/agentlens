"""API route for fork & replay."""

from fastapi import APIRouter, HTTPException

from agentlens.replay.engine import replay, replay_deterministic
from agentlens.sdk.models import ReplayMode, ReplayRequest
from agentlens.server import db

router = APIRouter(prefix="/api", tags=["replay"])


@router.post("/replay")
async def replay_trace(request: ReplayRequest):
    original = await db.get_trace(request.trace_id)
    if not original:
        raise HTTPException(
            status_code=404, detail=f"Trace {request.trace_id} not found"
        )

    if request.mode in (ReplayMode.LIVE, ReplayMode.HYBRID):
        if "function_path" not in original.metadata:
            raise HTTPException(
                status_code=400,
                detail=(
                    "This trace was recorded without function_path metadata. "
                    "Live/hybrid replay requires traces captured with AgentLens >= 0.2. "
                    "Re-run your agent to create a new trace, then try again."
                ),
            )

    result = await replay(original, request)
    await db.save_trace(result.replay_trace)
    return result
