# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant Tests - WebGUI i18n & Element IDs Verification
# =============================================================================
# Description:
#   Комплексный набор тестов для верификации стандартов сквозной интернационализации
#   (i18n) и уникальных идентификаторов элементов (id) в веб-интерфейсе:
#   - Проверка: каждый элемент с атрибутом data-i18n* обязательно имеет атрибут id
#   - Проверка отсутствия дублирующихся ID внутри каждого HTML-шаблона
#   - Проверка отсутствия коллизий ID между index.html и tab_workspace/index.html
#   - Проверка наличия всех используемых ключей i18n в 4 локалях (ru, en, he, uk)
#   - Проверка доступности статических файлов и разметки через REST API
#
# File: test_webgui_i18n_ids.py
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-25 23:50:00
# =============================================================================

from __future__ import annotations
"""Тесты валидации наличия ID у всех элементов с i18n и целостности локалей."""

from collections import Counter
import json
from pathlib import Path
import pytest
from bs4 import BeautifulSoup
from httpx import ASGITransport, AsyncClient

from apps.ai_assistant.main import app

_WEBGUI_DIR = Path(__file__).resolve().parent.parent / "api" / "webgui"
_LOCALES_DIR = _WEBGUI_DIR / "locales"


def test_all_i18n_elements_have_id_attribute() -> None:
    """Проверяет, что каждый элемент с data-i18n* во всех HTML файлах имеет атрибут id.

    Требование:
        «Не все элементы поддерживают i18n. У тех у кого уже есть такая поддержка
        должны иметь свой id элемента.»
    """
    html_files = sorted(list(_WEBGUI_DIR.glob("**/*.html")))
    assert html_files, "Не найдено ни одного HTML файла в apps/ai_assistant/api/webgui"

    total_i18n_found = 0
    missing_ids = []

    for html_path in html_files:
        soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
        i18n_elements = soup.find_all(lambda el: any(attr.startswith("data-i18n") for attr in el.attrs))
        total_i18n_found += len(i18n_elements)

        for el in i18n_elements:
            elem_id = el.get("id")
            if not elem_id or not elem_id.strip():
                i18n_attrs = {k: v for k, v in el.attrs.items() if k.startswith("data-i18n")}
                missing_ids.append((html_path.name, el.name, i18n_attrs))

    assert total_i18n_found > 100, f"Найдено слишком мало i18n элементов ({total_i18n_found})"
    assert not missing_ids, f"Обнаружены элементы с data-i18n без атрибута id: {missing_ids}"


def test_no_duplicate_ids_in_any_html_file() -> None:
    """Проверяет полное отсутствие дублирующихся атрибутов id внутри каждого HTML файла."""
    html_files = sorted(list(_WEBGUI_DIR.glob("**/*.html")))

    for html_path in html_files:
        soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
        all_elements_with_id = soup.find_all(attrs={"id": True})
        ids = [elem["id"] for elem in all_elements_with_id]
        id_counts = Counter(ids)

        duplicates = {elem_id: count for elem_id, count in id_counts.items() if count > 1}
        assert not duplicates, f"Дублирующиеся ID в файле {html_path.name}: {duplicates}"


def test_no_id_overlap_between_index_and_tab_workspace() -> None:
    """Проверяет отсутствие пересечений ID между index.html и динамически загружаемым tab_workspace."""
    index_path = _WEBGUI_DIR / "index.html"
    ws_path = _WEBGUI_DIR / "tab_workspace" / "index.html"

    assert index_path.exists() and ws_path.exists()

    soup_index = BeautifulSoup(index_path.read_text(encoding="utf-8"), "html.parser")
    soup_ws = BeautifulSoup(ws_path.read_text(encoding="utf-8"), "html.parser")

    ids_index = set(elem["id"] for elem in soup_index.find_all(attrs={"id": True}))
    ids_ws = set(elem["id"] for elem in soup_ws.find_all(attrs={"id": True}))

    overlap = ids_index & ids_ws
    assert not overlap, f"Обнаружено пересечение ID между index.html и tab_workspace: {overlap}"


def test_all_i18n_keys_exist_in_all_locales() -> None:
    """Проверяет, что все ключи, используемые в разметке, присутствуют во всех 4 языках (ru, en, he, uk)."""
    locales = {}
    for lang in ["ru", "en", "he", "uk"]:
        locale_path = _LOCALES_DIR / f"{lang}.json"
        assert locale_path.exists(), f"Файл локализации {lang}.json не найден"
        locales[lang] = json.loads(locale_path.read_text(encoding="utf-8"))

    def resolve_key(dictionary: dict, dot_path: str):
        parts = dot_path.split(".")
        cur = dictionary
        for part in parts:
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return None
        return cur

    missing_keys = []
    html_files = sorted(list(_WEBGUI_DIR.glob("**/*.html")))

    for html_path in html_files:
        soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
        for el in soup.find_all():
            for attr_name, attr_val in el.attrs.items():
                if attr_name.startswith("data-i18n") and isinstance(attr_val, str):
                    for lang, lang_dict in locales.items():
                        val = resolve_key(lang_dict, attr_val)
                        if val is None:
                            missing_keys.append((lang, attr_val, html_path.name))

    assert not missing_keys, f"Обнаружены отсутствующие ключи локализации: {missing_keys}"


@pytest.mark.asyncio
async def test_tab_workspace_markup_served_correctly() -> None:
    """Проверяет обслуживание статического файла tab_workspace/index.html сервером FastAPI."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/html/tab_workspace/index.html")
        assert res.status_code == 200, "tab_workspace/index.html недоступен через эндпоинт /html/"
        soup = BeautifulSoup(res.text, "html.parser")

        # Проверяем ключевые элементы с i18n и id
        header_title = soup.find(id="ws-header-title")
        assert header_title is not None
        assert header_title.get("data-i18n") == "workspace.headerTitle"

        subtab_step1 = soup.find(id="subtab-ws-step1-text")
        assert subtab_step1 is not None
        assert subtab_step1.get("data-i18n") == "workspace.subtabs.files"

        create_btn = soup.find(id="ws-create-btn-text")
        assert create_btn is not None
        assert create_btn.get("data-i18n") == "workspace.createBtn"
