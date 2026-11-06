# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Tests - IDE Navigation & Electron Shell
# =============================================================================
# Description:
#   TDD-тесты для стандартной IDE панели навигации (Activity Bar), навигатора
#   по файлам (File Explorer в стиле VS Code), верхнего раскрывающегося окна
#   выбора рабочего пространства (Command Center Workspace Picker)
#   и интеграции с десктопной оболочкой Electron.
#
#   Проверяет:
#   1. Наличие вертикального Activity Bar в главном шаблоне index.html с ключевыми
#      инструментами IDE (Explorer, Git Commits, Diff, Timeline, WikiLLM, Graph,
#      Models, Search RAG, Verification, Extensions, Mail).
#   2. Наличие стандартного навигатора по файлам (#ide-file-navigator) слева с
#      интерактивным деревом файлов/папок и кнопками управления.
#   3. Наличие верхнего раскрывающегося окна выбора рабочего пространства
#      (#ide-command-center, #ide-workspace-picker-btn, #ideWorkspacePickerModal).
#   4. Наличие статических стилей IDE навигации в nav.css и скрипта ide_file_explorer.js.
#   5. Контракт Electron оболочки: сканирование папок с .git (scanGitWorkspaces),
#      IPC-мост (workspaces:list-git, workspaces:set-active) и нативное меню.
#   6. Доступность REST API /api/v1/workspaces/{id}/directory-contents.
#
# File: test_ide_navigation.py
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-06 23:14:00
# =============================================================================

from __future__ import annotations
"""Тестирование интерфейса IDE на базе VS Code (File Explorer & Command Center Workspace Picker)."""

from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient
from apps.ai_assistant.main import app


@pytest.mark.asyncio
async def test_ide_activity_bar_and_file_explorer_in_index() -> None:
    """Проверяет наличие Activity Bar, навигатора по файлам и Command Center в разметке index.html."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/")
        assert res.status_code == 200
        html = res.text

        # 1. Проверяем контейнер Activity Bar
        assert 'id="ide-activity-bar"' in html
        assert 'class="ide-activity-bar' in html

        # 2. Проверяем основные кнопки IDE инструментов
        assert 'id="ide-nav-workspace"' in html
        assert 'data-tab="tab-workspace"' in html
        assert 'id="ide-nav-commits"' in html
        assert 'id="ide-nav-diff"' in html
        assert 'id="ide-nav-timeline"' in html
        assert 'id="ide-nav-chat"' in html
        assert 'id="ide-nav-graph"' in html
        assert 'id="ide-nav-rag"' in html
        assert 'id="ide-nav-verification"' in html

        # 3. Проверяем стандартный навигатор по файлам слева (File Explorer как в VS Code)
        assert 'id="ide-file-navigator"' in html
        assert 'class="ide-file-sidebar"' in html
        assert 'id="ide-file-tree-container"' in html
        assert 'id="ide-explorer-ws-title"' in html
        assert 'id="ide-btn-new-file"' in html
        assert 'id="ide-btn-refresh-explorer"' in html
        assert 'id="ide-btn-collapse-explorer"' in html

        # 4. Проверяем верхнее раскрывающееся окно выбора рабочего пространства (Command Center)
        assert 'id="ide-command-center"' in html
        assert 'id="ide-workspace-picker-btn"' in html
        assert 'id="ide-command-center-ws-name"' in html
        assert 'id="ideWorkspacePickerModal"' in html
        assert 'id="ide-ws-quick-search"' in html
        assert 'id="ide-ws-picker-list"' in html

        # 5. Проверяем служебные кнопки нижней группы IDE
        assert 'id="ide-nav-electron-btn"' in html
        assert 'id="ide-nav-settings"' in html
        assert 'id="ide-nav-theme-btn"' in html
        assert 'id="electronStatusModal"' in html

        # 6. Проверяем модальные окна ПКМ контекстного меню проводника (Добавить, Редактировать, Версии, Удалить)
        assert 'id="modal-ide-create-item"' in html
        assert 'id="modal-ide-file-editor"' in html
        assert 'id="modal-ide-file-versions"' in html
        assert 'id="modal-ide-confirm-delete"' in html


@pytest.mark.asyncio
async def test_ide_navigation_and_file_explorer_assets_served() -> None:
    """Проверяет отдачу клиентских скриптов и стилей навигатора по файлам."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Проверяем наличие стилей .ide-file-sidebar и .ide-command-center в nav.css
        res_css = await client.get("/html/css/nav.css")
        assert res_css.status_code == 200
        css = res_css.text
        assert ".ide-activity-bar" in css
        assert ".ide-file-sidebar" in css
        assert ".ide-command-center" in css
        assert ".ide-tree-item" in css

        # Проверяем наличие скриптов ide_navigation.js и ide_file_explorer.js
        res_nav_js = await client.get("/html/js/ide_navigation.js")
        assert res_nav_js.status_code == 200
        assert "initIdeNavigation" in res_nav_js.text

        res_exp_js = await client.get("/html/js/ide_file_explorer.js")
        assert res_exp_js.status_code == 200
        assert "initIdeFileExplorer" in res_exp_js.text
        assert "buildTreeHierarchy" in res_exp_js.text
        assert "refreshFileTree" in res_exp_js.text

        # Проверяем наличие скрипта контекстного меню проводника ide_tree_context_menu.js
        res_tree_cm_js = await client.get("/html/js/ide_tree_context_menu.js")
        assert res_tree_cm_js.status_code == 200
        assert "initIdeTreeContextMenu" in res_tree_cm_js.text
        assert "openEditorModal" in res_tree_cm_js.text
        assert "openVersionsModal" in res_tree_cm_js.text
        assert "?.onclick =" not in res_tree_cm_js.text, "Недопустимо присваивание через optional chaining слева от '='"


