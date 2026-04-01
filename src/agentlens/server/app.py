"""FastAPI application — serves API endpoints and the bundled React frontend."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from agentlens.server import db
from agentlens.server.routes import replay, traces

STATIC_DIR = Path(__file__).parent / "static"


def create_app() -> FastAPI:
    app = FastAPI(title="AgentLens", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(traces.router)
    app.include_router(replay.router)

    @app.get("/api/health")
    async def health():
        count = await db.get_traces_count()
        return {"status": "ok", "version": "0.1.0", "traces_count": count}

    if STATIC_DIR.exists() and (STATIC_DIR / "index.html").exists():
        app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
    else:

        @app.get("/")
        async def no_frontend():
            return JSONResponse(
                {
                    "message": "AgentLens API is running. Frontend not built.",
                    "hint": "Run: cd frontend && npm install && npm run build",
                },
                status_code=200,
            )

    return app
