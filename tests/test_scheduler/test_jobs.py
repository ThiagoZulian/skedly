"""Tests for scheduler job implementations — all external calls fully mocked."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

_TZ = ZoneInfo("America/Sao_Paulo")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _make_httpx_response(status: int = 200, json_data: dict | None = None) -> MagicMock:
    """Return a MagicMock that quacks like an httpx.Response."""
    resp = MagicMock()
    resp.status_code = status
    resp.text = ""
    resp.json.return_value = json_data or {}
    resp.raise_for_status = MagicMock()
    return resp


def _async_client_ctx(response: MagicMock) -> MagicMock:
    """Return a context-manager mock whose .post/.get returns *response*."""
    client = AsyncMock()
    client.post = AsyncMock(return_value=response)
    client.get = AsyncMock(return_value=response)
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx, client


# ─────────────────────────────────────────────────────────────────────────────
# _send_telegram
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_send_telegram_success():
    """_send_telegram posts to Telegram Bot API and succeeds on 200."""
    resp = _make_httpx_response(200)
    ctx, client = _async_client_ctx(resp)

    with patch("src.scheduler.jobs.httpx.AsyncClient", return_value=ctx):
        from src.scheduler.jobs import _send_telegram

        await _send_telegram("12345", "Hello")

    client.post.assert_awaited_once()
    call_kwargs = client.post.call_args
    assert "12345" in str(call_kwargs)
    assert "Hello" in str(call_kwargs)


@pytest.mark.asyncio
async def test_send_telegram_non_200_raises(caplog):
    """_send_telegram raises HTTPStatusError on non-2xx responses (no silent swallow)."""
    import httpx

    resp = _make_httpx_response(400)
    # Make raise_for_status actually raise so the new behaviour is exercised.
    resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "400", request=MagicMock(), response=resp
    )
    ctx, _ = _async_client_ctx(resp)

    with patch("src.scheduler.jobs.httpx.AsyncClient", return_value=ctx):
        from src.scheduler.jobs import _send_telegram

        with pytest.raises(httpx.HTTPStatusError):
            await _send_telegram("12345", "Hello")


# ─────────────────────────────────────────────────────────────────────────────
# send_reminder_job
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_send_reminder_job_sends_message_and_updates_db():
    """send_reminder_job calls Telegram and marks the reminder as sent."""
    resp = _make_httpx_response(200)
    ctx, client = _async_client_ctx(resp)

    mock_reminder = MagicMock()
    mock_reminder.status = "pending"
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.get = AsyncMock(return_value=mock_reminder)
    mock_session.commit = AsyncMock()

    with (
        patch("src.scheduler.jobs.httpx.AsyncClient", return_value=ctx),
        patch("src.memory.database.get_async_session", return_value=mock_session),
    ):
        from src.scheduler.jobs import send_reminder_job

        await send_reminder_job(reminder_id=1, user_id="42", message="Pagar DAS")

    client.post.assert_awaited_once()
    assert mock_reminder.status == "sent"
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_reminder_job_reminder_not_in_db():
    """send_reminder_job handles gracefully when reminder row is missing."""
    resp = _make_httpx_response(200)
    ctx, _ = _async_client_ctx(resp)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.get = AsyncMock(return_value=None)
    mock_session.commit = AsyncMock()

    with (
        patch("src.scheduler.jobs.httpx.AsyncClient", return_value=ctx),
        patch("src.memory.database.get_async_session", return_value=mock_session),
    ):
        from src.scheduler.jobs import send_reminder_job

        # Should not raise
        await send_reminder_job(reminder_id=999, user_id="42", message="Test")

    mock_session.commit.assert_not_awaited()


# ─────────────────────────────────────────────────────────────────────────────
# send_daily_briefing
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_send_daily_briefing_sends_briefing():
    """send_daily_briefing fetches context, calls LLM, and sends via Telegram."""
    from langchain_core.messages import AIMessage

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="📅 Bom dia! Briefing de hoje..."))

    resp = _make_httpx_response(200)
    ctx, client = _async_client_ctx(resp)

    with (
        patch("src.tools.calendar.list_events") as mock_events,
        patch("src.tools.clickup.list_tasks") as mock_tasks,
        patch("src.llm.providers.get_gemini_flash", return_value=mock_llm),
        patch("src.scheduler.jobs.httpx.AsyncClient", return_value=ctx),
    ):
        mock_events.ainvoke = AsyncMock(return_value="Reunião às 10h")
        mock_tasks.ainvoke = AsyncMock(return_value="Tarefa: Deploy")

        from src.scheduler.jobs import send_daily_briefing

        await send_daily_briefing("12345")

    client.post.assert_awaited_once()
    payload = client.post.call_args.kwargs.get("json") or client.post.call_args[1].get("json", {})
    assert str(payload.get("chat_id")) == "12345"
    assert "Briefing" in payload.get("text", "")


@pytest.mark.asyncio
async def test_send_daily_briefing_handles_llm_error(caplog):
    """send_daily_briefing logs exception and does not crash on LLM failure."""
    import logging

    with (
        patch("src.tools.calendar.list_events") as mock_events,
        patch("src.tools.clickup.list_tasks") as mock_tasks,
        patch("src.llm.providers.get_gemini_flash", side_effect=RuntimeError("LLM down")),
    ):
        mock_events.ainvoke = AsyncMock(return_value="")
        mock_tasks.ainvoke = AsyncMock(return_value="")

        from src.scheduler.jobs import send_daily_briefing

        with caplog.at_level(logging.ERROR, logger="src.scheduler.jobs"):
            await send_daily_briefing("99999")

    assert any("send_daily_briefing" in rec.message for rec in caplog.records)


# ─────────────────────────────────────────────────────────────────────────────
# check_deadlines
# ─────────────────────────────────────────────────────────────────────────────


def _make_task(name: str, due_offset_hours: int = 12) -> dict:
    """Build a minimal ClickUp task dict with a due date."""
    due_dt = datetime.now(_TZ).replace(microsecond=0)
    from datetime import timedelta

    due_dt += timedelta(hours=due_offset_hours)
    return {
        "id": "abc123",
        "name": name,
        "status": {"status": "open"},
        "due_date": str(int(due_dt.timestamp() * 1000)),
    }


@pytest.mark.asyncio
async def test_check_deadlines_sends_alert_when_tasks_found():
    """check_deadlines sends an alert when tasks are due within threshold."""
    tasks = [_make_task("Deploy produção", due_offset_hours=20)]
    clickup_resp = _make_httpx_response(200, json_data={"tasks": tasks})
    telegram_resp = _make_httpx_response(200)

    # We need two separate client mocks: GET for ClickUp, POST for Telegram
    clickup_client = AsyncMock()
    clickup_client.get = AsyncMock(return_value=clickup_resp)
    clickup_client.post = AsyncMock(return_value=telegram_resp)
    clickup_ctx = MagicMock()
    clickup_ctx.__aenter__ = AsyncMock(return_value=clickup_client)
    clickup_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("src.scheduler.jobs.httpx.AsyncClient", return_value=clickup_ctx):
        from src.scheduler.jobs import check_deadlines

        await check_deadlines("42")

    clickup_client.get.assert_awaited_once()
    clickup_client.post.assert_awaited_once()
    payload = clickup_client.post.call_args.kwargs.get("json") or {}
    assert "Deploy produção" in payload.get("text", "")
    assert str(payload.get("chat_id")) == "42"


@pytest.mark.asyncio
async def test_check_deadlines_silent_when_no_tasks():
    """check_deadlines does NOT send any message when no tasks are due."""
    clickup_resp = _make_httpx_response(200, json_data={"tasks": []})

    client = AsyncMock()
    client.get = AsyncMock(return_value=clickup_resp)
    client.post = AsyncMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("src.scheduler.jobs.httpx.AsyncClient", return_value=ctx):
        from src.scheduler.jobs import check_deadlines

        await check_deadlines("42")

    client.get.assert_awaited_once()
    client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_check_deadlines_handles_http_error(caplog):
    """check_deadlines logs an exception on ClickUp API failure."""
    import logging

    import httpx as _httpx

    client = AsyncMock()
    mock_bad_resp = MagicMock()
    mock_bad_resp.status_code = 401
    mock_bad_resp.raise_for_status = MagicMock(
        side_effect=_httpx.HTTPStatusError("Unauthorized", request=MagicMock(), response=mock_bad_resp)
    )
    client.get = AsyncMock(return_value=mock_bad_resp)
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("src.scheduler.jobs.httpx.AsyncClient", return_value=ctx),
        caplog.at_level(logging.ERROR, logger="src.scheduler.jobs"),
    ):
        from src.scheduler.jobs import check_deadlines

        await check_deadlines("42")

    assert any("check_deadlines" in rec.message for rec in caplog.records)


# ─────────────────────────────────────────────────────────────────────────────
# register_fixed_cron_jobs
# ─────────────────────────────────────────────────────────────────────────────


def test_register_fixed_cron_jobs_adds_two_jobs():
    """register_fixed_cron_jobs registers exactly daily_briefing and deadline_alerts."""
    mock_scheduler = MagicMock()

    with patch("src.config.settings.briefing_hour", 8, create=True):
        from src.scheduler.setup import register_fixed_cron_jobs

        register_fixed_cron_jobs(mock_scheduler, "99")

    assert mock_scheduler.add_job.call_count == 2
    job_ids = {call.kwargs.get("id") for call in mock_scheduler.add_job.call_args_list}
    assert "daily_briefing" in job_ids
    assert "deadline_alerts" in job_ids
