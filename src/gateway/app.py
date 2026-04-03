"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from src.gateway.routes import telegram as telegram_router

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    """Configure basic logging for the application."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


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

    # ── LangSmith tracing (configured in Etapa 8) ────────────────────────────
    # Tracing setup is deferred to Etapa 8; the placeholder is kept here
    # so the lifespan structure is already in place.

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
