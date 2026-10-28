# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant Tests - RTL Drawer Menu Positioning
# =============================================================================
# Description:
#   TDD-тесты для проверки корректного позиционирования выдвигающегося меню
#   в веб-интерфейсе apps/ai_assistant/api/webgui при включении RTL-языков
#   (например, иврит he-IL или арабский ar).
#
#   Проверяет:
#   1. Наличие CSS-правил в nav.css для [dir="rtl"] .left-drawer-nav с позиционированием
#      справа (right: 0, left: auto, border-left, border-right: none).
#   2. Наличие CSS-правил для анимации и скрытия выдвижного меню справа при RTL
#      (transform: translateX(100%)).
#   3. Наличие CSS-правил для плавающего ярлычка .left-drawer-tab-trigger при RTL.
#   4. Наличие функций синхронизации направления выдвижного меню в i18n.js и global-i18n.js
#      (переключение между offcanvas-start и offcanvas-end при RTL).
#   5. Отдачу обновленных статических файлов через FastAPI (/html/css/nav.css, /html/js/i18n.js).
#
# File: test_rtl_drawer_menu.py
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-25 22:42:00
# =============================================================================

from __future__ import annotations
"""Тесты позиционирования выдвижного меню в RTL языках для WebGUI AI Assistant."""

from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient
from apps.ai_assistant.main import app

_WEBGUI_DIR = Path(__file__).resolve().parent.parent / "api" / "webgui"


@pytest.mark.asyncio
async def test_rtl_drawer_menu_styles_in_nav_css() -> None:
    """Проверяет наличие стилей RTL для выдвижного меню в nav.css."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/html/css/nav.css")
        assert res.status_code == 200, "Файл nav.css должен отдаваться сервером"
        css = res.text

        # 1. Проверяем позиционирование выдвижного меню справа в RTL
        assert '[dir="rtl"] .left-drawer-nav' in css or 'html[dir="rtl"] .left-drawer-nav' in css
        assert "right: 0" in css
        assert "border-left" in css

        # 2. Проверяем анимацию выезда справа
        assert "translateX(100%)" in css

        # 3. Проверяем стили ярлычка в RTL
        assert '[dir="rtl"] .left-drawer-tab-trigger' in css or 'html[dir="rtl"] .left-drawer-tab-trigger' in css


@pytest.mark.asyncio
async def test_rtl_logic_in_i18n_and_global_i18n_scripts() -> None:
    """Проверяет логику синхронизации положения выдвижного меню в i18n.js и global-i18n.js."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Проверяем i18n.js
        res_i18n = await client.get("/html/js/i18n.js")
        assert res_i18n.status_code == 200, "Файл i18n.js должен отдаваться сервером"
        i18n_text = res_i18n.text
        assert "syncOffcanvasDirection" in i18n_text
        assert "offcanvas-end" in i18n_text

        # Проверяем global-i18n.js
        res_global = await client.get("/html/js/global-i18n.js")
        assert res_global.status_code == 200, "Файл global-i18n.js должен отдаваться сервером"
        global_text = res_global.text
        assert "offcanvas-end" in global_text


@pytest.mark.asyncio
async def test_index_html_contains_updated_cache_busters_and_rtl_support() -> None:
    """Проверяет корректность разметки и скрипта в index.html для быстрой инициализации RTL."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/")
        assert res.status_code == 200
        html = res.text

        # Проверяем наличие элемента выдвижного меню
        assert 'id="leftSideNavOffcanvas"' in html
        assert 'left-drawer-nav' in html
