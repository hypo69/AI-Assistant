# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Tests - System Tour Tests
# =============================================================================
# Description:
#   Модульные и интеграционные тесты для интерактивного гид-тура по возможностям
#   системы умного хранения документации (System Tour Guide Component).
#   Проверяет отдачу статических ассетов, структуру шагов, CSS-стили темы,
#   наличие точек входа в index.html и tab_workspace/index.html.
#
# File: test_system_tour.py
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-26 01:00:00
# =============================================================================

from __future__ import annotations
"""Тесты для клиентского гид-тура по системе умного хранения документации."""

import pytest
from httpx import ASGITransport, AsyncClient

from apps.ai_assistant.main import app


@pytest.mark.asyncio
async def test_system_tour_script_assets_served() -> None:
    """Проверяет доступность скрипта system_tour.js и его API."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/html/components/system_tour/system_tour.js")
        assert res.status_code == 200, "Скрипт system_tour.js недоступен"
        content = res.text
        assert "TOUR_STEPS" in content, "TOUR_STEPS отсутствуют в system_tour.js"
        assert "window.SystemTour" in content, "Глобальный объект window.SystemTour отсутствует"
        assert "step-overview" in content, "Шаг обзора архитектуры отсутствует"
        assert "step-workspace" in content, "Шаг рабочих областей отсутствует"
        assert "step-nlp-facts" in content, "Шаг NLP-анализаторов отсутствует"
        assert "step-temporal-graph" in content, "Шаг темпорального графа отсутствует"
        assert "step-rag-qa" in content, "Шаг RAG и Q&A отсутствует"
        assert "step-verification-audit" in content, "Шаг верификации и аудита отсутствует"
        assert "Кем была вымыта рама?" in content, "Пример с русским языком отсутствует"
        assert "למי הייתה חווה?" in content, "Пример с ивритом отсутствует"


@pytest.mark.asyncio
async def test_system_tour_css_styles_served() -> None:
    """Проверяет доступность CSS-стилей тура и соблюдение дизайн-токенов тем."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/html/components/system_tour/system_tour.css")
        assert res.status_code == 200, "Стили system_tour.css недоступны"
        css = res.text
        assert ".system-tour-modal" in css, "Селектор .system-tour-modal отсутствует"
        assert ".tour-stepper" in css, "Селектор .tour-stepper отсутствует"
        assert ".tour-step-pill" in css, "Селектор .tour-step-pill отсутствует"
        assert ".tour-feature-card" in css, "Селектор .tour-feature-card отсутствует"
        assert "var(--card-bg" in css, "Переменные темы не используются для фона карточки"
        assert "var(--border-color" in css, "Переменные темы не используются для границ"
        assert "80vw" in css, "Ширина 80% окна (80vw) не задана для тура"
        assert "80vh" in css, "Высота 80% окна (80vh) не задана для тура"


@pytest.mark.asyncio
async def test_index_html_contains_system_tour_integration() -> None:
    """Проверяет подключение скрипта, стилей и кнопок вызова тура в index.html."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/")
        assert res.status_code == 200, "Главная страница index.html недоступна"
        html = res.text
        assert "system_tour.css" in html, "system_tour.css не подключен в index.html"
        assert "system_tour.js" in html, "system_tour.js не подключен в index.html"
        assert 'id="btn-start-system-tour"' in html, "Кнопка тура в навигационной панели отсутствует"
        assert 'id="ide-nav-tour-btn"' in html, "Кнопка тура в боковом меню IDE отсутствует"
        assert 'id="help-btn-start-tour"' in html, "Кнопка тура в модальном окне справки отсутствует"


@pytest.mark.asyncio
async def test_workspace_tab_contains_system_tour_button() -> None:
    """Проверяет наличие кнопки гид-тура в основной вкладке tab_workspace."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/html/tab_workspace/index.html")
        assert res.status_code == 200, "Файл tab_workspace/index.html недоступен"
        html = res.text
        assert 'data-term="system_tour"' in html, "Атрибут подсказки system_tour отсутствует на кнопке"


@pytest.mark.asyncio
async def test_tooltips_and_locales_include_system_tour() -> None:
    """Проверяет наличие термина system_tour в базе подсказок и в словаре локализации."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Проверка базы знаний подсказок
        res_tt = await client.get("/html/js/global-tooltips-i18n.js")
        assert res_tt.status_code == 200
        assert "'system_tour'" in res_tt.text, "Термин system_tour отсутствует в global-tooltips-i18n.js"

        # Проверка локали ru.json
        res_loc = await client.get("/html/locales/ru.json")
        assert res_loc.status_code == 200
        data = res_loc.json()
        assert "systemTour" in data, "Секция systemTour отсутствует в ru.json"
        assert "btnTour" in data["systemTour"]
