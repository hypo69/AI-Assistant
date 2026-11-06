"""
=============================================================================
Process Name: WebGUI Menu Maintainer - Automated Audit and Fix Tool
=============================================================================
Description:
  Инструмент автоматической проверки, контроля качества и автоисправления (--fix)
  меню суб-панелей и подменю блоков WebGUI. Обеспечивает соблюдение принципа
  «Меню - всегда меню», наличие статических тултипов без обращения к AI-модели,
  сквозное связывание i18n, двухуровневую URL-маршрутизацию и генерацию
  локального menu_config.json для Drag & Drop.

Usage Examples:
  1. Полный аудит всех вкладок WebGUI:
     py .agents/skills/webgui-menu-maintainer/scripts/menu_auditor.py audit

  2. Аудит с автоматическим исправлением (--fix):
     py .agents/skills/webgui-menu-maintainer/scripts/menu_auditor.py audit --fix

  3. Прямая команда автоисправления для конкретной вкладки:
     py .agents/skills/webgui-menu-maintainer/scripts/menu_auditor.py fix --tab tab_models

  4. Автоматическая генерация menu_config.json для вкладки:
     py .agents/skills/webgui-menu-maintainer/scripts/menu_auditor.py scaffold-config --tab tab_workspace

File: menu_auditor.py
Package: .agents/skills/webgui-menu-maintainer/scripts
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-11-01 13:30:00
=============================================================================
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


CANONICAL_COMMENT = "<!-- Блок меню переключения панелей на вкладке. Выбранная панель добавляется в url -->"


class WebGUIMenuAuditor:
    """Аудитор и автофиксер структуры навигационных меню и подменю блоков WebGUI."""

    def __init__(self, root_dir: Optional[Path] = None):
        self.root_dir = root_dir or Path(__file__).resolve().parents[4]
        self.locales_dir = self._find_locales_dir()
        self.ru_dict = self._load_dict("ru")

    def _find_locales_dir(self) -> Optional[Path]:
        candidates = [
            self.root_dir / "apps" / "ai_assistant" / "api" / "webgui" / "locales",
            self.root_dir / "apps" / "windows" / "api" / "webgui" / "locales",
        ]
        for c in candidates:
            if c.is_dir():
                return c
        return None

    def _load_dict(self, lang: str = "ru") -> Dict[str, Any]:
        if not self.locales_dir:
            return {}
        dict_file = self.locales_dir / f"{lang}.json"
        if dict_file.is_file():
            try:
                return json.loads(dict_file.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_dict(self, lang: str, data: Dict[str, Any]) -> None:
        if not self.locales_dir:
            return
        dict_file = self.locales_dir / f"{lang}.json"
        try:
            dict_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            print(f"⚠️ Не удалось сохранить {lang}.json: {e}")

    def discover_tab_directories(self) -> List[Path]:
        """Ищет все директории вкладок tab_* в проекте."""
        found = []
        search_roots = [
            self.root_dir / "apps" / "ai_assistant" / "api" / "webgui",
            self.root_dir / "apps" / "windows" / "api" / "webgui",
        ]
        for s_root in search_roots:
            if s_root.is_dir():
                for p in s_root.glob("tab_*"):
                    if p.is_dir() and (p / "index.html").is_file():
                        found.append(p)
        return sorted(found)

    def audit_tab(self, tab_dir: Path) -> Dict[str, Any]:
        """Проводит аудит разметки, скриптов и конфигурации menu_config.json вкладки."""
        tab_name = tab_dir.name
        html_file = tab_dir / "index.html"
        js_file = tab_dir / "main.js"
        config_file = tab_dir / "menu_config.json"

        html_content = html_file.read_text(encoding="utf-8") if html_file.is_file() else ""
        js_content = js_file.read_text(encoding="utf-8") if js_file.is_file() else ""

        issues = []
        passed = []

        # 1. Проверяем наличие субменю
        has_subtabs_nav = bool(
            re.search(r'id="[^"]*subtabs-nav"', html_content) or
            re.search(r'role="tablist"', html_content) or
            'data-bs-toggle="pill"' in html_content or
            'data-bs-toggle="tab"' in html_content
        )

        has_blocks_nav = bool(
            re.search(r'id="[^"]*blocks-nav"', html_content) or
            'data-block-id=' in html_content
        )

        if not has_subtabs_nav and not has_blocks_nav:
            return {
                "tab": tab_name,
                "has_menu": False,
                "issues": [],
                "passed": ["Простая вкладка без внутренних суб-панелей"]
            }

        # 2. Проверка обязательного комментария
        comment_pattern = r'<!--.*?(?:Блок меню переключения панелей|блок меню суб-вкладок).*?-->'
        if re.search(comment_pattern, html_content, re.IGNORECASE):
            passed.append("Обязательный комментарий блока меню присутствует")
        else:
            issues.append(f"Отсутствует канонический комментарий меню: {CANONICAL_COMMENT}")

        # 3. Проверка кнопок субменю
        btn_matches = re.findall(r'<button[^>]+(?:data-bs-toggle=["\'](?:pill|tab)["\']|data-panel-id=|data-block-id=)[^>]*>', html_content)
        if btn_matches:
            passed.append(f"Найдено {len(btn_matches)} кнопок суб-панелей/блоков")

            for btn in btn_matches:
                # Проверка data-bs-toggle
                if 'data-bs-toggle="tab"' in btn:
                    issues.append(f"Кнопка использует data-bs-toggle='tab' вместо канонического data-bs-toggle='pill': {btn[:70]}...")

                # Проверка стиля «Меню - всегда меню»
                if "btn-outline-" not in btn:
                    issues.append(f"Кнопка не соответствует стилю btn-outline-*: {btn[:80]}...")

                # Проверка мгновенных тултипов (БЕЗ модели)
                has_title = 'title=' in btn
                has_i18n_title = 'data-i18n-title=' in btn

                if has_title and has_i18n_title:
                    passed.append(f"Статический тултип и i18n-title присутствуют для кнопки {btn[:60]}...")
                elif not has_title and not has_i18n_title:
                    issues.append(f"Кнопка меню не имеет статического тултипа (title/data-i18n-title): {btn[:80]}...")

                # Проверка связки с i18n
                if has_i18n_title:
                    title_key_m = re.search(r'data-i18n-title="([^"]+)"', btn)
                    if title_key_m and self.ru_dict:
                        key = title_key_m.group(1)
                        if key not in self.ru_dict:
                            issues.append(f"Ключ тултипа '{key}' отсутствует в ru.json")

        # 4. Проверка поддержки URL-хэша в JS
        if has_subtabs_nav:
            if "updateUrlWithPanel" in js_content or "history.replaceState" in js_content or "location.hash" in js_content:
                passed.append("Синхронизация с URL (#tab-<id>#<panel_id>) обнаружена в скрипте")
            else:
                issues.append("В main.js отсутствует логика синхронизации URL-хэша для панелей вкладки")

        # 5. Проверка поддержки block-<id> если есть подменю блоков
        if has_blocks_nav:
            if "block-" in html_content and ("block" in js_content.lower() or "block-" in js_content):
                passed.append("Двухуровневая маршрутизация блока (#block-<block_id>) поддержана")
            else:
                issues.append("Присутствует разметка блоков data-block-id, но в скрипте main.js нет поддержки #block-<id>")

        # 6. Проверка наличия и валидности menu_config.json
        if config_file.is_file():
            try:
                cfg_data = json.loads(config_file.read_text(encoding="utf-8"))
                if cfg_data.get("draggable") is True:
                    passed.append("Локальный файл menu_config.json найден и Drag & Drop включен")
                else:
                    passed.append("Локальный файл menu_config.json найден")
            except Exception as e:
                issues.append(f"Ошибка синтаксиса в menu_config.json: {e}")
        else:
            issues.append(f"В каталоге {tab_name} отсутствует локальный menu_config.json для Drag & Drop")

        return {
            "tab": tab_name,
            "has_menu": True,
            "issues": issues,
            "passed": passed
        }

    def scaffold_menu_config(self, tab_dir: Path) -> Dict[str, Any]:
        """Автоматически генерирует menu_config.json из разметки index.html вкладки."""
        tab_name = tab_dir.name
        html_file = tab_dir / "index.html"
        if not html_file.is_file():
            raise FileNotFoundError(f"index.html не найден в {tab_dir}")

        html_content = html_file.read_text(encoding="utf-8")
        clean_tab_id = f"tab-{tab_name.replace('tab_', '')}"
        prefix = tab_name.replace('tab_', '')

        # 1. Парсим кнопки субпанелей (Уровень 1)
        subtab_buttons = re.findall(r'<button[^>]+(?:data-bs-toggle=["\'](?:pill|tab)["\'])[^>]*>.*?</button>', html_content, re.DOTALL)
        subtabs_items = []
        for idx, btn_html in enumerate(subtab_buttons):
            btn_tag = re.search(r'<button([^>]+)>', btn_html).group(1)
            b_id = re.search(r'id="([^"]+)"', btn_tag)
            p_id = re.search(r'data-panel-id="([^"]+)"', btn_tag)
            b_block = re.search(r'data-block-id="([^"]+)"', btn_tag)
            if b_block:
                # Это блок Уровня 2, пропускаем в subtabs
                continue
            t_target = re.search(r'data-bs-target="([^"]+)"', btn_tag)
            i18n_lbl = re.search(r'data-i18n="([^"]+)"', btn_html)
            i18n_title = re.search(r'data-i18n-title="([^"]+)"', btn_tag)
            title_attr = re.search(r'title="([^"]+)"', btn_tag)
            icon_m = re.search(r'<i class="([^"]+)"', btn_html)

            btn_id_val = b_id.group(1) if b_id else f"btn-{idx}"
            subtabs_items.append({
                "id": p_id.group(1).replace("panel-", "") if p_id else f"item_{idx}",
                "button_id": btn_id_val,
                "pane_id": t_target.group(1).replace("#", "") if t_target else "",
                "panel_id": p_id.group(1) if p_id else "",
                "icon": icon_m.group(1) if icon_m else "bi-card-checklist",
                "label_i18n": i18n_lbl.group(1) if i18n_lbl else "",
                "title_i18n": i18n_title.group(1) if i18n_title else "",
                "default_title": title_attr.group(1) if title_attr else "",
                "order": idx
            })

        # 2. Парсим подменю блоков (Уровень 2) если есть
        blocks_data = {}
        block_buttons = re.findall(r'<button[^>]+data-block-id=["\']([^"\']+)["\'][^>]*>.*?</button>', html_content, re.DOTALL)
        if block_buttons:
            block_items = []
            for idx, b_id_val in enumerate(block_buttons):
                m_btn = re.search(rf'<button[^>]+data-block-id=["\']{re.escape(b_id_val)}["\'][^>]*>.*?</button>', html_content, re.DOTALL)
                if not m_btn:
                    continue
                btn_str = m_btn.group(0)
                btn_tag = re.search(r'<button([^>]+)>', btn_str).group(1)
                b_id = re.search(r'id="([^"]+)"', btn_tag)
                t_target = re.search(r'data-bs-target="([^"]+)"', btn_tag)
                i18n_lbl = re.search(r'data-i18n="([^"]+)"', btn_str)
                i18n_title = re.search(r'data-i18n-title="([^"]+)"', btn_tag)
                title_attr = re.search(r'title="([^"]+)"', btn_tag)
                icon_m = re.search(r'<i class="([^"]+)"', btn_str)

                block_items.append({
                    "id": b_id_val.replace("block-", ""),
                    "button_id": b_id.group(1) if b_id else f"btn-block-{idx}",
                    "pane_id": t_target.group(1).replace("#", "") if t_target else "",
                    "block_id": b_id_val,
                    "icon": icon_m.group(1) if icon_m else "bi-grid",
                    "label_i18n": i18n_lbl.group(1) if i18n_lbl else "",
                    "title_i18n": i18n_title.group(1) if i18n_title else "",
                    "default_title": title_attr.group(1) if title_attr else "",
                    "order": idx
                })
            blocks_data["default"] = {
                "nav_id": f"{prefix}-blocks-nav",
                "storage_key": f"{clean_tab_id}_blocks_order",
                "items": block_items
            }

        config = {
            "$schema": "webgui-menu-v1",
            "tab_id": clean_tab_id,
            "draggable": True,
            "subtabs": {
                "nav_id": f"{prefix}-subtabs-nav",
                "storage_key": f"{clean_tab_id}_subtabs_order",
                "items": subtabs_items
            }
        }
        if blocks_data:
            config["blocks"] = blocks_data

        out_path = tab_dir / "menu_config.json"
        out_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
        return config

    def fix_tab(self, tab_dir: Path) -> Dict[str, Any]:
        """Автоматически исправляет разметку, тултипы, i18n, JS-роутинг и menu_config.json вкладки."""
        tab_name = tab_dir.name
        html_file = tab_dir / "index.html"
        js_file = tab_dir / "main.js"

        if not html_file.is_file():
            return {"tab": tab_name, "fixed": False, "message": "index.html не найден"}

        html_content = html_file.read_text(encoding="utf-8")
        js_content = js_file.read_text(encoding="utf-8") if js_file.is_file() else ""
        clean_tab_id = f"tab-{tab_name.replace('tab_', '')}"
        prefix = tab_name.replace('tab_', '')

        has_subtabs_nav = bool(
            re.search(r'id="[^"]*subtabs-nav"', html_content) or
            re.search(r'role="tablist"', html_content) or
            'data-bs-toggle="pill"' in html_content or
            'data-bs-toggle="tab"' in html_content
        )
        has_blocks_nav = bool(
            re.search(r'id="[^"]*blocks-nav"', html_content) or
            'data-block-id=' in html_content
        )

        if not has_subtabs_nav and not has_blocks_nav:
            return {"tab": tab_name, "fixed": False, "message": "Вкладка без меню, изменений не требуется"}

        changes_made = []
        locales = {
            "ru": self._load_dict("ru"),
            "en": self._load_dict("en"),
            "he": self._load_dict("he"),
            "uk": self._load_dict("uk"),
        }
        locales_modified = False

        # 1. Канонический комментарий
        comment_pattern = r'<!--.*?(?:Блок меню переключения панелей|блок меню суб-вкладок).*?-->'
        if not re.search(comment_pattern, html_content, re.IGNORECASE):
            # Ищем nav/tablist
            m_nav = re.search(r'([ \t]*)(<[a-zA-Z0-9_-]+[^>]+(?:id="[^"]*(?:subtabs-nav|pills-tab|TabNav|subtabs)[^"]*"|role="tablist")[^>]*>)', html_content)
            if m_nav:
                indent = m_nav.group(1)
                tag = m_nav.group(2)
                replacement = f"{indent}{CANONICAL_COMMENT}\n{indent}{tag}"
                html_content = html_content[:m_nav.start()] + replacement + html_content[m_nav.end():]
                changes_made.append("Добавлен канонический комментарий меню")
            else:
                m_hdr = re.search(r'(</div>\s*<!--\s*(?:Top Block|Контент|Содержимое)[^>]*-->|</div>\s*<div class="row)', html_content)
                if m_hdr:
                    html_content = html_content[:m_hdr.start()] + f"\n{CANONICAL_COMMENT}\n" + html_content[m_hdr.start():]
                    changes_made.append("Добавлен канонический комментарий меню")

        # 2. Исправление кнопок (стили, data-bs-toggle="pill", title, data-i18n-title)
        def replace_button(match):
            nonlocal locales_modified, changes_made
            btn_tag = match.group(1)
            inner_content = match.group(2)
            closing_tag = match.group(3)

            # data-bs-toggle="tab" -> "pill"
            if 'data-bs-toggle="tab"' in btn_tag:
                btn_tag = btn_tag.replace('data-bs-toggle="tab"', 'data-bs-toggle="pill"')
                changes_made.append("Заменен data-bs-toggle='tab' на 'pill'")

            # Класс кнопки
            cls_m = re.search(r'class="([^"]+)"', btn_tag)
            if cls_m:
                old_cls = cls_m.group(1)
                if "btn-outline-" not in old_cls:
                    is_block = 'data-block-id' in btn_tag or 'block-' in btn_tag
                    is_active = 'active' in old_cls
                    base_cls = "btn btn-sm btn-outline-secondary" if is_block else "btn btn-sm btn-outline-primary"
                    active_cls = " active" if is_active else ""
                    
                    # Извлечем полезные модификаторы расположения
                    extras = []
                    for c in old_cls.split():
                        if c in ['text-start', 'position-relative', 'w-100', 'text-truncate']:
                            extras.append(c)
                    extra_str = (" " + " ".join(extras)) if extras else ""
                    new_cls = f"{base_cls}{active_cls} d-flex align-items-center gap-1.5 py-1 px-2.5 rounded{extra_str}".strip()
                    btn_tag = btn_tag.replace(f'class="{old_cls}"', f'class="{new_cls}"')
                    changes_made.append(f"Обновлен класс кнопки: {new_cls}")

            # data-panel-id
            if 'data-panel-id=' not in btn_tag and 'data-block-id=' not in btn_tag:
                target_m = re.search(r'data-bs-target="#([^"]+)"', btn_tag) or re.search(r'aria-controls="([^"]+)"', btn_tag)
                if target_m:
                    raw_id = target_m.group(1).replace('tab-pane-', '').replace('pill-', '').replace('doc-subtab-', '')
                    panel_id = f"panel-{raw_id}"
                    btn_tag = btn_tag.replace('>', f' data-panel-id="{panel_id}">', 1)
                    changes_made.append(f"Добавлен data-panel-id='{panel_id}'")

            # Статический тултип и data-i18n-title
            has_title = 'title=' in btn_tag
            has_i18n_title = 'data-i18n-title=' in btn_tag

            if not has_title or not has_i18n_title or (has_i18n_title and locales["ru"]):
                # Извлекаем читаемую подпись
                label = ""
                span_m = re.search(r'<span[^>]*>(.*?)</span>', inner_content)
                if span_m:
                    label = re.sub(r'<[^>]+>', '', span_m.group(1)).strip()
                if not label:
                    label = re.sub(r'<[^>]+>', '', inner_content).strip()
                label = re.sub(r'\s+', ' ', label).strip()
                if not label:
                    label = "Панель"

                # Генерируем ключ и подсказку
                b_id_m = re.search(r'id="([^"]+)"', btn_tag)
                target_m = re.search(r'data-bs-target="#([^"]+)"', btn_tag)
                btn_ident = b_id_m.group(1) if b_id_m else (target_m.group(1) if target_m else "btn")
                clean_ident = re.sub(r'^(?:subtab-|nav-|pill-|btn-)', '', btn_ident).replace('-tab', '')
                
                is_block = 'data-block-id' in btn_tag or 'block-' in btn_tag
                category = "blocks" if is_block else "subtabs"
                title_key = f"{prefix}.{category}.{clean_ident}Title"

                title_ru = f"Раздел: {label}" if "раздел" not in label.lower() and len(label) < 25 else label

                if not has_title:
                    btn_tag = btn_tag.replace('>', f' title="{title_ru}">', 1)
                    changes_made.append(f"Добавлен title='{title_ru}'")
                else:
                    cur_title_m = re.search(r'title="([^"]+)"', btn_tag)
                    if cur_title_m:
                        title_ru = cur_title_m.group(1)

                if not has_i18n_title:
                    btn_tag = btn_tag.replace('>', f' data-i18n-title="{title_key}">', 1)
                    changes_made.append(f"Добавлен data-i18n-title='{title_key}'")
                else:
                    cur_key_m = re.search(r'data-i18n-title="([^"]+)"', btn_tag)
                    if cur_key_m:
                        title_key = cur_key_m.group(1)

                # Пополняем словари локалей
                if title_key not in locales["ru"]:
                    locales["ru"][title_key] = title_ru
                    locales["en"][title_key] = f"Section: {label}"
                    locales["he"][title_key] = title_ru
                    locales["uk"][title_key] = title_ru
                    locales_modified = True
                    changes_made.append(f"Добавлен ключ i18n '{title_key}' в словари")

            return btn_tag + inner_content + closing_tag

        btn_re = re.compile(r'(<button[^>]+(?:data-bs-toggle=["\'](?:pill|tab)["\']|data-panel-id=|data-block-id=)[^>]*>)(.*?)(</button>)', re.DOTALL)
        html_content = btn_re.sub(replace_button, html_content)

        # Сохраняем index.html если изменился
        if html_file.read_text(encoding="utf-8") != html_content:
            html_file.write_text(html_content, encoding="utf-8")

        # Сохраняем словари если были добавлены ключи
        if locales_modified:
            for lang, data in locales.items():
                self._save_dict(lang, data)
            self.ru_dict = locales["ru"]

        # 3. Синхронизация URL-хэша в main.js
        if js_file.is_file():
            js_text = js_file.read_text(encoding="utf-8")
            if "updateUrlWithPanel" not in js_text and "history.replaceState" not in js_text and "location.hash" not in js_text:
                sync_js = f"""
