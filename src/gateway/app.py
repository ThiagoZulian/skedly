"""FastAPI application entry point."""

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.config import settings
from src.gateway.routes import telegram as telegram_router

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    """Configure basic logging for the application."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _configure_langsmith() -> None:
    """Enable LangSmith tracing if the API key is present.

    Sets the standard LangSmith environment variables so that all LangChain
    and LangGraph calls are automatically traced without any code changes.
    """
    if not settings.langsmith_api_key or not settings.langsmith_tracing:
        logger.info("LangSmith tracing disabled (LANGSMITH_TRACING=false or no key)")
        return

    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
    os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project
    logger.info("LangSmith tracing enabled — project: %s", settings.langsmith_project)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown hooks.

    Startup:
    - Configures logging.
    - Optionally enables LangSmith tracing if the API key is present.

    Shutdown:
    - Logs a clean shutdown message.
    """
    _configure_logging()
    logger.info("SecretarIA starting up…")

    _configure_langsmith()

    yield

    logger.info("SecretarIA shutting down…")


app = FastAPI(
    title="SecretarIA",
    description="Assistente pessoal de IA com LangGraph, Telegram, Google Calendar e ClickUp.",
    version="0.1.0",
    lifespan=lifespan,
)

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(telegram_router.router)


# ── Health check ──────────────────────────────────────────────────────────────


@app.get("/health", tags=["infra"])
async def health() -> dict[str, str]:
    """Simple liveness probe used by Docker healthcheck and load balancers."""
    return {"status": "ok"}
