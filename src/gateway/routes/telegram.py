"""Telegram webhook route — receives updates from the Telegram Bot API."""

import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel

from src.config import settings
from src.gateway.validators import validate_telegram_secret

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhooks"])


# ── Pydantic models for Telegram Update payload ───────────────────────────────


class TelegramUser(BaseModel):
    """Represents a Telegram user or bot."""

    id: int
    is_bot: bool = False
    first_name: str
    last_name: str | None = None
    username: str | None = None
    language_code: str | None = None


class TelegramChat(BaseModel):
    """Represents a Telegram chat."""

    id: int
    type: str  # private | group | supergroup | channel
    title: str | None = None
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None


class TelegramMessage(BaseModel):
    """Represents a Telegram message."""

    message_id: int
    from_: TelegramUser | None = None
    chat: TelegramChat
    date: int
    text: str | None = None

    model_config = {"populate_by_name": True}

    @classmethod
    def model_validate(cls, obj: Any, **kwargs: Any) -> "TelegramMessage":  # type: ignore[override]
        """Map ``from`` → ``from_`` to avoid the Python keyword conflict."""
        if isinstance(obj, dict) and "from" in obj and "from_" not in obj:
            obj = {**obj, "from_": obj.pop("from")}
        return super().model_validate(obj, **kwargs)


class TelegramUpdate(BaseModel):
    """Top-level Telegram Update object."""

    update_id: int
    message: TelegramMessage | None = None
    edited_message: TelegramMessage | None = None
    # We only handle message for now; other update types are ignored.


# ── Route ─────────────────────────────────────────────────────────────────────


@router.post("/telegram", status_code=status.HTTP_200_OK)
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, str]:
    """Receive and process a Telegram update.

    Validates the secret token header, parses the update, logs the incoming
    message and returns 200 so Telegram stops retrying.

    Args:
        request: Raw FastAPI request (used to read the body).
        x_telegram_bot_api_secret_token: Value from Telegram's secret header.

    Returns:
        Simple acknowledgement dict.
    """
    # ── Validate secret ───────────────────────────────────────────────────────
    if not validate_telegram_secret(
        x_telegram_bot_api_secret_token, settings.telegram_webhook_secret
    ):
        logger.warning("Rejected Telegram update: invalid secret token")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid secret token")

    # ── Parse payload ─────────────────────────────────────────────────────────
    body = await request.json()
    update = TelegramUpdate.model_validate(body)

    message = update.message or update.edited_message
    if message is None:
        logger.debug("Received Telegram update with no message (update_id=%d)", update.update_id)
        return {"status": "ignored"}

    text = message.text or ""
    user_id = str(message.from_.id) if message.from_ else "unknown"
    chat_id = message.chat.id

    logger.info(
        "Telegram update | update_id=%d | user=%s | chat=%d | text=%r",
        update.update_id,
        user_id,
        chat_id,
        text[:100],
    )

    # ── Invoke graph (wired in Etapa 7) ───────────────────────────────────────
    # Placeholder — graph invocation added in Etapa 7.

    return {"status": "ok"}
