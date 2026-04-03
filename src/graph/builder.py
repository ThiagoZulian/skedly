"""LangGraph StateGraph builder for the SecretarIA agent."""

import logging

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, StateGraph

from src.graph.edges import route_by_intent
from src.graph.nodes.classify_intent import classify_intent
from src.graph.nodes.format_response import format_response
from src.graph.state import AgentState

logger = logging.getLogger(__name__)


def build_graph(checkpointer: AsyncSqliteSaver | None = None) -> StateGraph:
    """Compile and return the SecretarIA LangGraph.

    Graph topology (Phase 1):
    ::

        START → classify_intent → [route_by_intent] → format_response → END

    Args:
        checkpointer: Optional async SQLite checkpointer for conversation
                      persistence. If None, the graph runs without memory.

    Returns:
        A compiled LangGraph ready to invoke.
    """
    graph = StateGraph(AgentState)

    # ── Nodes ─────────────────────────────────────────────────────────────────
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("format_response", format_response)

    # ── Edges ─────────────────────────────────────────────────────────────────
    graph.set_entry_point("classify_intent")
    graph.add_conditional_edges(
        "classify_intent",
        route_by_intent,
        {
            "format_response": "format_response",
        },
    )
    graph.add_edge("format_response", END)

    # ── Compile ───────────────────────────────────────────────────────────────
    compiled = graph.compile(checkpointer=checkpointer)
    logger.info("SecretarIA graph compiled successfully")
    return compiled
