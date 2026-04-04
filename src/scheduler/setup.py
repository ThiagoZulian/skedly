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


def init_scheduler() -> AsyncIOScheduler:
    """Create, configure and start the APScheduler AsyncIOScheduler.

    Uses a SQLite job store so jobs survive restarts.
    Called once during the FastAPI lifespan startup.

    Returns:
        The running scheduler instance.
    """
    global _scheduler

    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    jobstores = {
        "default": SQLAlchemyJobStore(url=f"sqlite:///{_DB_PATH}"),
    }
    _scheduler = AsyncIOScheduler(jobstores=jobstores, timezone="America/Sao_Paulo")
    _scheduler.start()
    logger.info("APScheduler started with SQLite job store at %s", _DB_PATH)
    return _scheduler


def shutdown_scheduler() -> None:
    """Stop the scheduler gracefully. Called during FastAPI lifespan shutdown."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")
    _scheduler = None
