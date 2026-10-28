# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Test AI Assistant Workspace Git History & Panel Routing
# =============================================================================
# Description:
#   Модульные тесты для проверки изоляции истории Git рабочих пространств:
#   - Разрешение пути репозитория (repo_resolver) по workspace_id и по умолчанию.
#   - Передача workspace_id и repo_path в эндпоинты панелей (/v1/panel/{panel_id}).
#   - Передача workspace_id в эндпоинты истории файлов (/api/v1/history, diff).
#   - API эндпоинты сохранения и получения активного пространства (/api/v1/workspaces/active).
#   - API эндпоинты глобальной установки активного репозитория (/api/v1/git/maintenance/active-repo).
#   - Поддержка событий смены пространства и getActiveWorkspaceId на фронтенде.
#
# File: test_workspace_git_history.py
# Package: apps/ai_assistant/tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 19:05:00
# =============================================================================

from __future__ import annotations
"""Модульные тесты интеграции Git-истории с изолированными рабочими пространствами."""

from pathlib import Path
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.ai_assistant.core.repo_resolver import resolve_repo_path
from apps.ai_assistant.api.routers.router_panel import router as panel_router
from apps.ai_assistant.api.routers.router_file_history import router as file_history_router
from apps.ai_assistant.api.routers.router_knowledge import router as knowledge_router
from apps.ai_assistant.api.routers.router_git_maintenance import router as git_maintenance_router
from apps.ai_assistant.core.workspace_manager import WorkspaceManager


_WEBGUI_DIR = Path(__file__).resolve().parent.parent / "api" / "webgui"


def test_repo_resolver_fallback_and_custom_path(tmp_path: Path) -> None:
    """Проверяет корректное разрешение путей по умолчанию и явных путей."""
    # 1. По умолчанию возвращает текущий репозиторий проекта или активной области
    resolved_default = resolve_repo_path()
    assert resolved_default.exists()

    # 2. Прямой существующий путь возвращается без изменений
    custom_dir = tmp_path / "custom_repo"
    custom_dir.mkdir()
    resolved_custom = resolve_repo_path(repo_path=str(custom_dir))
    assert resolved_custom == custom_dir.resolve()

    # 3. Служебные идентификаторы (main, root) возвращают корень проекта
    assert resolve_repo_path(workspace_id="main") == Path(".").resolve()
    assert resolve_repo_path(workspace_id="root") == Path(".").resolve()


def test_active_workspace_endpoints_and_persistence() -> None:
    """Проверяет эндпоинты GET и POST /api/v1/workspaces/active и флаг is_active."""
    app = FastAPI()
    app.include_router(knowledge_router)
    client = TestClient(app)

    # 1. Убеждаемся, что есть хотя бы одна рабочая область
    wm = WorkspaceManager()
    workspaces = wm.list_workspaces()
    if not workspaces:
        wm.seed_demo_workspace("test_demo_ws")
        workspaces = wm.list_workspaces()
    target_ws = workspaces[0]["workspace_id"]

    # 2. Фиксируем целевую область как активную через POST API
    post_res = client.post("/api/v1/workspaces/active", json={"workspace_id": target_ws})
    assert post_res.status_code == 200
    post_data = post_res.json()
    assert post_data["status"] == "ok"
    assert post_data["workspace_id"] == target_ws

    # 3. Запрашиваем текущее активное пространство через GET API
    get_res = client.get("/api/v1/workspaces/active")
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert get_data["status"] == "ok"
    assert get_data["workspace_id"] == target_ws

    # 4. Проверяем флаг is_active в списке всех областей
    list_res = client.get("/api/v1/workspaces")
    assert list_res.status_code == 200
    list_data = list_res.json()
    ws_item = next((w for w in list_data["workspaces"] if w["workspace_id"] == target_ws), None)
    assert ws_item is not None
    assert ws_item.get("is_active") is True


