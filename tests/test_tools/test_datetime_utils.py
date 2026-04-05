"""Tests for datetime_utils tools — no mocks needed (pure Python)."""

from datetime import date, timedelta

from src.tools.datetime_utils import (
    format_date_br,
    get_current_datetime,
    get_weekday,
    parse_relative_date,
)


def test_get_current_datetime_contains_date():
    result = get_current_datetime.invoke({})
    today = date.today().isoformat()[:7]  # YYYY-MM
    assert today in result


def test_parse_relative_date_hoje():
    result = parse_relative_date.invoke({"text": "hoje"})
    assert result == date.today().isoformat()


def test_parse_relative_date_amanha():
    result = parse_relative_date.invoke({"text": "amanhã"})
    assert result == (date.today() + timedelta(days=1)).isoformat()


def test_parse_relative_date_proxima_segunda():
    result = parse_relative_date.invoke({"text": "próxima segunda"})
    parsed = date.fromisoformat(result)
    assert parsed.weekday() == 0  # Monday


def test_parse_relative_date_final_do_mes():
    result = parse_relative_date.invoke({"text": "final do mês"})
    parsed = date.fromisoformat(result)
    assert parsed.month == date.today().month
    assert parsed.day >= 28


def test_parse_relative_date_absolute_br():
    result = parse_relative_date.invoke({"text": "15/06/2026"})
    assert result == "2026-06-15"


def test_parse_relative_date_unknown():
    result = parse_relative_date.invoke({"text": "quinzena passada"})
    assert "Não consegui" in result


def test_get_weekday_monday():
    result = get_weekday.invoke({"date_str": "2026-04-06"})  # April 6 2026 is Monday
    assert result == "segunda-feira"


def test_get_weekday_sunday():
    result = get_weekday.invoke({"date_str": "2026-04-05"})
    assert result == "domingo"


def test_format_date_br():
    result = format_date_br.invoke({"date_str": "2026-04-06"})
    assert "segunda-feira" in result
    assert "abril" in result
    assert "2026" in result
