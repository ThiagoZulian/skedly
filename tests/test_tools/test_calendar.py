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
        result = await list_events.ainvoke({"days_ahead": 7, "calendar_id": "primary"})
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


@pytest.mark.asyncio
async def test_create_event_error_returns_string():
    svc = MagicMock()
    svc.events.return_value.insert.return_value.execute.side_effect = Exception("forbidden")
    with patch("src.tools.calendar.get_calendar_service", return_value=svc):
        from src.tools.calendar import create_event
        result = await create_event.ainvoke({
            "title": "X", "start": "2026-04-07T14:00:00-03:00",
            "end": "2026-04-07T15:00:00-03:00",
        })
    assert "Erro" in result


@pytest.mark.asyncio
async def test_delete_event_error_returns_string():
    svc = MagicMock()
    svc.events.return_value.delete.return_value.execute.side_effect = Exception("not found")
    with patch("src.tools.calendar.get_calendar_service", return_value=svc):
        from src.tools.calendar import delete_event
        result = await delete_event.ainvoke({"event_id": "ghost"})
    assert "Erro" in result


@pytest.mark.asyncio
async def test_find_free_slots_all_busy_returns_no_slots():
    """When the entire day is blocked there should be no free slots."""
    busy = [{"start": "2026-04-07T08:00:00-03:00", "end": "2026-04-07T20:00:00-03:00"}]
    with patch("src.tools.calendar.get_calendar_service", return_value=_make_service(busy=busy)):
        from src.tools.calendar import find_free_slots
        result = await find_free_slots.ainvoke({"date": "2026-04-07", "duration_minutes": 60, "calendar_id": "primary"})
    assert "Sem horários" in result


@pytest.mark.asyncio
async def test_find_free_slots_error_returns_string():
    with patch("src.tools.calendar.get_calendar_service", side_effect=Exception("quota")):
        from src.tools.calendar import find_free_slots
        result = await find_free_slots.ainvoke({"date": "2026-04-07", "duration_minutes": 30})
    assert "Erro" in result


@pytest.mark.asyncio
async def test_delete_calendar():
    svc = MagicMock()
    svc.calendars.return_value.delete.return_value.execute.return_value = {}
    with patch("src.tools.calendar.get_calendar_service", return_value=svc):
        from src.tools.calendar import delete_calendar
        result = await delete_calendar.ainvoke({"calendar_id": "cal123"})
    assert "deletada" in result.lower()
    assert "cal123" in result


@pytest.mark.asyncio
async def test_delete_calendar_error_returns_string():
    svc = MagicMock()
    svc.calendars.return_value.delete.return_value.execute.side_effect = Exception("forbidden")
    with patch("src.tools.calendar.get_calendar_service", return_value=svc):
        from src.tools.calendar import delete_calendar
        result = await delete_calendar.ainvoke({"calendar_id": "cal123"})
    assert "Erro" in result


def test_fmt_event_with_datetime():
    from src.tools.calendar import _fmt_event
    ev = {"id": "x1", "summary": "Stand-up", "start": {"dateTime": "2026-04-05T09:00:00-03:00"}}
    result = _fmt_event(ev)
    assert "[x1]" in result
    assert "Stand-up" in result
    assert "2026-04-05" in result


def test_fmt_event_with_all_day():
    from src.tools.calendar import _fmt_event
    ev = {"id": "x2", "summary": "Feriado", "start": {"date": "2026-04-21"}}
    result = _fmt_event(ev)
    assert "[x2]" in result
    assert "2026-04-21" in result


def test_fmt_event_no_summary():
    from src.tools.calendar import _fmt_event
    ev = {"id": "x3", "start": {"dateTime": "2026-04-05T10:00:00-03:00"}}
    result = _fmt_event(ev)
    assert "sem título" in result
