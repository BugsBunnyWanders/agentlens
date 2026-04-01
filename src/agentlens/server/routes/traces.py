"""API routes for trace listing, detail, and deletion."""

from fastapi import APIRouter, HTTPException

from agentlens.server import db

router = APIRouter(prefix="/api/traces", tags=["traces"])


@router.get("")
async def list_traces(limit: int = 50, offset: int = 0, status: str | None = None):
    traces, total = await db.list_traces(limit, offset, status)
    return {"traces": traces, "total": total}


@router.get("/{trace_id}")
async def get_trace(trace_id: str):
    trace = await db.get_trace(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail=f"Trace {trace_id} not found")
    return trace


@router.get("/{trace_id}/replays")
async def get_replays(trace_id: str):
    replays = await db.get_replays(trace_id)
    return {"replays": replays}


@router.delete("/{trace_id}")
async def delete_trace(trace_id: str):
    deleted = await db.delete_trace(trace_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Trace {trace_id} not found")
    return {"ok": True}
