"""Google Calendar LangChain tools.

All tools are async — the synchronous Google API client is run in a thread
pool via ``asyncio.to_thread`` to avoid blocking the event loop.

All tools accept an optional ``calendar_id`` parameter. Pass ``"all"`` to
operate across every calendar the user has access to (default for read
operations). Pass ``"primary"`` or a specific calendar ID for write
operations.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from langchain_core.tools import tool

from src.tools._google_auth import get_calendar_service

logger = logging.getLogger(__name__)
_TZ = ZoneInfo("America/Sao_Paulo")


# ── Helpers ───────────────────────────────────────────────────────────────────


def _fmt_event(ev: dict, calendar_name: str = "") -> str:
    """Format a single Calendar event dict into a human-readable line."""
    start = ev["start"].get("dateTime", ev["start"].get("date", ""))
    title = ev.get("summary", "(sem título)")
    cal = f" [{calendar_name}]" if calendar_name else ""
    return f"[{ev['id']}] {title} — {start}{cal}"


def _get_all_calendar_ids(service) -> list[tuple[str, str]]:
    """Return list of (id, summary) for all calendars the user has access to."""
    result = service.calendarList().list().execute()
    return [(c["id"], c.get("summary", c["id"])) for c in result.get("items", [])]


# ── Tools ─────────────────────────────────────────────────────────────────────


@tool
async def list_calendars() -> str:
    """Lista todas as agendas disponíveis no Google Calendar do usuário.

    Retorna ID, nome e papel de acesso de cada agenda. Use os IDs retornados
    para operações em agendas específicas.

    Returns:
        Lista formatada de agendas com ID e nome.
    """

    def _sync() -> str:
        service = get_calendar_service()
        result = service.calendarList().list().execute()
        items = result.get("items", [])
        if not items:
            return "Nenhuma agenda encontrada."
        lines = []
        for cal in items:
            role = cal.get("accessRole", "")
            lines.append(f"[{cal['id']}] {cal.get('summary', '?')} (acesso: {role})")
        return "\n".join(lines)

    try:
        return await asyncio.to_thread(_sync)
    except Exception as exc:
        logger.exception("list_calendars failed")
        return f"Erro ao listar agendas: {exc}"


@tool
async def list_events(days_ahead: int = 7, calendar_id: str = "all") -> str:
    """Lista eventos do Google Calendar nos próximos N dias.

    Args:
        days_ahead: Número de dias à frente para buscar (padrão: 7).
        calendar_id: ID da agenda a consultar. Use ``"all"`` para buscar em
            todas as agendas (padrão), ``"primary"`` para a agenda principal,
            ou um ID específico obtido via ``list_calendars``.

    Returns:
        Lista formatada de eventos com ID, título, horário e agenda de origem.
    """

    def _sync() -> str:
        service = get_calendar_service()
        now = datetime.now(_TZ)
        end = now + timedelta(days=days_ahead)

        if calendar_id == "all":
            calendars = _get_all_calendar_ids(service)
        else:
            # Single calendar — fetch its name for display
            try:
                cal_meta = service.calendarList().get(calendarId=calendar_id).execute()
                cal_name = cal_meta.get("summary", calendar_id)
            except Exception:
                cal_name = calendar_id
            calendars = [(calendar_id, cal_name)]

        all_events: list[tuple[datetime, str]] = []

        for cal_id, cal_name in calendars:
            try:
                result = (
                    service.events()
                    .list(
                        calendarId=cal_id,
                        timeMin=now.isoformat(),
                        timeMax=end.isoformat(),
                        singleEvents=True,
                        orderBy="startTime",
                        maxResults=50,
                    )
                    .execute()
                )
                for ev in result.get("items", []):
                    # Skip working location and focus time entries — these are
                    # Google Calendar status markers, not real appointments.
                    if ev.get("eventType") in ("workingLocation", "focusTime"):
                        continue
                    raw = ev["start"].get("dateTime", ev["start"].get("date", ""))
                    try:
                        dt = datetime.fromisoformat(raw).astimezone(_TZ)
                    except Exception:
                        dt = now
                    all_events.append((dt, _fmt_event(ev, cal_name)))
            except Exception:
                logger.warning("Failed to list events for calendar %s", cal_id)

        if not all_events:
            return "Nenhum evento encontrado no período."

        all_events.sort(key=lambda x: x[0])
        return "\n".join(line for _, line in all_events)

    try:
        return await asyncio.to_thread(_sync)
    except Exception as exc:
        logger.exception("list_events failed")
        return f"Erro ao listar eventos: {exc}"


@tool
async def create_event(
    title: str,
    start: str,
    end: str,
    description: str = "",
    calendar_id: str = "primary",
) -> str:
    """Cria um evento no Google Calendar.

    Args:
        title: Título do evento.
        start: Data/hora de início em ISO 8601, ex: ``2026-04-05T14:00:00-03:00``.
        end: Data/hora de fim em ISO 8601.
        description: Descrição opcional do evento.
        calendar_id: ID da agenda onde criar o evento. Use ``"primary"`` para
            a agenda principal (padrão) ou um ID obtido via ``list_calendars``.

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
        created = service.events().insert(calendarId=calendar_id, body=body).execute()
        return f"Evento criado. ID: {created['id']} — {title} ({start})"

    try:
        return await asyncio.to_thread(_sync)
    except Exception as exc:
        logger.exception("create_event failed")
        return f"Erro ao criar evento: {exc}"


