"""FastAPI application entry point."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pythonjsonlogger import json as jsonlogger
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from src.config import settings
from src.gateway.limiter import limiter
from src.gateway.routes import calendar as calendar_router
from src.gateway.routes import clickup as clickup_router
from src.gateway.routes import telegram as telegram_router

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    """Configure root logger — JSON format when LOG_FORMAT=json, text otherwise."""
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    if root.handlers:
        # Already configured (e.g. during tests) — don't duplicate handlers.
        return

    if settings.log_format == "json":
        handler = logging.StreamHandler()
        formatter = jsonlogger.JsonFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
            rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
        )
        handler.setFormatter(formatter)
        root.addHandler(handler)
        # Propagate JSON handler to library loggers that own their own handlers
        for lib in ("uvicorn", "uvicorn.access", "uvicorn.error", "apscheduler"):
            lib_logger = logging.getLogger(lib)
            lib_logger.handlers = [handler]
            lib_logger.propagate = False
    else:
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
    version="0.3.0",
    lifespan=lifespan,
)

# ── Rate limiting ─────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Return HTTP 429 with a friendly Portuguese message."""
    return JSONResponse(
        status_code=429,
        content={"detail": "Muitas requisições. Aguarde um momento antes de tentar novamente."},
    )


app.include_router(telegram_router.router)
app.include_router(clickup_router.router)
app.include_router(calendar_router.router)


@app.get("/health", tags=["infra"])
async def health() -> dict[str, str]:
    """Liveness probe — checks subsystem status."""
    from sqlalchemy import text

    from src.memory.database import _get_engine
    from src.scheduler.setup import get_scheduler

    # DB check
    db_status = "ok"
    try:
        async with _get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    # Scheduler check
    try:
        scheduler = get_scheduler()
        scheduler_status = "ok" if scheduler.running else "stopped"
    except RuntimeError:
        scheduler_status = "stopped"

    return {
        "status": "ok",
        "db": db_status,
        "scheduler": scheduler_status,
        "version": "0.3.0",
    }


@app.get("/ready", tags=["infra"])
async def ready() -> dict[str, str]:
    """Readiness probe — returns 503 until scheduler is running."""
    from src.scheduler.setup import get_scheduler

    try:
        scheduler = get_scheduler()
        running = scheduler.running
    except RuntimeError:
        running = False

    if not running:
        from fastapi.responses import JSONResponse as _JSONResponse

        return _JSONResponse(  # type: ignore[return-value]
            status_code=503,
            content={"status": "not ready", "reason": "scheduler not running"},
        )
    return {"status": "ready"}
