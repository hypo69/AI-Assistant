# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant Tests - WebGUI Refactoring & Navigation Verification
# =============================================================================
# Description:
#   Модульные и интеграционные тесты для проверки рефакторинга веб-интерфейса:
#   - Проверка наличия ссылки на главную страницу (#app-brand-link) и ID (#app-title)
#   - Проверка семантических ID навигационных элементов и кнопок бокового меню
#   - Проверка отсутствия дубликатов ID в DOM-дереве index.html
#   - Проверка интеграции обработчика клика по брендингу в main.js
#
# File: test_webgui_refactoring.py
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 19:05:00
# =============================================================================

from __future__ import annotations
"""Тесты валидации рефакторинга веб-интерфейса AI Assistant."""

from collections import Counter
from pathlib import Path
import re
import pytest
from bs4 import BeautifulSoup
from httpx import ASGITransport, AsyncClient

from apps.ai_assistant.main import app

_WEBGUI_DIR = Path(__file__).resolve().parent.parent / "api" / "webgui"


@pytest.mark.asyncio
async def test_brand_link_and_title_attributes() -> None:
    """Проверяет брендинг как ссылку на главную страницу с обязательным атрибутом id.

    Шаги:
        1. Запрашивает корневой URL '/'.
        2. Проверяет наличие ссылки #app-brand-link с href='/'.
        3. Проверяет дочерние элементы #app-brand-icon и #app-title.
        4. Проверяет интернационализацию data-i18n='app.title' и текст названия.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/")
        assert res.status_code == 200, "Корневой маршрут недоступен"
        soup = BeautifulSoup(res.text, "html.parser")

        # 1. Ссылка на главную страницу
        brand_link = soup.find("a", id="app-brand-link")
        assert brand_link is not None, "Элемент <a id='app-brand-link'> не найден в разметке"
        assert brand_link.get("href") == "/", "Ссылка брендинга должна вести на главную страницу '/'"
        assert "text-decoration-none" in brand_link.get("class", []), "Ссылка должна содержать text-decoration-none"

        # 2. Иконка брендинга
        brand_icon = brand_link.find(id="app-brand-icon")
        assert brand_icon is not None, "Иконка брендинга #app-brand-icon отсутствует"

        # 3. Текст заголовка
        title_span = brand_link.find(id="app-title")
        assert title_span is not None, "Текстовый заголовок приложения #app-title отсутствует"
        assert title_span.get("data-i18n") == "app.title", "Отсутствует data-i18n='app.title'"
        assert "AI Assistant — Умное Версионирование" in title_span.text, "Некорректный текст заголовка по умолчанию"


@pytest.mark.asyncio
async def test_navigation_and_drawer_elements_have_unique_ids() -> None:
    """Проверяет, что все функциональные элементы навигации и панели снабжены уникальными ID."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/")
        assert res.status_code == 200
        soup = BeautifulSoup(res.text, "html.parser")

        expected_ids = [
            "app-brand-link",
            "app-brand-icon",
            "app-title",
            "ide-command-center",
            "ide-workspace-picker-btn",
            "top-nav-help-btn",
            "user-menu-item-settings",
            "user-menu-item-logout",
            "left-drawer-floating-trigger",
            "left-drawer-close-btn",
            "btn-switch-to-ai-assistant",
            "drawer-nav-tab-status",
            "drawer-nav-tab-git-maintenance",
        ]

        for elem_id in expected_ids:
            elem = soup.find(id=elem_id)
            assert elem is not None, f"Элемент с id='{elem_id}' не найден в index.html"

        assert soup.find(id="top-workspace-control-container") is None, (
            "Устаревший контейнер #top-workspace-control-container должен быть удалён из index.html"
        )


def test_duplicate_elements_removed_from_drawer_menu() -> None:
    """Проверяет, что элементы, представленные в Activity Bar, удалены из выдвижного меню."""
    index_path = _WEBGUI_DIR / "index.html"
    html_text = index_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html_text, "html.parser")

    drawer = soup.find(id="leftSideNavOffcanvas")
    assert drawer is not None, "Элемент #leftSideNavOffcanvas не найден"

    # Элементы, которые были удалены из выдвижного меню, так как уже присутствуют в Activity Bar
    removed_ids = [
        "drawer-btn-start-tour",
        "drawer-nav-tab-workspace",
        "drawer-nav-tab-timeline",
        "drawer-nav-tab-commits",
        "drawer-nav-tab-diff",
        "drawer-nav-tab-wikillm",
        "drawer-nav-tab-graph",
        "drawer-nav-tab-models",
        "drawer-nav-tab-rag",
        "drawer-nav-tab-verification",
        "drawer-nav-tab-gmail",
        "drawer-nav-tab-plugins",
        "drawer-nav-tab-theme-editor",
    ]

    for elem_id in removed_ids:
        elem_in_drawer = drawer.find(id=elem_id)
        assert elem_in_drawer is None, (
            f"Элемент с id='{elem_id}' не должен находиться в раскрывающемся меню, "
            f"так как он уже есть в боковом меню приложения (Activity Bar)"
        )

    # При этом в Activity Bar эти инструменты присутствуют
    activity_bar = soup.find(id="ide-activity-bar")
    assert activity_bar is not None, "Элемент #ide-activity-bar не найден"
    assert activity_bar.find(id="ide-nav-workspace") is not None
    assert activity_bar.find(id="ide-nav-commits") is not None
    assert activity_bar.find(id="ide-nav-diff") is not None
    assert activity_bar.find(id="ide-nav-timeline") is not None
    assert activity_bar.find(id="ide-nav-wikillm") is not None
    assert activity_bar.find(id="ide-nav-graph") is not None
    assert activity_bar.find(id="ide-nav-models") is not None
    assert activity_bar.find(id="ide-nav-rag") is not None
    assert activity_bar.find(id="ide-nav-verification") is not None
    assert activity_bar.find(id="ide-nav-plugins") is not None
    assert activity_bar.find(id="ide-nav-gmail") is not None
    assert activity_bar.find(id="ide-nav-theme-btn") is not None
    assert activity_bar.find(id="ide-nav-tour-btn") is not None


def test_no_duplicate_ids_in_index_html() -> None:
    """Проверяет полное отсутствие дубликатов атрибута id во всем документе index.html."""
    index_path = _WEBGUI_DIR / "index.html"
    assert index_path.exists(), "index.html не найден"
    html_text = index_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html_text, "html.parser")

    all_elements_with_id = soup.find_all(attrs={"id": True})
    ids = [elem["id"] for elem in all_elements_with_id]
    id_counts = Counter(ids)

    duplicates = {elem_id: count for elem_id, count in id_counts.items() if count > 1}
    assert not duplicates, f"Обнаружены дублирующиеся ID в index.html: {duplicates}"


def test_main_js_registers_brand_link_handler() -> None:
    """Проверяет регистрацию обработчика клика по брендингу в скрипте main.js."""
    main_js_path = _WEBGUI_DIR / "js" / "main.js"
    assert main_js_path.exists(), "main.js не найден"
    js_text = main_js_path.read_text(encoding="utf-8")

    assert "app-brand-link" in js_text, "Обработчик app-brand-link отсутствует в main.js"
    assert "switchMainTab('tab-workspace')" in js_text, "Вызов switchMainTab отсутствует в обработчике бренда"
