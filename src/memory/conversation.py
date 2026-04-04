"""Helpers for persisting and retrieving conversation history."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from src.memory.database import get_async_session
from src.memory.models import Conversation

logger = logging.getLogger(__name__)


async def save_conversation(user_id: str, human_text: str, ai_text: str) -> None:
    """Persist a human/AI exchange to the conversations table.

    Args:
        user_id: Telegram user ID string.
        human_text: The user's message.
        ai_text: The agent's response.
    """
    payload = json.dumps(
        {"human": human_text, "ai": ai_text, "ts": datetime.now(UTC).isoformat()},
        ensure_ascii=False,
    )
    try:
        async with get_async_session() as session:
            session.add(Conversation(user_id=user_id, messages_json=payload))
            await session.commit()
    except Exception:
        logger.exception("save_conversation failed for user=%s", user_id)


async def get_recent_conversations(user_id: str, limit: int = 5) -> list[dict]:
    """Return the most recent conversation snapshots for a user.

    Args:
        user_id: Telegram user ID string.
        limit: Maximum number of exchanges to return (newest first).

    Returns:
        List of dicts with ``human``, ``ai``, and ``ts`` keys.
    """
    from sqlalchemy import desc, select

    try:
        async with get_async_session() as session:
            result = await session.execute(
                select(Conversation)
                .where(Conversation.user_id == user_id)
                .order_by(desc(Conversation.created_at))
                .limit(limit)
            )
            rows = result.scalars().all()
        return [json.loads(row.messages_json) for row in reversed(rows)]
    except Exception:
        logger.exception("get_recent_conversations failed for user=%s", user_id)
        return []
