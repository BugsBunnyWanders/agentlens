"""LangChain agent with AgentLens tracing — no API keys needed.

Uses LangChain's FakeListChatModel to simulate LLM responses while still
exercising the full callback pipeline (chain, LLM, tool spans).

Usage:
    pip install agentlens-xray[langchain]
    python examples/langchain_basic.py
    agentlens serve
"""

import time

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from agentlens.integrations.langchain import AgentLensCallbackHandler


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool
def search_restaurants(city: str, cuisine: str) -> str:
    """Search for restaurants in a city by cuisine type."""
    data = {
        ("tokyo", "sushi"): [
            {"name": "Sukiyabashi Jiro", "rating": 4.9, "price": "$$$$"},
            {"name": "Sushi Saito", "rating": 4.8, "price": "$$$$"},
            {"name": "Tsukiji Outer Market", "rating": 4.5, "price": "$$"},
        ],
        ("tokyo", "ramen"): [
            {"name": "Ichiran Shibuya", "rating": 4.7, "price": "$"},
            {"name": "Fuunji", "rating": 4.6, "price": "$"},
        ],
    }
    key = (city.lower(), cuisine.lower())
    results = data.get(key, [{"name": f"Best {cuisine} in {city}", "rating": 4.0, "price": "$$"}])
    return str(results)


@tool
def get_weather(city: str) -> str:
    """Get current weather for a city."""
    weather = {
        "tokyo": "72°F, clear skies, humidity 55%",
        "paris": "58°F, partly cloudy",
        "new york": "45°F, windy",
    }
    return weather.get(city.lower(), f"75°F, pleasant in {city}")


@tool
def book_restaurant(name: str, party_size: int, time: str) -> str:
    """Book a table at a restaurant."""
    return f"Reservation confirmed at {name} for {party_size} guests at {time}."


# ---------------------------------------------------------------------------
# Fake chat model that returns pre-scripted tool calls and responses
# ---------------------------------------------------------------------------

class ScriptedChatModel:
    """A fake chat model that follows a script of responses.

    Implements just enough of the LangChain ChatModel interface to work
    with manual invocation and fire all the right callbacks.
    """

    def __init__(self, responses: list, callbacks: list[BaseCallbackHandler] | None = None):
        self._responses = list(responses)
        self._idx = 0
        self._callbacks = callbacks or []

    def invoke(self, messages, config=None, **kwargs):
        callbacks = self._callbacks
        if config and "callbacks" in config:
            callbacks = config["callbacks"]

        # Notify callbacks: LLM start
        from uuid import uuid4
        run_id = uuid4()
        parent_run_id = None
        serialized = {"name": "ScriptedChatModel", "kwargs": {"model_name": "gpt-4o-mini"}}

        for cb in callbacks:
            if hasattr(cb, "on_llm_start"):
                cb.on_llm_start(
                    serialized,
                    [str(m.content) for m in messages if hasattr(m, "content")],
                    run_id=run_id,
                    parent_run_id=parent_run_id,
                    messages=[[m for m in messages]],
                )

        # Get next scripted response
        response = self._responses[self._idx % len(self._responses)]
        self._idx += 1

        # Build a fake LLM result for callbacks
        class FakeGeneration:
            def __init__(self, msg):
                self.text = msg.content if hasattr(msg, "content") else str(msg)
                self.message = msg

        class FakeLLMResult:
            def __init__(self, msg):
                self.generations = [[FakeGeneration(msg)]]
                self.llm_output = {
                    "token_usage": {
                        "prompt_tokens": len(str(messages)) // 4,
                        "completion_tokens": len(str(response.content)) // 4,
                        "total_tokens": (len(str(messages)) + len(str(response.content))) // 4,
                    },
                    "model_name": "gpt-4o-mini",
                }

        # Notify callbacks: LLM end
        for cb in callbacks:
            if hasattr(cb, "on_llm_end"):
                cb.on_llm_end(FakeLLMResult(response), run_id=run_id)

        return response


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    tools = [search_restaurants, get_weather, book_restaurant]
    tool_map = {t.name: t for t in tools}

    # Script the LLM responses to simulate a multi-step agent
    scripted_responses = [
        # Step 1: Agent decides to check weather and search restaurants
        AIMessage(
            content="Let me check the weather in Tokyo and find some great sushi restaurants for you.",
            tool_calls=[
                {"name": "get_weather", "args": {"city": "Tokyo"}, "id": "call_weather_1"},
                {"name": "search_restaurants", "args": {"city": "Tokyo", "cuisine": "sushi"}, "id": "call_search_1"},
            ],
        ),
        # Step 2: Agent also wants ramen options
        AIMessage(
            content="Great weather! Let me also find some ramen spots.",
            tool_calls=[
                {"name": "search_restaurants", "args": {"city": "Tokyo", "cuisine": "ramen"}, "id": "call_search_2"},
            ],
        ),
        # Step 3: Agent books a restaurant
        AIMessage(
            content="Excellent options! Let me book the top-rated sushi place for you.",
            tool_calls=[
                {"name": "book_restaurant", "args": {"name": "Sukiyabashi Jiro", "party_size": 2, "time": "7:00 PM"}, "id": "call_book_1"},
            ],
        ),
        # Step 4: Final summary (no tool calls)
        AIMessage(
            content=(
                "Here's your Tokyo dining plan:\n\n"
                "🌤 Weather: 72°F, clear skies — perfect for exploring!\n\n"
                "🍣 Top Sushi Picks:\n"
                "  1. Sukiyabashi Jiro (4.9★) — BOOKED for 2 at 7 PM\n"
                "  2. Sushi Saito (4.8★)\n\n"
                "🍜 Ramen Recommendations:\n"
                "  1. Ichiran Shibuya (4.7★)\n"
                "  2. Fuunji (4.6★)\n\n"
                "Your reservation at Sukiyabashi Jiro is confirmed. Enjoy Tokyo!"
            ),
        ),
    ]

    llm = ScriptedChatModel(scripted_responses)

    # Run the agent loop with AgentLens tracing
    with AgentLensCallbackHandler(trace_name="tokyo_dining_agent") as handler:
        config = {"callbacks": [handler]}

        messages = [
            SystemMessage(content="You are a helpful travel assistant that finds restaurants and makes reservations."),
            HumanMessage(content="I'm visiting Tokyo tomorrow with my partner. Can you find us great sushi and ramen spots, and book the best one?"),
        ]

        print("=" * 60)
        print("Tokyo Dining Agent")
        print("=" * 60)

        # Agent loop: keep going until the LLM stops calling tools
        step = 1
        while True:
            print(f"\n--- Step {step} ---")
            response = llm.invoke(messages, config=config)
            messages.append(response)

            print(f"Agent: {response.content}")

            if not response.tool_calls:
                print("\n[Agent finished — no more tool calls]")
                break

            # Execute each tool call
            for tc in response.tool_calls:
                tool_fn = tool_map[tc["name"]]
                print(f"  → Calling {tc['name']}({tc['args']})")

                # Invoke tool with callbacks so AgentLens captures it
                result = tool_fn.invoke(tc["args"], config=config)
                print(f"    Result: {result[:80]}{'...' if len(str(result)) > 80 else ''}")

                messages.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))

            step += 1

    print("\n" + "=" * 60)
    print("Trace saved! Run 'agentlens serve' to view it in the UI.")
    print("=" * 60)

    # Give the recorder time to flush
    time.sleep(1)


if __name__ == "__main__":
    main()
