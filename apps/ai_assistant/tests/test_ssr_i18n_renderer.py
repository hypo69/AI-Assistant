# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant Tests - SSR i18n Placeholder Renderer
# =============================================================================
# Description:
#   Тесты серверного рендеринга i18n-плейсхолдеров {{key}} в HTML-шаблонах:
#   - Определение языка по query-параметрам, cookie и Accept-Language
#   - Подстановка переводов через SmartMultiDirStaticFiles (/html/tab_create_workspace/index.html)
#   - Экранирование HTML-атрибутов (placeholder, title)
#   - Отсутствие неразрешённых токенов {{...}} и кириллицы в исходном HTML-шаблоне.
#
# File: test_ssr_i18n_renderer.py
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-11 19:58:00
# =============================================================================

from __future__ import annotations

import re
from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from apps.ai_assistant.main import app
from apps.common.webgui.i18n_renderer import (
    detect_language_from_scope,
    render_i18n_placeholders,
)

_TAB_CWS_HTML = (
    Path(__file__).resolve().parent.parent
    / "api"
    / "webgui"
    / "tab_create_workspace"
    / "index.html"
)


def test_detect_language_priority() -> None:
    """Проверяет приоритет определения языка: query -> cookie -> Accept-Language -> default."""
    # 1. Query имеет наивысший приоритет над cookie и заголовком
    scope_qs = {
        "query_string": b"lang=he",
        "headers": [
            (b"cookie", b"app_language=en"),
            (b"accept-language", b"uk-UA,uk;q=0.9"),
        ],
    }
    assert detect_language_from_scope(scope_qs) == "he"

    # 2. Cookie важнее Accept-Language
    scope_cookie = {
        "query_string": b"",
        "headers": [
            (b"cookie", b"app_language=en"),
            (b"accept-language", b"ru-RU,ru;q=0.9"),
        ],
    }
    assert detect_language_from_scope(scope_cookie) == "en"

    # 3. Нормализация ua -> uk
    scope_ua = {
        "query_string": b"locale=ua",
        "headers": [],
    }
    assert detect_language_from_scope(scope_ua) == "uk"

    # 4. Accept-Language fallback
    scope_accept = {
        "query_string": b"",
        "headers": [(b"accept-language", b"he-IL,he;q=0.9,en;q=0.8")],
    }
    assert detect_language_from_scope(scope_accept) == "he"

    # 5. Default fallback
    assert detect_language_from_scope({"query_string": b"", "headers": []}) == "ru"


def test_render_i18n_placeholders_attribute_escaping_and_script_safety(tmp_path: Path) -> None:
    """Проверяет экранирование кавычек в атрибутах и неприкосновенность <script>."""
    locales_dir = tmp_path / "locales"
    locales_dir.mkdir()
    (locales_dir / "ru.json").write_text(
        '{"ui": {"btn": "Нажать <b>тут</b>"}, "titles": {"tip": "Подсказка \\"в кавычках\\" <i>ok</i>"}}',
        encoding="utf-8",
    )

    raw_html = (
        '<button data-i18n-title="titles.tip" title="{{titles.tip}}">'
        '<span data-i18n="ui.btn">{{ui.btn}}</span>'
        "</button>"
        "<script>const x = '{{ui.btn}}';</script>"
    )
    rendered = render_i18n_placeholders(raw_html, "ru", [tmp_path])

    assert 'title="Подсказка &quot;в кавычках&quot; ok"' in rendered
    assert '<span data-i18n="ui.btn">Нажать <b>тут</b></span>' in rendered
    assert "const x = '{{ui.btn}}';" in rendered


def test_tab_create_workspace_html_has_zero_hardcoded_natural_text() -> None:
    """Проверяет, что в исходном HTML tab_create_workspace/index.html нет захардкоженного текста."""
    raw = _TAB_CWS_HTML.read_text(encoding="utf-8")
    # Удаляем заголовок-комментарий с описанием файла
    body = re.sub(r"<!--.*?-->", "", raw, flags=re.DOTALL)
    # Удаляем валидные токены {{key}}
    without_tokens = re.sub(r"\{\{[a-zA-Z0-9_.-]+\}\}", "", body)

    # Не должно остаться ни одной кириллической буквы в разметке/атрибутах
    cyrillic = re.findall(r"[А-Яа-яЁё]+", without_tokens)
    assert not cyrillic, f"Обнаружен захардкоженный кириллический текст в HTML: {cyrillic}"


def _strip_comments(html_text: str) -> str:
    """Удаляет HTML-комментарии при проверке отсутствия неразрешённых токенов."""
    return re.sub(r"<!--.*?-->", "", html_text, flags=re.DOTALL)


@pytest.mark.asyncio
async def test_ssr_tab_create_workspace_renders_all_languages() -> None:
    """Проверяет SSR-отдачу /html/tab_create_workspace/index.html на 4 языках без токенов {{...}}."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Русский (по умолчанию)
        res_ru = await client.get("/html/tab_create_workspace/index.html")
        assert res_ru.status_code == 200
        assert "Создать новое пространство" in res_ru.text
        assert 'title="Вернуться к списку рабочих областей"' in res_ru.text
        assert "{{" not in _strip_comments(res_ru.text)

        # 2. Английский через ?lang=en
        res_en = await client.get("/html/tab_create_workspace/index.html?lang=en")
        assert res_en.status_code == 200
        assert "Create New Workspace" in res_en.text
        assert 'title="Back to workspaces list"' in res_en.text
        assert "{{" not in _strip_comments(res_en.text)

        # 3. Иврит через cookie app_language=he
        res_he = await client.get(
            "/html/tab_create_workspace/index.html",
            cookies={"app_language": "he"},
        )
        assert res_he.status_code == 200
        assert "יצירת מרחב עבודה חדש" in res_he.text
        assert 'title="חזרה לרשימת מרחבי העבודה"' in res_he.text
        assert "{{" not in _strip_comments(res_he.text)

        # 4. Украинский через ?lang=uk
        res_uk = await client.get("/html/tab_create_workspace/index.html?lang=uk")
        assert res_uk.status_code == 200
        assert "Створити новий простір" in res_uk.text
        assert "{{" not in _strip_comments(res_uk.text)
