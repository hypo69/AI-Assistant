# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant Tests - Tooltips Editor Tab & API Tests
# =============================================================================
# Description:
#   TDD-тесты для проверки вкладки редактора всплывающих подсказок (tab_tooltips),
#   API-эндпоинтов /api/v1/tooltips, одноразового автоперевода, сохранения,
#   отсутствия кнопок вызова AI-модели и исключения плейсхолдеров/сырых ключей.
#
# File: test_tooltips_editor_tab.py
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 17:36:00
# =============================================================================

from __future__ import annotations

from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from apps.ai_assistant.main import app

WEBGUI_DIR = Path(__file__).resolve().parent.parent / "api" / "webgui"


@pytest.mark.asyncio
async def test_tooltips_api_get_catalog() -> None:
    """Проверяет получение полного каталога подсказок через API."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/tooltips")
        assert res.status_code == 200, "Эндпоинт GET /api/v1/tooltips вернул ошибку"
        data = res.json()
        assert "tooltips" in data, "Поле 'tooltips' отсутствует в ответе"
        assert "stats" in data, "Поле 'stats' отсутствует в ответе"
        assert len(data["tooltips"]) > 0, "Каталог подсказок пуст"
        assert data["stats"]["total"] > 0, "Счетчик подсказок равен 0"

        # Проверяем структуру первой подсказки
        first = data["tooltips"][0]
        assert "key" in first
        assert "titles" in first
        assert "summaries" in first
        assert "ru" in first["titles"]


@pytest.mark.asyncio
async def test_no_placeholder_or_raw_keys_in_tooltips_catalog() -> None:
    """Проверяет отсутствие сырых ключей перевода и плейсхолдеров в каталоге тултипов."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/tooltips")
        assert res.status_code == 200
        data = res.json()
        tooltips = data.get("tooltips", [])
        
        suspicious_list = []
        for item in tooltips:
            k = item.get("key", "")
            for lang, text in item.get("titles", {}).items():
                if text == k and ("." in k or "_" in k):
                    suspicious_list.append(f"Сырой ключ вместо перевода: key='{k}' lang='{lang}' val='{text}'")
                if "Загрузка..." in str(text):
                    suspicious_list.append(f"Плейсхолдер 'Загрузка...' в заголовке: key='{k}' lang='{lang}'")
            for lang, text in item.get("summaries", {}).items():
                if text == k and ("." in k or "_" in k):
                    suspicious_list.append(f"Сырой ключ вместо описания: key='{k}' lang='{lang}' val='{text}'")
                if "Загрузка..." in str(text):
                    suspicious_list.append(f"Плейсхолдер 'Загрузка...' в описании: key='{k}' lang='{lang}'")

        assert len(suspicious_list) == 0, "\n".join(suspicious_list)


@pytest.mark.asyncio
async def test_tooltips_api_one_shot_translate() -> None:
    """Проверяет работу эндпоинта одноразового автоперевода текстов подсказки."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "text": "Рабочая область проекта",
            "source_lang": "ru",
            "target_langs": ["en", "he", "uk"]
        }
        res = await client.post("/api/v1/tooltips/translate", json=payload)
        assert res.status_code == 200, "Эндпоинт POST /api/v1/tooltips/translate вернул ошибку"
        data = res.json()
        assert "translations" in data
        assert "en" in data["translations"]
        assert "he" in data["translations"]
        assert "uk" in data["translations"]
        assert len(data["translations"]["en"]) > 0
        assert len(data["translations"]["he"]) > 0
        assert len(data["translations"]["uk"]) > 0


@pytest.mark.asyncio
async def test_tooltips_api_update_tooltip() -> None:
    """Проверяет обновление подсказки через PUT /api/v1/tooltips/{key}."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        key = "workspace"
        payload = {
            "category": "Рабочая область",
            "icon": "📁",
            "titles": {
                "ru": "Рабочее пространство",
                "en": "Workspace",
                "he": "מרחב עבודה",
                "uk": "Робочий простір"
            },
            "summaries": {
                "ru": "Рабочая область проекта со связанными файлами.",
                "en": "Project workspace with linked files.",
                "he": "מרחב עבודה של הפרויקט.",
                "uk": "Робочий простір проєкту."
            }
        }
        res = await client.put(f"/api/v1/tooltips/{key}", json=payload)
        assert res.status_code == 200, "Ошибка сохранения подсказки"
        data = res.json()
        assert data.get("status") == "ok"
        assert data.get("key") == key


@pytest.mark.asyncio
async def test_tooltips_tab_assets_served() -> None:
    """Проверяет доступность HTML и JS файлов вкладки tab_tooltips."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res_html = await client.get("/html/tab_tooltips/index.html")
        assert res_html.status_code == 200, "Вкладка /html/tab_tooltips/index.html недоступна"
        html = res_html.text
        assert 'id="tooltips-subtabs-nav"' in html, "Меню субвкладок отсутствует"
        assert 'id="tooltips-table"' in html, "Таблица подсказок отсутствует"
        assert 'id="preview-lang-switch"' in html, "Переключатель языка предпросмотра отсутствует"

        res_js = await client.get("/html/tab_tooltips/main.js")
        assert res_js.status_code == 200, "Скрипт /html/tab_tooltips/main.js недоступен"
        js = res_js.text
        assert "loadTooltips" in js
        assert "autoTranslateCurrent" in js
        assert "saveCurrentTooltip" in js


def test_tooltips_script_has_no_model_action_buttons() -> None:
    """Проверяет, что кнопки вызова модели удалены из шаблона тултипа global-tooltips-i18n.js."""
    script_path = WEBGUI_DIR / "js" / "global-tooltips-i18n.js"
    assert script_path.exists()
    content = script_path.read_text(encoding="utf-8")

    # Проверяем отсутствие кнопки вызова модели в шаблоне
    assert "id=\"ai-smart-tooltip-action-btn\"" not in content, "Кнопка вызова модели не удалена из шаблона тултипа"
    assert "Узнать больше у модели" not in content, "Текст 'Узнать больше у модели' остался в шаблоне"
    assert "Обратиться к модели за уточнением" not in content, "Текст 'Обратиться к модели' остался в шаблоне"


def test_index_html_contains_tooltips_navigation_button() -> None:
    """Проверяет наличие кнопки перехода на вкладку tooltips в index.html."""
    index_path = WEBGUI_DIR / "index.html"
    content = index_path.read_text(encoding="utf-8")
    assert 'data-tab="tab-tooltips"' in content, "Кнопка вкладки tab-tooltips отсутствует в Activity Bar"
    assert 'id="tab-tooltips"' in content, "Контейнер вкладки tab-tooltips отсутствует в mainTabContent"
