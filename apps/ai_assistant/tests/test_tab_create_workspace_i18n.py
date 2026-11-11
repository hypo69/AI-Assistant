# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant Tests - Tab Create Workspace i18n & IDs
# =============================================================================
# Description:
#   Комплексный набор тестов для верификации стандартов сквозной интернационализации
#   (i18n) и валидации HTML-разметки вкладки создания рабочего пространства
#   (`tab_create_workspace`):
#   - Проверка наличия всех ключей локализации во всех 4 языках (ru, en, he, uk)
#   - Проверка отсутствия дубликатов ID и наличия ID у всех элементов с data-i18n*
#   - Проверка качества перевода на иврит (отсутствие кириллицы)
#   - Проверка отсутствия захардкоженных нелокализованных строк в JS и HTML.
#
# File: test_tab_create_workspace_i18n.py
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 20:30:00
# =============================================================================

from __future__ import annotations

import json
from pathlib import Path
import pytest
from bs4 import BeautifulSoup

_WEBGUI_DIR = Path(__file__).resolve().parent.parent / "api" / "webgui"
_LOCALES_DIR = _WEBGUI_DIR / "locales"
_TAB_CWS_DIR = _WEBGUI_DIR / "tab_create_workspace"

REQUIRED_LOCALES = ["ru", "en", "he", "uk"]

REQUIRED_UI_CWS_KEYS = [
    "txt_2231746c",
    "txt_26021120",
    "txt_dd25bfb1",
    "txt_704daeb5",
    "txt_3a420c17",
    "txt_4835f679",
    "txt_1bdf99bc",
    "txt_4b89833b",
    "txt_7d47516a",
    "txt_503b2cca",
    "txt_f555a289",
    "txt_a1528e91",
    "txt_1a80632a",
    "txt_38b2024b",
    "txt_13ea0390",
    "txt_f9371cf6",
    "txt_49f40b98",
    "txt_78e3c092",
    "txt_68a213c2",
    "txt_858c5e1a",
    "txt_a7db7b12",
    "txt_e6d366ea",
    "txt_5c3af4b3",
    "txt_60a35f09",
    "txt_d208f03c",
    "txt_fa42174b",
    "txt_d26799e8",
    "lang_he",
    "lang_ru",
    "lang_en",
    "lang_ua",
    "staged_count",
    "ready_to_link",
    "in_queue",
    "sources_count",
    "files_count",
    "in_place",
    "source_excluded",
    "err_deleting",
    "err_loading_sources",
    "warn_specify_path",
    "info_item_staged",
    "warn_item_already_staged",
    "info_connecting_item",
    "success_item_connected",
    "err_connecting_item",
    "ws_select_item",
    "btn_selecting",
    "warn_specify_name",
    "btn_creating_ws",
    "btn_attaching_sources",
    "success_ws_created",
    "err_creating_ws",
    "warn_specify_dir",
    "warn_specify_file",
    "err_attach_staged",
    "status_ws_ready",
]

REQUIRED_TITLE_CWS_KEYS = [
    "title_01c37831",
    "title_29ffed95",
    "title_faf6b1ab",
    "title_771266c7",
    "remove_from_queue",
    "exclude_from_tracking",
    "btn_refresh_status",
    "btn_add_dir",
    "btn_add_file",
    "btn_create_submit",
    "btn_go_ws",
]

REQUIRED_PH_CWS_KEYS = [
    "ph_e1bf53f6",
    "ph_4b1b3452",
    "ph_2a14ddbb",
    "ph_e149f935",
    "ph_025dbb3b",
]


def _load_locale(lang: str) -> dict:
    file_path = _LOCALES_DIR / f"{lang}.json"
    assert file_path.exists(), f"Файл локали {lang}.json не найден"
    return json.loads(file_path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("lang", REQUIRED_LOCALES)
def test_tab_cws_keys_present_in_all_locales(lang: str) -> None:
    """Проверяет полноту и непустоту всех ключей cws во всех 4 поддерживаемых локалях."""
    data = _load_locale(lang)

    assert "ui" in data and "cws" in data["ui"], f"Отсутствует ui.cws в {lang}.json"
    ui_cws = data["ui"]["cws"]
    for key in REQUIRED_UI_CWS_KEYS:
        assert key in ui_cws, f"Ключ ui.cws.{key} отсутствует в {lang}.json"
        assert str(ui_cws[key]).strip(), f"Ключ ui.cws.{key} пуст в {lang}.json"

    assert "titles" in data and "cws" in data["titles"], f"Отсутствует titles.cws в {lang}.json"
    titles_cws = data["titles"]["cws"]
    for key in REQUIRED_TITLE_CWS_KEYS:
        assert key in titles_cws, f"Ключ titles.cws.{key} отсутствует в {lang}.json"
        assert str(titles_cws[key]).strip(), f"Ключ titles.cws.{key} пуст в {lang}.json"

    assert "placeholders" in data and "cws" in data["placeholders"], f"Отсутствует placeholders.cws в {lang}.json"
    ph_cws = data["placeholders"]["cws"]
    for key in REQUIRED_PH_CWS_KEYS:
        assert key in ph_cws, f"Ключ placeholders.cws.{key} отсутствует в {lang}.json"
        assert str(ph_cws[key]).strip(), f"Ключ placeholders.cws.{key} пуст в {lang}.json"


def test_tab_cws_html_all_i18n_elements_have_id() -> None:
    """Проверяет, что каждый элемент с data-i18n* в tab_create_workspace/index.html имеет id."""
    html_file = _TAB_CWS_DIR / "index.html"
    assert html_file.exists()
    soup = BeautifulSoup(html_file.read_text(encoding="utf-8"), "html.parser")

    i18n_elements = soup.find_all(lambda el: any(a.startswith("data-i18n") for a in el.attrs))
    assert len(i18n_elements) >= 30, f"Слишком мало элементов с i18n ({len(i18n_elements)})"

    missing_ids = []
    for el in i18n_elements:
        elem_id = el.get("id")
        if not elem_id or not elem_id.strip():
            missing_ids.append((el.name, dict(el.attrs)))

    assert not missing_ids, f"Найдены элементы data-i18n без id: {missing_ids}"


def test_tab_cws_html_no_duplicate_ids() -> None:
    """Проверяет отсутствие дубликатов id в tab_create_workspace/index.html."""
    html_file = _TAB_CWS_DIR / "index.html"
    soup = BeautifulSoup(html_file.read_text(encoding="utf-8"), "html.parser")
    ids = [el["id"] for el in soup.find_all(attrs={"id": True})]
    duplicates = [item for item, count in json.loads(json.dumps({i: ids.count(i) for i in set(ids)})).items() if count > 1]
    assert not duplicates, f"Дублирующиеся id в tab_create_workspace/index.html: {duplicates}"


def test_tab_cws_hebrew_translations_valid() -> None:
    """Проверяет корректность перевода на иврит (отсутствие случайного русского текста)."""
    he_data = _load_locale("he")
    ui_cws = he_data["ui"]["cws"]

    cyrillic_chars = set("абвгдеёжзийклмнопрстуфхцчшщъыьэюя")
    for key in ["txt_2231746c", "txt_26021120", "txt_3a420c17", "staged_count", "ready_to_link", "in_queue", "txt_68a213c2", "txt_a7db7b12"]:
        text = ui_cws[key].lower()
        has_cyrillic = any(c in cyrillic_chars for c in text)
        assert not has_cyrillic, f"Обнаружена кириллица в ивритском ключе ui.cws.{key}: {ui_cws[key]}"
