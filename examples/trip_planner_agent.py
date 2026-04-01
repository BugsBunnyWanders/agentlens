"""Trip Planner Agent — a real multi-step agent using OpenAI, traced with AgentLens.

Uses tool-calling to look up weather, attractions, and restaurants,
then builds a day-by-day itinerary via multiple LLM passes.

Usage:
    export OPENAI_API_KEY="sk-..."
    python examples/trip_planner_agent.py

Then run `agentlens serve` to view the trace.
"""

import asyncio
import json
import os
import random
from datetime import datetime, timedelta

from openai import AsyncOpenAI

import agentlens

client = AsyncOpenAI()
MODEL = "gpt-4o-mini"

# ---------------------------------------------------------------------------
# Simulated tool backends (these would be real APIs in production)
# ---------------------------------------------------------------------------

WEATHER_DATA = {
    "Paris": {"temp_c": 18, "condition": "Partly cloudy", "humidity": 62},
    "Tokyo": {"temp_c": 24, "condition": "Sunny", "humidity": 55},
    "New York": {"temp_c": 15, "condition": "Clear", "humidity": 48},
    "London": {"temp_c": 12, "condition": "Rainy", "humidity": 78},
    "Rome": {"temp_c": 22, "condition": "Sunny", "humidity": 40},
}

ATTRACTIONS_DATA = {
    "Paris": [
        {"name": "Eiffel Tower", "type": "landmark", "rating": 4.7, "visit_hours": 2},
        {"name": "Louvre Museum", "type": "museum", "rating": 4.8, "visit_hours": 3},
        {"name": "Montmartre", "type": "neighborhood", "rating": 4.5, "visit_hours": 2},
        {"name": "Notre-Dame", "type": "landmark", "rating": 4.6, "visit_hours": 1},
        {"name": "Musee d'Orsay", "type": "museum", "rating": 4.7, "visit_hours": 2},
    ],
    "Tokyo": [
        {"name": "Senso-ji Temple", "type": "temple", "rating": 4.6, "visit_hours": 1},
        {"name": "Shibuya Crossing", "type": "landmark", "rating": 4.4, "visit_hours": 1},
        {"name": "Meiji Shrine", "type": "shrine", "rating": 4.7, "visit_hours": 1.5},
        {"name": "Akihabara", "type": "district", "rating": 4.3, "visit_hours": 2},
        {"name": "Tsukiji Outer Market", "type": "market", "rating": 4.5, "visit_hours": 1.5},
    ],
    "New York": [
        {"name": "Central Park", "type": "park", "rating": 4.8, "visit_hours": 2},
        {"name": "Statue of Liberty", "type": "landmark", "rating": 4.6, "visit_hours": 3},
        {"name": "MoMA", "type": "museum", "rating": 4.7, "visit_hours": 2},
        {"name": "Brooklyn Bridge", "type": "landmark", "rating": 4.5, "visit_hours": 1},
        {"name": "Times Square", "type": "district", "rating": 4.2, "visit_hours": 1},
    ],
}

RESTAURANTS_DATA = {
    "Paris": [
        {"name": "Le Comptoir", "cuisine": "French", "price": "$$$", "rating": 4.6},
        {"name": "Breizh Cafe", "cuisine": "French/Crepes", "price": "$$", "rating": 4.5},
        {"name": "Pink Mamma", "cuisine": "Italian", "price": "$$", "rating": 4.4},
    ],
    "Tokyo": [
        {"name": "Ichiran Ramen", "cuisine": "Ramen", "price": "$", "rating": 4.5},
        {"name": "Sushi Dai", "cuisine": "Sushi", "price": "$$$", "rating": 4.8},
        {"name": "Gonpachi", "cuisine": "Izakaya", "price": "$$", "rating": 4.3},
    ],
    "New York": [
        {"name": "Joe's Pizza", "cuisine": "Pizza", "price": "$", "rating": 4.5},
        {"name": "Peter Luger", "cuisine": "Steakhouse", "price": "$$$$", "rating": 4.6},
        {"name": "Xi'an Famous Foods", "cuisine": "Chinese", "price": "$", "rating": 4.4},
    ],
}


@agentlens.wrap_tool(name="get_weather")
async def get_weather(destination: str) -> dict:
    """Look up current weather for a destination."""
    await asyncio.sleep(0.05)  # simulate network
    if destination in WEATHER_DATA:
        return {"destination": destination, **WEATHER_DATA[destination]}
    return {
        "destination": destination,
        "temp_c": random.randint(10, 30),
        "condition": random.choice(["Sunny", "Cloudy", "Rainy"]),
        "humidity": random.randint(30, 80),
    }


@agentlens.wrap_tool(name="search_attractions")
async def search_attractions(destination: str, limit: int = 5) -> list[dict]:
    """Search for top attractions in a destination."""
    await asyncio.sleep(0.05)
    attractions = ATTRACTIONS_DATA.get(destination, [
        {"name": f"{destination} Old Town", "type": "neighborhood", "rating": 4.3, "visit_hours": 2},
        {"name": f"{destination} National Museum", "type": "museum", "rating": 4.5, "visit_hours": 2},
        {"name": f"{destination} Central Park", "type": "park", "rating": 4.4, "visit_hours": 1.5},
    ])
    return attractions[:limit]


@agentlens.wrap_tool(name="search_restaurants")
async def search_restaurants(destination: str, limit: int = 3) -> list[dict]:
    """Search for recommended restaurants in a destination."""
    await asyncio.sleep(0.05)
    restaurants = RESTAURANTS_DATA.get(destination, [
        {"name": f"{destination} Bistro", "cuisine": "Local", "price": "$$", "rating": 4.3},
        {"name": f"{destination} Street Food", "cuisine": "Street Food", "price": "$", "rating": 4.4},
    ])
    return restaurants[:limit]


