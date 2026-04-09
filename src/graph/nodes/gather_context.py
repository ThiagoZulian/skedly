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
    """Collect relevant data (events, tasks, datetime, history, preferences) based on intent.

    Calls tools directly (not via LLM) to pre-populate ``state["context"]``
    so that ``plan_action`` has everything it needs without extra round-trips.

    Args:
        state: Current agent state with ``intent`` and ``user_id`` set.

    Returns:
        Partial state dict with ``context`` populated.
    """
    intent = state.get("intent", "general_chat")
    user_id = state.get("user_id", "")
    context: dict = state.get("context", {}).copy()

    # Always include current datetime
    context["current_datetime"] = get_current_datetime.invoke({})

    # ── User preferences ──────────────────────────────────────────────────────
    if user_id:
        try:
            from src.memory.preferences import get_all_preferences

            prefs = await get_all_preferences(user_id)
            if prefs:
                context["user_preferences"] = prefs
        except Exception as exc:
            logger.warning("gather_context: get_all_preferences failed: %s", exc)

    # ── Recent conversation history ───────────────────────────────────────────
    if user_id:
        try:
            from src.memory.conversation import get_recent_conversations

            history = await get_recent_conversations(user_id, limit=3)
            if history:
                context["recent_history"] = history
        except Exception as exc:
            logger.warning("gather_context: get_recent_conversations failed: %s", exc)

    # ── Calendar events ───────────────────────────────────────────────────────
    if intent in _CALENDAR_INTENTS:
        try:
            from src.tools.calendar import list_events

            cal_filter = context.get("user_preferences", {}).get("calendar_filter", "all")
            context["events"] = await list_events.ainvoke({"days_ahead": 7, "calendar_id": cal_filter})
        except Exception as exc:
            logger.warning("gather_context: list_events failed: %s", exc)
            context["events"] = f"(Erro ao buscar eventos: {exc})"

    # ── ClickUp tasks ─────────────────────────────────────────────────────────
    if intent in _TASK_INTENTS:
        try:
            from src.tools.clickup import list_tasks

            context["tasks"] = await list_tasks.ainvoke({})
        except Exception as exc:
            logger.warning("gather_context: list_tasks failed: %s", exc)
            context["tasks"] = f"(Erro ao buscar tarefas: {exc})"

    # ── Existing reminders (for set_reminder context) ─────────────────────────
    if intent == "set_reminder":
        try:
            from src.tools.reminders import list_reminders

            context["existing_reminders"] = await list_reminders.ainvoke({"user_id": user_id})
        except Exception as exc:
            logger.warning("gather_context: list_reminders failed: %s", exc)

    logger.info("gather_context done for intent=%s keys=%s", intent, list(context.keys()))
    return {"context": context}
