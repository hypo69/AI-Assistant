# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Root - Manage Tools CLI
# =============================================================================
# Description:
#   Универсальный диспетчер командной строки (CLI) для проекта AI-Assistant.
#
#   Зачем нужен этот модуль:
#     1. Единый CLI-интерфейс: консолидация управления навыками (skills), базой знаний (rag),
#        агентами, базой данных (db), документацией (docs), плагинами и тестами.
#     2. Автоматизация обслуживания: запуск миграций, валидация целостности БД SQLite/FAISS
#        и генерация документации.
#     3. UTF-8 нормализация: обеспечивает корректный вывод кириллицы в консоли Windows.
#
#   Поддерживаемые группы команд:
#     - skills: Управление и аудит навыков агентов (.agents/skills/).
#     - rag: Построение, валидация и очистка поисковых индексов FAISS.
#     - db: Проверка целостности и миграции SQLite хранилищ знаний.
#     - docs: Автоматическая генерация и проверка документации.
#     - plugins / agents / ui / test: Управление подсистемами проекта.
#
# Usage Examples:
#   CLI:
#     py manage_tools.py skills list
#     py manage_tools.py rag build
#     py manage_tools.py db check-integrity
#     py manage_tools.py docs generate
#
# File: manage_tools.py
# Project: ai-windows-admin
# Package: root
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 17:39:00
# =============================================================================

from __future__ import annotations

import argparse
import sys
from dotenv import load_dotenv

from header import __root__
from scripts.cli.commands import (
    COMMAND_HANDLERS,
    register_all_parsers,
)

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

load_dotenv(__root__ / '.env')


def main() -> int:
    """Главная точка входа универсального CLI управления инструментами проекта AI-Assistant.

    Returns:
        int: Код завершения команды (0 — успешно, 1 — ошибка).
    """
    parser = argparse.ArgumentParser(
        prog='manage_tools.py',
        description='Universal CLI for managing ai-windows-admin project tools and agents',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  py manage_tools.py skills list                          # список всех доступных навыков
  py manage_tools.py rag rebuild                          # пересборка индекса RAG
  py manage_tools.py agents list                          # список AI-агентов
  py manage_tools.py db status                            # проверка SQLite баз знаний
  py manage_tools.py docs generate                        # генерация документации
'''
    )
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    register_all_parsers(subparsers)

    args, unknown = parser.parse_known_args()

    if args.command in ('rag', 'docs', 'plugins', 'db') and getattr(args, 'subcommand', None):
        argv_list = list(sys.argv[1:])
        if args.subcommand in argv_list:
            sub_idx = argv_list.index(args.subcommand)
            args.rest = argv_list[sub_idx + 1:]
        else:
            args.rest = unknown
    elif unknown:
        if hasattr(args, 'rest') and isinstance(args.rest, list):
            args.rest = args.rest + unknown
        else:
            args.rest = unknown

    if not args.command:
        parser.print_help()
        return 0

    if args.command == 'assist':
        from scripts.cli import assist
        sys.argv = ['assist'] + getattr(args, 'rest', [])
        return assist.main()

    if args.command != 'test' and not getattr(args, 'subcommand', ''):
        parser.print_help()
        return 0

    handler = COMMAND_HANDLERS.get(args.command)
    if not handler:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == '__main__':
    sys.exit(main())
