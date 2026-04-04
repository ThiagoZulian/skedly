"""Tests for Google Calendar tools — Google API fully mocked."""

from unittest.mock import MagicMock, patch

import pytest


def _make_service(events=None, busy=None):
    svc = MagicMock()
    events_list = svc.events.return_value.list.return_value.execute
    events_list.return_value = {"items": events or []}
    svc.events.return_value.insert.return_value.execute.return_value = {
        "id": "evt123", "summary": "Reunião"
    }
    svc.events.return_value.delete.return_value.execute.return_value = {}
    fb = svc.freebusy.return_value.query.return_value.execute
    fb.return_value = {"calendars": {"primary": {"busy": busy or []}}}
    return svc


@pytest.mark.asyncio
async def test_list_events_empty():
    with patch("src.tools.calendar.get_calendar_service", return_value=_make_service()):
        from src.tools.calendar import list_events
        result = await list_events.ainvoke({"days_ahead": 7})
    assert "Nenhum evento" in result


@pytest.mark.asyncio
async def test_list_events_with_items():
    events = [{"id": "1", "summary": "Standup", "start": {"dateTime": "2026-04-07T09:00:00-03:00"}}]
    with patch("src.tools.calendar.get_calendar_service", return_value=_make_service(events=events)):
        from src.tools.calendar import list_events
        result = await list_events.ainvoke({"days_ahead": 7})
    assert "Standup" in result
    assert "1" in result


@pytest.mark.asyncio
async def test_create_event():
    with patch("src.tools.calendar.get_calendar_service", return_value=_make_service()):
        from src.tools.calendar import create_event
        result = await create_event.ainvoke({
            "title": "Reunião", "start": "2026-04-07T14:00:00-03:00",
            "end": "2026-04-07T15:00:00-03:00",
        })
    assert "evt123" in result
    assert "criado" in result.lower()


@pytest.mark.asyncio
async def test_delete_event():
    with patch("src.tools.calendar.get_calendar_service", return_value=_make_service()):
        from src.tools.calendar import delete_event
        result = await delete_event.ainvoke({"event_id": "evt123"})
    assert "deletado" in result.lower()


@pytest.mark.asyncio
async def test_find_free_slots_no_busy():
    with patch("src.tools.calendar.get_calendar_service", return_value=_make_service(busy=[])):
        from src.tools.calendar import find_free_slots
        result = await find_free_slots.ainvoke({"date": "2026-04-07", "duration_minutes": 60})
    assert "Horários livres" in result


@pytest.mark.asyncio
async def test_list_events_error_returns_string():
    with patch("src.tools.calendar.get_calendar_service", side_effect=Exception("auth error")):
        from src.tools.calendar import list_events
        result = await list_events.ainvoke({"days_ahead": 3})
    assert "Erro" in result