def test_electron_git_workspaces_contract_and_directory() -> None:
    """Проверяет сканирование директорий с Git и IPC-контракт Electron оболочки."""
    electron_dir = Path(__file__).resolve().parent.parent / "electron"
    main_js_path = electron_dir / "main.js"
    preload_js_path = electron_dir / "preload.js"

    assert main_js_path.exists(), "Файл main.js Electron должен существовать"
    assert preload_js_path.exists(), "Файл preload.js Electron должен существовать"

    main_text = main_js_path.read_text(encoding="utf-8")
    preload_text = preload_js_path.read_text(encoding="utf-8")

    assert "scanGitWorkspaces" in main_text
    assert ".git" in main_text
    assert "workspaces:list-git" in main_text
    assert "workspaces:set-active" in main_text
    assert "updateApplicationMenu" in main_text

    assert "listGitWorkspaces" in preload_text
    assert "setActiveWorkspace" in preload_text
    assert "onWorkspaceSwitched" in preload_text


@pytest.mark.asyncio
async def test_workspace_directory_contents_api_for_file_explorer() -> None:
    """Проверяет эндпоинт содержимого каталога для построения дерева файлов."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Проверяем эндпоинт для рабочей области default
        res = await client.get("/api/v1/workspaces/default/directory-contents")
        assert res.status_code == 200
        data = res.json()
        assert "workspace_id" in data
        assert "items" in data
        assert isinstance(data["items"], list)
        assert len(data["items"]) > 0

        # Проверяем структуру элементов дерева файлов
        first_item = data["items"][0]
        assert "name" in first_item
        assert "rel_path" in first_item
        assert "is_dir" in first_item
        assert "tracked_by_git" in first_item

@pytest.mark.asyncio
async def test_ide_viewport_width_and_responsiveness() -> None:
    """Проверяет адаптивную ширину основного окна и предотвращение переполнения по ширине."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res_css = await client.get("/html/css/nav.css")
        assert res_css.status_code == 200
        css = res_css.text

        # 1. Проверяем расчет ширины вьюпорта при открытом сайдбаре
        assert "width: calc(100% - 308px)" in css
        assert "max-width: calc(100% - 308px)" in css

        # 2. Проверяем расчет ширины вьюпорта при свернутом сайдбаре
        assert "width: calc(100% - 48px)" in css
        assert "max-width: calc(100% - 48px)" in css

        # 3. Проверяем адаптивность шапки в index.html
        res_html = await client.get("/")
        assert res_html.status_code == 200
        html = res_html.text
        assert "nav-actions-right" in html
        assert "d-none d-xxl-inline" in html



