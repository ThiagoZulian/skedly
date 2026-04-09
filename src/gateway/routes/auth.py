"""Google OAuth web flow — /auth/google (start) and /auth/google/callback routes."""

from __future__ import annotations

import asyncio
import logging
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from google_auth_oauthlib.flow import Flow

from src.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

_SCOPES = ["https://www.googleapis.com/auth/calendar"]
_CREDENTIALS_PATH = Path(__file__).parents[3] / "credentials" / "google_oauth.json"


def _redirect_uri() -> str:
    return f"{settings.app_base_url}/auth/google/callback"


async def create_oauth_state(user_id: str) -> str:
    """Generate a short-lived state token and persist it mapped to user_id."""
    from sqlalchemy import delete

    from src.memory.database import get_async_session
    from src.memory.models import OAuthState

    state = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + timedelta(minutes=10)

    async with get_async_session() as session:
        await session.execute(
            delete(OAuthState).where(OAuthState.expires_at < datetime.now(UTC))
        )
        session.add(OAuthState(state=state, user_id=user_id, expires_at=expires_at))
        await session.commit()

    return state


async def _consume_state(state: str) -> str | None:
    """Return user_id for a valid state and delete it; None if invalid/expired."""
    from sqlalchemy import delete, select

    from src.memory.database import get_async_session
    from src.memory.models import OAuthState

    try:
        async with get_async_session() as session:
            result = await session.execute(
                select(OAuthState)
                .where(OAuthState.state == state, OAuthState.expires_at >= datetime.now(UTC))
                .limit(1)
            )
            row = result.scalar_one_or_none()
            if not row:
                return None
            user_id = row.user_id
            await session.execute(delete(OAuthState).where(OAuthState.state == state))
            await session.commit()
        return user_id
    except Exception:
        logger.exception("_consume_state failed")
        return None


@router.get("/google")
async def start_google_oauth(state: str) -> RedirectResponse:
    """Validate state and redirect to Google's consent screen."""
    from sqlalchemy import select

    from src.memory.database import get_async_session
    from src.memory.models import OAuthState

    async with get_async_session() as session:
        result = await session.execute(
            select(OAuthState)
            .where(OAuthState.state == state, OAuthState.expires_at >= datetime.now(UTC))
            .limit(1)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(400, "Link inválido ou expirado. Use /conectar-google novamente.")

    flow = Flow.from_client_secrets_file(str(_CREDENTIALS_PATH), scopes=_SCOPES, redirect_uri=_redirect_uri())
    auth_url, _ = flow.authorization_url(access_type="offline", state=state, prompt="consent")
    return RedirectResponse(auth_url)


@router.get("/google/callback")
async def google_oauth_callback(code: str, state: str) -> HTMLResponse:
    """Exchange code for tokens, persist, and notify the user via Telegram."""
    user_id = await _consume_state(state)
    if not user_id:
        raise HTTPException(400, "Estado OAuth inválido ou expirado.")

    flow = Flow.from_client_secrets_file(str(_CREDENTIALS_PATH), scopes=_SCOPES, redirect_uri=_redirect_uri())
    await asyncio.to_thread(flow.fetch_token, code=code)

    from src.tools._google_auth import _save_token_to_db
    await _save_token_to_db(user_id, flow.credentials.to_json())
    logger.info("Google OAuth completed for user_id=%s", user_id)

    try:
        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(url, json={"chat_id": user_id, "text": "✅ Google Calendar conectado! Já posso ver sua agenda."})
    except Exception:
        logger.exception("Failed to notify user_id=%s after OAuth", user_id)

    return HTMLResponse("""<html><head><meta charset="utf-8"><title>Skedly</title></head>
<body style="font-family:sans-serif;text-align:center;padding:60px">
<h1>✅ Google Calendar conectado!</h1><p>Pode fechar esta aba e voltar ao Telegram.</p>
</body></html>""")
