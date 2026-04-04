"""Helpers for reading and writing per-user preferences."""

from __future__ import annotations

import logging

from sqlalchemy import select

from src.memory.database import get_async_session
from src.memory.models import UserPreference

logger = logging.getLogger(__name__)


async def get_preference(user_id: str, key: str, default: str = "") -> str:
    """Retrieve a single user preference value.

    Args:
        user_id: Telegram user ID string.
        key: Preference key (e.g. ``"timezone"``, ``"name"``).
        default: Value to return when the key is not found.

    Returns:
        The stored value, or ``default`` if absent.
    """
    try:
        async with get_async_session() as session:
            result = await session.execute(
                select(UserPreference)
                .where(UserPreference.user_id == user_id, UserPreference.key == key)
                .limit(1)
            )
            row = result.scalar_one_or_none()
        return row.value if row else default
    except Exception:
        logger.exception("get_preference failed user=%s key=%s", user_id, key)
        return default


async def set_preference(user_id: str, key: str, value: str) -> None:
    """Upsert a user preference (insert or update existing row).

    Args:
        user_id: Telegram user ID string.
        key: Preference key.
        value: New value to store.
    """
    try:
        async with get_async_session() as session:
            result = await session.execute(
                select(UserPreference)
                .where(UserPreference.user_id == user_id, UserPreference.key == key)
                .limit(1)
            )
            row = result.scalar_one_or_none()
            if row:
                row.value = value
            else:
                session.add(UserPreference(user_id=user_id, key=key, value=value))
            await session.commit()
    except Exception:
        logger.exception("set_preference failed user=%s key=%s", user_id, key)


async def get_all_preferences(user_id: str) -> dict[str, str]:
    """Return all preferences for a user as a flat dict.

    Args:
        user_id: Telegram user ID string.

    Returns:
        Dict mapping preference keys to values.
    """
    try:
        async with get_async_session() as session:
            result = await session.execute(
                select(UserPreference).where(UserPreference.user_id == user_id)
            )
            rows = result.scalars().all()
        return {row.key: row.value for row in rows}
    except Exception:
        logger.exception("get_all_preferences failed user=%s", user_id)
        return {}
