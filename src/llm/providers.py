"""LLM provider factories.

Each factory creates a configured LangChain chat model instance.
Callers should use these instead of instantiating models directly so that
configuration (api keys, model names, temperature) stays in one place.
"""

from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI

from src.config import settings


def get_gemini_flash() -> ChatGoogleGenerativeAI:
    """Return a ChatGoogleGenerativeAI instance configured for Gemini 2.5 Flash.

    Used for simple and medium-complexity intents (free tier / Vertex AI).

    Returns:
        Configured Gemini Flash chat model.
    """
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-preview-04-17",
        google_api_key=settings.google_ai_api_key,
        temperature=0.2,
        max_output_tokens=2048,
    )


def get_claude_sonnet() -> ChatAnthropic:
    """Return a ChatAnthropic instance configured for Claude Sonnet 4.6.

    Used for complex intents that require deeper reasoning (e.g. weekly
    replanning, priority analysis, daily briefing).

    Returns:
        Configured Claude Sonnet chat model.
    """
    return ChatAnthropic(
        model="claude-sonnet-4-6",
        api_key=settings.anthropic_api_key,
        temperature=0.2,
        max_tokens=4096,
    )
