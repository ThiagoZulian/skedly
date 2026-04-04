"""Tests for the model router — no real LLM calls."""

from unittest.mock import MagicMock, patch

import pytest

from src.llm.router import INTENT_COMPLEXITY_MAP, IntentComplexity, get_model_for_intent


@pytest.fixture(autouse=True)
def _mock_providers():
    flash = MagicMock(name="gemini-flash")
    pro = MagicMock(name="gemini-pro")
    with (
        patch("src.llm.router.get_gemini_flash", return_value=flash),
        patch("src.llm.router.get_gemini_pro", return_value=pro),
    ):
        yield flash, pro


def test_simple_intent_uses_flash(_mock_providers):
    flash, pro = _mock_providers
    model = get_model_for_intent("query_tasks")
    assert model is flash


def test_complex_intent_uses_pro(_mock_providers):
    flash, pro = _mock_providers
    model = get_model_for_intent("reorganize")
    assert model is pro


def test_daily_briefing_uses_pro(_mock_providers):
    flash, pro = _mock_providers
    model = get_model_for_intent("daily_briefing")
    assert model is pro


def test_medium_intent_short_message_uses_flash(_mock_providers):
    flash, pro = _mock_providers
    model = get_model_for_intent("schedule_event", message_length=50, has_history=False)
    assert model is flash


def test_medium_intent_long_message_escalates_to_pro(_mock_providers):
    flash, pro = _mock_providers
    model = get_model_for_intent("schedule_event", message_length=500, has_history=False)
    assert model is pro


def test_medium_intent_with_history_escalates_to_pro(_mock_providers):
    flash, pro = _mock_providers
    model = get_model_for_intent("create_task", message_length=50, has_history=True)
    assert model is pro


def test_unknown_intent_defaults_to_flash(_mock_providers):
    flash, pro = _mock_providers
    model = get_model_for_intent("some_future_intent")
    assert model is flash


def test_all_intents_have_complexity_mapping():
    known_intents = [
        "query_calendar", "query_tasks", "general_chat",
        "schedule_event", "create_task", "set_reminder",
        "reorganize", "daily_briefing", "priority_analysis",
    ]
    for intent in known_intents:
        assert intent in INTENT_COMPLEXITY_MAP, f"Missing mapping for: {intent}"
        assert isinstance(INTENT_COMPLEXITY_MAP[intent], IntentComplexity)