# ---------------------------------------------------------------------------
# LLM-powered agent steps
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather for a travel destination",
            "parameters": {
                "type": "object",
                "properties": {
                    "destination": {"type": "string", "description": "City name"},
                },
                "required": ["destination"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_attractions",
            "description": "Search for top tourist attractions in a destination",
            "parameters": {
                "type": "object",
                "properties": {
                    "destination": {"type": "string", "description": "City name"},
                    "limit": {"type": "integer", "description": "Max results", "default": 5},
                },
                "required": ["destination"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_restaurants",
            "description": "Search for recommended restaurants in a destination",
            "parameters": {
                "type": "object",
                "properties": {
                    "destination": {"type": "string", "description": "City name"},
                    "limit": {"type": "integer", "description": "Max results", "default": 3},
                },
                "required": ["destination"],
            },
        },
    },
]

TOOL_DISPATCH = {
    "get_weather": get_weather,
    "search_attractions": search_attractions,
    "search_restaurants": search_restaurants,
}


@agentlens.wrap_llm(name="plan_research", model=MODEL)
async def plan_research(destination: str, num_days: int) -> dict:
    """First LLM call: decide what tools to call to gather info."""
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are a trip planning assistant. Use the provided tools to gather weather, attractions, and restaurant info for the destination. Call all three tools.",
            },
            {
                "role": "user",
                "content": f"I'm planning a {num_days}-day trip to {destination}. Please look up the weather, top attractions, and restaurant recommendations.",
            },
        ],
        tools=TOOLS,
        tool_choice="auto",
    )
    return response


async def execute_tool_calls(response) -> list[dict]:
    """Execute tool calls from the LLM response and return results."""
    results = []
    if not response.choices[0].message.tool_calls:
        return results

    for tool_call in response.choices[0].message.tool_calls:
        fn_name = tool_call.function.name
        fn_args = json.loads(tool_call.function.arguments)
        fn = TOOL_DISPATCH.get(fn_name)
        if fn:
            result = await fn(**fn_args)
            results.append({
                "tool_call_id": tool_call.id,
                "name": fn_name,
                "result": result,
            })
    return results


@agentlens.wrap_llm(name="build_itinerary", model=MODEL)
async def build_itinerary(
    destination: str,
    num_days: int,
    weather: dict,
    attractions: list[dict],
    restaurants: list[dict],
) -> str:
    """Second LLM call: build a day-by-day itinerary from the gathered data."""
    start_date = datetime.now() + timedelta(days=7)
    dates = [(start_date + timedelta(days=i)).strftime("%A, %B %d") for i in range(num_days)]

    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a trip planning assistant. Create a detailed day-by-day itinerary. "
                    "Include specific times, attraction visits, meals at the recommended restaurants, "
                    "and practical tips. Consider the weather when planning. Be concise but helpful."
                ),
            },
            {
                "role": "user",
                "content": f"""Build a {num_days}-day itinerary for {destination}.

Dates: {', '.join(dates)}

Weather: {json.dumps(weather)}

Top Attractions:
{json.dumps(attractions, indent=2)}

Recommended Restaurants:
{json.dumps(restaurants, indent=2)}

Please create a day-by-day plan.""",
            },
        ],
    )
    return response.choices[0].message.content


@agentlens.wrap_llm(name="add_travel_tips", model=MODEL)
async def add_travel_tips(destination: str, itinerary: str, weather: dict) -> str:
    """Third LLM call: add practical travel tips and a summary."""
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a travel expert. Given an itinerary, add a brief section with "
                    "practical tips: what to pack, local customs, transportation advice, "
                    "and money-saving tips. Keep it under 200 words."
                ),
            },
            {
                "role": "user",
                "content": f"""Destination: {destination}
Current weather: {json.dumps(weather)}

Itinerary:
{itinerary}

Add practical travel tips for this trip.""",
            },
        ],
    )
    return response.choices[0].message.content


# ---------------------------------------------------------------------------
# Main agent
# ---------------------------------------------------------------------------

@agentlens.trace(name="trip_planner_agent")
async def trip_planner(destination: str, num_days: int) -> str:
    """Plan a trip: gather info with tools, build itinerary, add tips."""

    # Step 1: LLM decides what to research (calls tools)
    research_response = await plan_research(destination, num_days)

    # Step 2: Execute the tool calls
    tool_results = await execute_tool_calls(research_response)

    # Extract results by tool name
    weather = {}
    attractions = []
    restaurants = []
    for tr in tool_results:
        if tr["name"] == "get_weather":
            weather = tr["result"]
        elif tr["name"] == "search_attractions":
            attractions = tr["result"]
        elif tr["name"] == "search_restaurants":
            restaurants = tr["result"]

    # Step 3: Build itinerary from gathered data
    itinerary = await build_itinerary(destination, num_days, weather, attractions, restaurants)

    # Step 4: Add travel tips
    tips = await add_travel_tips(destination, itinerary, weather)

    # Combine final output
    final = f"# {destination} — {num_days}-Day Trip Plan\n\n{itinerary}\n\n---\n\n## Travel Tips\n\n{tips}"
    return final


async def main():
    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: Set OPENAI_API_KEY environment variable first.")
        print("  export OPENAI_API_KEY='sk-...'")
        return

    destination = "Paris"
    num_days = 3

    print(f"Planning a {num_days}-day trip to {destination}...\n")
    result = await trip_planner(destination, num_days)
    print(result)
    print("\n" + "=" * 60)
    print("Trace saved! Run 'agentlens serve' to view it.")

    # Give recorder time to flush
    await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
