"""End-to-end integration tests for the SecretarIA agent.

The LangGraph is invoked for real; only external I/O is mocked:
  - LLM calls (Gemini Flash / Pro)
  - Telegram Bot API HTTP calls
  - ClickUp API HTTP calls
  - Google Calendar API calls
  - Database helpers (preferences, conversation history)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage


# ── Helpers ───────────────────────────────────────────────────────────────────

VALID_SECRET = "test-secret-integration"

TELEGRAM_CALENDAR_UPDATE = {
    "update_id": 100,
    "message": {
        "message_id": 1,
        "from": {"id": 42, "is_bot": False, "first_name": "Thiago"},
        "chat": {"id": 99, "type": "private"},
        "date": 1700000000,
        "text": "qual minha agenda?",
    },
}

TELEGRAM_CHAT_UPDATE = {
    "update_id": 101,
    "message": {
        "message_id": 2,
        "from": {"id": 42, "is_bot": False, "first_name": "Thiago"},
        "chat": {"id": 99, "type": "private"},
        "date": 1700000001,
        "text": "olá",
    },
}


def _make_llm_mock(content: str) -> MagicMock:
    """Return a LangChain-compatible LLM mock that always returns *content*."""
    ai_msg = AIMessage(content=content)
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=ai_msg)
    llm.bind_tools = MagicMock(return_value=llm)
    return llm


# ── Fixture: real graph with mocked LLMs ──────────────────────────────────────


@pytest.fixture()
def real_graph():
    """Build the LangGraph with mocked LLMs (no checkpointer)."""
    from src.graph.builder import build_graph

    classify_llm = _make_llm_mock("query_calendar")
    plan_llm = _make_llm_mock("Você não tem eventos nos próximos 7 dias.")

    with (
        patch("src.graph.nodes.classify_intent.get_gemini_flash", return_value=classify_llm),
        patch("src.graph.nodes.plan_action.get_model_for_intent", return_value=plan_llm),
        patch("src.graph.nodes.format_response.get_gemini_flash", return_value=plan_llm),
    ):
        return build_graph()


# ── Test 1: query_calendar flow via HTTP webhook ──────────────────────────────


@pytest.mark.asyncio
async def test_webhook_query_calendar_returns_events() -> None:
    """POST /webhook/telegram 'qual minha agenda?' → agent returns calendar response."""
    from src.config import settings
    from src.graph.builder import build_graph
    from fastapi.testclient import TestClient

    classify_llm = _make_llm_mock("query_calendar")
    plan_llm = _make_llm_mock("Você não tem eventos nos próximos 7 dias.")

    with (
        patch("src.graph.nodes.classify_intent.get_gemini_flash", return_value=classify_llm),
        patch("src.graph.nodes.plan_action.get_model_for_intent", return_value=plan_llm),
        patch("src.graph.nodes.format_response.get_gemini_flash", return_value=plan_llm),
        patch("src.tools.calendar.list_events", new=MagicMock(ainvoke=AsyncMock(return_value="Sem eventos"))),
        patch("src.gateway.routes.telegram.validate_telegram_secret", return_value=True),
        patch(
            "src.gateway.routes.telegram._send_telegram_message",
            new_callable=AsyncMock,
        ) as mock_send,
        patch("src.memory.preferences.set_preference", new_callable=AsyncMock),
        patch("src.memory.conversation.save_conversation", new_callable=AsyncMock),
        patch("src.memory.preferences.get_all_preferences", new_callable=AsyncMock, return_value={}),
        patch("src.memory.conversation.get_recent_conversations", new_callable=AsyncMock, return_value=[]),
    ):
        from src.gateway.app import app
        import src.gateway.routes.telegram as tg

        graph = build_graph()
        tg._graph = graph

        with TestClient(app, raise_server_exceptions=False) as client:
            headers = {"x-telegram-bot-api-secret-token": VALID_SECRET}
            r = client.post("/webhook/telegram", json=TELEGRAM_CALENDAR_UPDATE, headers=headers)

    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    # The agent should have sent something via Telegram
    mock_send.assert_awaited_once()
    sent_text: str = mock_send.call_args[0][1]  # second positional arg is the text
    assert len(sent_text) > 0


# ── Test 2: general_chat flow via HTTP webhook ────────────────────────────────


@pytest.mark.asyncio
async def test_webhook_general_chat_returns_response() -> None:
    """POST /webhook/telegram 'olá' → general_chat intent → agent replies."""
    from src.graph.builder import build_graph
    from fastapi.testclient import TestClient

    classify_llm = _make_llm_mock("general_chat")
    chat_llm = _make_llm_mock("Olá! Como posso ajudar você hoje?")

    with (
        patch("src.graph.nodes.classify_intent.get_gemini_flash", return_value=classify_llm),
        patch("src.graph.nodes.format_response.get_gemini_flash", return_value=chat_llm),
        patch("src.gateway.routes.telegram.validate_telegram_secret", return_value=True),
        patch(
            "src.gateway.routes.telegram._send_telegram_message",
            new_callable=AsyncMock,
        ) as mock_send,
        patch("src.memory.preferences.set_preference", new_callable=AsyncMock),
        patch("src.memory.conversation.save_conversation", new_callable=AsyncMock),
    ):
        from src.gateway.app import app
        import src.gateway.routes.telegram as tg

        graph = build_graph()
        tg._graph = graph

        with TestClient(app, raise_server_exceptions=False) as client:
            headers = {"x-telegram-bot-api-secret-token": VALID_SECRET}
            r = client.post("/webhook/telegram", json=TELEGRAM_CHAT_UPDATE, headers=headers)

    assert r.status_code == 200
    mock_send.assert_awaited_once()
    sent_text: str = mock_send.call_args[0][1]
    assert "Olá" in sent_text or len(sent_text) > 0


# ── Test 3: send_daily_briefing sends via Telegram ────────────────────���───────


@pytest.mark.asyncio
async def test_send_daily_briefing_calls_telegram() -> None:
    """send_daily_briefing calls _send_telegram with briefing content."""
    briefing_llm = _make_llm_mock("*Bom dia!* Hoje você tem 2 compromissos.")

    mock_list_events = MagicMock()
    mock_list_events.ainvoke = AsyncMock(return_value="Reunião às 10h")
    mock_list_tasks = MagicMock()
    mock_list_tasks.ainvoke = AsyncMock(return_value="1 tarefa aberta")

    with (
        patch("src.llm.providers.get_gemini_flash", return_value=briefing_llm),
        patch(
            "src.scheduler.jobs._send_telegram",
            new_callable=AsyncMock,
        ) as mock_tg,
        patch("src.tools.calendar.list_events", new=mock_list_events),
        patch("src.tools.clickup.list_tasks", new=mock_list_tasks),
    ):
        from src.scheduler.jobs import send_daily_briefing

        await send_daily_briefing("99")

    mock_tg.assert_awaited_once()
    chat_id, text = mock_tg.call_args[0]
    assert chat_id == "99"
    assert len(text) > 0


# ── Test 4: check_deadlines with upcoming tasks sends alert ───────────────────


@pytest.mark.asyncio
async def test_check_deadlines_sends_alert_for_upcoming_tasks() -> None:
    """check_deadlines sends a Telegram alert when tasks are due soon."""
    import time

    # Task due in 1 day (within deadline_alert_days=2)
    soon = int(time.time() * 1000) + 86400 * 1000  # 1 day from now in ms

    clickup_response = {
        "tasks": [
            {
                "id": "abc123",
                "name": "Pagar DAS",
                "due_date": str(soon),
                "status": {"status": "open"},
                "priority": {"priority": "2"},
                "url": "https://app.clickup.com/t/abc123",
            }
        ]
    }

    with (
        patch("src.scheduler.jobs.httpx.AsyncClient") as mock_client_cls,
        patch(
            "src.scheduler.jobs._send_telegram",
            new_callable=AsyncMock,
        ) as mock_tg,
    ):
        mock_resp = MagicMock()
        mock_resp.json.return_value = clickup_response
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        from src.scheduler.jobs import check_deadlines
        from src.config import settings

        with patch.object(settings, "clickup_default_list_id", "list123"):
            await check_deadlines("99")

    mock_tg.assert_awaited_once()
    _, alert_text = mock_tg.call_args[0]
    assert "Pagar DAS" in alert_text
