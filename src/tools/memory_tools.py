"""LangChain tools for reading and writing user preferences from the agent."""

from __future__ import annotations

import logging

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
async def get_user_preference(user_id: str, key: str) -> str:
    """Retrieve a stored user preference by key.

    Use this when you need to recall something the user told you previously,
    such as their name, timezone, or working hours.

    Args:
        user_id: The Telegram user ID.
        key: The preference key to look up (e.g. 'name', 'timezone', 'working_hours').

    Returns:
        The stored value, or an empty string if not found.
    """
    from src.memory.preferences import get_preference

    value = await get_preference(user_id, key)
    if value:
        return f"Preferência '{key}' do usuário {user_id}: {value}"
    return f"Nenhuma preferência '{key}' encontrada para o usuário {user_id}."


@tool
async def set_user_preference(user_id: str, key: str, value: str) -> str:
    """Store or update a user preference.

    Use this when the user tells you something personal that should be remembered
    for future conversations, such as their name, preferred timezone, or routine.

    Args:
        user_id: The Telegram user ID.
        key: The preference key (e.g. 'name', 'timezone', 'working_hours').
        value: The value to store.

    Returns:
        Confirmation message.
    """
    from src.memory.preferences import set_preference

    await set_preference(user_id, key, value)
    return f"Preferência '{key}' salva com sucesso para o usuário {user_id}."


@tool
async def get_conversation_history(user_id: str, limit: int = 3) -> str:
    """Retrieve the recent conversation history for a user.

    Use this to recall what was discussed in previous sessions when the user
    references a past conversation or asks 'what did we talk about before?'.

    Args:
        user_id: The Telegram user ID.
        limit: Number of recent exchanges to retrieve (default 3, max 10).

    Returns:
        Formatted string of recent exchanges, or a message if no history exists.
    """
    from src.memory.conversation import get_recent_conversations

    exchanges = await get_recent_conversations(user_id, limit=min(limit, 10))
    if not exchanges:
        return "Nenhum histórico de conversa encontrado."

    lines = []
    for i, ex in enumerate(exchanges, 1):
        ts = ex.get("ts", "")[:16].replace("T", " ")
        lines.append(f"[{i}] ({ts})\n  Você: {ex['human']}\n  IA: {ex['ai']}")
    return "\n\n".join(lines)


MEMORY_TOOLS = [get_user_preference, set_user_preference, get_conversation_history]
