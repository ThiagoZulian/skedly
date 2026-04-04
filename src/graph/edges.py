"""Conditional edge functions for the SecretarIA LangGraph."""

from __future__ import annotations

import logging

from langchain_core.messages import AIMessage

from src.graph.state import AgentState

logger = logging.getLogger(__name__)

_CHAT_ONLY_INTENTS = {"general_chat"}


def route_by_intent(state: AgentState) -> str:
    """Route after classify_intent: chat goes straight to format_response, others to gather_context."""
    intent = state.get("intent", "general_chat")
    if intent in _CHAT_ONLY_INTENTS:
        logger.debug("route_by_intent: %s → format_response", intent)
        return "format_response"
    logger.debug("route_by_intent: %s → gather_context", intent)
    return "gather_context"


def route_after_plan(state: AgentState) -> str:
    """Route after plan_action: if LLM issued tool_calls go to execute_tools, else format_response."""
    messages = state.get("messages", [])
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            if getattr(msg, "tool_calls", None):
                logger.debug("route_after_plan → execute_tools")
                return "execute_tools"
            break
    logger.debug("route_after_plan → format_response")
    return "format_response"
