"""LLM provider factories.

Each factory creates a configured LangChain chat model instance.
Callers should use these instead of instantiating models directly so that
configuration (api keys, model names, temperature) stays in one place.

Model strategy:
- Gemini 2.5 Flash — simple/medium intents (~80 % of requests, free tier)
- Gemini 2.5 Pro   — complex intents (free tier, stronger reasoning)
- Vertex AI        — backup if free-tier quotas are exhausted (uses same models)
"""

from langchain_google_genai import ChatGoogleGenerativeAI

from src.config import settings


def get_gemini_flash() -> ChatGoogleGenerativeAI:
    """Return a ChatGoogleGenerativeAI instance configured for Gemini 2.5 Flash.

    Used for simple and medium-complexity intents (free tier, fast).

    Returns:
        Configured Gemini 2.5 Flash chat model.
    """
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-preview-04-17",
        google_api_key=settings.google_ai_api_key,
        temperature=0.2,
        max_output_tokens=2048,
    )


def get_gemini_pro() -> ChatGoogleGenerativeAI:
    """Return a ChatGoogleGenerativeAI instance configured for Gemini 2.5 Pro.

    Used for complex intents that require deeper reasoning (e.g. weekly
    replanning, priority analysis, daily briefing). Free tier via Google AI
    Studio; falls back to Vertex AI ($300 credits) if quota is exhausted.

    Returns:
        Configured Gemini 2.5 Pro chat model.
    """
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-pro-preview-03-25",
        google_api_key=settings.google_ai_api_key,
        temperature=0.3,
        max_output_tokens=8192,
    )
