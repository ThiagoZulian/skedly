"""format_response node — generates the final natural-language reply."""

from __future__ import annotations

import logging
from pathlib import Path

from langchain_core.messages import AIMessage, SystemMessage

from src.graph.state import AgentState
from src.llm.providers import get_gemini_flash

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT_PATH = Path(__file__).parents[3] / "prompts" / "system.md"


def _extract_text(content: str | list) -> str:
    """Extract plain text from an LLM message content.

    Handles both plain strings and lists of content blocks (e.g. Claude Sonnet
    returns ``[{'type': 'text', 'text': '...', 'extras': {...}}]``).
    """
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = [
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        ]
        return " ".join(p for p in parts if p).strip()
    return str(content).strip()


async def format_response(state: AgentState) -> dict:
    """Produce the final response string for the user.

    Two cases:
    - **Tool flow**: ``plan_action`` already produced a final AIMessage (no tool_calls).
      Extract its content directly — no extra LLM call needed.
    - **general_chat / direct**: No AIMessage from plan_action. Call Gemini Flash
      to generate a conversational response from the message history.

    Args:
        state: Agent state with ``messages`` and optional ``intent``.

    Returns:
        Partial state dict with ``response`` set.
    """
    messages = state.get("messages", [])

    # Look for the last AI message without pending tool_calls
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and not getattr(msg, "tool_calls", None):
            response = _extract_text(msg.content)
            if response:
                logger.info("format_response: using existing AI message")
                return {"response": response}

    # No usable AI message — call LLM directly (general_chat path)
    logger.info("format_response: calling LLM for general_chat response")
    try:
        llm = get_gemini_flash()
        system = _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
        ai_response = await llm.ainvoke([SystemMessage(content=system), *messages])
        return {"response": _extract_text(ai_response.content)}
    except Exception:
        logger.exception("format_response LLM call failed")
        return {"response": "Desculpe, não consegui processar sua mensagem. Tente novamente."}
