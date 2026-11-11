# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Dev Tool - HTML i18n Placeholders Migrator
# =============================================================================
# Description:
#   Инструмент аудита и миграции HTML-шаблонов WebGUI на строгий стандарт
#   i18n-плейсхолдеров {{key}} без захардкоженного текста по умолчанию:
#   - Проверяет наличие ключей в словарях locales/*.json (ru, en, he, uk)
#   - Проверяет наличие атрибута id у всех элементов с data-i18n*
#   - Заменяет текст внутри тегов и атрибуты placeholder / title / label / aria-label
#     на токены вида {{key}} (при условии существования ключа в ru.json)
#   - Поддерживает безопасный режим --dry-run и точечную миграцию --target.
#
# Usage Examples:
#   py scripts/dev/migrate_html_i18n.py --dry-run
#   py scripts/dev/migrate_html_i18n.py --apply --target apps/ai_assistant/api/webgui/tab_create_workspace/index.html
#
# File: migrate_html_i18n.py
# Package: scripts.dev
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-11 19:58:00
# =============================================================================

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple
from bs4 import BeautifulSoup, Comment, Tag

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from logger import logger
from apps.common.webgui.i18n_renderer import resolve_translation
_DEFAULT_SCAN_DIRS = (
    _PROJECT_ROOT / "apps" / "ai_assistant" / "api" / "webgui",
    _PROJECT_ROOT / "apps" / "common" / "webgui",
)
_CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]+")
_TOKEN_ONLY_RE = re.compile(r"^\{\{[a-zA-Z0-9_.-]+\}\}$")

_ATTR_MAP: Tuple[Tuple[str, str], ...] = (
    ("data-i18n-placeholder", "placeholder"),
    ("data-i18n-title", "title"),
    ("data-i18n-label", "label"),
    ("data-i18n-aria-label", "aria-label"),
)


