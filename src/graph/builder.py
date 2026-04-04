"""LangGraph StateGraph builder for the SecretarIA agent."""

from __future__ import annotations

import logging

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, StateGraph

from src.graph.edges import route_after_plan, route_by_intent
from src.graph.nodes.classify_intent import classify_intent
from src.graph.nodes.execute_tools import execute_tools
from src.graph.nodes.format_response import format_response
from src.graph.nodes.gather_context import gather_context
from src.graph.nodes.plan_action import plan_action
from src.graph.state import AgentState

logger = logging.getLogger(__name__)


def build_graph(checkpointer: AsyncSqliteSaver | None = None):
    """Compile and return the SecretarIA LangGraph.

    Graph topology (Phase 2)::

        START → classify_intent
                  ├─[general_chat]──────────────────────────→ format_response → END
                  └─[others]──→ gather_context → plan_action
                                                    ├─[tool_calls]──→ execute_tools ──┐
                                                    └─[done]──→ format_response → END  │
                                                         ↑____________________________┘

    Args:
        checkpointer: Optional async SQLite checkpointer for conversation persistence.

    Returns:
        A compiled LangGraph ready to invoke.
    """
    graph = StateGraph(AgentState)

    graph.add_node("classify_intent", classify_intent)
    graph.add_node("gather_context", gather_context)
    graph.add_node("plan_action", plan_action)
    graph.add_node("execute_tools", execute_tools)
    graph.add_node("format_response", format_response)

    graph.set_entry_point("classify_intent")

    graph.add_conditional_edges(
        "classify_intent",
        route_by_intent,
        {"gather_context": "gather_context", "format_response": "format_response"},
    )
    graph.add_edge("gather_context", "plan_action")
    graph.add_conditional_edges(
        "plan_action",
        route_after_plan,
        {"execute_tools": "execute_tools", "format_response": "format_response"},
    )
    # After tools run, always go back to plan_action so LLM sees results
    graph.add_edge("execute_tools", "plan_action")
    graph.add_edge("format_response", END)

    compiled = graph.compile(checkpointer=checkpointer)
    logger.info("SecretarIA graph compiled successfully")
    return compiled
