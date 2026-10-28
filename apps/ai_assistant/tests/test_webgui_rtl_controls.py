# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant Tests - WebGUI RTL & Controls Layout Verification
# =============================================================================
# Description:
#   Модульные тесты для проверки двунаправленного интерфейса (RTL/LTR)
#   и упорядочивания элементов управления (кнопки закрытия модальных окон,
#   отступы, шапки диалогов) в веб-интерфейсе apps/ai_assistant/api/webgui.
#
# File: test_webgui_rtl_controls.py
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-25 23:14:00
# =============================================================================

from __future__ import annotations
"""Тесты валидации двунаправленного интерфейса RTL/LTR и упорядочивания контролов."""

import json
from pathlib import Path
import re
import pytest
from bs4 import BeautifulSoup

_WEBGUI_DIR = Path(__file__).resolve().parent.parent / "api" / "webgui"


def test_modal_headers_order_and_close_buttons() -> None:
    """Проверяет упорядочивание элементов управления в шапках модальных окон.

    В каждом модальном окне:
    1. Заголовок расположен первым (start).
    2. Кнопка .btn-close расположена вторым элементом (end).
    3. Кнопка содержит data-bs-dismiss="modal" и aria-label="Close".
    """
    html_files = [
        _WEBGUI_DIR / "index.html",
        _WEBGUI_DIR / "tab_gmail" / "index.html",
        _WEBGUI_DIR / "tab_models" / "index.html",
        _WEBGUI_DIR / "tab_plugins" / "index.html",
        _WEBGUI_DIR / "tab_theme_editor" / "index.html",
        _WEBGUI_DIR / "ai_modal_dialog" / "index.html",
        _WEBGUI_DIR / "ai_modal_dialog" / "ai_modal_dialog.html",
    ]

    for file_path in html_files:
        assert file_path.exists(), f"Файл разметки {file_path} не найден"
        soup = BeautifulSoup(file_path.read_text(encoding="utf-8"), "html.parser")
        headers = soup.find_all(class_=re.compile(r"\b(modal-header|ai-modal-header)\b"))

        for header in headers:
            close_btn = header.find(class_=re.compile(r"\bbtn-close\b"))
            if not close_btn:
                continue

            # Проверяем атрибуты кнопки закрытия
            aria_label = close_btn.get("aria-label", "")
            assert aria_label in ("Close", "Закрыть"), (
                f"Кнопка закрытия в {file_path.name} должна содержать aria-label='Close' или 'Закрыть'"
            )

            # Проверяем, что кнопка закрытия идет после заголовка (в конце шапки)
            children = [c for c in header.children if getattr(c, "name", None)]
            assert len(children) >= 2, f"Шапка в {file_path.name} должна содержать заголовок и кнопку закрытия"
            assert children[-1] == close_btn, (
                f"Кнопка закрытия в {file_path.name} должна быть последним дочерним элементом шапки"
            )


def test_rtl_stylesheet_rules() -> None:
    """Проверяет наличие и корректность правил в rtl.css и его импорт в main.css.

    Шаги:
    1. Проверяет существование rtl.css и его импорт в main.css.
    2. Проверяет, что для [dir="rtl"] кнопка .btn-close имеет margin-right: auto
       (сдвиг в левый угол).
    3. Проверяет, что для LTR кнопка .btn-close имеет margin-left: auto
       (сдвиг в правый угол).
    4. Проверяет зеркалирование утилит me-*/ms-*.
    """
    rtl_css_path = _WEBGUI_DIR / "css" / "rtl.css"
    main_css_path = _WEBGUI_DIR / "css" / "main.css"

    assert rtl_css_path.exists(), "Файл css/rtl.css не найден"
    assert main_css_path.exists(), "Файл css/main.css не найден"

    main_css = main_css_path.read_text(encoding="utf-8")
    assert 'import "rtl.css' in main_css or "import 'rtl.css" in main_css, (
        "Файл main.css должен импортировать rtl.css"
    )

    rtl_css = rtl_css_path.read_text(encoding="utf-8")

    # Проверка RTL позиционирования в левый угол
    assert '[dir="rtl"] .modal-header .btn-close' in rtl_css
    assert "margin-right: auto !important" in rtl_css
    assert "margin-left:" in rtl_css

    # Проверка LTR позиционирования в правый угол
    assert "margin-left: auto !important" in rtl_css
    assert "margin-right:" in rtl_css

    # Проверка зеркалирования отступов
    assert '[dir="rtl"] .me-1 { margin-left: 0.25rem !important;' in rtl_css
    assert '[dir="rtl"] .ms-1 { margin-right: 0.25rem !important;' in rtl_css

    # Проверка позиционирования боковой панели offcanvas
    assert '[dir="rtl"] .offcanvas.offcanvas-start' in rtl_css
    assert "right: 0 !important" in rtl_css
    assert "left: auto !important" in rtl_css


