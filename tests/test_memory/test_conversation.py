"""Tests for conversation persistence helpers — DB fully mocked."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_session(rows=None):
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    session.add = MagicMock()  # sync in SQLAlchemy async API
    session.commit = AsyncMock()

    result = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = rows or []
    result.scalars.return_value = scalars
    session.execute = AsyncMock(return_value=result)
    return session


@pytest.mark.asyncio
async def test_save_conversation_commits():
    session = _make_session()
    with patch("src.memory.conversation.get_async_session", return_value=session):
        from src.memory.conversation import save_conversation

        await save_conversation("u1", "Oi", "Olá!")

    session.add.assert_called_once()
    session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_save_conversation_handles_db_error():
    session = AsyncMock()
    session.__aenter__ = AsyncMock(side_effect=RuntimeError("DB down"))

    with patch("src.memory.conversation.get_async_session", return_value=session):
        from src.memory.conversation import save_conversation

        # Should not raise — errors are swallowed with a warning
        await save_conversation("u1", "Oi", "Olá!")


@pytest.mark.asyncio
async def test_get_recent_conversations_empty():
    session = _make_session(rows=[])
    with patch("src.memory.conversation.get_async_session", return_value=session):
        from src.memory.conversation import get_recent_conversations

        result = await get_recent_conversations("u1")

    assert result == []


@pytest.mark.asyncio
async def test_get_recent_conversations_returns_parsed_json():
    import json

    row = MagicMock()
    row.messages_json = json.dumps({"human": "Oi", "ai": "Olá!", "ts": "2026-04-04T10:00:00"})

    session = _make_session(rows=[row])
    with patch("src.memory.conversation.get_async_session", return_value=session):
        from src.memory.conversation import get_recent_conversations

        result = await get_recent_conversations("u1", limit=1)

    assert len(result) == 1
    assert result[0]["human"] == "Oi"
    assert result[0]["ai"] == "Olá!"
