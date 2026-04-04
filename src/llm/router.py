"""Model router — selects the appropriate Gemini model based on intent and context complexity."""

from __future__ import annotations

from enum import StrEnum

from langchain_google_genai import ChatGoogleGenerativeAI

from src.llm.providers import get_gemini_flash, get_gemini_pro


class IntentComplexity(StrEnum):
    """Complexity tiers that determine which LLM handles the request."""

    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


# Maps each intent category (from classify_intent) to a base complexity tier.
INTENT_COMPLEXITY_MAP: dict[str, IntentComplexity] = {
    "query_calendar": IntentComplexity.SIMPLE,
    "query_tasks": IntentComplexity.SIMPLE,
    "general_chat": IntentComplexity.SIMPLE,
    "schedule_event": IntentComplexity.MEDIUM,
    "create_task": IntentComplexity.MEDIUM,
    "set_reminder": IntentComplexity.MEDIUM,
    "reorganize": IntentComplexity.COMPLEX,
    "daily_briefing": IntentComplexity.COMPLEX,
    "priority_analysis": IntentComplexity.COMPLEX,
}

# Messages longer than this threshold suggest more complex reasoning is needed.
_LONG_MESSAGE_CHARS = 300


def get_model_for_intent(
    intent: str,
    message_length: int = 0,
    has_history: bool = False,
) -> ChatGoogleGenerativeAI:
    """Return the most appropriate Gemini model for the given intent and context.

    Routing logic:
    - ``complex`` intents → Gemini 2.5 Pro always
    - ``simple`` / ``medium`` intents with long messages or rich history → Gemini 2.5 Pro
    - Everything else → Gemini 2.5 Flash (free tier, fast, ~80 % of requests)

    Args:
        intent: Intent category string (e.g. ``"schedule_event"``).
        message_length: Character count of the user's message (optional).
        has_history: Whether rich conversation history is available (optional).

    Returns:
        A configured LangChain chat model ready to invoke.
    """
    complexity = INTENT_COMPLEXITY_MAP.get(intent, IntentComplexity.SIMPLE)

    if complexity == IntentComplexity.COMPLEX:
        return get_gemini_pro()

    # Escalate Flash → Pro for medium intents with long messages or multi-turn history
    if complexity == IntentComplexity.MEDIUM and (
        message_length > _LONG_MESSAGE_CHARS or has_history
    ):
        return get_gemini_pro()

    return get_gemini_flash()
