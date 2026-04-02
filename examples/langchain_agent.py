"""LangChain agent with AgentLens tracing via callback handler.

Demonstrates automatic trace capture from a LangChain tool-calling agent.

Usage:
    pip install agentlens-xray[langchain] langchain-openai
    export OPENAI_API_KEY="sk-..."
    python examples/langchain_agent.py
    agentlens serve
"""

import os

from agentlens.integrations.langchain import AgentLensCallbackHandler


def main():
    if not os.environ.get("OPENAI_API_KEY"):
        print("Set OPENAI_API_KEY first: export OPENAI_API_KEY='sk-...'")
        return

    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.tools import tool
        from langchain_core.messages import HumanMessage
    except ImportError:
        print("Install dependencies: pip install langchain-openai langchain-core")
        return

    # Define tools
    @tool
    def get_weather(city: str) -> str:
        """Get current weather for a city."""
        weather_data = {
            "San Francisco": "62F, foggy",
            "New York": "45F, clear",
            "London": "50F, rainy",
        }
        return weather_data.get(city, f"72F, sunny in {city}")

    @tool
    def get_population(city: str) -> str:
        """Get the population of a city."""
        pop_data = {
            "San Francisco": "870,000",
            "New York": "8.3 million",
            "London": "9 million",
        }
        return pop_data.get(city, f"Unknown population for {city}")

    # Create the model with tools
    llm = ChatOpenAI(model="gpt-4o-mini")
    llm_with_tools = llm.bind_tools([get_weather, get_population])

    # Run with AgentLens tracing
    with AgentLensCallbackHandler(trace_name="langchain_city_info") as handler:
        config = {"callbacks": [handler]}

        print("Asking about San Francisco...\n")
        messages = [HumanMessage(content="What's the weather and population of San Francisco?")]

        # First call — LLM decides to call tools
        response = llm_with_tools.invoke(messages, config=config)
        print(f"LLM wants to call: {[tc['name'] for tc in response.tool_calls]}")

        # Execute tool calls
        from langchain_core.messages import ToolMessage

        messages.append(response)
        for tc in response.tool_calls:
            if tc["name"] == "get_weather":
                result = get_weather.invoke(tc["args"], config=config)
            elif tc["name"] == "get_population":
                result = get_population.invoke(tc["args"], config=config)
            else:
                result = "Unknown tool"
            messages.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))

        # Second call — LLM synthesizes the answer
        final = llm_with_tools.invoke(messages, config=config)
        print(f"\nFinal answer: {final.content}")

    print("\nTrace saved! Run 'agentlens serve' to view it.")
    import time
    time.sleep(1)


if __name__ == "__main__":
    main()
