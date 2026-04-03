"""Model router — selects the appropriate Gemini model based on intent complexity."""

from enum import StrEnum

from langchain_google_genai import ChatGoogleGenerativeAI

from src.llm.providers import get_gemini_flash, get_gemini_pro


class IntentComplexity(StrEnum):
    """Complexity tiers that determine which LLM handles the request."""

    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


# Maps each intent category (from classify_intent) to a complexity tier.
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


def get_model_for_intent(intent: str) -> ChatGoogleGenerativeAI:
    """Return the most appropriate Gemini model for the given intent.

    Routing logic:
    - ``simple`` / ``medium`` intents → Gemini 2.5 Flash (free tier, fast, ~80 % of requests)
    - ``complex`` intents → Gemini 2.5 Pro (free tier, stronger reasoning)

    Unknown intents default to Gemini Flash.

    Args:
        intent: Intent category string (e.g. ``"schedule_event"``).

    Returns:
        A configured LangChain chat model ready to invoke.
    """
    complexity = INTENT_COMPLEXITY_MAP.get(intent, IntentComplexity.SIMPLE)

    if complexity == IntentComplexity.COMPLEX:
        return get_gemini_pro()

    return get_gemini_flash()
