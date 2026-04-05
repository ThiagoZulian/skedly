"""Tests for tenacity retry behaviour in ClickUp tools and scheduler jobs."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

# ── ClickUp _get / _post / _put ───────────────────────────────────────────────


def _make_5xx_response() -> httpx.Response:
    return httpx.Response(500, text="internal server error")


def _make_4xx_response() -> httpx.Response:
    return httpx.Response(404, text="not found")


@pytest.mark.asyncio
async def test_clickup_get_retries_on_5xx() -> None:
    """_get retries up to 3 times on 5xx errors before raising."""
    from src.tools.clickup import _get

    call_count = 0

    async def fake_get(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise httpx.HTTPStatusError("500", request=MagicMock(), response=_make_5xx_response())

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = fake_get
        mock_client_cls.return_value = mock_client

        with pytest.raises(httpx.HTTPStatusError):
            await _get("/test")

    assert call_count == 3, f"Expected 3 attempts, got {call_count}"


@pytest.mark.asyncio
async def test_clickup_get_does_not_retry_on_4xx() -> None:
    """_get does NOT retry on 4xx errors — raises immediately after 1 attempt."""
    from src.tools.clickup import _get

    call_count = 0

    async def fake_get(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise httpx.HTTPStatusError("404", request=MagicMock(), response=_make_4xx_response())

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = fake_get
        mock_client_cls.return_value = mock_client

        with pytest.raises(httpx.HTTPStatusError):
            await _get("/test")

    assert call_count == 1, f"Expected 1 attempt (no retry on 4xx), got {call_count}"


@pytest.mark.asyncio
async def test_clickup_get_retries_on_timeout() -> None:
    """_get retries on timeout exceptions."""
    from src.tools.clickup import _get

    call_count = 0

    async def fake_get(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise httpx.TimeoutException("timeout")

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = fake_get
        mock_client_cls.return_value = mock_client

        with pytest.raises(httpx.TimeoutException):
            await _get("/test")

    assert call_count == 3, f"Expected 3 attempts, got {call_count}"


# ── Scheduler _send_telegram ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_send_telegram_retries_on_5xx() -> None:
    """_send_telegram retries 3 times on 5xx responses."""
    from src.scheduler.jobs import _send_telegram

    call_count = 0

    async def fake_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise httpx.HTTPStatusError("500", request=MagicMock(), response=_make_5xx_response())

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = fake_post
        mock_client_cls.return_value = mock_client

        with pytest.raises(httpx.HTTPStatusError):
            await _send_telegram("123", "hello")

    assert call_count == 3, f"Expected 3 attempts, got {call_count}"


@pytest.mark.asyncio
async def test_send_telegram_does_not_retry_on_4xx() -> None:
    """_send_telegram does NOT retry on 4xx — raises immediately."""
    from src.scheduler.jobs import _send_telegram

    call_count = 0

    async def fake_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise httpx.HTTPStatusError("403", request=MagicMock(), response=_make_4xx_response())

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = fake_post
        mock_client_cls.return_value = mock_client

        with pytest.raises(httpx.HTTPStatusError):
            await _send_telegram("123", "hello")

    assert call_count == 1, f"Expected 1 attempt (no retry on 4xx), got {call_count}"
