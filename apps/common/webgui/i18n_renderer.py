# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Common WebGUI - SSR i18n Placeholder Renderer
# =============================================================================
# Description:
#   Серверный рендерер i18n-плейсхолдеров вида {{dot.path.key}} в HTML-шаблонах.
#   Обеспечивает:
#   - Нулевой хардкод языковых строк в исходных HTML-файлах
#   - Автоматическое определение языка запроса (query -> cookie -> Accept-Language -> default)
#   - Кэширование словарей локализации с отслеживанием mtime файлов
#   - Безопасное HTML-экранирование при подстановке внутрь значений атрибутов
#   - Мгновенный отклик без мерцания непереведённых токенов (FOUT).
#
# File: i18n_renderer.py
# Project: ai-windows-admin
# Package: apps.common.webgui
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-11 19:52:00
# =============================================================================

from __future__ import annotations

import html
import json
import re
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple
from urllib.parse import parse_qs

from logger import logger

SUPPORTED_LANGS: Tuple[str, ...] = ("ru", "en", "he", "uk")
RTL_LANGS: Tuple[str, ...] = ("he", "ar")
DEFAULT_LANG: str = "ru"

# Токен строго вида {{section.sub.key}} (исключает JS/шаблонные выражения с пробелами)
_PLACEHOLDER_PATTERN = re.compile(r"\{\{([a-zA-Z0-9_.-]+)\}\}")
_HTML_TAG_LANG_PATTERN = re.compile(r"<html\b([^>]*)>", re.IGNORECASE)
_STRIP_TAGS_PATTERN = re.compile(r"<[^>]+>")

# Кэш объединённых словарей: (tuple(locales_dirs), lang) -> (mtime_signature, merged_dict)
_LOCALE_CACHE: Dict[Tuple[Tuple[str, ...], str], Tuple[Tuple[Tuple[str, int], ...], Dict[str, Any]]] = {}


def normalize_lang_code(raw_tag: Optional[str]) -> Optional[str]:
    """Нормализует тег языка/локали (ru-RU, ua, he_IL) к поддерживаемому коду.

    Args:
        raw_tag (Optional[str]): Исходный языковой тег.

    Returns:
        Optional[str]: Код языка из SUPPORTED_LANGS или None, если язык не поддерживается.
    """
    if not raw_tag or not isinstance(raw_tag, str):
        return None
    cleaned = raw_tag.strip().strip("`'\"").lower().replace("_", "-")
    if not cleaned:
        return None
    base = cleaned.split("-")[0]
    if base == "ua":
        base = "uk"
    return base if base in SUPPORTED_LANGS else None


