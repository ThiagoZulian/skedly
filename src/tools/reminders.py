"""Reminder LangChain tools — persist jobs to SQLite via APScheduler."""

from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from langchain_core.tools import tool

logger = logging.getLogger(__name__)
_TZ = ZoneInfo("America/Sao_Paulo")


@tool
async def create_reminder(message: str, remind_at: str, user_id: str) -> str:
    """Cria um lembrete que será enviado via Telegram no horário especificado.

    O lembrete é persistido no SQLite e sobrevive a restarts do servidor.

    Args:
        message: Texto do lembrete (ex: ``"Pagar o DAS"``).
        remind_at: Data/hora no formato ISO 8601 (``YYYY-MM-DDTHH:MM:SS``).
                   Assume fuso America/Sao_Paulo se não especificado.
        user_id: ID do usuário Telegram que receberá o lembrete.

    Returns:
        Confirmação com o ID do lembrete criado.
    """
    try:
        from src.memory.database import get_async_session
        from src.memory.models import Reminder
        from src.scheduler.jobs import send_reminder_job
        from src.scheduler.setup import get_scheduler

        # Parse the datetime
        dt = datetime.fromisoformat(remind_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_TZ)

        # Persist to DB
        async with get_async_session() as session:
            reminder = Reminder(user_id=user_id, message=message, remind_at=dt, status="pending")
            session.add(reminder)
            await session.commit()
            await session.refresh(reminder)
            reminder_id = reminder.id

        # Register APScheduler job
        scheduler = get_scheduler()
        scheduler.add_job(
            send_reminder_job,
            trigger="date",
            run_date=dt,
            kwargs={"reminder_id": reminder_id, "user_id": user_id, "message": message},
            id=f"reminder_{reminder_id}",
            replace_existing=True,
        )

        formatted = dt.strftime("%d/%m/%Y às %H:%M")
        return f"Lembrete criado (ID: {reminder_id}) — '{message}' em {formatted}."
    except Exception as exc:
        logger.exception("create_reminder failed")
        return f"Erro ao criar lembrete: {exc}"


@tool
async def list_reminders(user_id: str) -> str:
    """Lista todos os lembretes pendentes de um usuário.

    Args:
        user_id: ID do usuário Telegram.

    Returns:
        Lista de lembretes pendentes ou mensagem de "nenhum lembrete".
    """
    try:
        from sqlalchemy import select

        from src.memory.database import get_async_session
        from src.memory.models import Reminder

        async with get_async_session() as session:
            result = await session.execute(
                select(Reminder)
                .where(Reminder.user_id == user_id, Reminder.status == "pending")
                .order_by(Reminder.remind_at)
            )
            reminders = result.scalars().all()

        if not reminders:
            return "Nenhum lembrete pendente."

        lines = []
        for r in reminders:
            dt_str = r.remind_at.strftime("%d/%m/%Y %H:%M")
            lines.append(f"[{r.id}] {r.message} — {dt_str}")
        return "\n".join(lines)
    except Exception as exc:
        logger.exception("list_reminders failed")
        return f"Erro ao listar lembretes: {exc}"


@tool
async def delete_reminder(reminder_id: str) -> str:
    """Cancela e deleta um lembrete pelo seu ID.

    Args:
        reminder_id: ID numérico do lembrete (obtido via list_reminders).

    Returns:
        Confirmação de cancelamento ou mensagem de erro.
    """
    try:
        from src.memory.database import get_async_session
        from src.memory.models import Reminder
        from src.scheduler.setup import get_scheduler

        rid = int(reminder_id)

        async with get_async_session() as session:
            reminder = await session.get(Reminder, rid)
            if not reminder:
                return f"Lembrete {reminder_id} não encontrado."
            reminder.status = "cancelled"
            await session.commit()

        # Remove from scheduler if still scheduled
        scheduler = get_scheduler()
        job_id = f"reminder_{rid}"
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)

        return f"Lembrete {reminder_id} cancelado."
    except ValueError:
        return f"ID inválido: '{reminder_id}'. Informe um número inteiro."
    except Exception as exc:
        logger.exception("delete_reminder failed")
        return f"Erro ao deletar lembrete {reminder_id}: {exc}"


REMINDER_TOOLS = [create_reminder, list_reminders, delete_reminder]
