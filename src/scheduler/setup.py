"""APScheduler setup — AsyncIOScheduler with SQLite job store."""

from __future__ import annotations

import logging
from pathlib import Path

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None

_DB_PATH = Path("data/scheduler.db")


def get_scheduler() -> AsyncIOScheduler:
    """Return the running scheduler instance (must call init_scheduler first)."""
    if _scheduler is None:
        raise RuntimeError("Scheduler not initialised — call init_scheduler() in lifespan.")
    return _scheduler


def register_fixed_cron_jobs(scheduler: AsyncIOScheduler, chat_id: str | None = None) -> None:  # noqa: ARG001 — kept for backward compat
    """Register the fixed daily cron jobs for briefing and deadline alerts.

    Both jobs run in the America/Sao_Paulo timezone. The briefing fires at
    ``settings.briefing_hour:00`` and the deadline check fires 5 minutes later.

    Args:
        scheduler: The running AsyncIOScheduler instance.
        chat_id: Telegram chat ID to deliver proactive messages to.
    """
    from src.config import settings
    from src.scheduler.jobs import check_deadlines, send_daily_briefing

    briefing_hour = settings.briefing_hour

    scheduler.add_job(
        send_daily_briefing,
        trigger="cron",
        hour=briefing_hour,
        minute=0,
        timezone="America/Sao_Paulo",
        kwargs={"chat_id": chat_id},
        id="daily_briefing",
        replace_existing=True,
        misfire_grace_time=300,
    )
    logger.info(
        "Registered daily_briefing cron at %02d:00 BRT for chat_id=%s",
        briefing_hour,
        chat_id,
    )

    scheduler.add_job(
        check_deadlines,
        trigger="cron",
        hour=briefing_hour,
        minute=5,
        timezone="America/Sao_Paulo",
        kwargs={"chat_id": chat_id},
        id="deadline_alerts",
        replace_existing=True,
        misfire_grace_time=300,
    )
    logger.info(
        "Registered deadline_alerts cron at %02d:05 BRT for chat_id=%s",
        briefing_hour,
        chat_id,
    )


def init_scheduler() -> AsyncIOScheduler:
    """Create, configure and start the APScheduler AsyncIOScheduler.

    Uses a SQLite job store so jobs survive restarts.
    If ``settings.telegram_chat_id`` is configured, registers the fixed daily
    cron jobs (briefing + deadline alerts) immediately after startup.
    Called once during the FastAPI lifespan startup.

    Returns:
        The running scheduler instance.
    """
    global _scheduler

    from src.config import settings

    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    jobstores = {
        "default": SQLAlchemyJobStore(url=f"sqlite:///{_DB_PATH}"),
    }
    _scheduler = AsyncIOScheduler(jobstores=jobstores, timezone="America/Sao_Paulo")
    _scheduler.start()
    logger.info("APScheduler started with SQLite job store at %s", _DB_PATH)

    from src.scheduler.jobs import check_all_deadlines, send_all_briefings

    briefing_hour = settings.briefing_hour
    scheduler.add_job(
        send_all_briefings,
        trigger="cron",
        hour=briefing_hour,
        minute=0,
        timezone="America/Sao_Paulo",
        id="daily_briefings",
        replace_existing=True,
        misfire_grace_time=300,
    )
    scheduler.add_job(
        check_all_deadlines,
        trigger="cron",
        hour=briefing_hour,
        minute=5,
        timezone="America/Sao_Paulo",
        id="deadline_alerts",
        replace_existing=True,
        misfire_grace_time=300,
    )
    logger.info("Registered multi-user briefing cron at %02d:00/05 BRT", briefing_hour)

    return _scheduler


def shutdown_scheduler() -> None:
    """Stop the scheduler gracefully. Called during FastAPI lifespan shutdown."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")
    _scheduler = None
