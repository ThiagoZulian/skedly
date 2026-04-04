"""FastAPI application entry point."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.config import settings
from src.gateway.routes import calendar as calendar_router
from src.gateway.routes import clickup as clickup_router
from src.gateway.routes import telegram as telegram_router

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _configure_langsmith() -> None:
    """Enable LangSmith tracing if configured."""
    if not settings.langsmith_api_key or not settings.langsmith_tracing:
        return
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
    os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project
    logger.info("LangSmith tracing enabled — project: %s", settings.langsmith_project)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup: DB, scheduler, checkpointer, graph. Shutdown: cleanup."""
    _configure_logging()
    logger.info("SecretarIA starting up…")
    _configure_langsmith()

    # Database
    from src.memory.database import init_db
    await init_db()

    # Scheduler
    from src.scheduler.setup import init_scheduler, shutdown_scheduler
    init_scheduler()

    # LangGraph checkpointer — rebuild graph with persistence
    from src.graph.builder import build_graph
    from src.memory.checkpointer import close_checkpointer, get_checkpointer
    checkpointer = await get_checkpointer()
    import src.gateway.routes.telegram as tg_route
    tg_route._graph = build_graph(checkpointer=checkpointer)
    logger.info("Graph rebuilt with SQLite checkpointer")

    yield

    # Shutdown
    shutdown_scheduler()
    await close_checkpointer()
    logger.info("SecretarIA shutting down…")


app = FastAPI(
    title="SecretarIA",
    description="Assistente pessoal de IA com LangGraph, Telegram, Google Calendar e ClickUp.",
    version="0.2.0",
    lifespan=lifespan,
)

app.include_router(telegram_router.router)
app.include_router(clickup_router.router)
app.include_router(calendar_router.router)


@app.get("/health", tags=["infra"])
async def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}
