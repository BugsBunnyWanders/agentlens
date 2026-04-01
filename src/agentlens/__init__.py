"""AgentLens — local-first AI agent debugger with fork & replay."""

from agentlens.sdk.decorators import trace, wrap_llm, wrap_tool
from agentlens.sdk.tracer import start_trace, start_trace_async

__version__ = "0.1.0"
__all__ = ["trace", "wrap_llm", "wrap_tool", "start_trace", "start_trace_async", "serve"]


def serve(port: int = 7600, host: str = "127.0.0.1") -> None:
    """Start the AgentLens server."""
    import uvicorn

    from agentlens.server.app import create_app

    app = create_app()
    uvicorn.run(app, host=host, port=port)
