"""Google Calendar push notification webhook route."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request, status
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhook", tags=["webhooks"])


@router.post("/calendar", status_code=status.HTTP_200_OK)
async def calendar_webhook(request: Request) -> dict[str, str]:
    """Receive Google Calendar push notifications.

    Google Calendar sends a POST with headers describing the change;
    the body is usually empty. We invoke the agent to refresh context.
    """
    resource_id = request.headers.get("X-Goog-Resource-ID", "unknown")
    resource_state = request.headers.get("X-Goog-Resource-State", "unknown")
    logger.info("Calendar push notification: state=%s resource=%s", resource_state, resource_id)

    # Ignore 'sync' messages (sent when the channel is first created)
    if resource_state == "sync":
        return {"status": "ignored"}

    try:
        from src.gateway.routes.telegram import _graph

        text = "[Evento Calendar] Alteração detectada na agenda"
        state = {
            "messages": [HumanMessage(content=text)],
            "intent": "query_calendar",
            "context": {"calendar_event": resource_state},
            "response": "",
            "user_id": "system",
        }
        config = {"configurable": {"thread_id": "calendar_webhook"}}
        await _graph.ainvoke(state, config=config)
    except Exception:
        logger.exception("Calendar webhook graph invocation failed")

    return {"status": "ok"}
