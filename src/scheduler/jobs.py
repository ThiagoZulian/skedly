"""APScheduler job implementations."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from src.config import settings

logger = logging.getLogger(__name__)

_TZ = ZoneInfo("America/Sao_Paulo")
_TELEGRAM_API = "https://api.telegram.org"
_CLICKUP_BASE = "https://api.clickup.com/api/v2"
_PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"


# ── Retry policy ─────────────────────────────────────────────────────────────


def _is_retryable_http(exc: BaseException) -> bool:
    """Retry on 5xx responses and timeouts; pass 4xx through immediately."""
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


# ── Internal helpers ──────────────────────────────────────────────────────────


@retry(
    retry=retry_if_exception(_is_retryable_http),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)
async def _send_telegram(chat_id: str, text: str) -> None:
    """Send a text message to a Telegram chat via the Bot API.

    Args:
        chat_id: Telegram chat/user ID.
        text: Message text (Markdown supported).
    """
    url = f"{_TELEGRAM_API}/bot{settings.telegram_bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()


# ── Dynamic reminder job ──────────────────────────────────────────────────────


async def send_reminder_job(reminder_id: int, user_id: str, message: str) -> None:
    """Send a reminder message via Telegram and mark it as sent in the DB.

    This coroutine is registered as an APScheduler async job and runs at the
    scheduled time inside the event loop.

    Args:
        reminder_id: DB row ID of the Reminder (used to update status).
        user_id: Telegram user/chat ID to send the message to.
        message: Reminder text.
    """
    await _send_telegram(user_id, f"⏰ *Lembrete:* {message}")

    # Update reminder status to 'sent' in the DB
    try:
        from src.memory.database import get_async_session
        from src.memory.models import Reminder

        async with get_async_session() as session:
            reminder = await session.get(Reminder, reminder_id)
            if reminder:
                reminder.status = "sent"
                await session.commit()
    except Exception:
        logger.exception("send_reminder_job: failed to update reminder status id=%d", reminder_id)


# ── Fixed cron jobs ───────────────────────────────────────────────────────────


async def send_daily_briefing(chat_id: str) -> None:
    """Send the daily morning briefing to a Telegram chat.

    Fetches the next 7 days of calendar events and all open ClickUp tasks,
    then uses Gemini Flash + prompts/daily_briefing.md to compose a concise
    briefing in Brazilian Portuguese.

    Args:
        chat_id: Telegram chat/user ID to deliver the briefing to.
    """
    logger.info("send_daily_briefing: building briefing for chat_id=%s", chat_id)
    try:
        # ── Collect context ───────────────────────────────────────────────────
        from src.tools.calendar import list_events
        from src.tools.clickup import list_tasks

        events_text = await list_events.ainvoke({"days_ahead": 7})
        tasks_text = await list_tasks.ainvoke({})

        now = datetime.now(_TZ)
        current_time = now.strftime("%A, %d/%m/%Y %H:%M (Brasília)")

        # ── Load briefing prompt ──────────────────────────────────────────────
        system_prompt = (_PROMPTS_DIR / "daily_briefing.md").read_text(encoding="utf-8")

        user_content = (
            f"Data/hora atual: {current_time}\n\n"
            f"Eventos dos próximos 7 dias:\n{events_text}\n\n"
            f"Tarefas ClickUp abertas:\n{tasks_text}"
        )

        # ── Generate briefing with Gemini Flash ───────────────────────────────
        from langchain_core.messages import HumanMessage, SystemMessage

        from src.llm.providers import get_gemini_flash

        llm = get_gemini_flash()
        ai_response = await llm.ainvoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=user_content)]
        )
        briefing_text: str = ai_response.content  # type: ignore[assignment]

        # ── Send via Telegram ─────────────────────────────────────────────────
        await _send_telegram(chat_id, briefing_text)
        logger.info("send_daily_briefing: sent successfully to chat_id=%s", chat_id)

    except Exception:
        logger.exception("send_daily_briefing: failed for chat_id=%s", chat_id)


async def check_deadlines(chat_id: str) -> None:
    """Alert about ClickUp tasks whose due date falls within the next N days.

    Queries the ClickUp API directly with ``due_date_gt`` / ``due_date_lt``
    filters so we get structured data instead of the pre-formatted tool string.

    Args:
        chat_id: Telegram chat/user ID to send the deadline alert to.
    """
    logger.info("check_deadlines: checking for chat_id=%s", chat_id)
    try:
        now = datetime.now(_TZ)
        alert_days = settings.deadline_alert_days
        cutoff = now + timedelta(days=alert_days)

        # ClickUp expects Unix timestamps in milliseconds
        due_gt = int(now.timestamp() * 1000)
        due_lt = int(cutoff.timestamp() * 1000)

        headers = {
            "Authorization": settings.clickup_api_token,
            "Content-Type": "application/json",
        }

        effective_list_id = settings.clickup_default_list_id
        if effective_list_id:
            url = f"{_CLICKUP_BASE}/list/{effective_list_id}/task"
        else:
            url = f"{_CLICKUP_BASE}/team/{settings.clickup_team_id}/task"

        params = {
            "due_date_gt": str(due_gt),
            "due_date_lt": str(due_lt),
            "include_closed": "false",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()

        tasks = data.get("tasks", [])
        if not tasks:
            logger.info("check_deadlines: no upcoming deadlines")
            return

        lines = [f"⚠️ *{len(tasks)} tarefa(s) vencem nos próximos {alert_days} dias:*\n"]
        for t in tasks:
            due_ms = t.get("due_date")
            if due_ms:
                due_dt = datetime.fromtimestamp(int(due_ms) / 1000, tz=_TZ)
                due_str = due_dt.strftime("%d/%m %H:%M")
            else:
                due_str = "data não definida"
            lines.append(f"• [{t['status']['status']}] {t['name']} — vence {due_str}")

        await _send_telegram(chat_id, "\n".join(lines))
        logger.info("check_deadlines: alerted %d tasks for chat_id=%s", len(tasks), chat_id)

    except Exception:
        logger.exception("check_deadlines: failed for chat_id=%s", chat_id)
