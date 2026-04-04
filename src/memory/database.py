"""Async SQLAlchemy engine and session factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.memory.models import Base

logger = logging.getLogger(__name__)

_DB_PATH = Path("data/secretary.db")
_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_engine():
    global _engine
    if _engine is None:
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        url = f"sqlite+aiosqlite:///{_DB_PATH}"
        _engine = create_async_engine(url, echo=False)
    return _engine


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(_get_engine(), expire_on_commit=False)
    return _session_factory


async def init_db() -> None:
    """Create all tables if they don't exist. Called once at startup."""
    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialised at %s", _DB_PATH)


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager that yields a transactional session."""
    async with _get_session_factory()() as session:
        yield session