@pytest.mark.asyncio
async def test_sidebar_system_files_filtering_and_show_all_toggle() -> None:
    """Проверяет сокрытие служебных файлов по умолчанию и наличие кнопки Показать всё (без лишнего тумблера)."""
    import json
    from apps.ai_assistant.core.workspace_items_tracker import WorkspaceItemsTracker

    webgui_dir = Path(__file__).resolve().parent.parent / "api" / "webgui"
    index_html = (webgui_dir / "index.html").read_text(encoding="utf-8")
    explorer_js = (webgui_dir / "js" / "ide_file_explorer.js").read_text(encoding="utf-8")

    # 1. Проверяем разметку боковой панели (Primary Side Bar Explorer) на наличие кнопки "Показать всё"
    assert 'id="ide-btn-toggle-show-all"' in index_html, "Кнопка переключателя 'Показать всё' отсутствует в шапке сайдбара"
    assert 'id="ide-switch-show-all"' not in index_html, "Дублирующий тумблер 'Показать всё' должен отсутствовать в сайдбаре"
    assert 'id="ide-explorer-toolbar"' not in index_html, "Дублирующий тулбар сайдбара должен отсутствовать"

    # 2. Проверяем функции фильтрации и управления в ide_file_explorer.js
    assert "isSystemItem" in explorer_js, "Функция isSystemItem отсутствует в ide_file_explorer.js"
    assert "getVisibleItems" in explorer_js, "Функция getVisibleItems отсутствует в ide_file_explorer.js"
    assert "setShowAllFiles" in explorer_js, "Функция setShowAllFiles отсутствует в ide_file_explorer.js"
    assert "updateShowAllControls" in explorer_js, "Функция updateShowAllControls отсутствует в ide_file_explorer.js"
    assert "ai:system-files-toggled" in explorer_js, "Событие синхронизации ai:system-files-toggled отсутствует"

    # 3. Проверяем наличие ключей локализации во всех поддерживаемых языках (RU, EN, HE, UK)
    locales_dir = webgui_dir / "locales"
    for lang in ["ru", "en", "he", "uk"]:
        loc_file = locales_dir / f"{lang}.json"
        assert loc_file.exists(), f"Файл локализации {lang}.json отсутствует"
        loc_data = json.loads(loc_file.read_text(encoding="utf-8"))
        assert "showAllFiles" in loc_data.get("workspace", {}), f"workspace.showAllFiles отсутствует в {lang}.json"
        assert "hideSystemFiles" in loc_data.get("workspace", {}), f"workspace.hideSystemFiles отсутствует в {lang}.json"
        assert "toggleShowAll" in loc_data.get("titles", {}).get("ide", {}), f"titles.ide.toggleShowAll отсутствует в {lang}.json"

    # 4. Проверяем корректность флагов is_system для служебных файлов рабочего пространства
    from apps.ai_assistant.core.workspace_manager import WorkspaceManager
    wm = WorkspaceManager()
    ws_id = "test_sidebar_toggle_ws"
    ws = wm.create_or_select_workspace(workspace_id=ws_id, name="Sidebar Toggle WS")
    tracker = WorkspaceItemsTracker(wm)
    try:
        contents = tracker.get_directory_contents(ws_id)
        items = contents["items"]
        sys_items = [i for i in items if i.get("is_system")]
        assert len(sys_items) >= 2, "Служебные файлы не распознаны как is_system"
        for i in sys_items:
            n = i["name"].lower()
            rel = i["rel_path"].lower()
            assert (
                n.startswith(".")
                or n.startswith("_")
                or n in ("readme.md", "assets", "knowledge_base.md")
                or any(p.startswith(".") or p.startswith("_") or p == "assets" for p in rel.split("/"))
            ), f"Неожиданный служебный файл: {i}"
    finally:
        try:
            wm.registry.delete_workspace(ws_id)
        except Exception:
            pass
        import os, stat, shutil
        ws_p = wm.workspaces_dir / ws_id
        if ws_p.exists():
            def _rm_ro(func, path, exc):
                os.chmod(path, stat.S_IWRITE)
                func(path)
            shutil.rmtree(ws_p, onerror=_rm_ro)