def test_git_maintenance_active_repo_endpoints(tmp_path: Path) -> None:
    """Проверяет эндпоинты GET и POST /api/v1/git/maintenance/active-repo."""
    app = FastAPI()
    app.include_router(git_maintenance_router)
    client = TestClient(app)

    # 1. Запрос текущего активного репозитория
    get_res = client.get("/api/v1/git/maintenance/active-repo")
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert get_data["status"] == "ok"
    assert "repo_path" in get_data
    assert "repo_name" in get_data

    # 2. Глобальная установка активного репозитория
    test_repo = tmp_path / "test_active_git"
    test_repo.mkdir()
    post_res = client.post(
        "/api/v1/git/maintenance/active-repo",
        json={"repo_path": str(test_repo), "workspace_id": "test_active_ws"},
    )
    assert post_res.status_code == 200
    post_data = post_res.json()
    assert post_data["status"] == "ok"
    assert post_data["workspace_id"] == "test_active_ws"

    # 3. Повторная проверка через GET
    get_res2 = client.get("/api/v1/git/maintenance/active-repo")
    assert get_res2.status_code == 200
    assert get_res2.json()["workspace_id"] == "test_active_ws"


def test_panel_router_workspace_id_integration(tmp_path: Path) -> None:
    """Проверяет эндпоинт GET /v1/panel/panel-commits с передачей workspace_id."""
    app = FastAPI()
    app.include_router(panel_router)
    client = TestClient(app)

    # Запрос данных панели с фиктивным workspace_id
    response = client.get("/v1/panel/panel-commits?limit=5&workspace_id=demo")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ok"
    assert data["panel_id"] == "panel-commits"
    assert data["workspace_id"] == "demo"
    assert "repo_path" in data
    assert isinstance(data["data"], list)


def test_file_history_router_workspace_id_support(tmp_path: Path) -> None:
    """Проверяет поддержку параметра workspace_id в эндпоинтах истории Git."""
    app = FastAPI()
    app.include_router(file_history_router)
    client = TestClient(app)

    response = client.get("/api/v1/history?limit=5&workspace_id=demo")
    assert response.status_code == 200
    commits = response.json()
    assert isinstance(commits, list)


def test_frontend_workspace_synchronization_scripts() -> None:
    """Проверяет наличие функций и обработчиков синхронизации на фронтенде."""
    # 1. Проверяем top_workspace_dropdown.js
    top_dropdown_js = _WEBGUI_DIR / "js" / "top_workspace_dropdown.js"
    assert top_dropdown_js.exists()
    top_code = top_dropdown_js.read_text(encoding="utf-8")
    assert "export function getActiveWorkspaceId()" in top_code
    assert "export function getActiveRepoPath()" in top_code
    assert "export async function setGlobalActiveRepo" in top_code
    assert "top-select-git-repo" in top_code
    assert "workspace:changed" in top_code
    assert "repo:changed" in top_code

    # 2. Проверяем index.html на наличие селектора в Command Center и отсутствие устаревшего контейнера
    index_html = _WEBGUI_DIR / "index.html"
    index_code = index_html.read_text(encoding="utf-8")
    assert 'id="ide-command-center"' in index_code
    assert 'id="top-workspace-control-container"' not in index_code

    # 3. Проверяем panel-loader.js
    panel_loader_js = _WEBGUI_DIR / "js" / "panel-loader.js"
    assert panel_loader_js.exists()
    loader_code = panel_loader_js.read_text(encoding="utf-8")
    assert "getActiveWorkspaceId" in loader_code
    assert "workspace_id=" in loader_code
    assert "repo_path=" in loader_code
    assert "workspace:changed" in loader_code
    assert "repo:changed" in loader_code

    # 4. Проверяем вкладки истории на обработку repo:changed
    commits_panel_js = _WEBGUI_DIR / "tab_commits" / "panel_commits" / "panel.js"
    assert "repo:changed" in commits_panel_js.read_text(encoding="utf-8")

    timeline_panel_js = _WEBGUI_DIR / "tab_timeline" / "panel_timeline" / "panel.js"
    assert "repo:changed" in timeline_panel_js.read_text(encoding="utf-8")

    diff_panel_js = _WEBGUI_DIR / "tab_diff" / "panel_diff_stats" / "panel.js"
    diff_code = diff_panel_js.read_text(encoding="utf-8")
    assert "repo:changed" in diff_code
    assert "workspace_id=" in diff_code
