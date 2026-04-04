"""LangGraph SQLite checkpointer lifecycle management."""

from __future__ import annotations

import logging
from pathlib import Path

import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

logger = logging.getLogger(__name__)

_CHECKPOINT_DB = Path("data/checkpoints.db")
_conn: aiosqlite.Connection | None = None
_checkpointer: AsyncSqliteSaver | None = None


async def get_checkpointer() -> AsyncSqliteSaver:
    """Return (or create) the singleton AsyncSqliteSaver.

    Opens the aiosqlite connection on first call and reuses it thereafter.
    """
    global _conn, _checkpointer
    if _checkpointer is None:
        _CHECKPOINT_DB.parent.mkdir(parents=True, exist_ok=True)
        _conn = await aiosqlite.connect(str(_CHECKPOINT_DB))
        _checkpointer = AsyncSqliteSaver(_conn)
        await _checkpointer.setup()
        logger.info("LangGraph checkpointer initialised at %s", _CHECKPOINT_DB)
    return _checkpointer


async def close_checkpointer() -> None:
    """Close the aiosqlite connection. Called during FastAPI lifespan shutdown."""
    global _conn, _checkpointer
    if _conn:
        await _conn.close()
        logger.info("LangGraph checkpointer closed")
    _conn = None
    _checkpointer = None
