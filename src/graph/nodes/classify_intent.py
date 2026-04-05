"""classify_intent node — determines what the user wants to do."""

import logging
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from src.graph.state import AgentState
from src.llm.providers import get_gemini_flash

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parents[3] / "prompts" / "classify_intent.md"
_FALLBACK_INTENT = "general_chat"

# Valid intent categories (must match prompts/classify_intent.md).
VALID_INTENTS = frozenset(
    {
        "schedule_event",
        "query_calendar",
        "create_task",
        "query_tasks",
        "set_reminder",
        "reorganize",
        "daily_briefing",
        "general_chat",
    }
)


def _load_prompt() -> str:
    """Load the classify_intent system prompt from disk.

    Returns:
        The prompt file contents as a string.

    Raises:
        FileNotFoundError: If prompts/classify_intent.md does not exist.
    """
    return _PROMPT_PATH.read_text(encoding="utf-8")


async def classify_intent(state: AgentState) -> dict:
    """Classify the user's intent from the latest message.

    Reads the last HumanMessage from ``state["messages"]``, sends it to
    Gemini Flash with the classification system prompt, and returns the
    updated state with ``intent`` set.

    Args:
        state: Current agent state.

    Returns:
        Partial state dict with ``intent`` populated.
    """
    messages = state.get("messages", [])
    if not messages:
        logger.warning("classify_intent called with empty messages; defaulting to general_chat")
        return {"intent": _FALLBACK_INTENT}

    # Extract the text of the last human message — content may be a str, list,
    # or dict depending on the LLM provider returning the message.
    last_message = messages[-1]
    raw = last_message.content if hasattr(last_message, "content") else str(last_message)
    if isinstance(raw, list):
        user_text = " ".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in raw)
    elif isinstance(raw, dict):
        user_text = raw.get("text", str(raw))
    else:
        user_text = str(raw)

    system_prompt = _load_prompt()
    llm = get_gemini_flash()

    try:
        response = await llm.ainvoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_text),
            ]
        )
        content = response.content
        if isinstance(content, list):
            content = " ".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)
        elif isinstance(content, dict):
            content = content.get("text", str(content))
        raw_intent = str(content).strip().lower()

        # Guard against hallucinated categories.
        intent = raw_intent if raw_intent in VALID_INTENTS else _FALLBACK_INTENT

        if raw_intent not in VALID_INTENTS:
            logger.warning(
                "LLM returned unknown intent %r for message %r — falling back to %s",
                raw_intent,
                user_text[:80],
                _FALLBACK_INTENT,
            )
    except Exception:
        logger.exception("classify_intent LLM call failed; defaulting to %s", _FALLBACK_INTENT)
        intent = _FALLBACK_INTENT

    logger.info("Classified intent: %r → %s", user_text[:60], intent)
    return {"intent": intent}
