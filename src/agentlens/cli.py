"""CLI entry point: agentlens serve, agentlens traces."""

from __future__ import annotations

import asyncio
import os

import click


@click.group()
def main():
    """AgentLens - AI agent debugger with fork & replay."""
    pass


@main.command()
@click.option("--port", default=None, type=int, help="Port to serve on")
@click.option("--host", default="127.0.0.1", help="Host to bind to")
def serve(port: int | None, host: str):
    """Start the AgentLens web UI."""
    import uvicorn

    from agentlens.server.app import create_app

    if port is None:
        port = int(os.environ.get("AGENTLENS_PORT", "7600"))

    app = create_app()
    click.echo(f"AgentLens running at http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


@main.command()
@click.option("--last", default=10, help="Number of recent traces to show")
def traces(last: int):
    """List recent traces in the terminal."""
    asyncio.run(_list_traces(last))


async def _list_traces(last: int) -> None:
    from agentlens.server.db import list_traces

    traces_list, total = await list_traces(limit=last)

    if not traces_list:
        click.echo("No traces found.")
        return

    click.echo(f"Showing {len(traces_list)} of {total} traces:\n")
    click.echo(f"{'ID':<38} {'Name':<25} {'Status':<12} {'Duration':<12} {'Spans':<8}")
    click.echo("-" * 95)

    for t in traces_list:
        duration = ""
        if t.total_duration_ms is not None:
            if t.total_duration_ms < 1000:
                duration = f"{t.total_duration_ms:.0f}ms"
            else:
                duration = f"{t.total_duration_ms / 1000:.1f}s"

        spans_count = str(len(t.spans)) if t.spans else "-"
        click.echo(
            f"{t.id:<38} {t.name:<25} {t.status:<12} {duration:<12} {spans_count:<8}"
        )


if __name__ == "__main__":
    main()
