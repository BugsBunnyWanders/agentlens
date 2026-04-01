"""API route for fork & replay."""

from fastapi import APIRouter, HTTPException

from agentlens.replay.engine import replay_deterministic
from agentlens.sdk.models import ReplayRequest
from agentlens.server import db

router = APIRouter(prefix="/api", tags=["replay"])


@router.post("/replay")
async def replay_trace(request: ReplayRequest):
    original = await db.get_trace(request.trace_id)
    if not original:
        raise HTTPException(
            status_code=404, detail=f"Trace {request.trace_id} not found"
        )

    result = replay_deterministic(original, request)
    await db.save_trace(result.replay_trace)
    return result
