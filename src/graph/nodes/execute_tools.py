"""execute_tools node — runs tool calls requested by the LLM."""

from __future__ import annotations

import logging

from langgraph.prebuilt import ToolNode

from src.tools import ALL_TOOLS

logger = logging.getLogger(__name__)

# ToolNode handles both sync and async tools, error catching, and message formatting.
_tool_node = ToolNode(ALL_TOOLS)


async def execute_tools(state: dict) -> dict:
    """Execute all tool calls present in the last AIMessage.

    Delegates entirely to LangGraph's ToolNode which:
    - Reads tool_calls from the last AIMessage in state["messages"]
    - Runs each tool (async-aware)
    - Appends ToolMessage results to messages

    Args:
        state: Agent state dict (must have ``messages`` with a trailing AIMessage).

    Returns:
        Partial state dict with ToolMessage(s) appended to ``messages``.
    """
    logger.debug("execute_tools: running tool calls")
    result = await _tool_node.ainvoke(state)
    return result
