"""End-to-end graph tests — LLM and external APIs fully mocked."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.graph.builder import build_graph
from src.graph.state import AgentState


def _state(text: str) -> AgentState:
    return {
        "messages": [HumanMessage(content=text)],
        "intent": "",
        "context": {},
        "response": "",
        "user_id": "test-user",
    }


def _llm(content: str) -> MagicMock:
    m = MagicMock()
    m.ainvoke = AsyncMock(return_value=AIMessage(content=content))
    m.bind_tools = MagicMock(return_value=m)
    return m


@pytest.mark.asyncio
async def test_general_chat_skips_gather_and_plan():
    """general_chat goes straight to format_response without calling plan_action."""
    classify_llm = _llm("general_chat")
    format_llm = _llm("Olá! Como posso ajudar?")

    graph = build_graph()

    with (
        patch("src.graph.nodes.classify_intent.get_gemini_flash", return_value=classify_llm),
        patch("src.graph.nodes.format_response.get_gemini_flash", return_value=format_llm),
    ):
        result = await graph.ainvoke(_state("Oi"))

    assert result["intent"] == "general_chat"
    assert result["response"] == "Olá! Como posso ajudar?"


@pytest.mark.asyncio
async def test_query_tasks_populates_context(monkeypatch):
    """query_tasks goes through gather_context, populates context, then plan_action."""
    monkeypatch.setenv("CLICKUP_DEFAULT_LIST_ID", "list1")

    classify_llm = _llm("query_tasks")
    plan_llm = _llm("Você tem 0 tarefas.")

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"tasks": []}
    mock_resp.raise_for_status = MagicMock()

    graph = build_graph()

    with (
        patch("src.graph.nodes.classify_intent.get_gemini_flash", return_value=classify_llm),
        patch("src.graph.nodes.plan_action.get_model_for_intent", return_value=plan_llm),
        patch("src.tools.clickup.httpx.AsyncClient") as mock_client,
    ):
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)
        result = await graph.ainvoke(_state("Quais são minhas tarefas?"))

    assert result["intent"] == "query_tasks"
    assert "tasks" in result["context"]
    assert result["response"] == "Você tem 0 tarefas."


@pytest.mark.asyncio
async def test_schedule_event_populates_events_context():
    """schedule_event intent should pre-fetch calendar events in gather_context."""
    classify_llm = _llm("schedule_event")
    plan_llm = _llm("Evento agendado com sucesso.")

    mock_svc = MagicMock()
    mock_svc.events.return_value.list.return_value.execute.return_value = {"items": []}

    graph = build_graph()

    with (
        patch("src.graph.nodes.classify_intent.get_gemini_flash", return_value=classify_llm),
        patch("src.graph.nodes.plan_action.get_model_for_intent", return_value=plan_llm),
        patch("src.tools._google_auth.get_credentials", AsyncMock(return_value=MagicMock())),
        patch("src.tools.calendar.build_calendar_service", return_value=mock_svc),
    ):
        result = await graph.ainvoke(_state("Agendar reunião amanhã"))

    assert result["intent"] == "schedule_event"
    assert "events" in result["context"]
    assert result["response"] == "Evento agendado com sucesso."


@pytest.mark.asyncio
async def test_classify_llm_error_falls_back_to_general_chat():
    """If classify_intent LLM raises, intent defaults to general_chat and graph completes."""
    classify_llm = MagicMock()
    classify_llm.ainvoke = AsyncMock(side_effect=RuntimeError("LLM indisponível"))

    format_llm = _llm("Desculpe, tente novamente.")

    graph = build_graph()

    with (
        patch("src.graph.nodes.classify_intent.get_gemini_flash", return_value=classify_llm),
        patch("src.graph.nodes.format_response.get_gemini_flash", return_value=format_llm),
    ):
        result = await graph.ainvoke(_state("Qualquer coisa"))

    assert result["intent"] == "general_chat"
    assert result["response"]


@pytest.mark.asyncio
async def test_plan_action_llm_error_still_returns_response(monkeypatch):
    """If plan_action LLM fails, format_response still produces a response."""
    monkeypatch.setenv("CLICKUP_DEFAULT_LIST_ID", "list1")

    classify_llm = _llm("query_tasks")

    broken_llm = MagicMock()
    broken_llm.bind_tools = MagicMock(return_value=broken_llm)
    broken_llm.ainvoke = AsyncMock(side_effect=RuntimeError("plan LLM down"))

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"tasks": []}
    mock_resp.raise_for_status = MagicMock()

    graph = build_graph()

    with (
        patch("src.graph.nodes.classify_intent.get_gemini_flash", return_value=classify_llm),
        patch("src.graph.nodes.plan_action.get_model_for_intent", return_value=broken_llm),
        patch("src.tools.clickup.httpx.AsyncClient") as mock_client,
    ):
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)
        result = await graph.ainvoke(_state("Ver tarefas"))

    assert result["response"]  # some error message was produced
