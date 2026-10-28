# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant - Standard IDE Plugins Marketplace
# =============================================================================
# Description:
#   Каталог стандартных плагинов расширения в стиле VS Code Marketplace.
#   Обеспечивает формирование метаданных, генерацию шаблонного кода плагинов,
#   установку в каталог plugins/user-plugins и корректное удаление модулей.
#
# Usage Examples:
#   catalog = get_marketplace_catalog(installed_names)
#   install_marketplace_plugin("sqlite_db_viewer")
#   uninstall_user_plugin("sqlite_db_viewer")
#
# File: plugins_marketplace.py
# Package: apps.ai_assistant.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 18:45:00
# =============================================================================

from __future__ import annotations

"""Каталог стандартных плагинов расширения IDE и менеджер установки."""

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from header import __root__
from logger import logger

# Каталог стандартных расширений IDE
STANDARD_MARKETPLACE_CATALOG: List[Dict[str, Any]] = [
    {
        "id": "sqlite_db_viewer",
        "title": "SQLite & Telemetry Explorer",
        "title_i18n": {"ru": "SQLite и Телеметрия Explorer", "en": "SQLite & Telemetry Explorer"},
        "version": "1.2.0",
        "author": "hypo69",
        "category": "Databases & Telemetry",
        "icon": "🗄️",
        "rating": 4.9,
        "downloads": "24.5k",
        "description": "Интерактивный просмотр таблиц SQLite, телеметрии процессов и выполнение прямых SQL-запросов в IDE.",
        "description_i18n": {
            "ru": "Интерактивный просмотр таблиц SQLite, телеметрии процессов и выполнение прямых SQL-запросов в IDE.",
            "en": "Interactive SQLite tables inspector, process telemetry viewer, and direct SQL executor in IDE.",
        },
        "default_config": {
            "default_db_path": "data/telemetry.db",
            "max_query_rows": 100,
            "auto_refresh_sec": 5,
        },
    },
    {
        "id": "python_ide_tools",
        "title": "Python Language Tools & Linter",
        "title_i18n": {"ru": "Python IDE Tools и Линтер", "en": "Python Language Tools & Linter"},
        "version": "2.0.1",
        "author": "AI Assistant Team",
        "category": "Programming Languages",
        "icon": "🐍",
        "rating": 5.0,
        "downloads": "48.2k",
        "description": "Поддержка Python: проверка синтаксиса PEP 8, автодополнение, запуск тестов pytest и валидация импортов.",
        "description_i18n": {
            "ru": "Поддержка Python: проверка синтаксиса PEP 8, автодополнение, запуск тестов pytest и валидация импортов.",
            "en": "Rich Python support: PEP 8 linting, autocompletion, pytest runner, and imports validation.",
        },
        "default_config": {
            "lint_on_save": True,
            "flake8_max_line_length": 120,
            "pytest_args": "-v",
        },
    },
    {
        "id": "markdown_notes",
        "title": "Markdown & Obsidian Notes Hub",
        "title_i18n": {"ru": "Заметки Markdown и Obsidian Hub", "en": "Markdown & Obsidian Notes Hub"},
        "version": "1.4.0",
        "author": "hypo69",
        "category": "Documentation & Notes",
        "icon": "📝",
        "rating": 4.8,
        "downloads": "19.8k",
        "description": "Просмотрщик и редактор заметок со встроенным рендером Math/Mermaid и поддержкой ссылок Obsidian Vault.",
        "description_i18n": {
            "ru": "Просмотрщик и редактор заметок со встроенным рендером Math/Mermaid и поддержкой ссылок Obsidian Vault.",
            "en": "Markdown notes editor with KaTeX math, Mermaid diagrams, and Obsidian Vault links integration.",
        },
        "default_config": {
            "vault_dir": "docs/obsidian",
            "enable_mermaid": True,
            "enable_katex": True,
        },
    },
    {
        "id": "gitlens_inspector",
        "title": "GitLens & Code History",
        "title_i18n": {"ru": "GitLens и Хронология Кода", "en": "GitLens & Code History"},
        "version": "1.5.0",
        "author": "AI Assistant Team",
        "category": "SCM & Version Control",
        "icon": "🔍",
        "rating": 4.9,
        "downloads": "36.1k",
        "description": "Визуализация истории строк (blame), просмотр веток, детальный аудит коммитов и изменений в реальном времени.",
        "description_i18n": {
            "ru": "Визуализация истории строк (blame), просмотр веток, детальный аудит коммитов и изменений в реальном времени.",
            "en": "Inline Git blame annotations, branch visualizer, and commit history audit in real time.",
        },
        "default_config": {
            "show_inline_blame": True,
            "max_commit_history": 50,
        },
    },
    {
        "id": "ai_copilot_assistant",
        "title": "AI Code Copilot & Refactorer",
        "title_i18n": {"ru": "ИИ Копилот и Авто-Рефакторинг", "en": "AI Code Copilot & Refactorer"},
        "version": "2.1.0",
        "author": "hypo69",
        "category": "AI Assistants",
        "icon": "🤖",
        "rating": 4.9,
        "downloads": "52.7k",
        "description": "Автономный ИИ-помощник для генерации кода, объяснения ошибок и авто-рефакторинга по стандартам проекта.",
        "description_i18n": {
            "ru": "Автономный ИИ-помощник для генерации кода, объяснения ошибок и авто-рефакторинга по стандартам проекта.",
            "en": "Autonomous AI coding companion for smart refactoring, code explanation, and bug fixing.",
        },
        "default_config": {
            "model_provider": "gemini",
            "temperature": 0.2,
            "auto_suggest": True,
        },
    },
    {
        "id": "rest_api_client",
        "title": "REST API & HTTP Client",
        "title_i18n": {"ru": "REST Клиент и Тестирование API", "en": "REST API & HTTP Client"},
        "version": "1.1.0",
        "author": "AI Assistant Team",
        "category": "Network & Debugging",
        "icon": "⚡",
        "rating": 4.7,
        "downloads": "15.3k",
        "description": "Инструмент для тестирования REST эндпоинтов, отправки HTTP/JSON запросов и инспекции ответов.",
        "description_i18n": {
            "ru": "Инструмент для тестирования REST эндпоинтов, отправки HTTP/JSON запросов и инспекции ответов.",
            "en": "Interactive HTTP & REST request runner with headers, payload, and response viewer.",
        },
        "default_config": {
            "timeout_sec": 30,
            "follow_redirects": True,
        },
    },
    {
        "id": "docker_manager",
        "title": "Docker & Container Monitor",
        "title_i18n": {"ru": "Монитор Контейнеров Docker", "en": "Docker & Container Monitor"},
        "version": "1.0.4",
        "author": "AI Assistant Team",
        "category": "DevOps & Containers",
        "icon": "🐳",
        "rating": 4.6,
        "downloads": "11.8k",
        "description": "Мониторинг запущенных контейнеров Docker, просмотр логов и инспекция локальных образов.",
        "description_i18n": {
            "ru": "Мониторинг запущенных контейнеров Docker, просмотр логов и инспекция локальных образов.",
            "en": "Inspect running Docker containers, view live logs, and monitor image resource usage.",
        },
        "default_config": {
            "docker_host": "tcp://localhost:2375",
            "auto_refresh_sec": 10,
        },
    },
    {
        "id": "code_formatter",
        "title": "Prettier Code Formatter",
        "title_i18n": {"ru": "Форматирование Кода Prettier", "en": "Prettier Code Formatter"},
        "version": "1.3.0",
        "author": "AI Assistant Team",
        "category": "Formatters & Linters",
        "icon": "✨",
        "rating": 4.8,
        "downloads": "29.4k",
        "description": "Автоматическое форматирование Python, JSON, HTML, CSS и Markdown файлов при сохранении.",
        "description_i18n": {
            "ru": "Автоматическое форматирование Python, JSON, HTML, CSS и Markdown файлов при сохранении.",
            "en": "Automatic code formatting for Python, JSON, HTML, CSS, and Markdown on save.",
        },
        "default_config": {
            "format_on_save": True,
            "indent_size": 4,
        },
    },
    {
        "id": "telegram_alerts",
        "title": "Telegram Alerts & Notifier",
        "title_i18n": {"ru": "Оповещения в Telegram", "en": "Telegram Alerts & Notifier"},
        "version": "1.2.2",
        "author": "hypo69",
        "category": "Notifications",
        "icon": "📢",
        "rating": 4.9,
        "downloads": "21.6k",
        "description": "Отправка мгновенных уведомлений о завершении тестов, сборке релизов и системных сбоях в Telegram.",
        "description_i18n": {
            "ru": "Отправка мгновенных уведомлений о завершении тестов, сборке релизов и системных сбоях в Telegram.",
            "en": "Instant alerts for build finishes, test suites, and system errors sent to Telegram channel.",
        },
        "default_config": {
            "notify_on_test_fail": True,
            "notify_on_build": True,
        },
    },
    {
        "id": "themes_pack",
        "title": "Modern Themes Pack",
        "title_i18n": {"ru": "Набор Тем Оформления IDE", "en": "Modern Themes Pack"},
        "version": "1.0.0",
        "author": "hypo69",
        "category": "Appearance",
        "icon": "🎨",
        "rating": 4.9,
        "downloads": "42.0k",
        "description": "Дополнительный набор контрастных и мягких тем оформления VS Code Dark / Light / Cyberpunk.",
        "description_i18n": {
            "ru": "Дополнительный набор контрастных и мягких тем оформления VS Code Dark / Light / Cyberpunk.",
            "en": "Curated collection of IDE color themes: Dark Modern, Monokai Pro, GitHub Dark, and Solarized.",
        },
        "default_config": {
            "active_theme": "dark_modern",
        },
    },
    {
        "id": "youtube_mp3",
        "title": "YouTube MP3 Downloader",
        "title_i18n": {"ru": "YouTube MP3 Загрузчик", "en": "YouTube MP3 Downloader"},
        "version": "1.0.0",
        "author": "hypo69",
        "category": "Media & Audio",
        "icon": "🎵",
        "rating": 5.0,
        "downloads": "31.2k",
        "description": "Загрузка аудиодорожек с YouTube в формате MP3 с автоконвертацией через yt-dlp и ffmpeg.",
        "description_i18n": {
            "ru": "Загрузка аудиодорожек с YouTube в формате MP3 с автоконвертацией через yt-dlp и ffmpeg.",
            "en": "Download YouTube audio tracks in MP3 format with automated yt-dlp & ffmpeg extraction.",
        },
        "default_config": {
            "download_dir": "data/downloads/music",
            "default_quality": "192",
            "embed_metadata": True,
        },
    },
]


