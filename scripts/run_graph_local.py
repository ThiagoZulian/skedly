"""Local REPL for testing the LangGraph agent without Telegram.

Usage:
    python scripts/run_graph_local.py

Requires a valid .env file with at least GOOGLE_AI_API_KEY (for Gemini Flash).
Type 'exit' or Ctrl+C to quit.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Ensure the project root is on the path when running as a script.
sys.path.insert(0, str(Path(__file__).parents[1]))

from langchain_core.messages import HumanMessage  # noqa: E402

from src.graph.builder import build_graph  # noqa: E402

logging.basicConfig(
    level=logging.WARNING,  # suppress INFO noise in interactive mode
    format="%(levelname)s | %(name)s | %(message)s",
)

graph = build_graph()


async def repl() -> None:
    """Run an interactive input/output loop against the compiled graph."""
    print("SecretarIA — local REPL (type 'exit' to quit)\n")
    thread_id = "local-test"

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if user_input.lower() in {"exit", "quit"}:
            print("Bye!")
            break

        if not user_input:
            continue

        state = {
            "messages": [HumanMessage(content=user_input)],
            "intent": "",
            "context": {},
            "response": "",
            "user_id": "local",
        }
        config = {"configurable": {"thread_id": thread_id}}

        result = await graph.ainvoke(state, config=config)
        print(f"SecretarIA [{result.get('intent', '?')}]: {result.get('response', '')}\n")


if __name__ == "__main__":
    asyncio.run(repl())
