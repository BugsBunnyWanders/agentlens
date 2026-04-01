# AgentLens

**Local-first AI agent debugger with fork & replay.**

AgentLens captures execution traces from multi-step AI agent workflows, visualizes them in a local web UI, and lets you fork a trace at any step, edit its output, and **re-execute downstream steps with real API calls** to see what would have happened differently.

Think of it as **Chrome DevTools for AI agents** — the Network tab + time-travel debugging, but for LLM agent workflows.

## The Problem

AI agents are non-deterministic. When a multi-step agent fails at step 7 of 12, developers currently have no way to:

1. See exactly what happened at each step (tool calls, LLM reasoning, intermediate state)
2. Reproduce the failure deterministically
3. Test a fix by replaying from the failure point without re-running the entire chain

## Quick Start

```bash
pip install -e .
python examples/basic_agent.py   # creates a sample trace (no API keys needed)
agentlens serve                  # opens the UI at localhost:7600
```

For a real agent with OpenAI:

```bash
export OPENAI_API_KEY="sk-..."
python examples/trip_planner_agent.py
agentlens serve
```

## Usage

### 1. Instrument Your Code

Add decorators to your existing agent functions — zero logic changes:

```python
import agentlens

@agentlens.trace(name="my_agent")
async def my_agent(query: str):
    data = await fetch_data(query)
    result = await analyze(data)
    return result

@agentlens.wrap_tool(name="fetch_data")
async def fetch_data(query: str) -> dict:
    return await api.search(query)

@agentlens.wrap_llm(name="analyze", model="gpt-4o-mini")
async def analyze(data: dict) -> str:
    response = await openai.chat.completions.create(...)
    return response.choices[0].message.content
```

There's also a context manager API:

```python
async with agentlens.start_trace_async("my_agent") as t:
    with t.span("fetch_data", kind="tool") as s:
        data = await fetch(...)
        s.record_output(data)
    with t.span("analyze", kind="llm", model="gpt-4o") as s:
        s.record_input({"messages": [...]})
        result = await llm.complete(...)
        s.record_output(result)
```

### 2. View Traces

```bash
agentlens serve                    # Web UI at localhost:7600
agentlens serve --port 8080        # Custom port
agentlens traces                   # List recent traces in terminal
agentlens traces --last 5          # Show last 5
```

### 3. Fork & Replay

In the web UI:

1. Click a trace to see its span timeline
2. Select a span and click **Fork & Replay**
3. Edit the span's output in the code editor
4. Choose a **replay mode**
5. Click **Replay from here** to create a forked trace
6. View the side-by-side comparison with diff highlighting

### Replay Modes

| Mode | What happens | Cost | Use case |
|------|-------------|------|----------|
| **Deterministic** | Only the edited span changes. Downstream spans are marked stale. | Free | Quick data annotation, bookmarking bugs |
| **Live** | All downstream spans re-execute with real API calls. | Token costs | "What would the LLM say if the tool returned different data?" |
| **Hybrid** | LLM spans re-execute live, tool spans return recorded data. | Lower token costs | Test LLM behavior with changed context, no tool side effects |

**Example:** Your weather tool returned "sunny" but the real weather is a blizzard. Fork the weather span, change it to blizzard, select **Live** mode. The LLM re-generates the itinerary accounting for severe weather — with real API calls, producing genuinely different output.

## Features

- **Zero-config tracing** — `pip install` and add decorators, traces go to local SQLite
- **Framework-agnostic** — works with any Python agent (LangGraph, CrewAI, OpenAI, Anthropic, custom)
- **Live replay** — re-execute downstream spans with real API calls after editing a span's output
- **Hybrid replay** — LLM calls go live, tool calls use recorded data (no side effects)
- **Async-first** — non-blocking trace capture, works in both sync and async code
- **Local-first** — no cloud accounts, no telemetry, everything stays on your machine
- **Keyboard navigable** — arrow keys / j/k to browse spans, `e` to edit

## Architecture

```
Your Agent Code
  --> @trace, @wrap_tool, @wrap_llm decorators capture spans
  --> Async queue --> SQLite (~/.agentlens/traces.db)
  --> FastAPI serves JSON API + bundled React frontend
  --> localhost:7600

Fork & Replay (Live mode):
  --> Load original trace, apply mutations
  --> Re-import user's function, set ReplayContext
  --> Decorators intercept each span:
      Before mutation: execute normally
      At mutation: return edited output
      After mutation: execute live (real API calls)
  --> Save new trace for side-by-side comparison
```

## Web UI Pages

- **Trace List** — all captured traces with status, duration, token count, cost
- **Trace Detail** — span timeline (left) + selected span I/O (right), keyboard navigable
- **Replay Comparison** — side-by-side original vs forked trace, with RE-EXECUTED / EDITED / STALE badges

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENTLENS_DB_PATH` | `~/.agentlens/traces.db` | SQLite database path |
| `AGENTLENS_PORT` | `7600` | Default server port |
| `AGENTLENS_ENABLED` | `true` | Set `false` to disable tracing (decorators become no-ops) |

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Frontend development (hot reload)
cd frontend && npm install && npm run dev

# Build frontend for production
cd frontend && npm run build

# Run tests
pytest

# Type checking
mypy src/agentlens
cd frontend && npx tsc --noEmit
```

## Project Structure

```
src/agentlens/
  sdk/              # Tracing SDK (decorators, context management, SQLite writer)
  server/           # FastAPI API + static file serving
  replay/
    engine.py       # Replay dispatcher (deterministic vs live)
    live.py         # Live replay engine (re-executes user functions)
    context.py      # ReplayContext (decorators check this at runtime)
  cli.py            # CLI entry point

frontend/           # React + TypeScript + Tailwind UI (Vite)
examples/           # Working examples (basic + OpenAI trip planner)
```

## Tech Stack

- **SDK**: Python 3.10+, Pydantic v2, aiosqlite, contextvars
- **Server**: FastAPI, Uvicorn
- **Frontend**: React 18, TypeScript, Tailwind CSS, CodeMirror, Vite
- **Storage**: SQLite (WAL mode, zero-config)

## License

MIT