def test_early_boot_rtl_script_in_index_html() -> None:
    """Проверяет наличие ранней инициализации направления RTL в <head> index.html."""
    index_html_path = _WEBGUI_DIR / "index.html"
    content = index_html_path.read_text(encoding="utf-8")

    assert "document.documentElement.setAttribute('dir', isRtl ? 'rtl' : 'ltr');" in content or (
        'document.documentElement.setAttribute("dir", isRtl ? "rtl" : "ltr");' in content
    ), "index.html должен содержать раннюю установку атрибута dir='rtl'/'ltr' в <head>"


def test_i18n_hebrew_direction_and_close_text() -> None:
    """Проверяет настройки локализации для иврита (he.json, i18n.js, global-i18n.js)."""
    he_json_path = _WEBGUI_DIR / "locales" / "he.json"
    assert he_json_path.exists(), "Файл locales/he.json не найден"

    he_data = json.loads(he_json_path.read_text(encoding="utf-8"))
    assert "common" in he_data
    assert "close" in he_data["common"]
    assert he_data["common"]["close"] == "סגור"

    i18n_js_path = _WEBGUI_DIR / "js" / "i18n.js"
    i18n_content = i18n_js_path.read_text(encoding="utf-8")
    assert "lang === 'he'" in i18n_content and ("'rtl'" in i18n_content)

    global_i18n_path = _WEBGUI_DIR / "global-i18n.js"
    global_i18n_content = global_i18n_path.read_text(encoding="utf-8")
    assert "this.lang === 'he'" in global_i18n_content or "newLang === 'he'" in global_i18n_content


def test_ai_modal_dialog_css_rtl_rules() -> None:
    """Проверяет специфичные стили RTL для ai_modal_dialog."""
    style_css_path = _WEBGUI_DIR / "ai_modal_dialog" / "style.css"
    content = style_css_path.read_text(encoding="utf-8")

    assert '[dir="rtl"] #universal-ai-table-modal .modal-header .btn-close' in content
    assert "margin-right: auto !important" in content
    assert "margin-left: auto !important" in content


