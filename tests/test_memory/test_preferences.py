"""Tests for user preference helpers — DB fully mocked."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_session(scalar=None):
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    session.add = MagicMock()  # sync in SQLAlchemy async API
    session.commit = AsyncMock()

    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar

    scalars = MagicMock()
    scalars.all.return_value = [scalar] if scalar else []
    result.scalars.return_value = scalars

    session.execute = AsyncMock(return_value=result)
    return session


@pytest.mark.asyncio
async def test_get_preference_found():
    row = MagicMock()
    row.value = "Thiago"
    session = _make_session(scalar=row)

    with patch("src.memory.preferences.get_async_session", return_value=session):
        from src.memory.preferences import get_preference

        result = await get_preference("u1", "name")

    assert result == "Thiago"


@pytest.mark.asyncio
async def test_get_preference_not_found_returns_default():
    session = _make_session(scalar=None)

    with patch("src.memory.preferences.get_async_session", return_value=session):
        from src.memory.preferences import get_preference

        result = await get_preference("u1", "name", default="Usuário")

    assert result == "Usuário"


@pytest.mark.asyncio
async def test_set_preference_inserts_new_row():
    session = _make_session(scalar=None)  # no existing row

    with patch("src.memory.preferences.get_async_session", return_value=session):
        from src.memory.preferences import set_preference

        await set_preference("u1", "timezone", "America/Sao_Paulo")

    session.add.assert_called_once()
    session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_set_preference_updates_existing_row():
    row = MagicMock()
    row.value = "old_value"
    session = _make_session(scalar=row)

    with patch("src.memory.preferences.get_async_session", return_value=session):
        from src.memory.preferences import set_preference

        await set_preference("u1", "timezone", "UTC")

    assert row.value == "UTC"
    session.commit.assert_called_once()
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_get_all_preferences_returns_dict():
    row1 = MagicMock()
    row1.key = "name"
    row1.value = "Thiago"
    row2 = MagicMock()
    row2.key = "timezone"
    row2.value = "America/Sao_Paulo"

    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    result = MagicMock()
    result.scalars.return_value.all.return_value = [row1, row2]
    session.execute = AsyncMock(return_value=result)

    with patch("src.memory.preferences.get_async_session", return_value=session):
        from src.memory.preferences import get_all_preferences

        prefs = await get_all_preferences("u1")

    assert prefs == {"name": "Thiago", "timezone": "America/Sao_Paulo"}


@pytest.mark.asyncio
async def test_get_preference_handles_db_error():
    session = AsyncMock()
    session.__aenter__ = AsyncMock(side_effect=RuntimeError("DB down"))

    with patch("src.memory.preferences.get_async_session", return_value=session):
        from src.memory.preferences import get_preference

        result = await get_preference("u1", "name", default="fallback")

    assert result == "fallback"
