"""ClickUp API v2 LangChain tools.

All tools are async and use httpx.AsyncClient.
API reference: https://clickup.com/api/
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from langchain_core.tools import tool
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from src.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.clickup.com/api/v2"
_TIMEOUT = 15.0

# Priority mapping (ClickUp uses 1=urgent, 2=high, 3=normal, 4=low)
_PRIORITY_LABELS = {1: "urgente", 2: "alta", 3: "normal", 4: "baixa"}


# ── Retry policy ─────────────────────────────────────────────────────────────


def _is_retryable(exc: BaseException) -> bool:
    """Return True for transient errors only (5xx and timeouts, not 4xx)."""
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


_retry_policy = retry(
    retry=retry_if_exception(_is_retryable),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)


# ── HTTP helpers ──────────────────────────────────────────────────────────────


def _headers() -> dict[str, str]:
    """Return ClickUp auth headers."""
    return {"Authorization": settings.clickup_api_token, "Content-Type": "application/json"}


@_retry_policy
async def _get(path: str, params: dict | None = None) -> dict[str, Any]:
    """Make an authenticated GET request to the ClickUp API."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(f"{_BASE_URL}{path}", headers=_headers(), params=params)
        resp.raise_for_status()
        return resp.json()


@_retry_policy
async def _post(path: str, body: dict) -> dict[str, Any]:
    """Make an authenticated POST request to the ClickUp API."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(f"{_BASE_URL}{path}", headers=_headers(), json=body)
        resp.raise_for_status()
        return resp.json()


@_retry_policy
async def _put(path: str, body: dict) -> dict[str, Any]:
    """Make an authenticated PUT request to the ClickUp API."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.put(f"{_BASE_URL}{path}", headers=_headers(), json=body)
        resp.raise_for_status()
        return resp.json()


# ── Tools ─────────────────────────────────────────────────────────────────────


@tool
async def list_tasks(list_id: str | None = None, status: str | None = None) -> str:
    """Lista tarefas do ClickUp, com filtragem opcional por lista e/ou status.

    Se ``list_id`` não for informado, usa o ``CLICKUP_DEFAULT_LIST_ID`` do .env.
    Se nenhuma lista estiver configurada, lista tarefas de toda a equipe.

    Args:
        list_id: ID da lista ClickUp (opcional).
        status: Filtra por status, ex: ``"open"``, ``"in progress"``, ``"done"`` (opcional).

    Returns:
        Lista formatada de tarefas com ID, nome, status e prioridade.
    """
    try:
        effective_list_id = list_id or settings.clickup_default_list_id

        if effective_list_id:
            params: dict = {"include_closed": "false"}
            if status:
                params["statuses[]"] = status
            data = await _get(f"/list/{effective_list_id}/task", params)
        else:
            # Fall back to team-level task query
            params = {"include_closed": "false"}
            if status:
                params["statuses[]"] = status
            data = await _get(f"/team/{settings.clickup_team_id}/task", params)

        tasks = data.get("tasks", [])
        if not tasks:
            return "Nenhuma tarefa encontrada."

        lines = []
        for t in tasks:
            priority = _PRIORITY_LABELS.get(
                (t.get("priority") or {}).get("id"), "sem prioridade"
            )
            due = t.get("due_date")
            due_str = f" | vence: {due}" if due else ""
            lines.append(
                f"[{t['id']}] {t['name']} — status: {t['status']['status']} | prioridade: {priority}{due_str}"
            )

        return "\n".join(lines)
    except httpx.HTTPStatusError as exc:
        logger.exception("list_tasks HTTP error")
        return f"Erro HTTP {exc.response.status_code} ao listar tarefas: {exc.response.text[:200]}"
    except Exception as exc:
        logger.exception("list_tasks failed")
        return f"Erro ao listar tarefas: {exc}"


