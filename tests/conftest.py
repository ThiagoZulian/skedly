"""Shared pytest fixtures for Skedly tests.

Environment variables are set at module level (before any src imports) so that
the lazy Settings singleton picks them up on first access.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

# ── Set test env vars BEFORE any src.config import ───────────────────────────
# This must be at module level, not inside fixtures, because pytest collects
# and imports test modules (which trigger src.config) before fixtures run.

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-telegram-token")
os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET", "test-webhook-secret")
os.environ.setdefault("CLICKUP_API_TOKEN", "test-clickup-token")
os.environ.setdefault("CLICKUP_TEAM_ID", "test-team-id")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-key")
os.environ.setdefault("GOOGLE_AI_API_KEY", "AIza-test-key")
os.environ.setdefault("APP_SECRET_KEY", "test-app-secret")
os.environ.setdefault("APP_PORT", "8000")
# chat_id 456 is used as default in _telegram_update helpers — make it admin
os.environ.setdefault("TELEGRAM_CHAT_ID", "456")

# Force lazy settings to reinitialise with the test values.
import src.config as _cfg  # noqa: E402

_cfg._settings = None  # reset any previously cached instance


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_settings_singleton():
    """Reset the Settings singleton before each test so env overrides apply."""
    import src.config as cfg

    original = cfg._settings
    cfg._settings = None
    yield
    cfg._settings = original


@pytest.fixture
def mock_llm():
    """Return a mock LLM that returns a fixed AIMessage without calling any API."""
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=AIMessage(content="general_chat"))
    return llm


@pytest.fixture
def test_client():
    """Return a FastAPI TestClient for the Skedly app.

    The graph module-level singleton is patched so no real LLM is ever
    called during gateway tests.
    """
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(
        return_value={
            "intent": "general_chat",
            "response": "Olá! Como posso ajudar?",
        }
    )

    with patch("src.gateway.routes.telegram._graph", mock_graph):
        from fastapi.testclient import TestClient

        from src.gateway.app import app

        client = TestClient(app, raise_server_exceptions=True)
        yield client
