"""LangGraph agent state definition."""

from typing import Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """Shared state object passed between all nodes in the LangGraph.

    Attributes:
        messages: Conversation history (accumulated via ``add_messages`` reducer).
        intent: Classified intent category (e.g. ``"schedule_event"``).
        context: Arbitrary context collected by ``gather_context`` (calendar,
                 tasks, current datetime, etc.).
        response: Final formatted response string to be sent to the user.
        user_id: Telegram user ID (string) of the message sender.
    """

    messages: Annotated[list[BaseMessage], add_messages]
    intent: str
    context: dict
    response: str
    user_id: str
