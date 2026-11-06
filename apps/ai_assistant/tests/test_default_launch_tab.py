# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Test AI Assistant Default Launch Tab and URL Routing
# =============================================================================
# Description:
#   Модульные тесты для проверки открытия по умолчанию вкладки диалога с ИИ
#   (http://localhost:8002/#tab-chat#workspace=<последний>) при запуске сервиса.
#   Проверяют:
#   - Формирование URL запуска в apps.ai_assistant.main.run
#   - Канонический URL загрузки в десктопной оболочке Electron (main.js)
#   - Разметку index.html (активная вкладка по умолчанию — tab-chat)
#   - Клиентскую маршрутизацию в apps/ai_assistant/api/webgui/js/main.js
#   - Предотвращение редиректа в top_workspace_dropdown.js при нахождении на вкладке чата
#
# File: test_default_launch_tab.py
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 19:36:00
# =============================================================================

from __future__ import annotations
"""Тесты для проверки открытия вкладки #tab-chat#workspace=<id> по умолчанию при старте."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from apps.ai_assistant.main import run


def test_main_run_default_url_with_active_workspace(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет, что при наличии активного рабочего пространства URL запуска формируется как #tab-chat#workspace=<id>."""
    mock_wm = MagicMock()
    mock_wm.list_workspaces.return_value = [{"workspace_id": "test_active_ws"}]
    mock_wm.get_active_workspace_id.return_value = "test_active_ws"
    mock_wm.get_active_workspace_id_from_config.return_value = "test_active_ws"

    with patch("apps.ai_assistant.core.workspace_manager.WorkspaceManager", return_value=mock_wm), \
         patch("apps.ai_assistant.main.launch_gui") as mock_launch_gui, \
         patch("apps.ai_assistant.main.is_port_in_use", return_value=True), \
         patch("apps.ai_assistant.main.resolve_occupied_port_action", return_value="connect"):

        run(port=8002, host="127.0.0.1", engine="electron", action="connect")

        mock_launch_gui.assert_called_once()
        called_url = mock_launch_gui.call_args[0][0]
        assert "http://127.0.0.1:8002/#tab-chat#workspace=test_active_ws" in called_url


def test_main_run_default_url_without_workspaces(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет, что при отсутствии рабочих пространств URL запуска формируется как #tab-chat."""
    mock_wm = MagicMock()
    mock_wm.list_workspaces.return_value = []
    mock_wm.get_active_workspace_id.return_value = None
    mock_wm.get_active_workspace_id_from_config.return_value = None

    with patch("apps.ai_assistant.core.workspace_manager.WorkspaceManager", return_value=mock_wm), \
         patch("apps.ai_assistant.main.launch_gui") as mock_launch_gui, \
         patch("apps.ai_assistant.main.is_port_in_use", return_value=True), \
         patch("apps.ai_assistant.main.resolve_occupied_port_action", return_value="connect"):

        run(port=8002, host="127.0.0.1", engine="electron", action="connect")

        mock_launch_gui.assert_called_once()
        called_url = mock_launch_gui.call_args[0][0]
        assert called_url == "http://127.0.0.1:8002/#tab-chat"


def test_electron_main_js_target_url_tab_chat() -> None:
    """Проверяет, что в apps/ai_assistant/electron/main.js по умолчанию используется #tab-chat#workspace=."""
    electron_main = Path(__file__).resolve().parent.parent / "electron" / "main.js"
    assert electron_main.exists(), "electron/main.js не найден"

    content = electron_main.read_text(encoding="utf-8")
    assert "/#tab-chat#workspace=" in content, "В electron/main.js не найден шаблон #tab-chat#workspace="
    assert "/#tab-chat" in content, "В electron/main.js не найден fallback #tab-chat"


def test_index_html_default_active_tab_is_chat() -> None:
    """Проверяет, что в index.html вкладкой по умолчанию является #tab-chat и кнопка ide-nav-chat активна."""
    index_html = Path(__file__).resolve().parent.parent / "api" / "webgui" / "index.html"
    assert index_html.exists(), "index.html не найден"

    html = index_html.read_text(encoding="utf-8")

    # Кнопка чата должна иметь класс active
    assert 'id="ide-nav-chat"' in html
    assert 'class="ide-activity-item active"' in html
    assert 'data-tab="tab-chat" id="ide-nav-chat"' in html

    # Кнопка workspace не должна иметь класс active
    assert 'class="ide-activity-item active" data-i18n-title="titles.ide.title_cbf933c4" data-tab="tab-workspace"' not in html

    # Контейнер содержимого вкладки tab-chat должен быть active show
    assert '<div class="tab-pane fade show active" id="tab-chat"></div>' in html
    assert '<div class="tab-pane fade show active" id="tab-workspace"></div>' not in html


def test_webgui_main_js_default_tab_and_hash() -> None:
    """Проверяет, что в apps/ai_assistant/api/webgui/js/main.js по умолчанию открывается tab-chat."""
    main_js = Path(__file__).resolve().parent.parent / "api" / "webgui" / "js" / "main.js"
    assert main_js.exists(), "main.js не найден"

    code = main_js.read_text(encoding="utf-8")
    assert "const tabId = parts[0] || 'tab-chat';" in code
    assert "initialTabId = 'tab-chat';" in code
    assert "#tab-chat#workspace=" in code


def test_top_workspace_dropdown_does_not_override_chat_tab() -> None:
    """Проверяет, что top_workspace_dropdown.js не перенаправляет принудительно на #tab-workspace#panel-documents, когда открыта вкладка чата."""
    dd_js = Path(__file__).resolve().parent.parent / "api" / "webgui" / "js" / "top_workspace_dropdown.js"
    assert dd_js.exists(), "top_workspace_dropdown.js не найден"

    code = dd_js.read_text(encoding="utf-8")
    assert "isWsTab" in code, "В top_workspace_dropdown.js отсутствует проверка активности вкладки workspace"
    assert "#tab-chat#workspace=" in code, "В top_workspace_dropdown.js отсутствует сохранение маршрута чата"
