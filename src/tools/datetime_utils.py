"""Datetime utility LangChain tools.

Pure Python tools — no external API calls, no mocks needed in tests.
All timestamps use America/Sao_Paulo unless the user specifies otherwise.
"""

from __future__ import annotations

import calendar
import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

_TZ = ZoneInfo("America/Sao_Paulo")

_WEEKDAYS_PT = {
    0: "segunda-feira",
    1: "terça-feira",
    2: "quarta-feira",
    3: "quinta-feira",
    4: "sexta-feira",
    5: "sábado",
    6: "domingo",
}

# Weekday name → weekday number (Monday=0)
_WEEKDAY_NAME_TO_NUM = {
    "segunda": 0,
    "terça": 1,
    "terca": 1,
    "quarta": 2,
    "quinta": 3,
    "sexta": 4,
    "sábado": 5,
    "sabado": 5,
    "domingo": 6,
}


@tool
def get_current_datetime() -> str:
    """Retorna a data e hora atual no fuso horário de Brasília (America/Sao_Paulo).

    Returns:
        String no formato ``YYYY-MM-DDTHH:MM:SS±HH:MM — Dia, DD/MM/YYYY HH:MM``.
    """
    now = datetime.now(_TZ)
    weekday = _WEEKDAYS_PT[now.weekday()]
    return (
        f"{now.isoformat()} — {weekday}, {now.strftime('%d/%m/%Y %H:%M')}"
    )


@tool
def parse_relative_date(text: str) -> str:
    """Converte expressões de data relativa em português para uma data ISO 8601.

    Expressões suportadas:
    - ``"hoje"``, ``"amanhã"``, ``"depois de amanhã"``
    - ``"próxima segunda"`` … ``"próximo domingo"``
    - ``"semana que vem"`` (retorna a segunda-feira da próxima semana)
    - ``"início do mês"`` (dia 1), ``"final do mês"`` (último dia)
    - ``"próximo mês"`` (dia 1 do mês seguinte)

    Datas absolutas no formato ``DD/MM/YYYY`` ou ``YYYY-MM-DD`` também são aceitas
    e retornadas normalizadas para ISO 8601.

    Args:
        text: Expressão de data em português (case-insensitive).

    Returns:
        Data no formato ``YYYY-MM-DD`` ou mensagem de erro.
    """
    today = date.today()
    normalized = text.strip().lower()

    # ── Relative keywords ─────────────────────────────────────────────────────
    if normalized == "hoje":
        return today.isoformat()
    if normalized in {"amanhã", "amanha"}:
        return (today + timedelta(days=1)).isoformat()
    if normalized in {"depois de amanhã", "depois de amanha"}:
        return (today + timedelta(days=2)).isoformat()
    if normalized in {"semana que vem", "próxima semana", "proxima semana"}:
        # Return the Monday of next week
        days_until_monday = (7 - today.weekday()) % 7 or 7
        return (today + timedelta(days=days_until_monday)).isoformat()
    if normalized in {"início do mês", "inicio do mes", "começo do mês", "comeco do mes"}:
        return today.replace(day=1).isoformat()
    if normalized in {"final do mês", "final do mes", "fim do mês", "fim do mes"}:
        last_day = calendar.monthrange(today.year, today.month)[1]
        return today.replace(day=last_day).isoformat()
    if normalized in {"próximo mês", "proximo mes"}:
        if today.month == 12:
            return date(today.year + 1, 1, 1).isoformat()
        return date(today.year, today.month + 1, 1).isoformat()

    # ── "próxima <weekday>" ────────────────────────────────────────────────────
    for prefix in ("próxima ", "proxima ", "próximo ", "proximo "):
        if normalized.startswith(prefix):
            day_name = normalized[len(prefix):]
            weekday_num = _WEEKDAY_NAME_TO_NUM.get(day_name)
            if weekday_num is not None:
                days_ahead = (weekday_num - today.weekday()) % 7 or 7
                return (today + timedelta(days=days_ahead)).isoformat()

    # ── Absolute date formats ─────────────────────────────────────────────────
    for fmt, _order in [
        ("%d/%m/%Y", "br"),
        ("%d/%m/%y", "br"),
        ("%Y-%m-%d", "iso"),
    ]:
        try:
            parsed = datetime.strptime(normalized, fmt).date()
            return parsed.isoformat()
        except ValueError:
            continue

    return f"Não consegui interpretar a data '{text}'. Use formatos como 'amanhã', 'próxima segunda' ou DD/MM/YYYY."


@tool
def get_weekday(date_str: str) -> str:
    """Retorna o dia da semana em português para uma data fornecida.

    Args:
        date_str: Data no formato ``YYYY-MM-DD`` ou ``DD/MM/YYYY``.

    Returns:
        Nome do dia da semana em português (ex: ``"segunda-feira"``).
    """
    try:
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
            try:
                d = datetime.strptime(date_str.strip(), fmt).date()
                return _WEEKDAYS_PT[d.weekday()]
            except ValueError:
                continue
        return f"Formato de data não reconhecido: '{date_str}'. Use YYYY-MM-DD ou DD/MM/YYYY."
    except Exception as exc:
        logger.exception("get_weekday failed")
        return f"Erro ao obter dia da semana: {exc}"


@tool
def format_date_br(date_str: str) -> str:
    """Formata uma data ISO 8601 no padrão brasileiro com o dia da semana.

    Args:
        date_str: Data em formato ISO 8601 (``YYYY-MM-DD`` ou com horário).

    Returns:
        Data formatada, ex: ``"segunda-feira, 07 de abril de 2026"``.
    """
    _MONTHS_PT = {
        1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril",
        5: "maio", 6: "junho", 7: "julho", 8: "agosto",
        9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro",
    }
    try:
        d = date.fromisoformat(date_str.split("T")[0])
        weekday = _WEEKDAYS_PT[d.weekday()]
        month = _MONTHS_PT[d.month]
        return f"{weekday}, {d.day:02d} de {month} de {d.year}"
    except Exception as exc:
        logger.exception("format_date_br failed")
        return f"Erro ao formatar data: {exc}"


# ── Tool list (exported for agent binding) ─────────────────────────────────────

DATETIME_TOOLS = [get_current_datetime, parse_relative_date, get_weekday, format_date_br]