def test_user_settings_modal_elements_ids_and_i18n() -> None:
    """Проверяет наличие ID, data-i18n и комментариев для элементов модального окна настроек."""
    index_path = _WEBGUI_DIR / "index.html"
    content = index_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(content, "html.parser")

    modal = soup.find(id="userSettingsModal")
    assert modal is not None, "Модальное окно userSettingsModal не найдено"

    # Проверяем обязательные идентификаторы элементов
    required_ids = [
        "modal-user-settings-body",
        "user-settings-auth-card",
        "user-settings-profile-row",
        "user-settings-avatar",
        "user-settings-avatar-fallback",
        "user-settings-info-col",
        "user-settings-name-badge-row",
        "user-settings-name",
        "user-settings-role-badge",
        "user-settings-email",
        "user-settings-google-badge",
        "user-settings-google-oauth-label",
        "user-settings-google-status",
        "user-settings-logout-btn",
        "user-settings-guest-card",
        "user-settings-auth-desc",
        "user-settings-auth-desc-text",
        "user-settings-google-btn",
        "user-settings-google-btn-text",
        "modal-lang-container",
        "modal-lang-selector-label",
        "modal-lang-selector-text",
        "modal-lang-selector",
        "opt-lang-ru",
        "opt-lang-en",
        "opt-lang-he",
        "opt-lang-uk",
        "modal-theme-container",
        "modal-theme-selector-label",
        "modal-theme-selector-text",
        "modal-theme-selector",
        "opt-theme-system",
        "optgroup-themes-dark",
        "opt-theme-dark",
        "opt-theme-dark-slate",
        "opt-theme-cyberpunk",
        "opt-theme-terminal",
        "opt-theme-nordic-frost",
        "opt-theme-high-contrast",
        "optgroup-themes-light",
        "opt-theme-brick",
        "opt-theme-light",
        "opt-theme-light-enterprise",
        "modal-theme-editor-section",
        "modal-btn-open-theme-editor",
        "modal-btn-open-theme-editor-label",
        "modal-theme-editor-desc",
        "modal-cache-manager-section",
        "btn-open-cache-manager",
        "modal-cache-manager-btn-label",
        "modal-cache-manager-desc",
        "modal-user-settings-footer",
        "modal-user-settings-close-btn",
    ]

    for elem_id in required_ids:
        elem = modal.find(id=elem_id)
        assert elem is not None, f"Элемент с id='{elem_id}' не найден в userSettingsModal"

    # Проверяем комментарии <!-- описание --> в разметке модального окна
    modal_raw = content[content.find('id="userSettingsModal"'):content.find('<!-- Модальное окно управления браузерным кешем -->')]
    expected_comments = [
        "<!-- Тело модального окна настроек интерфейса -->",
        "<!-- Карточка авторизованного пользователя Google OAuth -->",
        "<!-- Строка профиля с аватаром и информацией о пользователе -->",
        "<!-- Фото профиля пользователя Google -->",
        "<!-- Резервная иконка аватара при отсутствии фото -->",
        "<!-- Отображаемое имя пользователя -->",
        "<!-- Бейдж системной роли пользователя -->",
        "<!-- Электронная почта пользователя -->",
        "<!-- Индикатор статуса синхронизации с Google OAuth -->",
        "<!-- Кнопка выхода из учётной записи -->",
        "<!-- Карточка гостевого режима и входа через Google OAuth -->",
        "<!-- Описание авторизации и доступа к сервисам Google -->",
        "<!-- Кнопка входа через Google OAuth 2.0 -->",
        "<!-- Контейнер выбора языка интерфейса (i18n) -->",
        "<!-- Заголовок поля выбора языка интерфейса -->",
        "<!-- Выпадающий список выбора языка интерфейса -->",
        "<!-- Опция русского языка (ru-RU) -->",
        "<!-- Опция английского языка (en-US) -->",
        "<!-- Опция иврита (he-IL) -->",
        "<!-- Опция украинского языка (uk-UA) -->",
        "<!-- Контейнер выбора темы оформления интерфейса -->",
        "<!-- Заголовок поля выбора темы оформления -->",
        "<!-- Выпадающий список тем оформления -->",
        "<!-- Системная адаптивная тема -->",
        "<!-- Группа тёмных тем интерфейса -->",
        "<!-- Стандартная тёмная тема -->",
        "<!-- Тёмная сланцевая тема Dark Slate -->",
        "<!-- Неоновая киберпанк тема Cyberpunk Neon -->",
        "<!-- Консольная тема Terminal (Matrix / CRT) -->",
        "<!-- Скандинавская морозная тема Nordic Frost -->",
        "<!-- Тема высокой контрастности High Contrast -->",
        "<!-- Группа светлых тем интерфейса -->",
        "<!-- Кирпичная тема Terracotta Brick -->",
        "<!-- Стандартная светлая тема Light / NightView -->",
        "<!-- Корпоративная светлая тема Light Enterprise -->",
        "<!-- Секция навигации в Редактор тем оформления -->",
        "<!-- Кнопка перехода в Редактор тем оформления -->",
        "<!-- Описание возможностей редактора тем -->",
        "<!-- Секция диспетчера кеша браузера -->",
        "<!-- Кнопка открытия диалога управления кешем браузера -->",
        "<!-- Описание функций управления локальными данными и дисковой квотой -->",
        "<!-- Подвал модального окна настроек с кнопкой закрытия -->",
        "<!-- Кнопка закрытия модального окна настроек -->",
    ]

    for comment in expected_comments:
        assert comment in modal_raw, f"Комментарий '{comment}' не найден в разметке userSettingsModal"


