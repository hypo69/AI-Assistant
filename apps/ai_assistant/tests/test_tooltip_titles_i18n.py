# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Assistant WebGUI Tests - Tooltip Titles i18n
# =============================================================================
# Description:
#   TDD-тесты для проверки интернационализации атрибутов title и всплывающих подсказок.
#   - Проверяет отсутствие непереведенных заголовков и сырых ключей (titles.ide.*) в HTML.
#   - Проверяет наличие всех ключей data-i18n-title во всех поддерживаемых локалях (ru, en, uk, he).
#   - Проверяет отсутствие хардкодных title без атрибута data-i18n-title.
#   - Проверяет корректность клиентских скриптов global-tooltips-i18n.js и global-i18n.js.
#
# File: test_tooltip_titles_i18n.py
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 17:14:12
# =============================================================================

from __future__ import annotations

import json
import re
from pathlib import Path
import pytest


WEBGUI_DIR = Path(__file__).resolve().parent.parent / "api" / "webgui"
COMMON_WEBGUI_DIR = Path(__file__).resolve().parent.parent.parent / "common" / "webgui"
SUPPORTED_LANGS = ["ru", "en", "uk", "he"]


def resolve_dotted_key(dict_obj: dict, key_str: str):
    """Рекурсивно извлекает значение по точечному ключу из словаря."""
    parts = key_str.split(".")
    cur = dict_obj
    for p in parts:
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        else:
            return None
    return cur


def test_all_data_i18n_title_keys_exist_in_all_locales() -> None:
    """Проверяет, что каждый ключ data-i18n-title, используемый в разметке HTML, присутствует во всех 4 языках."""
    # Загружаем словари локализации
    merged_locales = {}
    for lang in SUPPORTED_LANGS:
        ai_data = json.loads((WEBGUI_DIR / "locales" / f"{lang}.json").read_text(encoding="utf-8"))
        common_data = json.loads((COMMON_WEBGUI_DIR / "locales" / f"{lang}.json").read_text(encoding="utf-8"))
        merged = {}
        merged.update(common_data)
        for k, v in ai_data.items():
            if k in merged and isinstance(merged[k], dict) and isinstance(v, dict):
                merged[k] = {**merged[k], **v}
            else:
                merged[k] = v
        merged_locales[lang] = merged

    r_title_key = re.compile(r'data-i18n-title=["\']([^"\']+)["\']')
    scanned_htmls = list(WEBGUI_DIR.glob("**/*.html")) + list(COMMON_WEBGUI_DIR.glob("**/*.html"))

    missing_report = []
    for html_file in scanned_htmls:
        content = html_file.read_text(encoding="utf-8")
        keys = r_title_key.findall(content)
        for k in keys:
            if k == "key":  # Пропускаем шаблонные примеры в документации
                continue
            for lang in SUPPORTED_LANGS:
                val = resolve_dotted_key(merged_locales[lang], k)
                if val is None or val == "":
                    missing_report.append(f"Ключ '{k}' отсутствует в '{lang}' (файл: {html_file.name})")

    assert len(missing_report) == 0, "\n".join(missing_report)


def test_no_raw_translation_keys_in_title_attributes() -> None:
    """Проверяет, что ни в одном title не записан сырой ключ перевода вида titles.ide.* или titles.*."""
    scanned_htmls = list(WEBGUI_DIR.glob("**/*.html")) + list(COMMON_WEBGUI_DIR.glob("**/*.html"))
    r_raw_key = re.compile(r'(?<![-a-zA-Z0-9])title=["\'](titles\.[^"\']+)["\']')

    raw_keys_found = []
    for html_file in scanned_htmls:
        content = html_file.read_text(encoding="utf-8")
        matches = r_raw_key.findall(content)
        for m in matches:
            raw_keys_found.append(f"Сырой ключ '{m}' в {html_file.name}")

    assert len(raw_keys_found) == 0, "\n".join(raw_keys_found)


def test_no_hardcoded_titles_without_data_i18n_title() -> None:
    """Проверяет, что все теги с атрибутом title содержат сопутствующий data-i18n-title."""
    scanned_htmls = list(WEBGUI_DIR.glob("**/*.html")) + list(COMMON_WEBGUI_DIR.glob("**/*.html"))
    r_tag = re.compile(r'<[^>]+>')
    r_title = re.compile(r'(?<![-a-zA-Z0-9])title=["\']([^"\']*)["\']')

    violations = []
    for html_file in scanned_htmls:
        content = html_file.read_text(encoding="utf-8")
        for tag in r_tag.findall(content):
            m_title = r_title.search(tag)
            if m_title:
                val = m_title.group(1).strip()
                if val and "data-i18n-title=" not in tag:
                    violations.append(f"Тег без data-i18n-title в {html_file.name}: {tag[:80]}")

    assert len(violations) == 0, "\n".join(violations)


def test_tooltip_scripts_contain_dynamic_i18n_translation_logic() -> None:
    """Проверяет наличие механизмов динамического перевода заголовков в global-tooltips-i18n.js."""
    script_path = WEBGUI_DIR / "js" / "global-tooltips-i18n.js"
    assert script_path.exists()
    content = script_path.read_text(encoding="utf-8")

    # 1. Проверяем обращение к базе знаний kb
    assert "dict.kb && dict.kb[v]" in content

    # 2. Проверяем разрешение data-i18n-title в resolveElementMeta
    assert "data-i18n-title" in content
    assert "i18n.t(i18nTitleKey)" in content

    # 3. Проверяем динамический callback title в Bootstrap Tooltip
    assert "title: () =>" in content

    # 4. Проверяем обработчик события смены языка
    assert "i18n:languageChanged" in content
    assert "i18n:ready" in content


def test_global_i18n_script_updates_data_original_title() -> None:
    """Проверяет, что global-i18n.js актуализирует data-original-title и data-bs-title."""
    script_path = WEBGUI_DIR / "js" / "global-i18n.js"
    assert script_path.exists()
    content = script_path.read_text(encoding="utf-8")

    assert "el.setAttribute('data-original-title', translated)" in content
    assert "window.dispatchEvent(new CustomEvent('i18n:ready'" in content
    assert "window.dispatchEvent(new CustomEvent('i18n:languageChanged'" in content
