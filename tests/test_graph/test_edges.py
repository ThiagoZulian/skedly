"""Tests for LangGraph conditional edge functions."""

import pytest
from langchain_core.messages import AIMessage

from src.graph.edges import route_after_plan, route_by_intent
from src.graph.state import AgentState


def _make_state(intent: str, messages: list | None = None) -> AgentState:
    return {
        "messages": messages or [],
        "intent": intent,
        "context": {},
        "response": "",
        "user_id": "test",
    }


@pytest.mark.parametrize(
    "intent",
    ["schedule_event", "query_calendar", "create_task", "query_tasks", "set_reminder", "reorganize", "daily_briefing"],
)
def test_route_by_intent_non_chat_goes_to_gather_context(intent: str):
    """Non-chat intents should route to gather_context in Phase 2."""
    assert route_by_intent(_make_state(intent)) == "gather_context"


def test_route_by_intent_general_chat_goes_to_format_response():
    """general_chat should skip gather_context and go straight to format_response."""
    assert route_by_intent(_make_state("general_chat")) == "format_response"


def test_route_by_intent_handles_empty_intent():
    """An empty intent string should default to gather_context (treated as non-chat)."""
    assert route_by_intent(_make_state("")) == "gather_context"


def test_route_by_intent_handles_unknown_intent():
    """An unknown intent string should route to gather_context without raising."""
    assert route_by_intent(_make_state("some_future_intent")) == "gather_context"


# ── route_after_plan ──────────────────────────────────────────────────────────


def test_route_after_plan_with_tool_calls_goes_to_execute_tools():
    """AI message with tool_calls should route to execute_tools."""
    ai_msg = AIMessage(content="", tool_calls=[{"name": "list_tasks", "args": {}, "id": "c1", "type": "tool_call"}])
    state = _make_state("query_tasks", messages=[ai_msg])
    assert route_after_plan(state) == "execute_tools"


def test_route_after_plan_without_tool_calls_goes_to_format_response():
    """AI message without tool_calls should route to format_response."""
    ai_msg = AIMessage(content="Aqui estão suas tarefas.")
    state = _make_state("query_tasks", messages=[ai_msg])
    assert route_after_plan(state) == "format_response"


def test_route_after_plan_no_messages_goes_to_format_response():
    """Empty messages should route to format_response safely."""
    assert route_after_plan(_make_state("query_tasks")) == "format_response"
