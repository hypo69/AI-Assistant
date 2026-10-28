# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant - Gmail i18n Tests
# =============================================================================
# Description:
#   Модульные тесты для проверки полной интернационализации (i18n) вкладки
#   управления почтой Gmail (tab_gmail).
#   Проверяет отсутствие русских хардкодных строк в en.json и he.json,
#   полноту словарей во всех поддерживаемых локалях (ru, en, he, uk),
#   а также поддержку реактивного переключения языка в JavaScript контроллере.
#
# File: test_gmail_i18n.py
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-27 15:55:00
# =============================================================================

from __future__ import annotations
"""Тесты валидации интернационализации (i18n) вкладки tab_gmail."""

import json
import re
from pathlib import Path
import pytest

_WEBGUI_DIR = Path(__file__).resolve().parent.parent / "api" / "webgui"
_LOCALES_DIR = _WEBGUI_DIR / "locales"
_GMAIL_DIR = _WEBGUI_DIR / "tab_gmail"


def test_gmail_locales_keys_completeness():
    """Проверяет полноту и соответствие наборов ключей во всех 4 языках для gmail."""
    locales = {}
    for lang in ["ru", "en", "he", "uk"]:
        file_path = _LOCALES_DIR / f"{lang}.json"
        assert file_path.exists(), f"Файл локали {file_path} не существует"
        locales[lang] = json.loads(file_path.read_text(encoding="utf-8"))

    ru_ui_keys = set(locales["ru"]["ui"]["gmail"].keys())
    ru_titles_keys = set(locales["ru"]["titles"]["gmail"].keys())
    ru_ph_keys = set(locales["ru"]["placeholders"]["gmail"].keys())

    for lang in ["en", "he", "uk"]:
        lang_ui_keys = set(locales[lang]["ui"]["gmail"].keys())
        lang_titles_keys = set(locales[lang]["titles"]["gmail"].keys())
        lang_ph_keys = set(locales[lang]["placeholders"]["gmail"].keys())

        assert ru_ui_keys == lang_ui_keys, f"Несовпадение ключей ui.gmail для языка {lang}"
        assert ru_titles_keys == lang_titles_keys, f"Несовпадение ключей titles.gmail для языка {lang}"
        assert ru_ph_keys == lang_ph_keys, f"Несовпадение ключей placeholders.gmail для языка {lang}"


def test_gmail_en_locale_has_no_cyrillic():
    """Проверяет, что английская локаль en.json для gmail не содержит кириллицы (хардкодного русского текста)."""
    en_file = _LOCALES_DIR / "en.json"
    en_dict = json.loads(en_file.read_text(encoding="utf-8"))

    cyrillic_pattern = re.compile(r"[\u0400-\u04FF]")

    for section in ["ui", "titles", "placeholders"]:
        gmail_sec = en_dict.get(section, {}).get("gmail", {})
        for key, val in gmail_sec.items():
            assert not cyrillic_pattern.search(val), (
                f"В английской локали en.json обнаружен русский текст в {section}.gmail.{key}: '{val}'"
            )

    # Проверка заголовков в меню ide
    assert not cyrillic_pattern.search(en_dict["ui"]["ide"]["txt_fdda44a9"])
    assert not cyrillic_pattern.search(en_dict["ui"]["ide"]["txt_97e9b1d0"])
    assert not cyrillic_pattern.search(en_dict["titles"]["ide"]["title_67bc02dd"])


def test_gmail_he_locale_has_no_cyrillic():
    """Проверяет, что иврит-локаль he.json для gmail не содержит остатков русской кириллицы."""
    he_file = _LOCALES_DIR / "he.json"
    he_dict = json.loads(he_file.read_text(encoding="utf-8"))

    cyrillic_pattern = re.compile(r"[\u0400-\u04FF]")

    for section in ["ui", "titles", "placeholders"]:
        gmail_sec = he_dict.get(section, {}).get("gmail", {})
        for key, val in gmail_sec.items():
            assert not cyrillic_pattern.search(val), (
                f"В иврит-локали he.json обнаружен русский текст в {section}.gmail.{key}: '{val}'"
            )


def test_gmail_html_has_all_data_i18n_and_unique_ids():
    """Проверяет, что каждый i18n элемент в tab_gmail/index.html имеет уникальный ID."""
    from bs4 import BeautifulSoup

    html_file = _GMAIL_DIR / "index.html"
    assert html_file.exists()
    soup = BeautifulSoup(html_file.read_text(encoding="utf-8"), "html.parser")

    i18n_elements = soup.find_all(lambda el: any(a.startswith("data-i18n") for a in el.attrs))
    ids = []
    for el in i18n_elements:
        el_id = el.get("id")
        assert el_id and el_id.strip(), f"Элемент {el.name} с i18n атрибутами не имеет id"
        ids.append(el_id)

    assert len(ids) == len(set(ids)), f"Обнаружены дубликаты ID в {html_file.name}"


def test_gmail_controller_supports_i18n_and_reactive_events():
    """Проверяет наличие обработчиков интернационализации в main.js."""
    js_file = _GMAIL_DIR / "main.js"
    assert js_file.exists()
    js_code = js_file.read_text(encoding="utf-8")

    assert "window.i18n" in js_code
    assert "i18n:languageChanged" in js_code
    assert "FOLDER_I18N_MAP" in js_code
    assert "getActiveLocale" in js_code
