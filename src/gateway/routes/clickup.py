"""ClickUp webhook route — receives task events from ClickUp."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException, Request, status
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from src.config import settings
from src.gateway.validators import validate_clickup_signature

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhook", tags=["webhooks"])


class ClickUpWebhookPayload(BaseModel):
    """ClickUp webhook payload envelope."""

    webhook_id: str | None = None
    event: str
    history_items: list[dict] | None = None
    task_id: str | None = None


# Map ClickUp event names to human-readable descriptions for the agent
_EVENT_DESCRIPTIONS = {
    "taskCreated": "Nova tarefa criada",
    "taskUpdated": "Tarefa atualizada",
    "taskDeleted": "Tarefa deletada",
    "taskStatusUpdated": "Status da tarefa alterado",
    "taskDueDateUpdated": "Data de vencimento da tarefa alterada",
}


@router.post("/clickup", status_code=status.HTTP_200_OK)
async def clickup_webhook(
    request: Request,
    x_signature: str | None = Header(default=None),
) -> dict[str, str]:
    """Receive and process a ClickUp webhook event.

    Validates HMAC signature, parses the event and invokes the LangGraph agent
    so it can proactively notify the user of relevant task changes.

    Args:
        request: Raw FastAPI request.
        x_signature: HMAC-SHA256 signature from the ``X-Signature`` header.
    """
    raw_body = await request.body()

    if settings.clickup_webhook_secret and (
        not x_signature
        or not validate_clickup_signature(raw_body, x_signature, settings.clickup_webhook_secret)
    ):
        logger.warning("Rejected ClickUp webhook: invalid signature")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature")

    body = await request.json()
    payload = ClickUpWebhookPayload.model_validate(body)

    event_desc = _EVENT_DESCRIPTIONS.get(payload.event, payload.event)
    task_id = payload.task_id or "desconhecida"
    logger.info("ClickUp event: %s | task_id=%s", payload.event, task_id)

    # Build a synthetic message and invoke the agent
    text = f"[Evento ClickUp] {event_desc} (task_id: {task_id})"

    try:
        from src.gateway.routes.telegram import _graph

        initial_state = {
            "messages": [HumanMessage(content=text)],
            "intent": "query_tasks",
            "context": {"clickup_event": payload.event, "task_id": task_id},
            "response": "",
            "user_id": "system",
        }
        config = {"configurable": {"thread_id": "clickup_webhook"}}
        await _graph.ainvoke(initial_state, config=config)
    except Exception:
        logger.exception("ClickUp webhook graph invocation failed")

    return {"status": "ok"}
