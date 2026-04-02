"""Raw OpenAI client usage with automatic tracing via wrap_openai.

No framework needed — just wrap your OpenAI client and all calls are traced.

Usage:
    export OPENAI_API_KEY="sk-..."
    python examples/raw_openai_client.py
    agentlens serve
"""

import os

from openai import OpenAI

import agentlens


def main():
    if not os.environ.get("OPENAI_API_KEY"):
        print("Set OPENAI_API_KEY first: export OPENAI_API_KEY='sk-...'")
        return

    # Wrap the client — that's it
    client = agentlens.wrap_openai(OpenAI())

    # Use within a trace for multi-step workflows
    with agentlens.start_trace("research_assistant") as t:
        # Step 1: Generate questions
        with t.span("generate_questions", kind="chain"):
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Generate 3 research questions about the given topic."},
                    {"role": "user", "content": "The impact of AI on software engineering"},
                ],
            )
            questions = response.choices[0].message.content
            print(f"Questions:\n{questions}\n")

        # Step 2: Answer each question
        with t.span("answer_questions", kind="chain"):
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Answer these research questions concisely (2-3 sentences each)."},
                    {"role": "user", "content": questions},
                ],
            )
            answers = response.choices[0].message.content
            print(f"Answers:\n{answers}\n")

        # Step 3: Synthesize
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Write a one-paragraph summary synthesizing these Q&A pairs."},
                {"role": "user", "content": f"Questions:\n{questions}\n\nAnswers:\n{answers}"},
            ],
        )
        summary = response.choices[0].message.content
        print(f"Summary:\n{summary}")

    print("\nTrace saved! Run 'agentlens serve' to view it.")

    # Or use without a trace — auto-creates a single-span trace per call
    print("\n--- Standalone call (auto-traced) ---")
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "What is 2+2?"}],
    )
    print(f"Answer: {response.choices[0].message.content}")

    import time
    time.sleep(1)


if __name__ == "__main__":
    main()