def _load_ru_dict(webgui_dir: Path) -> Dict[str, Any]:
    """Загружает объединённый словарь ru.json для проверки существования ключей."""
    merged: Dict[str, Any] = {}
    for candidate in (
        _PROJECT_ROOT / "apps" / "common" / "webgui" / "locales" / "ru.json",
        webgui_dir / "locales" / "ru.json",
    ):
        if candidate.exists():
            data = json.loads(candidate.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                merged.update(data)
                for section in ("ui", "titles", "placeholders", "workspace", "common"):
                    if isinstance(data.get(section), dict) and isinstance(merged.get(section), dict):
                        merged[section] = {**merged[section], **data[section]}
    return merged


def _has_nested_icon_or_i18n(el: Tag) -> bool:
    """Проверяет, содержит ли элемент вложенные иконки или дочерние data-i18n узлы."""
    for child in el.find_all(True):
        if child.name in ("i", "svg") or any(a.startswith("data-i18n") for a in child.attrs):
            return True
    return False


def process_html_file(
    html_path: Path,
    ru_dict: Dict[str, Any],
    apply_changes: bool = False,
) -> Dict[str, Any]:
    """Анализирует и опционально мигрирует один HTML-файл на плейсхолдеры {{key}}."""
    raw = html_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(raw, "html.parser")

    report: Dict[str, Any] = {
        "file": str(html_path.relative_to(_PROJECT_ROOT)),
        "hardcoded_i18n_elements": 0,
        "migrated_fields": 0,
        "skipped_missing_keys": [],
        "skipped_nested_markup": [],
        "missing_ids": [],
        "unmarked_cyrillic_count": 0,
    }

    changed = False

    for el in soup.find_all(lambda t: any(a.startswith("data-i18n") for a in t.attrs)):
        if not el.get("id"):
            report["missing_ids"].append(el.get("data-i18n") or el.get("data-i18n-title") or el.name)

        # 1. Атрибуты (placeholder, title, label, aria-label)
        for i18n_attr, target_attr in _ATTR_MAP:
            key = el.get(i18n_attr)
            if not key or not isinstance(key, str):
                continue
            cur_val = str(el.get(target_attr) or "").strip()
            expected_token = f"{{{{{key}}}}}"
            if cur_val != expected_token:
                report["hardcoded_i18n_elements"] += 1
                if resolve_translation(ru_dict, key) is None:
                    report["skipped_missing_keys"].append(key)
                    continue
                if apply_changes:
                    el[target_attr] = expected_token
                    report["migrated_fields"] += 1
                    changed = True

        # 2. Текстовое содержимое (data-i18n)
        body_key = el.get("data-i18n")
        if body_key and isinstance(body_key, str):
            expected_token = f"{{{{{body_key}}}}}"
            cur_inner = el.decode_contents().strip()
            if cur_inner != expected_token:
                report["hardcoded_i18n_elements"] += 1
                if _has_nested_icon_or_i18n(el):
                    report["skipped_nested_markup"].append(f"{el.get('id') or el.name}:{body_key}")
                elif resolve_translation(ru_dict, body_key) is None:
                    report["skipped_missing_keys"].append(body_key)
                elif apply_changes:
                    el.clear()
                    el.append(expected_token)
                    report["migrated_fields"] += 1
                    changed = True

    # Подсчёт оставшейся кириллицы без data-i18n (вне HTML-комментариев и скриптов)
    for text_node in soup.find_all(string=True):
        if isinstance(text_node, Comment):
            continue
        parent_name = text_node.parent.name if text_node.parent else ""
        if parent_name in ("script", "style", "[document]"):
            continue
        txt = str(text_node).strip()
        if not txt or _TOKEN_ONLY_RE.match(txt):
            continue
        if _CYRILLIC_RE.search(txt):
            has_i18n_ancestor = any(
                any(a.startswith("data-i18n") for a in anc.attrs)
                for anc in [text_node.parent, *text_node.parent.parents]
                if isinstance(anc, Tag)
            )
            if not has_i18n_ancestor:
                report["unmarked_cyrillic_count"] += 1

    if apply_changes and changed:
        html_path.write_text(str(soup), encoding="utf-8")

    return report


def main() -> None:
    """Точка входа CLI-скрипта аудита и миграции HTML на i18n-плейсхолдеры."""
    parser = argparse.ArgumentParser(description="Аудит и миграция HTML WebGUI на плейсхолдеры {{key}}")
    parser.add_argument("--apply", action="store_true", help="Применить замену хардкода на {{key}}")
    parser.add_argument("--dry-run", action="store_true", help="Только аудит без записи файлов (по умолчанию)")
    parser.add_argument("--target", type=str, default="", help="Конкретный HTML-файл или каталог для обработки")
    args = parser.parse_args()

    apply_changes = bool(args.apply and not args.dry_run)
    targets: List[Tuple[Path, Path]] = []

    if args.target:
        t_path = Path(args.target)
        if not t_path.is_absolute():
            t_path = (_PROJECT_ROOT / t_path).resolve()
        base_webgui = t_path.parent
        for scan_dir in _DEFAULT_SCAN_DIRS:
            if scan_dir in t_path.parents or t_path == scan_dir:
                base_webgui = scan_dir
                break
        if t_path.is_file():
            targets.append((t_path, base_webgui))
        elif t_path.is_dir():
            for f in sorted(t_path.rglob("*.html")):
                targets.append((f, base_webgui))
    else:
        for scan_dir in _DEFAULT_SCAN_DIRS:
            if scan_dir.exists():
                for f in sorted(scan_dir.rglob("*.html")):
                    targets.append((f, scan_dir))

    total_hardcoded = 0
    total_migrated = 0
    total_unmarked = 0

    for html_file, webgui_dir in targets:
        ru_dict = _load_ru_dict(webgui_dir)
        rep = process_html_file(html_file, ru_dict, apply_changes=apply_changes)
        total_hardcoded += rep["hardcoded_i18n_elements"]
        total_migrated += rep["migrated_fields"]
        total_unmarked += rep["unmarked_cyrillic_count"]

        if rep["hardcoded_i18n_elements"] or rep["unmarked_cyrillic_count"] or rep["missing_ids"]:
            logger.console(
                f"[i18nAudit] {rep['file']}: хардкод_в_i18n={rep['hardcoded_i18n_elements']}, "
                f"мигрировано={rep['migrated_fields']}, без_i18n_кириллица={rep['unmarked_cyrillic_count']}, "
                f"без_id={len(rep['missing_ids'])}, пропущено_ключей={len(rep['skipped_missing_keys'])}"
            )

    logger.console(
        f"[i18nAudit] ИТОГО: файлов={len(targets)}, хардкод_в_i18n={total_hardcoded}, "
        f"мигрировано={total_migrated}, без_i18n_кириллица={total_unmarked}"
    )


if __name__ == "__main__":
    main()