@tool
async def create_task(
    name: str,
    description: str = "",
    list_id: str | None = None,
    due_date: str | None = None,
    priority: int | None = None,
) -> str:
    """Cria uma nova tarefa no ClickUp.

    Args:
        name: Nome da tarefa.
        description: Descrição opcional (suporta Markdown).
        list_id: ID da lista onde criar (usa default se não informado).
        due_date: Data de vencimento no formato ISO 8601 (``YYYY-MM-DD`` ou ``YYYY-MM-DDTHH:MM:SS``).
        priority: Prioridade numérica — 1=urgente, 2=alta, 3=normal, 4=baixa.

    Returns:
        Confirmação com o ID e link da tarefa criada.
    """
    try:
        effective_list_id = list_id or settings.clickup_default_list_id
        if not effective_list_id:
            return (
                "Nenhuma lista informada e CLICKUP_DEFAULT_LIST_ID não está configurado. "
                "Informe o list_id ou configure a variável de ambiente."
            )

        body: dict[str, Any] = {"name": name, "description": description}
        if due_date:
            # ClickUp expects Unix timestamp in milliseconds
            from datetime import datetime

            dt = datetime.fromisoformat(due_date.split("T")[0])
            body["due_date"] = int(dt.timestamp() * 1000)
        if priority is not None:
            body["priority"] = priority

        data = await _post(f"/list/{effective_list_id}/task", body)
        return f"Tarefa criada. ID: {data['id']} — {name} | URL: {data.get('url', 'n/a')}"
    except httpx.HTTPStatusError as exc:
        logger.exception("create_task HTTP error")
        return f"Erro HTTP {exc.response.status_code} ao criar tarefa: {exc.response.text[:200]}"
    except Exception as exc:
        logger.exception("create_task failed")
        return f"Erro ao criar tarefa: {exc}"


@tool
async def update_task(
    task_id: str,
    status: str | None = None,
    priority: int | None = None,
    due_date: str | None = None,
) -> str:
    """Atualiza o status, prioridade e/ou data de vencimento de uma tarefa ClickUp.

    Args:
        task_id: ID da tarefa a atualizar.
        status: Novo status (ex: ``"in progress"``, ``"done"``).
        priority: Nova prioridade — 1=urgente, 2=alta, 3=normal, 4=baixa.
        due_date: Nova data de vencimento no formato ISO 8601.

    Returns:
        Confirmação da atualização.
    """
    try:
        body: dict[str, Any] = {}
        if status:
            body["status"] = status
        if priority is not None:
            body["priority"] = priority
        if due_date:
            from datetime import datetime

            dt = datetime.fromisoformat(due_date.split("T")[0])
            body["due_date"] = int(dt.timestamp() * 1000)

        if not body:
            return "Nenhum campo para atualizar foi informado."

        data = await _put(f"/task/{task_id}", body)
        return f"Tarefa {task_id} atualizada com sucesso. Nome: {data.get('name', '?')}"
    except httpx.HTTPStatusError as exc:
        logger.exception("update_task HTTP error")
        if exc.response.status_code == 404:
            return f"Tarefa {task_id} não encontrada."
        return f"Erro HTTP {exc.response.status_code}: {exc.response.text[:200]}"
    except Exception as exc:
        logger.exception("update_task failed")
        return f"Erro ao atualizar tarefa {task_id}: {exc}"


@tool
async def get_task_details(task_id: str) -> str:
    """Retorna os detalhes completos de uma tarefa ClickUp.

    Args:
        task_id: ID da tarefa.

    Returns:
        Detalhes formatados: nome, descrição, status, prioridade, assignees e datas.
    """
    try:
        data = await _get(f"/task/{task_id}")
        priority = _PRIORITY_LABELS.get(
            (data.get("priority") or {}).get("id"), "sem prioridade"
        )
        assignees = ", ".join(a.get("username", "?") for a in data.get("assignees", [])) or "nenhum"
        due = data.get("due_date") or "não definida"
        desc = (data.get("description") or "").strip()[:300]

        return (
            f"**{data['name']}** (ID: {data['id']})\n"
            f"Status: {data['status']['status']}\n"
            f"Prioridade: {priority}\n"
            f"Responsáveis: {assignees}\n"
            f"Vencimento: {due}\n"
            f"Descrição: {desc or '(vazia)'}\n"
            f"URL: {data.get('url', 'n/a')}"
        )
    except httpx.HTTPStatusError as exc:
        logger.exception("get_task_details HTTP error")
        if exc.response.status_code == 404:
            return f"Tarefa {task_id} não encontrada."
        return f"Erro HTTP {exc.response.status_code}: {exc.response.text[:200]}"
    except Exception as exc:
        logger.exception("get_task_details failed")
        return f"Erro ao buscar tarefa {task_id}: {exc}"


# ── Tool list (exported for agent binding) ─────────────────────────────────────

CLICKUP_TOOLS = [list_tasks, create_task, update_task, get_task_details]
