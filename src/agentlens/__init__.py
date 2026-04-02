"""AgentLens — local-first AI agent debugger with fork & replay."""

from agentlens.sdk.decorators import trace, wrap_llm, wrap_tool
from agentlens.sdk.tracer import start_trace, start_trace_async

__version__ = "0.3.0"
__all__ = [
    "trace", "wrap_llm", "wrap_tool",
    "start_trace", "start_trace_async",
    "serve", "wrap_openai", "wrap_anthropic",
]


def serve(port: int = 7600, host: str = "127.0.0.1") -> None:
    """Start the AgentLens server."""
    import uvicorn

    from agentlens.server.app import create_app

    app = create_app()
    uvicorn.run(app, host=host, port=port)


def wrap_openai(client):
    """Wrap an OpenAI client to auto-trace chat completion calls."""
    from agentlens.integrations.clients import wrap_openai as _wrap

    return _wrap(client)


def wrap_anthropic(client):
    """Wrap an Anthropic client to auto-trace message calls."""
    from agentlens.integrations.clients import wrap_anthropic as _wrap

    return _wrap(client)
