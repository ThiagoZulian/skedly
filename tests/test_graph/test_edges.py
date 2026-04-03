"""Tests for LangGraph conditional edge functions."""

import pytest

from src.graph.edges import route_by_intent
from src.graph.state import AgentState


def _make_state(intent: str) -> AgentState:
    return {
        "messages": [],
        "intent": intent,
        "context": {},
        "response": "",
        "user_id": "test",
    }


@pytest.mark.parametrize(
    "intent",
    [
        "schedule_event",
        "query_calendar",
        "create_task",
        "query_tasks",
        "set_reminder",
        "reorganize",
        "daily_briefing",
        "general_chat",
    ],
)
def test_route_by_intent_always_returns_format_response_in_phase1(intent: str):
    """In Phase 1 all intents should route to format_response."""
    assert route_by_intent(_make_state(intent)) == "format_response"


def test_route_by_intent_handles_empty_intent():
    """An empty intent string should route to format_response (safe default)."""
    assert route_by_intent(_make_state("")) == "format_response"


def test_route_by_intent_handles_unknown_intent():
    """An unknown intent string should route to format_response without raising."""
    assert route_by_intent(_make_state("some_future_intent")) == "format_response"
