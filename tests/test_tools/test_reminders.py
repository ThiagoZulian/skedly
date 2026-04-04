"""Tests for reminder tools — DB and scheduler fully mocked."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_create_reminder():
    mock_reminder = MagicMock(id=1)
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock(side_effect=lambda r: setattr(r, "id", 1))

    mock_scheduler = MagicMock()
    mock_scheduler.add_job = MagicMock()

    with (
        patch("src.memory.database.get_async_session", return_value=mock_session),
        patch("src.scheduler.setup.get_scheduler", return_value=mock_scheduler),
    ):
        from src.tools.reminders import create_reminder
        result = await create_reminder.ainvoke({
            "message": "Pagar DAS",
            "remind_at": "2026-12-31T09:00:00",
            "user_id": "123",
        })
    assert "Lembrete criado" in result or "Pagar DAS" in result or "Erro" not in result


@pytest.mark.asyncio
async def test_list_reminders_empty():
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    with patch("src.memory.database.get_async_session", return_value=mock_session):
        from src.tools.reminders import list_reminders
        result = await list_reminders.ainvoke({"user_id": "123"})
    assert "Nenhum lembrete" in result


@pytest.mark.asyncio
async def test_delete_reminder_not_found():
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.get = AsyncMock(return_value=None)

    with patch("src.memory.database.get_async_session", return_value=mock_session):
        from src.tools.reminders import delete_reminder
        result = await delete_reminder.ainvoke({"reminder_id": "999"})
    assert "não encontrado" in result


@pytest.mark.asyncio
async def test_delete_reminder_invalid_id():
    from src.tools.reminders import delete_reminder
    result = await delete_reminder.ainvoke({"reminder_id": "abc"})
    assert "inválido" in result.lower() or "ID" in result