def detect_language_from_scope(scope: Mapping[str, Any], default_lang: str = DEFAULT_LANG) -> str:
    """Определяет целевой язык интерфейса из ASGI scope запроса.

    Приоритет:
        1. Параметры URL query (`lang`, `locale`, `region`, `language-region`, `language_region`, `language`)
        2. Cookies (`app_language`, `app_locale`)
        3. Заголовок `Accept-Language`
        4. Значение по умолчанию (`default_lang`)

    Args:
        scope (Mapping[str, Any]): Словарь ASGI scope.
        default_lang (str, optional): Язык по умолчанию. По умолчанию "ru".

    Returns:
        str: Нормализованный код языка.
    """
    # 1. URL query string
    raw_qs = scope.get("query_string", b"")
    if isinstance(raw_qs, (bytes, bytearray)) and raw_qs:
        try:
            qs = parse_qs(raw_qs.decode("utf-8", errors="ignore"))
            for param in ("lang", "locale", "region", "language-region", "language_region", "language"):
                vals = qs.get(param)
                if vals:
                    detected = normalize_lang_code(vals[0])
                    if detected:
                        return detected
        except Exception as exc:
            logger.warning(f"[i18nSSR] Ошибка разбора query_string: {exc}")

    # Извлечение заголовков в нижнем регистре
    headers: Dict[str, str] = {}
    for k, v in scope.get("headers", ()) or ():
        if isinstance(k, (bytes, bytearray)) and isinstance(v, (bytes, bytearray)):
            headers[k.decode("latin-1").lower()] = v.decode("latin-1")

    # 2. Cookies
    cookie_header = headers.get("cookie", "")
    if cookie_header:
        try:
            cookie: SimpleCookie = SimpleCookie()
            cookie.load(cookie_header)
            for key in ("app_language", "app_locale"):
                morsel = cookie.get(key)
                if morsel and morsel.value:
                    detected = normalize_lang_code(morsel.value)
                    if detected:
                        return detected
        except Exception as exc:
            logger.warning(f"[i18nSSR] Ошибка разбора cookie: {exc}")

    # 3. Accept-Language
    accept_lang = headers.get("accept-language", "")
    if accept_lang:
        for part in accept_lang.split(","):
            lang_part = part.split(";")[0].strip()
            detected = normalize_lang_code(lang_part)
            if detected:
                return detected

    return default_lang if default_lang in SUPPORTED_LANGS else DEFAULT_LANG


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Рекурсивно объединяет два словаря локализации без мутации исходников."""
    result = dict(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result


def load_merged_locale(lang: str, webgui_dirs: Sequence[Path]) -> Dict[str, Any]:
    """Загружает и объединяет словари локализации из переданных директорий WebGUI.

    Порядок приоритета: более ранний каталог в `webgui_dirs` имеет более высокий
    приоритет (переопределяет общие переводы). Результат кэшируется с проверкой mtime.

    Args:
        lang (str): Код языка (`ru`, `en`, `he`, `uk`).
        webgui_dirs (Sequence[Path]): Директории WebGUI в порядке убывания приоритета.

    Returns:
        Dict[str, Any]: Объединённый словарь переводов.
    """
    norm_lang = normalize_lang_code(lang) or DEFAULT_LANG
    # Для каскадного слияния идём от базовых (конец списка) к приоритетным (начало)
    ordered_dirs = [Path(d).resolve() for d in reversed(webgui_dirs) if d]
    cache_key = (tuple(str(d) for d in ordered_dirs), norm_lang)

    locale_files = [d / "locales" / f"{norm_lang}.json" for d in ordered_dirs]
    signature = tuple(
        (str(f), f.stat().st_mtime_ns if f.exists() else -1)
        for f in locale_files
    )

    cached = _LOCALE_CACHE.get(cache_key)
    if cached and cached[0] == signature:
        return cached[1]

    merged: Dict[str, Any] = {}
    for loc_file in locale_files:
        if not loc_file.exists():
            continue
        try:
            data = json.loads(loc_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                merged = _deep_merge(merged, data)
        except Exception as exc:
            logger.error(f"[i18nSSR] Ошибка чтения словаря {loc_file}: {exc}")

    _LOCALE_CACHE[cache_key] = (signature, merged)
    return merged


def resolve_translation(dictionary: Dict[str, Any], dot_key: str) -> Optional[str]:
    """Ищет значение перевода по точечному или плоскому ключу.

    Args:
        dictionary (Dict[str, Any]): Словарь локализации.
        dot_key (str): Ключ вида `ui.cws.txt_2231746c`.

    Returns:
        Optional[str]: Строка перевода или None, если ключ не найден.
    """
    if dot_key in dictionary and not isinstance(dictionary[dot_key], dict):
        val = dictionary[dot_key]
        return str(val) if val is not None else None

    current: Any = dictionary
    for part in dot_key.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None

    if current is None or isinstance(current, dict):
        return None
    return str(current)


def _is_inside_html_attribute(text: str, pos: int) -> bool:
    """Определяет, находится ли позиция `pos` внутри HTML-атрибута открывающего тега."""
    last_lt = text.rfind("<", 0, pos)
    last_gt = text.rfind(">", 0, pos)
    if last_lt <= last_gt:
        return False

    snippet = text[last_lt:pos]
    in_single = False
    in_double = False
    for ch in snippet:
        if ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "'" and not in_double:
            in_single = not in_single
    return in_single or in_double


def _is_inside_script_or_style(text: str, pos: int) -> bool:
    """Проверяет, находится ли позиция внутри тегов `<script>` или `<style>`."""
    prefix_lower = text[:pos].lower()
    for tag in ("script", "style"):
        last_open = prefix_lower.rfind(f"<{tag}")
        if last_open != -1:
            last_close = prefix_lower.rfind(f"</{tag}")
            if last_close < last_open:
                return True
    return False


def _apply_html_dir_and_lang(html_text: str, lang: str) -> str:
    """Синхронизирует атрибуты `lang` и `dir` корневого тега `<html>` при SSR."""
    target_dir = "rtl" if lang in RTL_LANGS else "ltr"

    def _replace_html_attrs(match: re.Match[str]) -> str:
        attrs = match.group(1) or ""
        if re.search(r'\blang\s*=', attrs, re.IGNORECASE):
            attrs = re.sub(r'\blang\s*=\s*["\'][^"\']*["\']', f'lang="{lang}"', attrs, flags=re.IGNORECASE)
        else:
            attrs = f'{attrs} lang="{lang}"'

        if re.search(r'\bdir\s*=', attrs, re.IGNORECASE):
            attrs = re.sub(r'\bdir\s*=\s*["\'][^"\']*["\']', f'dir="{target_dir}"', attrs, flags=re.IGNORECASE)
        else:
            attrs = f'{attrs} dir="{target_dir}"'
        return f"<html{attrs}>"

    return _HTML_TAG_LANG_PATTERN.sub(_replace_html_attrs, html_text, count=1)


def render_i18n_placeholders(html_text: str, lang: str, webgui_dirs: Sequence[Path]) -> str:
    """Заменяет i18n-плейсхолдеры `{{key}}` в HTML на переводы выбранного языка.

    Особенности:
        - Если ключ отсутствует в выбранной локали, используется каскадный fallback на `ru`.
        - Если ключ не найден ни в одном словаре, токен `{{key}}` остаётся в разметке
          (Fail-Fast визуализация отсутствующего перевода).
        - Внутри HTML-атрибутов (`placeholder="..."`, `title="..."`) значения
          автоматически экранируются и очищаются от тегов.
        - Внутри блоков `<script>` и `<style>` замены не производятся.

    Args:
        html_text (str): Исходный HTML с плейсхолдерами `{{key}}`.
        lang (str): Целевой код языка.
        webgui_dirs (Sequence[Path]): Директории WebGUI для поиска словарей `locales/*.json`.

    Returns:
        str: Отрендеренный HTML.
    """
    norm_lang = normalize_lang_code(lang) or DEFAULT_LANG
    rendered_text = _apply_html_dir_and_lang(html_text, norm_lang)

    if "{{" not in rendered_text:
        return rendered_text

    primary_dict = load_merged_locale(norm_lang, webgui_dirs)
    fallback_dict = (
        load_merged_locale(DEFAULT_LANG, webgui_dirs)
        if norm_lang != DEFAULT_LANG
        else primary_dict
    )

    def _substitute(match: re.Match[str]) -> str:
        pos = match.start()
        if _is_inside_script_or_style(rendered_text, pos):
            return match.group(0)

        dot_key = match.group(1)
        translated = resolve_translation(primary_dict, dot_key)
        if translated is None and fallback_dict is not primary_dict:
            translated = resolve_translation(fallback_dict, dot_key)

        if translated is None:
            return match.group(0)

        if _is_inside_html_attribute(rendered_text, pos):
            plain_attr = _STRIP_TAGS_PATTERN.sub("", translated)
            return html.escape(plain_attr, quote=True)

        return translated

    return _PLACEHOLDER_PATTERN.sub(_substitute, rendered_text)