/**
 * Автоматическая синхронизация активной панели вкладки с URL-хэшем.
 */
export function initTabUrlHashRouting() {{
  const canonicalTabId = '{clean_tab_id}';
  const syncFromHash = () => {{
    const raw = window.location.hash || '';
    if (!raw.includes(canonicalTabId)) return;
    const parts = raw.replace(/^#/, '').split('#');
    const panelPart = parts.find((p) => p.startsWith('panel-'));
    if (panelPart) {{
      const btn = document.querySelector(`button[data-panel-id="${{panelPart}}"]`) ||
                  document.querySelector(`button[data-bs-target="#${{panelPart}}"]`);
      if (btn && window.bootstrap && window.bootstrap.Tab) {{
        new window.bootstrap.Tab(btn).show();
      }}
    }}
  }};

  document.addEventListener('click', (e) => {{
    const btn = e.target.closest('button[data-panel-id], button[data-bs-toggle="pill"]');
    if (btn) {{
      const panelId = btn.getAttribute('data-panel-id') || btn.getAttribute('data-bs-target')?.replace('#', '');
      const blockId = btn.getAttribute('data-block-id');
      if (panelId) {{
        let hash = `#${{canonicalTabId}}#${{panelId}}`;
        if (blockId) hash += `#${{blockId}}`;
        history.replaceState(null, null, hash);
      }}
    }}
  }});

  window.addEventListener('hashchange', syncFromHash);
  syncFromHash();
}}

if (typeof window !== 'undefined') {{
  window.initTabUrlHashRouting = initTabUrlHashRouting;
  if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', initTabUrlHashRouting);
  }} else {{
    initTabUrlHashRouting();
  }}
}}
"""
                js_file.write_text(js_text.rstrip() + "\n" + sync_js, encoding="utf-8")
                changes_made.append("Внедрена логика URL-хэш маршрутизации в main.js")

        # 4. Генерация/обновление menu_config.json
        self.scaffold_menu_config(tab_dir)
        changes_made.append("Сгенерирован актуальный menu_config.json")

        return {
            "tab": tab_name,
            "fixed": True,
            "changes": changes_made
        }

    def run_fix(self, target_tab: Optional[str] = None) -> List[Dict[str, Any]]:
        """Запускает автоматическое исправление для всех или выбранной вкладки."""
        tabs = self.discover_tab_directories()
        results = []
        for t_dir in tabs:
            if target_tab and t_dir.name != target_tab:
                continue
            res = self.fix_tab(t_dir)
            results.append(res)
        return results

    def run_audit(self, target_tab: Optional[str] = None) -> List[Dict[str, Any]]:
        """Запускает полный аудит всех или выбранной вкладки."""
        tabs = self.discover_tab_directories()
        results = []
        for t_dir in tabs:
            if target_tab and t_dir.name != target_tab:
                continue
            res = self.audit_tab(t_dir)
            results.append(res)
        return results


def main():
    parser = argparse.ArgumentParser(description="WebGUI Menu Maintainer CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit_parser = subparsers.add_parser("audit", help="Проверить меню вкладок на соответствие стандарту")
    audit_parser.add_argument("--tab", default=None, help="Имя конкретной вкладки для аудита (напр. tab_workspace)")
    audit_parser.add_argument("--fix", action="store_true", help="Автоматически исправить выявленные замечания")
    audit_parser.add_argument("--json", action="store_true", help="Вывод результатов в формате JSON")

    fix_parser = subparsers.add_parser("fix", help="Автоматически исправить разметку и привести к стандарту меню")
    fix_parser.add_argument("--tab", default=None, help="Имя конкретной вкладки (напр. tab_models)")
    fix_parser.add_argument("--json", action="store_true", help="Вывод результатов в формате JSON")

    scaffold_parser = subparsers.add_parser("scaffold-config", help="Сгенерировать menu_config.json для вкладки")
    scaffold_parser.add_argument("--tab", required=True, help="Имя вкладки (напр. tab_workspace)")

    args = parser.parse_args()
    auditor = WebGUIMenuAuditor()

    if args.command in ("audit", "fix"):
        is_fix_mode = (args.command == "fix") or getattr(args, "fix", False)

        if is_fix_mode:
            print("🔧 Запуск режима автоисправления (--fix)...")
            fix_results = auditor.run_fix(args.tab)
            for fr in fix_results:
                if fr.get("fixed"):
                    print(f"  ✓ {fr['tab']}: исправлено ({len(fr.get('changes', []))} изменений)")
                    for ch in fr.get("changes", []):
                        print(f"      - {ch}")

        # Повторно аудируем для финального отчета
        results = auditor.run_audit(args.tab)

        if getattr(args, "json", False):
            print(json.dumps(results, indent=2, ensure_ascii=False))
            total_issues = sum(len(r["issues"]) for r in results if r["has_menu"])
            sys.exit(1 if total_issues > 0 else 0)

        print("\n" + "=" * 75)
        print("  📋 ОТЧЁТ АУДИТА МЕНЮ ПАНЕЛЕЙ И ПОДМЕНЮ БЛОКОВ WEBGUI")
        print("=" * 75)

        total_menus = sum(1 for r in results if r["has_menu"])
        total_issues = sum(len(r["issues"]) for r in results if r["has_menu"])

        for r in results:
            if not r["has_menu"]:
                continue
            tab_name = r["tab"]
            issues_cnt = len(r["issues"])
            status_icon = "❌" if issues_cnt > 0 else "✅"

            print(f"\n{status_icon} Вкладка: {tab_name} (Замечаний: {issues_cnt})")
            for p in r["passed"]:
                print(f"   ✓ {p}")
            for iss in r["issues"]:
                print(f"   ! [WARNING] {iss}")

        print("\n" + "=" * 75)
        print(f"Итого проверено меню вкладок: {total_menus}. Замечаний: {total_issues}.")
        print("=" * 75)

        if total_issues > 0:
            print("\n❌ Обнаружены замечания! Меню не соответствует стандарту.")
            sys.exit(1)
        else:
            print("\n✅ Все проверенные меню строго соответствуют стандарту WebGUI!")
            sys.exit(0)

    elif args.command == "scaffold-config":
        tab_dirs = [d for d in auditor.discover_tab_directories() if d.name == args.tab]
        if not tab_dirs:
            print(f"❌ Директория вкладки '{args.tab}' не найдена")
            sys.exit(1)
        cfg = auditor.scaffold_menu_config(tab_dirs[0])
        print(f"✅ Успешно создан menu_config.json для {args.tab}:")
        print(json.dumps(cfg, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
