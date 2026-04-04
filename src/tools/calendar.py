"""Google Calendar LangChain tools.

All tools are async — the synchronous Google API client is run in a thread
pool via ``asyncio.to_thread`` to avoid blocking the event loop.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from langchain_core.tools import tool

from src.config import settings
from src.tools._google_auth import get_calendar_service

logger = logging.getLogger(__name__)
_TZ = ZoneInfo("America/Sao_Paulo")


# ── Helpers ───────────────────────────────────────────────────────────────────


def _fmt_event(ev: dict) -> str:
    """Format a single Calendar event dict into a human-readable line."""
    start = ev["start"].get("dateTime", ev["start"].get("date", ""))
    title = ev.get("summary", "(sem título)")
    return f"[{ev['id']}] {title} — {start}"


# ── Tools ─────────────────────────────────────────────────────────────────────


@tool
async def list_events(days_ahead: int = 7) -> str:
    """Lista eventos do Google Calendar nos próximos N dias.

    Args:
        days_ahead: Número de dias à frente para buscar (padrão: 7).

    Returns:
        Lista formatada de eventos com ID, título e horário.
    """

    def _sync() -> str:
        service = get_calendar_service()
        now = datetime.now(_TZ)
        end = now + timedelta(days=days_ahead)

        result = (
            service.events()
            .list(
                calendarId=settings.google_calendar_id,
                timeMin=now.isoformat(),
                timeMax=end.isoformat(),
                singleEvents=True,
                orderBy="startTime",
                maxResults=50,
            )
            .execute()
        )
        events = result.get("items", [])
        if not events:
            return "Nenhum evento encontrado no período."
        return "\n".join(_fmt_event(e) for e in events)

    try:
        return await asyncio.to_thread(_sync)
    except Exception as exc:
        logger.exception("list_events failed")
        return f"Erro ao listar eventos: {exc}"


@tool
async def create_event(title: str, start: str, end: str, description: str = "") -> str:
    """Cria um evento no Google Calendar.

    Args:
        title: Título do evento.
        start: Data/hora de início em ISO 8601, ex: ``2026-04-05T14:00:00-03:00``.
        end: Data/hora de fim em ISO 8601.
        description: Descrição opcional do evento.

    Returns:
        Confirmação com o ID do evento criado.
    """

    def _sync() -> str:
        service = get_calendar_service()
        body = {
            "summary": title,
            "description": description,
            "start": {"dateTime": start, "timeZone": "America/Sao_Paulo"},
            "end": {"dateTime": end, "timeZone": "America/Sao_Paulo"},
        }
        created = service.events().insert(calendarId=settings.google_calendar_id, body=body).execute()
        return f"Evento criado. ID: {created['id']} — {title} ({start})"

    try:
        return await asyncio.to_thread(_sync)
    except Exception as exc:
        logger.exception("create_event failed")
        return f"Erro ao criar evento: {exc}"


@tool
async def find_free_slots(date: str, duration_minutes: int = 60) -> str:
    """Encontra horários livres no Google Calendar para um dia específico.

    Busca slots entre 08:00 e 20:00 (horário de Brasília) com a duração solicitada.

    Args:
        date: Data no formato ``YYYY-MM-DD``.
        duration_minutes: Duração desejada do slot em minutos (padrão: 60).

    Returns:
        Lista de até 10 horários livres ou mensagem de "sem horários".
    """

    def _sync() -> str:
        service = get_calendar_service()
        day_start = datetime.fromisoformat(f"{date}T08:00:00").replace(tzinfo=_TZ)
        day_end = datetime.fromisoformat(f"{date}T20:00:00").replace(tzinfo=_TZ)

        freebusy = (
            service.freebusy()
            .query(
                body={
                    "timeMin": day_start.isoformat(),
                    "timeMax": day_end.isoformat(),
                    "timeZone": "America/Sao_Paulo",
                    "items": [{"id": settings.google_calendar_id}],
                }
            )
            .execute()
        )
        busy = freebusy["calendars"][settings.google_calendar_id]["busy"]

        delta = timedelta(minutes=duration_minutes)
        step = timedelta(minutes=30)
        slots: list[str] = []
        cursor = day_start

        for block in busy:
            b_start = datetime.fromisoformat(block["start"]).astimezone(_TZ)
            while cursor + delta <= b_start:
                slots.append(f"{cursor.strftime('%H:%M')} – {(cursor + delta).strftime('%H:%M')}")
                cursor += step
            cursor = max(cursor, datetime.fromisoformat(block["end"]).astimezone(_TZ))

        while cursor + delta <= day_end:
            slots.append(f"{cursor.strftime('%H:%M')} – {(cursor + delta).strftime('%H:%M')}")
            cursor += step

        if not slots:
            return f"Sem horários livres de {duration_minutes} min em {date}."
        top = slots[:10]
        return "Horários livres:\n" + "\n".join(f"- {s}" for s in top)

    try:
        return await asyncio.to_thread(_sync)
    except Exception as exc:
        logger.exception("find_free_slots failed")
        return f"Erro ao buscar horários livres: {exc}"


@tool
async def delete_event(event_id: str) -> str:
    """Deleta um evento do Google Calendar pelo seu ID.

    Args:
        event_id: ID do evento (obtido via list_events).

    Returns:
        Confirmação de deleção ou mensagem de erro.
    """

    def _sync() -> str:
        service = get_calendar_service()
        service.events().delete(
            calendarId=settings.google_calendar_id, eventId=event_id
        ).execute()
        return f"Evento {event_id} deletado com sucesso."

    try:
        return await asyncio.to_thread(_sync)
    except Exception as exc:
        logger.exception("delete_event failed")
        return f"Erro ao deletar evento {event_id}: {exc}"


# ── Tool list (exported for agent binding) ─────────────────────────────────────

CALENDAR_TOOLS = [list_events, create_event, find_free_slots, delete_event]
