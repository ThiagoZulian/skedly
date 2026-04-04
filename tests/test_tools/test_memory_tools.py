"""Tests for memory LangChain tools — helpers fully mocked."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_get_user_preference_found():
    with patch("src.memory.preferences.get_preference", AsyncMock(return_value="Thiago")):
        from src.tools.memory_tools import get_user_preference

        result = await get_user_preference.ainvoke({"user_id": "u1", "key": "name"})

    assert "Thiago" in result


@pytest.mark.asyncio
async def test_get_user_preference_not_found():
    with patch("src.memory.preferences.get_preference", AsyncMock(return_value="")):
        from src.tools.memory_tools import get_user_preference

        result = await get_user_preference.ainvoke({"user_id": "u1", "key": "name"})

    assert "Nenhuma preferência" in result


@pytest.mark.asyncio
async def test_set_user_preference():
    mock_set = AsyncMock()
    with patch("src.memory.preferences.set_preference", mock_set):
        from src.tools.memory_tools import set_user_preference

        result = await set_user_preference.ainvoke(
            {"user_id": "u1", "key": "timezone", "value": "America/Sao_Paulo"}
        )

    mock_set.assert_called_once_with("u1", "timezone", "America/Sao_Paulo")
    assert "salva" in result


@pytest.mark.asyncio
async def test_get_conversation_history_empty():
    with patch("src.memory.conversation.get_recent_conversations", AsyncMock(return_value=[])):
        from src.tools.memory_tools import get_conversation_history

        result = await get_conversation_history.ainvoke({"user_id": "u1", "limit": 3})

    assert "Nenhum histórico" in result


@pytest.mark.asyncio
async def test_get_conversation_history_with_items():
    exchanges = [
        {"human": "Oi", "ai": "Olá!", "ts": "2026-04-04T10:00:00"},
        {"human": "Que horas são?", "ai": "São 10h.", "ts": "2026-04-04T10:01:00"},
    ]
    with patch("src.memory.conversation.get_recent_conversations", AsyncMock(return_value=exchanges)):
        from src.tools.memory_tools import get_conversation_history

        result = await get_conversation_history.ainvoke({"user_id": "u1", "limit": 5})

    assert "Oi" in result
    assert "Olá!" in result


@pytest.mark.asyncio
async def test_get_conversation_history_caps_limit():
    """limit param should be capped at 10 internally."""
    mock_get = AsyncMock(return_value=[])
    with patch("src.memory.conversation.get_recent_conversations", mock_get):
        from src.tools.memory_tools import get_conversation_history

        await get_conversation_history.ainvoke({"user_id": "u1", "limit": 999})

    called_limit = mock_get.call_args[1]["limit"]
    assert called_limit <= 10
