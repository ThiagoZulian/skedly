"""APScheduler job implementations."""

from __future__ import annotations

import logging

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


async def send_reminder_job(reminder_id: int, user_id: str, message: str) -> None:
    """Send a reminder message via Telegram and mark it as sent in the DB.

    This coroutine is registered as an APScheduler async job and runs at the
    scheduled time inside the event loop.

    Args:
        reminder_id: DB row ID of the Reminder (used to update status).
        user_id: Telegram user/chat ID to send the message to.
        message: Reminder text.
    """
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": user_id,
        "text": f"⏰ *Lembrete:* {message}",
        "parse_mode": "Markdown",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                logger.error(
                    "send_reminder_job: Telegram error status=%d body=%s",
                    resp.status_code,
                    resp.text[:200],
                )
    except Exception:
        logger.exception("send_reminder_job: failed to send reminder_id=%d", reminder_id)
        return

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
