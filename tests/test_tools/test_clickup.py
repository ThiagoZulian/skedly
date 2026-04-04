"""Tests for ClickUp tools — httpx fully mocked."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _mock_response(json_data, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


@pytest.mark.asyncio
async def test_list_tasks_empty(monkeypatch):
    monkeypatch.setenv("CLICKUP_DEFAULT_LIST_ID", "list1")
    resp = _mock_response({"tasks": []})
    with patch("src.tools.clickup.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=resp)
        from src.tools.clickup import list_tasks
        result = await list_tasks.ainvoke({})
    assert "Nenhuma tarefa" in result


@pytest.mark.asyncio
async def test_list_tasks_with_items(monkeypatch):
    monkeypatch.setenv("CLICKUP_DEFAULT_LIST_ID", "list1")
    tasks = [{"id": "t1", "name": "Tarefa A", "status": {"status": "open"}, "priority": {"id": 3}, "due_date": None}]
    resp = _mock_response({"tasks": tasks})
    with patch("src.tools.clickup.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=resp)
        from src.tools.clickup import list_tasks
        result = await list_tasks.ainvoke({})
    assert "Tarefa A" in result
    assert "t1" in result


@pytest.mark.asyncio
async def test_create_task(monkeypatch):
    monkeypatch.setenv("CLICKUP_DEFAULT_LIST_ID", "list1")
    resp = _mock_response({"id": "t2", "name": "Nova task", "url": "https://app.clickup.com/t/t2"})
    with patch("src.tools.clickup.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=resp)
        from src.tools.clickup import create_task
        result = await create_task.ainvoke({"name": "Nova task"})
    assert "t2" in result
    assert "criada" in result.lower()


@pytest.mark.asyncio
async def test_create_task_no_list_id():
    import src.config as cfg
    old = cfg._settings
    cfg._settings = None
    import os
    os.environ.pop("CLICKUP_DEFAULT_LIST_ID", None)
    try:
        from src.tools.clickup import create_task
        result = await create_task.ainvoke({"name": "X"})
        assert "não está configurado" in result or "Nenhuma lista" in result
    finally:
        cfg._settings = old


@pytest.mark.asyncio
async def test_update_task():
    resp = _mock_response({"id": "t3", "name": "Task B"})
    with patch("src.tools.clickup.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.put = AsyncMock(return_value=resp)
        from src.tools.clickup import update_task
        result = await update_task.ainvoke({"task_id": "t3", "status": "done"})
    assert "atualizada" in result.lower()


@pytest.mark.asyncio
async def test_get_task_details():
    resp = _mock_response({
        "id": "t4", "name": "Task C", "status": {"status": "open"},
        "priority": {"id": 2}, "assignees": [], "due_date": None,
        "description": "desc", "url": "https://app.clickup.com/t/t4",
    })
    with patch("src.tools.clickup.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=resp)
        from src.tools.clickup import get_task_details
        result = await get_task_details.ainvoke({"task_id": "t4"})
    assert "Task C" in result
