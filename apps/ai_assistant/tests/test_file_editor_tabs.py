# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant Tests - Studio Code Central File Editor Tabs
# =============================================================================
# Description:
#   TDD-тесты для центрального окна редактора файлов Studio Code с поддержкой
#   открытых вкладок для каждого файла (#tab-workspace#panel-file-editor),
#   встроенного видео- и аудиоплеера HTML5 без выхода за рамки технологии,
#   потокового эндпоинта /file-raw, маршрутизации панелей и контекстного меню.
#
# File: test_file_editor_tabs.py
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 20:30:00
# =============================================================================

from __future__ import annotations
"""Тестирование центрального редактора файлов с вкладками Studio Code и встроенным видеоплеером."""

from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient
from apps.ai_assistant.main import app


@pytest.mark.asyncio
async def test_file_editor_panel_renamed_in_workspace_tab() -> None:
    """Проверяет переименование panel-editor в panel-file-editor в разметке и навигации."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/html/tab_workspace/index.html")
        assert res.status_code == 200
        html = res.text

        # Проверяем идентификатор суб-панели и кнопки
        assert 'data-panel-id="panel-file-editor"' in html
        assert 'id="subtab-ws-file-editor-btn"' in html
        assert 'id="subpane-ws-file-editor"' in html
        assert 'ws-embedded-editor-container' in html


@pytest.mark.asyncio
async def test_central_file_editor_assets_and_tabs_bar() -> None:
    """Проверяет разметку центрального редактора файлов с вкладками и встроенным плеером."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/html/tab_file_editor/index.html")
        assert res.status_code == 200
        html = res.text

        # 1. Полоса вкладок Studio Code
        assert 'id="fe-open-tabs-bar"' in html
        assert 'id="fe-btn-new-file"' in html
        assert 'id="fe-btn-close-all"' in html

        # 2. Подшапка файла и действия (в стиле Быстрого редактора)
        assert 'id="fe-active-file-name"' in html
        assert 'id="fe-active-file-path"' in html
        assert 'id="fe-view-mode-group"' in html
        assert 'id="fe-tab-mode-code"' in html
        assert 'id="fe-tab-mode-split"' in html
        assert 'id="fe-mode-split-text"' in html
        assert 'id="fe-tab-mode-preview"' in html
        assert 'id="fe-btn-save"' in html
        assert 'id="fe-btn-system-open"' in html

        # 3. Текстовый редактор, статистика и коммит
        assert 'id="fe-code-textarea"' in html
        assert 'id="fe-line-gutter"' in html
        assert 'id="fe-commit-msg-input"' in html
        assert 'id="fe-editor-stats"' in html

        # 4. Встроенный медиаплеер (Видео, Аудио, Картинки)
        assert 'id="fe-media-stage"' in html
        assert 'id="fe-media-video"' in html
        assert 'id="fe-media-audio"' in html
        assert 'id="fe-media-image"' in html


@pytest.mark.asyncio
async def test_central_file_editor_orchestrator_media_support() -> None:
    """Проверяет логику медиафайлов и видеоплеера в main.js редактора."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/html/tab_file_editor/main.js")
        assert res.status_code == 200
        js = res.text

        # Поддержка расширений медиа
        assert "VIDEO_EXTENSIONS" in js
        assert "AUDIO_EXTENSIONS" in js
        assert "fe-media-video" in js
        assert "fe-media-audio" in js
        assert "file-raw" in js

        # Проверка отсутствия дублирующихся export (ES-модуль)
        assert "closeOtherDocuments" in js
        assert "export function closeOtherDocuments" not in js
        assert "closeOtherDocuments," in js


@pytest.mark.asyncio
async def test_workspace_file_raw_endpoint_streams_media(tmp_path: Path) -> None:
    """Проверяет потоковую отдачу видео/медиа файлов через /workspaces/{id}/file-raw."""
    from apps.ai_assistant.core.workspace_manager import WorkspaceManager
    wm = WorkspaceManager()
    all_ws = wm.list_workspaces()
    assert len(all_ws) > 0
    ws_id = all_ws[0]["workspace_id"]
    _, ws_path = wm._get_or_create_workspace(ws_id)

    # Создаем тестовый видеофайл (dummy mp4)
    media_file = ws_path / "test_sample_video.mp4"
    dummy_mp4_bytes = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00isommp42"
    media_file.write_bytes(dummy_mp4_bytes)

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get(
                f"/api/v1/workspaces/{ws_id}/file-raw",
                params={"rel_path": "test_sample_video.mp4"},
            )
            assert res.status_code == 200
            assert "video/mp4" in res.headers.get("content-type", "")
            assert res.content == dummy_mp4_bytes
    finally:
        if media_file.exists():
            media_file.unlink()


@pytest.mark.asyncio
async def test_context_menu_routes_to_central_editor() -> None:
    """Проверяет маршрутизацию действий 'Быстрый редактор' в центральное окно с вкладками."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/html/js/ide_tree_context_menu.js")
        assert res.status_code == 200
        js = res.text

        # Проверяем вызовы центрального редактора
        assert 'openFileInWasmEditor' in js
        assert 'panel-file-editor' in js


