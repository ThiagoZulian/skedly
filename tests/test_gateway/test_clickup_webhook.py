"""Tests for the ClickUp webhook route — signature validation and graph invocation."""

import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

CLICKUP_SECRET = "test-clickup-secret"

_VALID_PAYLOAD = {
    "event": "taskStatusUpdated",
    "task_id": "abc123",
    "webhook_id": "wh1",
    "history_items": [],
}


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.fixture
def client():
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(return_value={"intent": "query_tasks", "response": "ok"})

    with (
        patch("src.gateway.routes.telegram._graph", mock_graph),
        patch("src.gateway.routes.telegram._send_telegram_message", AsyncMock()),
        patch("src.gateway.routes.clickup._graph", mock_graph, create=True),
    ):
        from src.gateway.app import app

        with TestClient(app, raise_server_exceptions=True) as c:
            yield c


# ── No signature configured (CLICKUP_WEBHOOK_SECRET not set) ─────────────────


def test_webhook_no_secret_configured_accepts_any_payload(client):
    """When no secret is configured, any payload should return 200."""
    resp = client.post("/webhook/clickup", json=_VALID_PAYLOAD)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_webhook_all_event_types_return_ok(client):
    """All known ClickUp event types should be accepted and return 200."""
    events = [
        "taskCreated",
        "taskUpdated",
        "taskDeleted",
        "taskStatusUpdated",
        "taskDueDateUpdated",
        "unknownFutureEvent",
    ]
    for event in events:
        payload = {**_VALID_PAYLOAD, "event": event}
        resp = client.post("/webhook/clickup", json=payload)
        assert resp.status_code == 200, f"Failed for event={event}"


def test_webhook_missing_task_id_still_returns_ok(client):
    """Payload without task_id should return 200 (task_id is optional)."""
    payload = {"event": "taskCreated", "webhook_id": "wh1"}
    resp = client.post("/webhook/clickup", json=payload)
    assert resp.status_code == 200


# ── Signature validation ──────────────────────────────────────────────────────


def test_webhook_valid_signature_accepted(monkeypatch):
    """Valid HMAC signature with matching secret should return 200."""
    monkeypatch.setenv("CLICKUP_WEBHOOK_SECRET", CLICKUP_SECRET)

    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(return_value={"intent": "query_tasks", "response": "ok"})

    with (
        patch("src.gateway.routes.telegram._graph", mock_graph),
        patch("src.gateway.routes.telegram._send_telegram_message", AsyncMock()),
    ):
        from src.gateway.app import app

        body = json.dumps(_VALID_PAYLOAD).encode()
        sig = _sign(body, CLICKUP_SECRET)

        import src.config as cfg
        cfg._settings = None  # force reload with new env var

        with TestClient(app) as c:
            resp = c.post(
                "/webhook/clickup",
                content=body,
                headers={"Content-Type": "application/json", "X-Signature": sig},
            )
        assert resp.status_code == 200


def test_webhook_invalid_signature_rejected(monkeypatch):
    """Wrong HMAC signature should return 403."""
    monkeypatch.setenv("CLICKUP_WEBHOOK_SECRET", CLICKUP_SECRET)

    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(return_value={"intent": "query_tasks", "response": "ok"})

    with (
        patch("src.gateway.routes.telegram._graph", mock_graph),
        patch("src.gateway.routes.telegram._send_telegram_message", AsyncMock()),
    ):
        from src.gateway.app import app

        import src.config as cfg
        cfg._settings = None

        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.post(
                "/webhook/clickup",
                json=_VALID_PAYLOAD,
                headers={"X-Signature": "deadbeef"},
            )
        assert resp.status_code == 403


def test_webhook_missing_signature_rejected(monkeypatch):
    """No X-Signature header when secret is configured should return 403."""
    monkeypatch.setenv("CLICKUP_WEBHOOK_SECRET", CLICKUP_SECRET)

    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(return_value={"intent": "query_tasks", "response": "ok"})

    with (
        patch("src.gateway.routes.telegram._graph", mock_graph),
        patch("src.gateway.routes.telegram._send_telegram_message", AsyncMock()),
    ):
        from src.gateway.app import app

        import src.config as cfg
        cfg._settings = None

        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.post("/webhook/clickup", json=_VALID_PAYLOAD)
        assert resp.status_code == 403
