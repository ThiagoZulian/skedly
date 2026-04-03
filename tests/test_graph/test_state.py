"""Tests for AgentState structure and message accumulation."""

from langchain_core.messages import AIMessage, HumanMessage

from src.graph.state import AgentState


def test_agent_state_has_required_keys():
    """AgentState TypedDict must contain all expected keys."""
    required_keys = {"messages", "intent", "context", "response", "user_id"}
    annotations = AgentState.__annotations__
    assert required_keys.issubset(annotations.keys())


def test_agent_state_can_be_constructed_as_dict():
    """AgentState values can be assigned as a plain dict."""
    state: AgentState = {
        "messages": [HumanMessage(content="Oi")],
        "intent": "general_chat",
        "context": {},
        "response": "",
        "user_id": "123",
    }
    assert state["intent"] == "general_chat"
    assert state["user_id"] == "123"
    assert len(state["messages"]) == 1


def test_agent_state_messages_accept_multiple_types():
    """Messages field accepts both HumanMessage and AIMessage."""
    state: AgentState = {
        "messages": [
            HumanMessage(content="Olá"),
            AIMessage(content="Olá! Como posso ajudar?"),
        ],
        "intent": "",
        "context": {},
        "response": "",
        "user_id": "42",
    }
    assert len(state["messages"]) == 2


def test_agent_state_context_is_dict():
    """Context field is a plain dict that can hold arbitrary data."""
    ctx = {"current_time": "2026-04-03T09:00:00", "events": []}
    state: AgentState = {
        "messages": [],
        "intent": "query_calendar",
        "context": ctx,
        "response": "",
        "user_id": "1",
    }
    assert state["context"]["current_time"] == "2026-04-03T09:00:00"