@pytest.mark.asyncio
async def test_file_editor_view_mode_split_support() -> None:
    """Проверяет поддержку режимов 'Вид', 'Редактор' и 'Вид/Редактор' (Split)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Разметка редактора
        res_html = await client.get("/html/tab_file_editor/index.html")
        assert res_html.status_code == 200
        html = res_html.text
        assert 'id="fe-tab-mode-code"' in html
        assert 'id="fe-tab-mode-split"' in html
        assert 'id="fe-tab-mode-preview"' in html
        assert 'data-i18n="ide.editorTabSplit"' in html
        assert 'data-i18n="ide.editorTabView"' in html

        # 2. Логика скрипта: наличие split и переключения
        res_js = await client.get("/html/tab_file_editor/main.js")
        assert res_js.status_code == 200
        js = res_js.text
        assert "switchActiveViewMode" in js
        assert "applyViewMode" in js
        assert "wasm-split-mode" in js
        assert "wasm-preview-mode" in js
        assert "fe-tab-mode-split" in js

        # 3. Стили split-режима
        res_css = await client.get("/html/tab_file_editor/style.css")
        assert res_css.status_code == 200
        css = res_css.text
        assert "wasm-split-mode" in css
        assert "wasm-preview-mode" in css
        assert "#fe-markdown-preview" in css


@pytest.mark.asyncio
async def test_markdown_preview_rendering_and_local_assets() -> None:
    """Проверяет локальную доступность библиотеки marked и парсера Markdown для файлов .md."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Локальная библиотека marked.min.js отдаётся со статусом 200 без зависимости от внешнего CDN
        res_marked = await client.get("/html/js/marked.min.js")
        assert res_marked.status_code == 200
        assert len(res_marked.content) > 10000

        # 2. Главный скрипт редактора содержит встроенный оффлайн-парсер parseMarkdownToHtml
        res_js = await client.get("/html/tab_file_editor/main.js")
        assert res_js.status_code == 200
        js = res_js.text
        assert "parseMarkdownToHtml" in js
        assert "ensureMarkedLoaded" in js
        # Автоматический режим split по умолчанию для Markdown
        assert "(ext === 'md' || ext === 'markdown') ? 'split' : 'code'" in js


@pytest.mark.asyncio
async def test_modal_file_editor_split_mode_and_markdown_preview() -> None:
    """Проверяет наличие кнопки Вид/Редактор и поддержку Markdown-предосмотра в модальном окне редактора."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Проверяем наличие кнопки сплит-режима в модальном окне редактора index.html
        res_html = await client.get("/")
        assert res_html.status_code == 200
        html = res_html.text
        assert 'id="ide-editor-tab-split"' in html
        assert 'data-i18n="ide.editorTabSplit"' in html
        assert 'id="ide-editor-stage"' in html

        # 2. Проверяем поддержку раздельного вида и оффлайн-парсера в ide_tree_context_menu.js
        res_js = await client.get("/html/js/ide_tree_context_menu.js")
        assert res_js.status_code == 200
        js = res_js.text
        assert "ide-editor-tab-split" in js
        assert "applyModalMode" in js
        assert "parseMarkdownToHtmlFallback" in js
        assert "window.parseMarkdownToHtml" in js
        assert "preprocessMarkdownContent" in js


@pytest.mark.asyncio
async def test_obsidian_frontmatter_and_wikilinks_formatting() -> None:
    """Проверяет корректность разбора YAML Frontmatter, ссылок Obsidian [[...]] и защиты переносов."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/html/tab_file_editor/main.js")
        assert res.status_code == 200
        js = res.text
        # Проверяем наличие предобработчика фронтматтера и викиссылок
        assert "preprocessMarkdownContent" in js
        assert "obsidian-wikilink" in js
        assert "YAML Frontmatter (Obsidian Metadata)" in js
        assert "window.marked.setOptions({ breaks: true, gfm: true })" in js


@pytest.mark.asyncio
async def test_extensionless_file_content_detection_and_api(tmp_path: Path) -> None:
    """Проверяет эвристическое определение типа для файла без расширения через API и клиентские скрипты."""
    from apps.ai_assistant.core.workspace_file_ops import WorkspaceFileOps
    from apps.ai_assistant.core.workspace_manager import WorkspaceManager

    # 1. Создаем файл без расширения с Obsidian Frontmatter в тестовой рабочей области
    wm = WorkspaceManager(workspaces_dir=tmp_path / "workspaces")
    ws_id = "test_ws"
    wm.ensure_workspace_folder(ws_id)
    obsidian_content = (
        "---\n"
        "generator: ai_assistant_obsidian\n"
        "title: \"דוד משה\"\n"
        "workspace_id: דוד_משה\n"
        "---\n\n"
        "לדוד משה היתה חווה\n"
    )
    WorkspaceFileOps.create_item(
        wm=wm,
        workspace_id=ws_id,
        rel_path="hebrew_note",
        is_dir=False,
        content=obsidian_content,
    )

    # 2. Вызываем WorkspaceFileOps.get_content
    res = WorkspaceFileOps.get_content(wm=wm, workspace_id=ws_id, rel_path="hebrew_note")
    assert res["status"] == "ok"
    assert res["is_binary"] is False
    assert res.get("detected_type") == "md"

    # 3. Проверяем клиентскую функцию detectFileTypeFromContent в main.js и ide_tree_context_menu.js
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res_main = await client.get("/html/tab_file_editor/main.js")
        assert res_main.status_code == 200
        assert "detectFileTypeFromContent" in res_main.text
        assert "detected_type" in res_main.text

        res_menu = await client.get("/html/js/ide_tree_context_menu.js")
        assert res_menu.status_code == 200
        assert "detectFileTypeFromContent" in res_menu.text
        assert "window.detectFileTypeFromContent = detectFileTypeFromContent" in res_menu.text





