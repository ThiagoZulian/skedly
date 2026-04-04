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
async def test_format_response_uses_existing_ai_message():
    """format_response should use an existing AIMessage without calling the LLM."""
    state = _make_state("", intent="schedule_event")
    state["messages"].append(AIMessage(content="Evento agendado com sucesso!"))

    result = await format_response(state)
    assert result["response"] == "Evento agendado com sucesso!"


@pytest.mark.asyncio
async def test_format_response_calls_llm_when_no_ai_message():
    """format_response should call Gemini Flash if no usable AIMessage exists."""
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="Olá, como posso ajudar?"))

    state = _make_state("Oi", intent="general_chat")

    with patch("src.graph.nodes.format_response.get_gemini_flash", return_value=mock_llm):
        result = await format_response(state)

    assert result["response"] == "Olá, como posso ajudar?"
    mock_llm.ainvoke.assert_called_once()


@pytest.mark.asyncio
async def test_format_response_handles_llm_error():
    """format_response should return a fallback string if LLM raises."""
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(side_effect=RuntimeError("LLM down"))

    state = _make_state("Oi", intent="general_chat")

    with patch("src.graph.nodes.format_response.get_gemini_flash", return_value=mock_llm):
        result = await format_response(state)

    assert result["response"]  # fallback message present
    assert "Desculpe" in result["response"]


@pytest.mark.asyncio
async def test_format_response_ignores_ai_message_with_tool_calls():
    """AIMessage with pending tool_calls should be skipped; LLM should be called."""
    tool_call = {"name": "list_tasks", "args": {}, "id": "c1", "type": "tool_call"}
    ai_with_tools = AIMessage(content="", tool_calls=[tool_call])

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="Resposta final"))

    state = _make_state("ver tarefas", intent="query_tasks")
    state["messages"].append(ai_with_tools)

    with patch("src.graph.nodes.format_response.get_gemini_flash", return_value=mock_llm):
        result = await format_response(state)

    assert result["response"] == "Resposta final"
