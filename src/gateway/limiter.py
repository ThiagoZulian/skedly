"""Shared SlowAPI limiter instance for rate limiting."""

from __future__ import annotations

import json
import logging

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)


async def _chat_id_key(request: Request) -> str:
    """Extract chat_id from Telegram update body for per-chat rate limiting.

    Falls back to the remote IP address if the body cannot be parsed.
    """
    try:
        body = await request.body()
        data = json.loads(body)
        message = data.get("message") or data.get("edited_message")
        if message and "chat" in message:
            return f"chat:{message['chat']['id']}"
    except Exception:
        pass
    return get_remote_address(request)


limiter = Limiter(key_func=_chat_id_key)