def test_user_settings_locales_hebrew_and_all_translations() -> None:
    """Проверяет полноту и корректность переводов userSettings на все поддерживаемые языки, включая иврит."""
    locales = ["he", "ru", "en", "uk"]
    required_keys = [
        "button",
        "title",
        "language",
        "languageSelectTitle",
        "theme",
        "themeSelectTitle",
        "themeLight",
        "themeBrick",
        "themeDark",
        "themeTerminal",
        "themeSystem",
        "themeDarkSlate",
        "themeCyberpunk",
        "themeNordicFrost",
        "themeHighContrast",
        "themeLightEnterprise",
        "themeSolarizedDark",
        "themeNightview",
        "themeGroupDark",
        "themeGroupLight",
        "themeGroupCustom",
        "themeEditorBtn",
        "themeEditorDesc",
        "cacheManagerBtn",
        "cacheManagerDesc",
        "googleOAuth",
        "googleSynced",
        "googleNotConnected",
        "googleSyncBtn",
        "googleDisabled",
        "logout",
        "authDesc",
        "signInGoogle",
        "userDefault",
        "close",
    ]

    for loc in locales:
        loc_path = _WEBGUI_DIR / "locales" / f"{loc}.json"
        assert loc_path.exists(), f"Файл локали {loc_path} не существует"
        data = json.loads(loc_path.read_text(encoding="utf-8"))
        assert "userSettings" in data, f"Секция userSettings отсутствует в {loc}.json"
        us = data["userSettings"]
        for key in required_keys:
            assert key in us, f"Ключ '{key}' отсутствует в {loc}.json [userSettings]"
            assert us[key], f"Значение ключа '{key}' пусто в {loc}.json [userSettings]"

    # Особая проверка для иврита: исключаем русские строки в иврите
    he_data = json.loads((_WEBGUI_DIR / "locales" / "he.json").read_text(encoding="utf-8"))
    he_us = he_data["userSettings"]
    assert "ערכת נושא" in he_us["theme"]
    assert "שפת ממשק" in he_us["language"]
    assert "עורך ערכות נושא" in he_us["themeEditorBtn"]
    assert "גדלים" in he_us["themeEditorDesc"]
    assert "מטמון דפדפן" in he_us["cacheManagerBtn"]
    assert "ניהול נתונים" in he_us["cacheManagerDesc"]
    assert "ערכות נושא כהות" in he_us["themeGroupDark"]
    assert "ערכות נושא בהירות" in he_us["themeGroupLight"]
    assert "כהה" in he_us["themeDark"]


def test_theme_engine_i18n_support() -> None:
    """Проверяет интеграцию i18n в theme-engine.js."""
    engine_path = _WEBGUI_DIR / "js" / "theme-engine.js"
    content = engine_path.read_text(encoding="utf-8")

    assert "_getThemeI18nKey(id)" in content, "Метод _getThemeI18nKey отсутствует в theme-engine.js"
    assert "_translate(key, fallback)" in content, "Метод _translate отсутствует в theme-engine.js"
    assert "languageChanged" in content, "theme-engine.js не подписан на languageChanged"
    assert "localeChanged" in content, "theme-engine.js не подписан на localeChanged"
    assert 'data-i18n-label="userSettings.themeGroupDark"' in content
    assert 'data-i18n-label="userSettings.themeGroupLight"' in content


def test_ide_activity_bar_rtl_support() -> None:
    """Проверяет RTL-поддержку панели Activity Bar, проводника файлов и вьюпорта."""
    rtl_css_path = _WEBGUI_DIR / "css" / "rtl.css"
    nav_css_path = _WEBGUI_DIR / "css" / "nav.css"
    fe_js_path = _WEBGUI_DIR / "js" / "ide_file_explorer.js"

    rtl_css = rtl_css_path.read_text(encoding="utf-8")
    nav_css = nav_css_path.read_text(encoding="utf-8")
    fe_js = fe_js_path.read_text(encoding="utf-8")

    # 1. Позиционирование Activity Bar справа в RTL
    assert '[dir="rtl"] .ide-activity-bar' in rtl_css
    assert '[dir="rtl"] .ide-activity-bar' in nav_css
    assert "right: 0 !important" in rtl_css
    assert "border-left: 1px solid" in rtl_css

    # 2. Позиционирование Side Bar справа в RTL
    assert '[dir="rtl"] .ide-file-sidebar' in rtl_css
    assert "right: 48px !important" in rtl_css
    assert "translateX(260px) !important" in rtl_css

    # 3. Отступы основного вьюпорта справа в RTL
    assert '[dir="rtl"] .ide-main-viewport' in rtl_css
    assert "margin-right: 308px !important" in rtl_css
    assert "margin-left: 0 !important" in rtl_css
    assert "margin-right: 48px !important" in rtl_css

    # 4. Дерево файлов: логические отступы и переключение шеврона
    assert "padding-inline-start" in fe_js
    assert "closedChevron" in fe_js or "bi-chevron-left" in fe_js
    assert "languageChanged" in fe_js


