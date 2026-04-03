"""Conditional edge functions for the SecretarIA LangGraph."""

import logging

from src.graph.state import AgentState

logger = logging.getLogger(__name__)


def route_by_intent(state: AgentState) -> str:
    """Route to the next node based on the classified intent.

    In Phase 1 all intents route directly to ``format_response``.
    Later phases will add routing to ``gather_context`` and ``plan_action``
    for intents that require tool use.

    Args:
        state: Current agent state with ``intent`` populated.

    Returns:
        Name of the next node to execute.
    """
    intent = state.get("intent", "general_chat")
    logger.debug("Routing intent=%s → format_response", intent)
    # Phase 1: all intents go straight to format_response.
    return "format_response"
