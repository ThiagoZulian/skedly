"""Tests for FastAPI gateway routes — zero external calls."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Must match TELEGRAM_WEBHOOK_SECRET set in conftest.py
WEBHOOK_SECRET = "test-webhook-secret"


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def client():
    """TestClient with graph and Telegram send patched out.

    env vars are already set at module level in conftest.py, so no additional
    settings patching is needed.
    """
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(
        return_value={
            "intent": "general_chat",
            "response": "Olá! Como posso ajudar?",
        }
    )

    with (
        patch("src.gateway.routes.telegram._graph", mock_graph),
        patch("src.gateway.routes.telegram._send_telegram_message", AsyncMock()),
    ):
        from src.gateway.app import app

        with TestClient(app, raise_server_exceptions=True) as c:
            yield c


# ── Helpers ───────────────────────────────────────────────────────────────────


def _telegram_update(text: str = "Oi", user_id: int = 123, chat_id: int = 456) -> dict:
    return {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "from": {
                "id": user_id,
                "is_bot": False,
                "first_name": "Tester",
            },
            "chat": {
                "id": chat_id,
                "type": "private",
                "first_name": "Tester",
            },
            "date": 1700000000,
            "text": text,
        },
    }


# ── Health endpoint ───────────────────────────────────────────────────────────


def test_health_returns_ok(client):
    """GET /health should return 200 with status:ok."""
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body


# ── Telegram webhook ──────────────────────────────────────────────────────────


def test_telegram_webhook_valid_secret_returns_ok(client):
    """POST /webhook/telegram with valid secret and message should return 200."""
    resp = client.post(
        "/webhook/telegram",
        json=_telegram_update("Olá"),
        headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_telegram_webhook_invalid_secret_returns_403(client):
    """POST /webhook/telegram with wrong secret should return 403."""
    resp = client.post(
        "/webhook/telegram",
        json=_telegram_update("Olá"),
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
    )
    assert resp.status_code == 403


def test_telegram_webhook_missing_secret_returns_403(client):
    """POST /webhook/telegram without secret header should return 403."""
    resp = client.post(
        "/webhook/telegram",
        json=_telegram_update("Olá"),
    )
    assert resp.status_code == 403


def test_telegram_webhook_no_message_returns_ignored(client):
    """Update with no message or edited_message should return status:ignored."""
    update = {"update_id": 99}
    resp = client.post(
        "/webhook/telegram",
        json=update,
        headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"


def test_telegram_webhook_empty_text_returns_ignored(client):
    """Message with empty text should return status:ignored without invoking graph."""
    resp = client.post(
        "/webhook/telegram",
        json=_telegram_update(text="   "),
        headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"


def test_telegram_webhook_graph_exception_returns_ok():
    """Even if the graph raises, the endpoint should return 200 (Telegram expects it)."""
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(side_effect=RuntimeError("graph boom"))

    with (
        patch("src.gateway.routes.telegram._graph", mock_graph),
        patch("src.gateway.routes.telegram._send_telegram_message", AsyncMock()),
    ):
        from src.gateway.app import app

        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.post(
                "/webhook/telegram",
                json=_telegram_update("teste"),
                headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET},
            )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
