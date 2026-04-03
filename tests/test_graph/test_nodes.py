"""Tests for LangGraph node functions using a mocked LLM."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.graph.nodes.classify_intent import VALID_INTENTS, classify_intent
from src.graph.nodes.format_response import format_response
from src.graph.state import AgentState


def _make_state(text: str, intent: str = "") -> AgentState:
    return {
        "messages": [HumanMessage(content=text)],
        "intent": intent,
        "context": {},
        "response": "",
        "user_id": "test-user",
    }


# ── classify_intent ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_classify_intent_returns_valid_intent():
    """classify_intent should return the intent from the LLM if it is valid."""
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="schedule_event"))

    with patch("src.graph.nodes.classify_intent.get_gemini_flash", return_value=mock_llm):
        result = await classify_intent(_make_state("Agendar reunião amanhã"))

    assert result["intent"] == "schedule_event"


@pytest.mark.asyncio
async def test_classify_intent_falls_back_on_unknown_category():
    """Unknown LLM response should fall back to general_chat."""
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="make_coffee"))

    with patch("src.graph.nodes.classify_intent.get_gemini_flash", return_value=mock_llm):
        result = await classify_intent(_make_state("Faz um café por favor"))

    assert result["intent"] == "general_chat"


@pytest.mark.asyncio
async def test_classify_intent_falls_back_on_llm_exception():
    """If the LLM raises an exception, intent should default to general_chat."""
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(side_effect=RuntimeError("LLM unavailable"))

    with patch("src.graph.nodes.classify_intent.get_gemini_flash", return_value=mock_llm):
        result = await classify_intent(_make_state("Qualquer coisa"))

    assert result["intent"] == "general_chat"


@pytest.mark.asyncio
async def test_classify_intent_empty_messages_defaults_to_general_chat():
    """Empty message list should return general_chat without calling the LLM."""
    state: AgentState = {
        "messages": [],
        "intent": "",
        "context": {},
        "response": "",
        "user_id": "x",
    }
    result = await classify_intent(state)
    assert result["intent"] == "general_chat"


@pytest.mark.parametrize("intent", list(VALID_INTENTS))
@pytest.mark.asyncio
async def test_classify_intent_accepts_all_valid_intents(intent: str):
    """Every valid intent category should pass through unchanged."""
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content=intent))

    with patch("src.graph.nodes.classify_intent.get_gemini_flash", return_value=mock_llm):
        result = await classify_intent(_make_state("test"))

    assert result["intent"] == intent


# ── format_response ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_format_response_includes_intent_label():
    """format_response should produce a non-empty response referencing the intent."""
    result = await format_response(_make_state("", intent="schedule_event"))
    assert "schedule_event" in result["response"]
    assert len(result["response"]) > 10


@pytest.mark.asyncio
async def test_format_response_handles_unknown_intent():
    """format_response should not crash for an unrecognised intent."""
    result = await format_response(_make_state("", intent="totally_unknown"))
    assert "response" in result
    assert result["response"]


@pytest.mark.asyncio
async def test_format_response_all_known_intents():
    """format_response should return a non-empty string for every known intent."""
    known_intents = [
        "schedule_event",
        "query_calendar",
        "create_task",
        "query_tasks",
        "set_reminder",
        "reorganize",
        "daily_briefing",
        "general_chat",
    ]
    for intent in known_intents:
        result = await format_response(_make_state("", intent=intent))
        assert result["response"], f"Empty response for intent={intent}"
