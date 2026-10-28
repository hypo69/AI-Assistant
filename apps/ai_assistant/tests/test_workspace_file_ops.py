# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Test AI Assistant Workspace File Operations
# =============================================================================
# Description:
#   Модульные и интеграционные тесты операций с файлами рабочего пространства:
#   - Создание файла и папки с коммитом в Git (Create)
#   - Чтение содержимого файла (Read)
#   - Редактирование и сохранение файла с коммитом (Update)
#   - Удаление файла и каталога с коммитом (Delete)
#   - Проверка защиты от Path Traversal
#   - REST API эндпоинты в router_knowledge
#
# File: test_workspace_file_ops.py
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-26 00:54:00
# =============================================================================

from __future__ import annotations
"""Модульные тесты файловых операций проводника в рабочих областях."""

from pathlib import Path
import pytest
from starlette.testclient import TestClient

from apps.ai_assistant.core.workspace_manager import WorkspaceManager
from apps.ai_assistant.core.workspace_file_ops import WorkspaceFileOps
from apps.ai_assistant.main import app


@pytest.fixture
def workspace_env(tmp_path: Path):
    """Инициализирует тестовую рабочую область с Git."""
    wm = WorkspaceManager(workspaces_dir=tmp_path / "workspaces")
    ws_id = "test_ops_ws"
    wm.ensure_workspace_folder(ws_id)
    return wm, ws_id


def test_create_read_edit_delete_file_lifecycle(workspace_env):
    """Тестирует полный жизненный цикл файла: создание, чтение, правка, удаление."""
    wm, ws_id = workspace_env

    # 1. Создание файла
    create_res = WorkspaceFileOps.create_item(
        wm=wm,
        workspace_id=ws_id,
        rel_path="docs/notes.md",
        is_dir=False,
        content="# Тестовая заметка\nТекст заметки.",
    )
    assert create_res["status"] == "ok"
    assert create_res["rel_path"] == "docs/notes.md"
    assert create_res["is_dir"] is False

    # 2. Чтение содержимого
    read_res = WorkspaceFileOps.get_content(wm=wm, workspace_id=ws_id, rel_path="docs/notes.md")
    assert read_res["status"] == "ok"
    assert "# Тестовая заметка" in read_res["content"]
    assert read_res["is_binary"] is False

    # 3. Редактирование и сохранение с авто-коммитом
    save_res = WorkspaceFileOps.save_content(
        wm=wm,
        workspace_id=ws_id,
        rel_path="docs/notes.md",
        content="# Обновленная заметка\nДобавлены новые строки.",
        commit_message="Обновление docs/notes.md",
    )
    assert save_res["status"] == "ok"

    # Проверяем, что обновленный контент считывается
    read_updated = WorkspaceFileOps.get_content(wm=wm, workspace_id=ws_id, rel_path="docs/notes.md")
    assert "# Обновленная заметка" in read_updated["content"]

    # 4. Удаление файла
    del_res = WorkspaceFileOps.delete_item(wm=wm, workspace_id=ws_id, rel_path="docs/notes.md")
    assert del_res["status"] == "ok"
    assert del_res["deleted"] == "docs/notes.md"

    # Проверяем, что файл больше не существует
    with pytest.raises(FileNotFoundError):
        WorkspaceFileOps.get_content(wm=wm, workspace_id=ws_id, rel_path="docs/notes.md")


def test_create_and_delete_directory(workspace_env):
    """Тестирует создание и удаление директории."""
    wm, ws_id = workspace_env

    dir_res = WorkspaceFileOps.create_item(
        wm=wm,
        workspace_id=ws_id,
        rel_path="subfolder/nested",
        is_dir=True,
    )
    assert dir_res["status"] == "ok"
    assert dir_res["is_dir"] is True

    # Удаление директории
    del_dir = WorkspaceFileOps.delete_item(wm=wm, workspace_id=ws_id, rel_path="subfolder")
    assert del_dir["status"] == "ok"


def test_path_traversal_protection(workspace_env):
    """Проверяет отклонение попыток выхода за пределы рабочей директории."""
    wm, ws_id = workspace_env

    with pytest.raises(ValueError):
        WorkspaceFileOps._normalize_and_resolve(Path("."), "../../secret.txt")

    with pytest.raises(ValueError):
        WorkspaceFileOps.create_item(wm=wm, workspace_id=ws_id, rel_path="../hack.txt")


def test_rest_api_file_ops_endpoints():
    """Проверяет REST API эндпоинты создания, чтения, редактирования и удаления."""
    client = TestClient(app)
    ws_id = "test_rest_ops_ws"

    # Создаём рабочее пространство
    init_res = client.post("/api/v1/workspaces", json={"workspace_id": ws_id, "name": "REST Ops WS"})
    assert init_res.status_code == 200

    # 1. POST /items/create
    post_res = client.post(
        f"/api/v1/workspaces/{ws_id}/items/create",
        json={"rel_path": "api_test.txt", "is_dir": False, "content": "Hello REST API"},
    )
    assert post_res.status_code == 200
    assert post_res.json()["status"] == "ok"

    # 2. GET /file-content
    get_res = client.get(f"/api/v1/workspaces/{ws_id}/file-content?rel_path=api_test.txt")
    assert get_res.status_code == 200
    assert get_res.json()["content"] == "Hello REST API"

    # 3. POST /file-content (Edit/Save)
    edit_res = client.post(
        f"/api/v1/workspaces/{ws_id}/file-content",
        json={"rel_path": "api_test.txt", "content": "Modified REST API text", "commit_message": "Edit via API"},
    )
    assert edit_res.status_code == 200

    # 4. DELETE /items
    del_res = client.delete(f"/api/v1/workspaces/{ws_id}/items?rel_path=api_test.txt")
    assert del_res.status_code == 200
    assert del_res.json()["deleted"] == "api_test.txt"
