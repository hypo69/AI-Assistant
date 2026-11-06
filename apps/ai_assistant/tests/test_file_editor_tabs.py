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
# Updated: 2026-11-06 23:15:00
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
