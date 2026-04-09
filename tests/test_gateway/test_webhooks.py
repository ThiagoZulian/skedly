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


# ── Approval flow tests ───────────────────────────────────────────────────────
# Non-admin users go through DB-based access control.
# user_id=999, chat_id=999 is used as a "non-admin" user in these tests.


def _non_admin_update(text: str = "Oi") -> dict:
    """Update from a non-admin user (chat_id != TELEGRAM_CHAT_ID=456)."""
    return _telegram_update(text=text, user_id=999, chat_id=999)


def test_new_user_gets_pending_response(client):
    """First message from an unknown user should register as pending and return ok."""
    with patch(
        "src.gateway.routes.telegram._check_or_register_user",
        AsyncMock(return_value=False),
    ):
        resp = client.post(
            "/webhook/telegram",
            json=_non_admin_update("Oi"),
            headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET},
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_pending_user_does_not_invoke_graph(client):
    """Message from a pending user must not reach the graph."""
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(return_value={"response": "should not see this"})

    with (
        patch("src.gateway.routes.telegram._graph", mock_graph),
        patch(
            "src.gateway.routes.telegram._check_or_register_user",
            AsyncMock(return_value=False),
        ),
    ):
        client.post(
            "/webhook/telegram",
            json=_non_admin_update("alguma coisa"),
            headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET},
        )

    mock_graph.ainvoke.assert_not_awaited()


def test_active_user_invokes_graph(client):
    """Message from an active (approved) user must reach the graph."""
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(return_value={"response": "ok", "intent": "chat"})

    with (
        patch("src.gateway.routes.telegram._graph", mock_graph),
        patch("src.gateway.routes.telegram._send_telegram_message", AsyncMock()),
        patch(
            "src.gateway.routes.telegram._check_or_register_user",
            AsyncMock(return_value=True),
        ),
    ):
        client.post(
            "/webhook/telegram",
            json=_non_admin_update("quais meus eventos?"),
            headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET},
        )

    mock_graph.ainvoke.assert_awaited_once()


def test_admin_aprovar_command_calls_handle_approval(client):
    """Admin sending /aprovar <id> must trigger _handle_approval(approve=True)."""
    mock_handle = AsyncMock()
    with (
        patch("src.gateway.routes.telegram._send_telegram_message", AsyncMock()),
        patch("src.gateway.routes.telegram._handle_approval", mock_handle),
    ):
        # chat_id=456 is TELEGRAM_CHAT_ID in tests → admin
        resp = client.post(
            "/webhook/telegram",
            json=_telegram_update(text="/aprovar 999", user_id=456, chat_id=456),
            headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET},
        )

    assert resp.status_code == 200
    mock_handle.assert_awaited_once_with(456, "999", approve=True)


def test_admin_rejeitar_command_calls_handle_approval(client):
    """Admin sending /rejeitar <id> must trigger _handle_approval(approve=False)."""
    mock_handle = AsyncMock()
    with (
        patch("src.gateway.routes.telegram._send_telegram_message", AsyncMock()),
        patch("src.gateway.routes.telegram._handle_approval", mock_handle),
    ):
        resp = client.post(
            "/webhook/telegram",
            json=_telegram_update(text="/rejeitar 999", user_id=456, chat_id=456),
            headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET},
        )

    assert resp.status_code == 200
    mock_handle.assert_awaited_once_with(456, "999", approve=False)


def test_non_admin_cannot_use_aprovar_command(client):
    """Non-admin sending /aprovar must be checked for access, not processed as admin command."""
    mock_check = AsyncMock(return_value=False)
    mock_handle = AsyncMock()

    with (
        patch("src.gateway.routes.telegram._check_or_register_user", mock_check),
        patch("src.gateway.routes.telegram._handle_approval", mock_handle),
    ):
        client.post(
            "/webhook/telegram",
            json=_non_admin_update("/aprovar 456"),
            headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET},
        )

    mock_handle.assert_not_awaited()
    mock_check.assert_awaited_once()
