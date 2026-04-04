"""Telegram webhook route — receives updates from the Telegram Bot API."""

import logging
from typing import Any

import httpx
from fastapi import APIRouter, Header, HTTPException, Request, status
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from src.config import settings
from src.gateway.limiter import limiter
from src.gateway.validators import validate_telegram_secret
from src.graph.builder import build_graph

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhooks"])

# Graph is compiled once and reused across requests.
_graph = build_graph()


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


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _send_telegram_message(chat_id: int, text: str) -> None:
    """Send a text message back to a Telegram chat via the Bot API.

    Args:
        chat_id: Target Telegram chat ID.
        text: Message text (supports Markdown v2 parse mode).
    """
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, json=payload)
        if resp.status_code != 200:
            logger.error(
                "Telegram sendMessage failed: status=%d body=%s",
                resp.status_code,
                resp.text[:200],
            )


# ── Route ─────────────────────────────────────────────────────────────────────


@router.post("/telegram", status_code=status.HTTP_200_OK)
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, str]:
    """Receive and process a Telegram update.

    Flow:
    1. Validate the secret token header.
    2. Parse the Telegram Update payload.
    3. Invoke the LangGraph agent.
    4. Send the agent response back via the Telegram Bot API.

    Args:
        request: Raw FastAPI request.
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

    if not text.strip():
        return {"status": "ignored"}

    # ── Persist chat_id for proactive outbound messages ───────────────────────
    try:
        from src.memory.preferences import set_preference

        await set_preference(user_id, "chat_id", str(chat_id))
    except Exception:
        logger.warning("Failed to persist chat_id for user=%s", user_id)

    # ── Invoke LangGraph agent ────────────────────────────────────────────────
    initial_state = {
        "messages": [HumanMessage(content=text)],
        "intent": "",
        "context": {},
        "response": "",
        "user_id": user_id,
    }

    config = {"configurable": {"thread_id": user_id}}

    try:
        result = await _graph.ainvoke(initial_state, config=config)
        response_text = result.get("response", "Desculpe, não consegui processar sua mensagem.")
    except Exception:
        logger.exception("Graph invocation failed for user=%s", user_id)
        response_text = "Ocorreu um erro interno. Tente novamente em instantes."

    # ── Persist conversation to DB (fire-and-forget) ──────────────────────────
    try:
        from src.memory.conversation import save_conversation

        await save_conversation(user_id, text, response_text)
    except Exception:
        logger.warning("Failed to persist conversation for user=%s", user_id)

    # ── Reply to user ─────────────────────────────────────────────────────────
    await _send_telegram_message(chat_id, response_text)

    return {"status": "ok"}