def get_marketplace_catalog(installed_names: List[str]) -> List[Dict[str, Any]]:
    """Возвращает каталог плагинов маркетплейса с отметкой об установке."""
    installed_set = {n.lower() for n in installed_names}
    catalog = []
    for item in STANDARD_MARKETPLACE_CATALOG:
        entry = dict(item)
        entry["installed"] = entry["id"].lower() in installed_set
        catalog.append(entry)
    return catalog


def _generate_plugin_code(meta: Dict[str, Any]) -> str:
    """Генерирует чистый код plugin.py для расширения BasePlugin."""
    plugin_id = meta["id"]
    cls_name = "".join(word.capitalize() for word in plugin_id.split("_")) + "Plugin"
    title = meta["title"]
    description = meta["description"]
    icon = meta["icon"]
    category = meta["category"]
    version = meta["version"]

    code = f'''# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: {title}
# =============================================================================
# Description:
#   {description}
#
# File: plugin.py
# Package: plugins.user-plugins.{plugin_id}
# Author: {meta.get("author", "AI Assistant Team")}
# Copyright: © 2026 {meta.get("author", "hypo69")}
# Updated: 2026-10-28 18:45:00
# =============================================================================

from __future__ import annotations

"""Модуль расширения {title} для IDE."""

from typing import Any, AsyncGenerator, Dict, List, Optional
from plugins.base import BasePlugin
from logger import logger


class {cls_name}(BasePlugin):
    """Реализация стандартного плагина {title}."""

    name: str = "{plugin_id}"
    title: str = "{title}"
    title_i18n: Dict[str, str] = {json.dumps(meta.get("title_i18n", {}), ensure_ascii=False)}
    version: str = "{version}"
    description: str = "{description}"
    description_i18n: Dict[str, str] = {json.dumps(meta.get("description_i18n", {}), ensure_ascii=False)}
    icon: str = "{icon}"
    category: str = "{category}"
    scope: str = "user"
    enabled: bool = True
    is_system: bool = False

    def __init__(self, ai_model: Any = None, config: Optional[Dict[str, Any]] = None) -> None:
        """Инициализация плагина."""
        super().__init__(ai_model=ai_model, config=config)
        self.is_running: bool = False

    async def start(self) -> None:
        """Запуск фоновых служб плагина."""
        self.is_running = True
        logger.info(f"[{plugin_id}] Плагин успешно запущен.")

    async def stop(self) -> None:
        """Остановка фоновых служб плагина."""
        self.is_running = False
        logger.info(f"[{plugin_id}] Плагин успешно остановлен.")

    async def handle(self, message: str, **kwargs: Any) -> AsyncGenerator[Dict[str, Any], None]:
        """Обработка входящего запроса или потока сообщений."""
        yield {{"status": "complete", "text": f"[{plugin_id}] Обработано: {{message}}"}}

    async def execute_action(self, action_id: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Выполнение действия плагина."""
        logger.info(f"[{plugin_id}] Вызов действия '{{action_id}}' с параметрами {{params}}")
        if action_id == "status":
            return {{"status": "ok", "plugin": self.name, "running": self.is_running}}
        return {{"status": "executed", "action": action_id}}

    def get_manifest(self, lang: Optional[str] = "ru") -> Dict[str, Any]:
        """Возвращает манифест плагина."""
        return {{
            "name": self.name,
            "title": self.get_title(lang),
            "version": self.version,
            "description": self.get_description(lang),
            "icon": self.icon,
            "category": self.category,
            "enabled": self.enabled,
            "scope": self.scope,
            "is_running": self.is_running,
            "actions": [
                {{"id": "status", "title": "Проверить статус", "icon": "bi-check2-circle"}}
            ],
            "tools": [],
            "fields": [],
            "config": self.config,
        }}


Plugin = {cls_name}
'''
    return code