@tool
async def find_free_slots(
    date: str,
    duration_minutes: int = 60,
    calendar_id: str = "all",
) -> str:
    """Encontra horários livres no Google Calendar para um dia específico.

    Busca slots entre 08:00 e 20:00 (horário de Brasília) considerando os
    eventos de todas as agendas (ou de uma específica).

    Args:
        date: Data no formato ``YYYY-MM-DD``.
        duration_minutes: Duração desejada do slot em minutos (padrão: 60).
        calendar_id: ID da agenda a considerar. Use ``"all"`` para considerar
            todas as agendas (padrão), evitando conflitos entre agendas.

    Returns:
        Lista de até 10 horários livres ou mensagem de "sem horários".
    """

    def _sync() -> str:
        service = get_calendar_service()
        day_start = datetime.fromisoformat(f"{date}T08:00:00").replace(tzinfo=_TZ)
        day_end = datetime.fromisoformat(f"{date}T20:00:00").replace(tzinfo=_TZ)

        if calendar_id == "all":
            cal_ids = [c[0] for c in _get_all_calendar_ids(service)]
        else:
            cal_ids = [calendar_id]

        freebusy = (
            service.freebusy()
            .query(
                body={
                    "timeMin": day_start.isoformat(),
                    "timeMax": day_end.isoformat(),
                    "timeZone": "America/Sao_Paulo",
                    "items": [{"id": cid} for cid in cal_ids],
                }
            )
            .execute()
        )

        # Merge busy blocks from all calendars
        all_busy: list[dict] = []
        for cid in cal_ids:
            all_busy.extend(freebusy["calendars"].get(cid, {}).get("busy", []))

        # Sort and merge overlapping blocks
        all_busy.sort(key=lambda b: b["start"])
        merged: list[tuple[datetime, datetime]] = []
        for block in all_busy:
            bs = datetime.fromisoformat(block["start"]).astimezone(_TZ)
            be = datetime.fromisoformat(block["end"]).astimezone(_TZ)
            if merged and bs <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], be))
            else:
                merged.append((bs, be))

        delta = timedelta(minutes=duration_minutes)
        step = timedelta(minutes=30)
        slots: list[str] = []
        cursor = day_start

        for b_start, b_end in merged:
            while cursor + delta <= b_start:
                slots.append(f"{cursor.strftime('%H:%M')} – {(cursor + delta).strftime('%H:%M')}")
                cursor += step
            cursor = max(cursor, b_end)

        while cursor + delta <= day_end:
            slots.append(f"{cursor.strftime('%H:%M')} – {(cursor + delta).strftime('%H:%M')}")
            cursor += step

        if not slots:
            return f"Sem horários livres de {duration_minutes} min em {date}."
        return "Horários livres:\n" + "\n".join(f"- {s}" for s in slots[:10])

    try:
        return await asyncio.to_thread(_sync)
    except Exception as exc:
        logger.exception("find_free_slots failed")
        return f"Erro ao buscar horários livres: {exc}"


@tool
async def delete_event(event_id: str, calendar_id: str = "primary") -> str:
    """Deleta um evento do Google Calendar pelo seu ID.

    Args:
        event_id: ID do evento (obtido via list_events).
        calendar_id: ID da agenda onde o evento está (padrão: ``"primary"``).
            Use o ID da agenda exibido pelo list_events.

    Returns:
        Confirmação de deleção ou mensagem de erro.
    """

    def _sync() -> str:
        service = get_calendar_service()
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        return f"Evento {event_id} deletado com sucesso."

    try:
        return await asyncio.to_thread(_sync)
    except Exception as exc:
        logger.exception("delete_event failed")
        return f"Erro ao deletar evento {event_id}: {exc}"


@tool
async def delete_calendar(calendar_id: str) -> str:
    """Deleta uma agenda do Google Calendar pelo seu ID.

    Não é possível deletar a agenda principal (``"primary"``).
    Use ``list_calendars`` para obter os IDs das agendas disponíveis.

    Args:
        calendar_id: ID da agenda a deletar (obtido via ``list_calendars``).

    Returns:
        Confirmação de deleção ou mensagem de erro.
    """

    def _sync() -> str:
        service = get_calendar_service()
        service.calendars().delete(calendarId=calendar_id).execute()
        return f"Agenda {calendar_id} deletada com sucesso."

    try:
        return await asyncio.to_thread(_sync)
    except Exception as exc:
        logger.exception("delete_calendar failed")
        return f"Erro ao deletar agenda {calendar_id}: {exc}"


@tool
async def create_calendar(name: str, description: str = "") -> str:
    """Cria uma nova agenda no Google Calendar do usuário.

    Args:
        name: Nome da nova agenda.
        description: Descrição opcional da agenda.

    Returns:
        Confirmação com o ID da agenda criada.
    """

    def _sync() -> str:
        service = get_calendar_service()
        body: dict = {"summary": name}
        if description:
            body["description"] = description
        created = service.calendars().insert(body=body).execute()
        return f"Agenda criada. ID: {created['id']} — {name}"

    try:
        return await asyncio.to_thread(_sync)
    except Exception as exc:
        logger.exception("create_calendar failed")
        return f"Erro ao criar agenda: {exc}"


# ── Tool list (exported for agent binding) ─────────────────────────────────────

CALENDAR_TOOLS = [
    list_calendars,
    list_events,
    create_event,
    find_free_slots,
    delete_event,
    create_calendar,
    delete_calendar,
]
