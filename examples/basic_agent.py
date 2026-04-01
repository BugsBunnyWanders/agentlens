"""Basic agent example — demonstrates AgentLens tracing with simulated tool/LLM calls.

No API keys required. Run this, then `agentlens serve` to view the trace.
"""

import asyncio

import agentlens


@agentlens.trace(name="weather_agent")
async def weather_agent(city: str) -> str:
    weather = await get_weather(city)
    forecast = await get_forecast(city)
    recommendation = await get_recommendation(weather, forecast)
    return recommendation


@agentlens.wrap_tool(name="get_weather")
async def get_weather(city: str) -> dict:
    """Simulated weather API call."""
    await asyncio.sleep(0.1)
    return {"city": city, "temp_f": 72, "condition": "sunny", "humidity": 45}


@agentlens.wrap_tool(name="get_forecast")
async def get_forecast(city: str) -> dict:
    """Simulated forecast API call."""
    await asyncio.sleep(0.15)
    return {
        "city": city,
        "next_3_days": [
            {"day": "Tomorrow", "high": 75, "low": 60, "condition": "partly cloudy"},
            {"day": "Day 2", "high": 78, "low": 62, "condition": "sunny"},
            {"day": "Day 3", "high": 70, "low": 55, "condition": "rainy"},
        ],
    }


@agentlens.wrap_llm(name="get_recommendation", model="simulated-llm")
async def get_recommendation(weather: dict, forecast: dict) -> str:
    """Simulated LLM call that generates a recommendation."""
    await asyncio.sleep(0.2)
    city = weather["city"]
    temp = weather["temp_f"]
    condition = weather["condition"]
    return (
        f"It's currently {condition} and {temp}F in {city}. "
        f"Great day for outdoor activities! "
        f"Note: rain expected in {forecast['next_3_days'][2]['day'].lower()}, "
        f"so plan accordingly."
    )


async def main():
    print("Running weather agent...")
    result = await weather_agent("San Francisco")
    print(f"\nAgent result: {result}")
    print("\nTrace saved! Run 'agentlens serve' to view it in the UI.")

    # Give the recorder time to flush
    await asyncio.sleep(0.5)


if __name__ == "__main__":
    asyncio.run(main())