def install_marketplace_plugin(plugin_id: str) -> Dict[str, Any]:
    """Устанавливает стандартный плагин из каталога маркетплейса в plugins/user-plugins."""
    meta = next((item for item in STANDARD_MARKETPLACE_CATALOG if item["id"].lower() == plugin_id.lower()), None)
    if not meta:
        raise ValueError(f"Плагин '{plugin_id}' не найден в каталоге маркетплейса")

    target_dir = __root__ / "plugins" / "user-plugins" / meta["id"]
    if target_dir.exists() and (target_dir / "plugin.py").exists():
        return {
            "status": "already_installed",
            "plugin_id": meta["id"],
            "message": f"Плагин '{meta['title']}' уже установлен",
            "path": str(target_dir),
        }

    target_dir.mkdir(parents=True, exist_ok=True)
    cls_name = "".join(word.capitalize() for word in meta["id"].split("_")) + "Plugin"

    # 1. Запись __init__.py с фабрикой plugin()
    init_content = f'''# -*- coding: utf-8 -*-
from typing import Any, Optional
from .plugin import {cls_name}


def plugin(ai_model: Any = None, config: Optional[dict] = None) -> {cls_name}:
    """Фабричная функция создания экземпляра плагина."""
    return {cls_name}(ai_model=ai_model, config=config)


__all__ = ["{cls_name}", "plugin"]
'''
    (target_dir / "__init__.py").write_text(init_content, encoding="utf-8")

    # 2. Запись plugin.py
    plugin_py_content = _generate_plugin_code(meta)
    (target_dir / "plugin.py").write_text(plugin_py_content, encoding="utf-8")

    # 3. Запись config.json
    cfg = meta.get("default_config", {})
    (target_dir / "config.json").write_text(json.dumps(cfg, indent=4, ensure_ascii=False), encoding="utf-8")

    # 4. Запись README.md
    readme_content = f'''# {meta["title"]}

{meta["description"]}

- **Версия:** {meta["version"]}
- **Категория:** {meta["category"]}
- **Автор:** {meta.get("author", "AI Assistant Team")}
'''
    (target_dir / "README.md").write_text(readme_content, encoding="utf-8")

    # Гарантируем, что поддиректория plugins/user-plugins в sys.path и plugins.__path__
    import sys
    import plugins
    user_plugins_dir = str(__root__ / "plugins" / "user-plugins")
    if hasattr(plugins, "__path__") and user_plugins_dir not in plugins.__path__:
        plugins.__path__.append(user_plugins_dir)

    logger.info(f"[plugins_marketplace] Плагин {meta['id']} успешно установлен в {target_dir}")
    return {
        "status": "success",
        "plugin_id": meta["id"],
        "title": meta["title"],
        "message": f"Плагин '{meta['title']}' успешно установлен",
        "path": str(target_dir),
    }


