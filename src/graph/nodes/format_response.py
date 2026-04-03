"""format_response node — shapes the final message sent back to the user."""

import logging

from src.graph.state import AgentState

logger = logging.getLogger(__name__)

# Human-readable labels for each intent, used in placeholder responses.
_INTENT_LABELS: dict[str, str] = {
    "schedule_event": "agendar um evento",
    "query_calendar": "consultar o calendário",
    "create_task": "criar uma tarefa",
    "query_tasks": "listar tarefas",
    "set_reminder": "definir um lembrete",
    "reorganize": "reorganizar a agenda",
    "daily_briefing": "ver o briefing diário",
    "general_chat": "conversar",
}


async def format_response(state: AgentState) -> dict:
    """Format the final response to be sent to the user via Telegram.

    In Phase 1 this node produces a confirmation message that echoes the
    classified intent. Later phases will replace this with a full LLM-generated
    response incorporating tool results.

    Args:
        state: Current agent state (must have ``intent`` populated).

    Returns:
        Partial state dict with ``response`` set.
    """
    intent = state.get("intent", "general_chat")
    label = _INTENT_LABELS.get(intent, intent)

    response = (
        f"Entendido! Identifico que você quer *{label}*.\n\n"
        f"_(Intent: `{intent}` — funcionalidade completa em breve!)_"
    )

    logger.info("Formatted response for intent=%s", intent)
    return {"response": response}
