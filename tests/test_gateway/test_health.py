"""Tests for /health and /ready endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client() -> TestClient:
    """TestClient with DB and scheduler mocked."""
    from src.gateway.app import app

    return TestClient(app, raise_server_exceptions=False)


# ── /health ───────────────────────────────────────────────────────────────────


def _make_mock_engine(execute_side_effect: Exception | None = None) -> MagicMock:
    """Build a mock SQLAlchemy async engine."""
    mock_conn = AsyncMock()
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)
    mock_conn.execute = AsyncMock(side_effect=execute_side_effect)
    mock_engine = MagicMock()
    mock_engine.connect.return_value = mock_conn
    return mock_engine


def test_health_ok_when_db_and_scheduler_running(client: TestClient) -> None:
    """GET /health returns 200 with all subsystems ok."""
    mock_scheduler = MagicMock()
    mock_scheduler.running = True

    with (
        patch("src.scheduler.setup.get_scheduler", return_value=mock_scheduler),
        patch("src.memory.database._get_engine", return_value=_make_mock_engine()),
    ):
        r = client.get("/health")

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert body["scheduler"] == "ok"
    assert "version" in body


def test_health_db_error(client: TestClient) -> None:
    """GET /health returns db=error when the DB query fails."""
    mock_scheduler = MagicMock()
    mock_scheduler.running = True

    with (
        patch("src.scheduler.setup.get_scheduler", return_value=mock_scheduler),
        patch(
            "src.memory.database._get_engine",
            return_value=_make_mock_engine(execute_side_effect=Exception("db down")),
        ),
    ):
        r = client.get("/health")

    assert r.status_code == 200
    body = r.json()
    assert body["db"] == "error"
    assert body["scheduler"] == "ok"


def test_health_scheduler_stopped(client: TestClient) -> None:
    """GET /health returns scheduler=stopped when the scheduler is not running."""
    with (
        patch("src.scheduler.setup.get_scheduler", side_effect=RuntimeError("not started")),
        patch("src.memory.database._get_engine", return_value=_make_mock_engine()),
    ):
        r = client.get("/health")

    assert r.status_code == 200
    body = r.json()
    assert body["scheduler"] == "stopped"


# ── /ready ────────────────────────────────────────────────────────────────────


def test_ready_returns_200_when_scheduler_running(client: TestClient) -> None:
    """GET /ready returns 200 when scheduler is running."""
    mock_scheduler = MagicMock()
    mock_scheduler.running = True

    with patch("src.scheduler.setup.get_scheduler", return_value=mock_scheduler):
        r = client.get("/ready")

    assert r.status_code == 200
    assert r.json()["status"] == "ready"


def test_ready_returns_503_when_scheduler_stopped(client: TestClient) -> None:
    """GET /ready returns 503 when scheduler has not started."""
    with patch("src.scheduler.setup.get_scheduler", side_effect=RuntimeError("not started")):
        r = client.get("/ready")

    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "not ready"
