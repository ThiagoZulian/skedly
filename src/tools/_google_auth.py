"""Google OAuth helper — manages credentials per user or falls back to owner token.json."""

from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/calendar"]
_PROJECT_ROOT = Path(__file__).parents[2]
_CREDENTIALS_PATH = _PROJECT_ROOT / "credentials" / "google_oauth.json"
_TOKEN_PATH = _PROJECT_ROOT / "credentials" / "token.json"

# Set per-request in the Telegram webhook handler and per-job in scheduled tasks.
current_user_id: ContextVar[str | None] = ContextVar("current_user_id", default=None)


async def get_credentials(user_id: str | None = None) -> Credentials:
    """Return valid Google OAuth credentials for the given user.

    Resolution order:
    1. Explicit ``user_id`` argument
    2. ``current_user_id`` ContextVar (set by webhook handler or scheduler job)
    3. Owner fallback — ``credentials/token.json``

    Refreshes expired tokens automatically and persists the updated token to DB.

    Args:
        user_id: Override user ID; useful in scheduled jobs where no request context exists.

    Returns:
        Valid Google OAuth2 Credentials instance.
    """
    import asyncio

    uid = user_id or current_user_id.get()

    if uid:
        token_json = await _load_token_from_db(uid)
        if token_json:
            creds = Credentials.from_authorized_user_info(json.loads(token_json), _SCOPES)
            if not creds.valid:
                if creds.expired and creds.refresh_token:
                    await asyncio.to_thread(creds.refresh, Request())
                    await _save_token_to_db(uid, creds.to_json())
            return creds

    # No DB token found — fall back to file-based owner credentials
    return await asyncio.to_thread(_load_file_credentials)


def build_calendar_service(creds: Credentials):
    """Build a Google Calendar API service (sync, for use inside thread pool)."""
    return build("calendar", "v3", credentials=creds)


def _load_file_credentials() -> Credentials:
    """Load or refresh the single-user file-based credentials (sync)."""
    if not _CREDENTIALS_PATH.exists():
        raise FileNotFoundError(
            f"Google OAuth credentials not found at {_CREDENTIALS_PATH}. "
            "Download them from https://console.cloud.google.com/."
        )

    creds: Credentials | None = None
    if _TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(_TOKEN_PATH), _SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            _TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
        else:
            raise RuntimeError(
                "No valid Google credentials found. "
                "Use /conectar-google in Telegram to authorise."
            )

    return creds


async def _load_token_from_db(user_id: str) -> str | None:
    """Load stored token JSON for a user from the database."""
    try:
        from sqlalchemy import select

        from src.memory.database import get_async_session
        from src.memory.models import UserGoogleToken

        async with get_async_session() as session:
            result = await session.execute(
                select(UserGoogleToken).where(UserGoogleToken.user_id == user_id).limit(1)
            )
            row = result.scalar_one_or_none()
        return row.token_json if row else None
    except Exception:
        logger.exception("_load_token_from_db failed for user=%s", user_id)
        return None


async def _save_token_to_db(user_id: str, token_json: str) -> None:
    """Upsert a Google OAuth token for a user in the database."""
    try:
        from datetime import datetime

        from sqlalchemy import select

        from src.memory.database import get_async_session
        from src.memory.models import UserGoogleToken

        async with get_async_session() as session:
            result = await session.execute(
                select(UserGoogleToken).where(UserGoogleToken.user_id == user_id).limit(1)
            )
            row = result.scalar_one_or_none()
            if row:
                row.token_json = token_json
                row.updated_at = datetime.utcnow()
            else:
                session.add(UserGoogleToken(user_id=user_id, token_json=token_json))
            await session.commit()
    except Exception:
        logger.exception("_save_token_to_db failed for user=%s", user_id)
