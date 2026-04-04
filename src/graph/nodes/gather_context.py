"""gather_context node — pre-fetches relevant data before plan_action."""

from __future__ import annotations

import logging

from src.graph.state import AgentState
from src.tools.datetime_utils import get_current_datetime

logger = logging.getLogger(__name__)

# Intents that need calendar data
_CALENDAR_INTENTS = {"schedule_event", "query_calendar", "reorganize", "daily_briefing"}
# Intents that need task data
_TASK_INTENTS = {"create_task", "query_tasks", "reorganize", "daily_briefing"}


async def gather_context(state: AgentState) -> dict:
    """Collect relevant data (events, tasks, datetime) based on intent.

    Calls tools directly (not via LLM) to pre-populate ``state["context"]``
    so that ``plan_action`` has everything it needs without extra round-trips.

    Args:
        state: Current agent state with ``intent`` set.

    Returns:
        Partial state dict with ``context`` populated.
    """
    intent = state.get("intent", "general_chat")
    context: dict = state.get("context", {}).copy()

    # Always include current datetime
    context["current_datetime"] = get_current_datetime.invoke({})

    if intent in _CALENDAR_INTENTS:
        try:
            from src.tools.calendar import list_events
            context["events"] = await list_events.ainvoke({"days_ahead": 7})
        except Exception as exc:
            logger.warning("gather_context: list_events failed: %s", exc)
            context["events"] = f"(Erro ao buscar eventos: {exc})"

    if intent in _TASK_INTENTS:
        try:
            from src.tools.clickup import list_tasks
            context["tasks"] = await list_tasks.ainvoke({})
        except Exception as exc:
            logger.warning("gather_context: list_tasks failed: %s", exc)
            context["tasks"] = f"(Erro ao buscar tarefas: {exc})"

    if intent == "set_reminder":
        try:
            from src.tools.reminders import list_reminders
            user_id = state.get("user_id", "")
            context["existing_reminders"] = await list_reminders.ainvoke({"user_id": user_id})
        except Exception as exc:
            logger.warning("gather_context: list_reminders failed: %s", exc)

    logger.info("gather_context done for intent=%s keys=%s", intent, list(context.keys()))
    return {"context": context}
