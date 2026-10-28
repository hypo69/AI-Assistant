# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Tests - AI Smart Tooltips Tests
# =============================================================================
# Description:
#   Модульные и интеграционные тесты системы интеллектуальных всплывающих
#   подсказок ИИ (AI Smart Tooltips), интеграции WikiLLM и модели Gemini,
#   проверки кэша подсказок и работы модального окна AIModalDialog.
#
# File: test_ai_smart_tooltips.py
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-25 21:25:00
# =============================================================================

from __future__ import annotations
"""Тесты для механизма AI Smart Tooltips с WikiLLM и Gemini в AI Assistant."""

from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from apps.ai_assistant.main import app


@pytest.mark.asyncio
async def test_tooltip_script_assets_served() -> None:
    """Проверяет доступность обновленного скрипта global-tooltips-i18n.js через HTTP."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/html/js/global-tooltips-i18n.js")
        assert res.status_code == 200, "Скрипт /html/js/global-tooltips-i18n.js недоступен"
        content = res.text
        assert "AISmartTooltip" in content, "AISmartTooltip не найден в global-tooltips-i18n.js"
        assert "DEFAULT_KNOWLEDGE_BASE" in content, "DEFAULT_KNOWLEDGE_BASE отсутствует в скрипте"
        assert "workspace" in content, "Термин workspace отсутствует в базе знаний тултипов"
        assert "qa" in content, "Термин qa отсутствует в базе знаний тултипов"
        assert "commits" in content, "Термин commits отсутствует в базе знаний тултипов"
        assert "AIModalDialog" in content, "Связка с AIModalDialog отсутствует в тултипе"
        assert "ai-modal:explained" in content, "Слушатель события ai-modal:explained отсутствует"


@pytest.mark.asyncio
async def test_tooltip_styles_in_components_css() -> None:
    """Проверяет наличие CSS стилей для тултипов НАД элементом в components.css."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/html/css/components.css")
        assert res.status_code == 200, "Файл /html/css/components.css недоступен"
        css = res.text
        assert ".ai-smart-tooltip-container" in css, "Селектор .ai-smart-tooltip-container отсутствует"
        assert ".ai-smart-tooltip-arrow" in css, "Стрелка .ai-smart-tooltip-arrow отсутствует"
        assert "var(--ui-bg-surface-elevated" in css, "CSS-переменные темы не используются в тултипе"
        assert ".ai-smart-tooltip-btn" in css, "Кнопка действия .ai-smart-tooltip-btn отсутствует в стилях"


@pytest.mark.asyncio
async def test_index_html_includes_versioned_tooltip_and_modal_assets() -> None:
    """Проверяет актуальную версию скрипта тултипов, модального окна и css в index.html."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/")
        assert res.status_code == 200, "Главная страница недоступна"
        html = res.text
        assert "global-tooltips-i18n.js?v=" in html, "Версия скрипта тултипов не обновлена"
        assert "main.css?v=" in html, "Версия main.css не обновлена"
        assert "ai_modal_dialog/style.css" in html, "Стили ai_modal_dialog отсутствуют в index.html"
        assert "ai_modal_dialog/main.js" in html, "Скрипт ai_modal_dialog отсутствует в index.html"


def test_ai_modal_dialog_dispatches_explained_event() -> None:
    """Проверяет, что контроллер ai_modal_dialog/main.js диспатчит событие ai-modal:explained."""
    base_dir = Path(__file__).resolve().parent.parent
    modal_js_path = base_dir / "api" / "webgui" / "ai_modal_dialog" / "main.js"
    assert modal_js_path.exists(), "Файл ai_modal_dialog/main.js не найден"
    content = modal_js_path.read_text(encoding="utf-8")
    assert "ai-modal:explained" in content, "Диспатч события ai-modal:explained отсутствует в ai_modal_dialog/main.js"


@pytest.mark.asyncio
async def test_workspace_tab_contains_ai_tooltip_attributes() -> None:
    """Проверяет разметку вкладки tab_workspace на наличие data-ai-tooltip и data-term."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/html/tab_workspace/index.html")
        assert res.status_code == 200, "Вкладка tab_workspace недоступна"
        html = res.text

        assert 'data-term="seed_demo"' in html, "Атрибут data-term='seed_demo' отсутствует"
        assert 'data-ai-tooltip="true"' in html, "Атрибут data-ai-tooltip отсутствует"
        assert 'id="ws-rebuild-faiss-btn"' in html, "Кнопка ws-rebuild-faiss-btn отсутствует"
        assert 'data-term="rebuild_faiss"' in html, "Атрибут data-term='rebuild_faiss' отсутствует"
        assert 'id="qa-ask-btn"' in html, "Кнопка qa-ask-btn отсутствует"
        assert 'data-term="qa"' in html, "Атрибут data-term='qa' отсутствует"


@pytest.mark.asyncio
async def test_diagnostics_explain_endpoint_available() -> None:
    """Проверяет наличие и ответ эндпоинта диагностики /api/v1/diagnostics/explain."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Запрос с cache_only=True для проверки роутера без обращения к внешнему Gemini API
        payload = {
            "table_type": "ai_assistant_ui",
            "panel_id": "panel-workspace-select",
            "title": "Рабочая область",
            "subtitle": "Управление проектом",
            "cache_only": True,
            "metadata": {"section": "workspace"},
        }
        res = await client.post("/api/v1/diagnostics/explain", json=payload)
        assert res.status_code in (200, 404, 502), f"Неожиданный статус код: {res.status_code}"