def uninstall_user_plugin(plugin_id: str) -> Dict[str, Any]:
    """Удаляет пользовательский плагин из каталога plugins/user-plugins."""
    import sys
    norm_id = plugin_id.strip().lower()
    target_dir = __root__ / "plugins" / "user-plugins" / norm_id

    # Проверка: если плагин в system-plugins или developer-plugins
    for scope_dir in ("system-plugins", "developer-plugins"):
        scope_path = __root__ / "plugins" / scope_dir / norm_id
        if scope_path.exists():
            raise PermissionError(f"Плагин '{plugin_id}' является частью '{scope_dir}' и не может быть удален с диска")

    if not target_dir.exists():
        raise FileNotFoundError(f"Плагин '{plugin_id}' не найден в каталоге пользовательских расширений")

    # Очистка модулей из sys.modules
    for mod_key in list(sys.modules.keys()):
        if mod_key == f"plugins.{norm_id}" or mod_key.startswith(f"plugins.{norm_id}."):
            sys.modules.pop(mod_key, None)

    shutil.rmtree(target_dir, ignore_errors=False)
    logger.info(f"[plugins_marketplace] Директория плагина {target_dir} удалена")
    return {
        "status": "success",
        "plugin_id": norm_id,
        "message": f"Плагин '{plugin_id}' успешно удален",
    }
