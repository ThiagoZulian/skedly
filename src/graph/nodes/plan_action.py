"""plan_action node — LLM decides what to do using the available tools."""

from __future__ import annotations

import logging
from pathlib import Path

from langchain_core.messages import SystemMessage

from src.graph.state import AgentState
from src.llm.router import get_model_for_intent
from src.tools import ALL_TOOLS

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT_PATH = Path(__file__).parents[3] / "prompts" / "system.md"
_PLAN_PROMPT_PATH = Path(__file__).parents[3] / "prompts" / "plan_action.md"


def _build_system_message(intent: str, context: dict) -> SystemMessage:
    """Combine system + plan_action prompts and inject pre-fetched context."""
    system = _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    plan = _PLAN_PROMPT_PATH.read_text(encoding="utf-8")
    combined = f"{system}\n\n{plan}"

    if context:
        ctx_lines = "\n".join(f"- **{k}**: {v}" for k, v in context.items())
        combined += f"\n\n## Contexto atual\n{ctx_lines}"

    return SystemMessage(content=combined)


async def plan_action(state: AgentState) -> dict:
    """Invoke the LLM (with tools bound) to plan and execute the user's request.

    The LLM sees the full message history plus pre-fetched context.
    It may call one or more tools (producing tool_calls in the AIMessage)
    or return a final text response.

    Args:
        state: Agent state with ``intent``, ``context``, and ``messages``.

    Returns:
        Partial state dict with the new AIMessage appended to ``messages``.
    """
    intent = state.get("intent", "general_chat")
    context = state.get("context", {})
    messages = list(state["messages"])

    # Limit context window to the last 20 messages (~10 turns) to avoid
    # unbounded token growth across long sessions.
    _MAX_MESSAGES = 20
    if len(messages) > _MAX_MESSAGES:
        messages = messages[-_MAX_MESSAGES:]

    # Pass routing hints so the router can escalate when needed
    last_text = messages[-1].content if messages else ""
    message_length = len(str(last_text))
    has_history = bool(context.get("recent_history"))

    llm = get_model_for_intent(intent, message_length=message_length, has_history=has_history)
    llm_with_tools = llm.bind_tools(ALL_TOOLS)

    system_msg = _build_system_message(intent, context)
    full_messages = [system_msg, *messages]

    try:
        response = await llm_with_tools.ainvoke(full_messages)
    except Exception:
        logger.exception("plan_action LLM call failed")
        from langchain_core.messages import AIMessage
        response = AIMessage(content="Desculpe, ocorreu um erro ao processar sua solicitação.")

    logger.info(
        "plan_action: intent=%s has_tool_calls=%s",
        intent,
        bool(getattr(response, "tool_calls", None)),
    )
    return {"messages": [response]}
