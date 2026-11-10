# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Agent Skill - Workspace Creator CLI
# =============================================================================
# Description:
#   Исполняемый интерфейс навыка workspace-creator для ИИ-моделей и CLI.
#   Позволяет модели автономно инспектировать локальную директорию на диске
#   и развёртывать полноценное рабочее пространство на её основе.
#
# Usage Examples:
#   CLI:
#     py workspace_creator_cli.py audit "C:/Users/onela/Desktop/דוד מושה" --json
#     py workspace_creator_cli.py create "C:/Users/onela/Desktop/דוד מושה" --id "david_moshe" --lang "he"
#
# File: workspace_creator_cli.py
# Package: .agents.skills.workspace-creator.scripts
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 16:50:00
# =============================================================================

from __future__ import annotations
"""CLI утилита навыка создания рабочего пространства на базе локальной папки."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Добавляем корень проекта в sys.path
_current = Path(__file__).resolve()
_root = _current.parents[4]  # .agents/skills/workspace-creator/scripts -> root
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from apps.ai_assistant.core.workspace_manager import WorkspaceManager
from apps.ai_assistant.core.workspace_creator_engine import WorkspaceCreatorEngine


def parse_args() -> argparse.Namespace:
    """Парсер аргументов командной строки."""
    parser = argparse.ArgumentParser(
        description="Workspace Creator Skill CLI - создание рабочего пространства на основе локальной папки."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Команда audit
    audit_parser = subparsers.add_parser("audit", help="Аудит и профилирование локальной папки.")
    audit_parser.add_argument("directory", type=str, help="Путь к локальной директории на диске.")
    audit_parser.add_argument("--json", action="store_true", help="Вывод в формате JSON.")

    # Команда create
    create_parser = subparsers.add_parser("create", help="Создание рабочего пространства на базе директории.")
    create_parser.add_argument("directory", type=str, help="Путь к локальной директории на диске.")
    create_parser.add_argument("--id", type=str, default=None, help="Идентификатор рабочего пространства.")
    create_parser.add_argument("--name", type=str, default=None, help="Отображаемое имя пространства.")
    create_parser.add_argument("--desc", type=str, default=None, help="Описание пространства.")
    create_parser.add_argument("--lang", type=str, default=None, choices=["ru", "he", "en", "ua"], help="Язык.")
    create_parser.add_argument("--copy", action="store_true", help="Копировать файлы вместо отслеживания на месте.")
    create_parser.add_argument("--json", action="store_true", help="Вывод в формате JSON.")

    return parser.parse_args()


async def main_async() -> int:
    """Асинхронная точка входа CLI."""
    args = parse_args()
    wm = WorkspaceManager()
    engine = WorkspaceCreatorEngine(wm)

    if args.command == "audit":
        try:
            profile = engine.audit_directory(args.directory)
            if args.json:
                print(json.dumps(profile, indent=2, ensure_ascii=False))
            else:
                print("=" * 60)
                print(f"📊 Аудит локальной папки: {profile['folder_name']}")
                print("=" * 60)
                print(f"Путь:                 {profile['qualified_path']}")
                print(f"Обнаружено файлов:    {profile['total_files']} ({profile['total_size_bytes']} байт)")
                print(f"Определённый язык:    {profile['detected_language']}")
                print(f"Рекомендуемый ID:     {profile['suggested_id']}")
                print(f"Рекомендуемое имя:    {profile['suggested_name']}")
                print(f"Описание:             {profile['suggested_description']}")
                print(f"Форматы:              {profile['extensions']}")
                print(f"Примеры файлов:       {profile['sample_files']}")
                print("=" * 60)
            return 0
        except Exception as exc:
            print(json.dumps({"status": "error", "message": str(exc)}) if args.json else f"Ошибка аудита: {exc}")
            return 1

    elif args.command == "create":
        try:
            res = await engine.create_workspace_from_directory(
                directory_path=args.directory,
                workspace_id=args.id,
                name=args.name,
                description=args.desc,
                language=args.lang,
                in_place=not args.copy,
            )
            if args.json:
                print(json.dumps(res, indent=2, ensure_ascii=False))
            else:
                print("=" * 60)
                print(f"✅ Рабочее пространство '{res['name']}' успешно создано!")
                print("=" * 60)
                print(f"ID:                   {res['workspace_id']}")
                print(f"Язык:                 {res['language']}")
                print(f"Папка пространства:   {res['path']}")
                print(f"Исходный каталог:     {res['source_qualified_path']}")
                print(f"Файлов подключено:    {res['files_linked']}")
                print("Стартовые подсказки:")
                for p in res.get("starter_prompts", []):
                    print(f"  • {p.get('text')}")
                print("=" * 60)
            return 0
        except Exception as exc:
            print(json.dumps({"status": "error", "message": str(exc)}) if args.json else f"Ошибка создания: {exc}")
            return 1

    return 0


def main() -> None:
    """Синхронная обертка CLI."""
    sys.exit(asyncio.run(main_async()))


if __name__ == "__main__":
    main()
