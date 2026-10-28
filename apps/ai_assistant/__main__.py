# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant - CLI Entrypoint
# =============================================================================
# Description:
#   Интерфейс командной строки (CLI) для взаимодействия с модулем умной истории версий:
#   выполнение естественных запросов, инкрементальная индексация и просмотр статуса.
#
# Usage Examples:
#   CLI:
#     python -m apps.ai_assistant
#     python -m apps.ai_assistant --connect
#     python -m apps.ai_assistant --restart
#     python -m apps.ai_assistant serve --port 8002 --connect
#     python -m apps.ai_assistant status
#     python -m apps.ai_assistant commits --limit 10
#     python -m apps.ai_assistant query "Когда исправлялась ошибка запуска телеметрии?"
#     python -m apps.ai_assistant index --limit 20
#
# File: __main__.py
# Project: ai-windows-admin
# Package: apps.ai_assistant
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-25 19:37:00
# =============================================================================

from __future__ import annotations
"""Точка входа CLI для модуля умной истории версий."""

import argparse
import asyncio
import sys
from logger import logger
from apps.ai_assistant.git_adapter import GitAdapter
from apps.ai_assistant.models import QueryRequest
from apps.ai_assistant.orchestrator import SmartHistoryOrchestrator
from apps.ai_assistant.rag_retriever import SmartHistoryRAGRetriever
from apps.ai_assistant.wiki_adapter import WikiAdapter


async def run_query(query_text: str, top_k: int = 5) -> None:
    """Выполняет запрос через координатор и выводит результат в консоль."""
    orchestrator = SmartHistoryOrchestrator()
    req = QueryRequest(query=query_text, top_k=top_k)
    res = await orchestrator.execute_query(req)
    logger.console(res.explanation)
    if res.suggested_quick_questions:
        logger.console("\nБыстрые вопросы для продолжения:")
        for q in res.suggested_quick_questions:
            logger.console(f"  • {q}")


def show_commits(limit: int = 20) -> None:
    """Отображает список последних коммитов."""
    git = GitAdapter()
    commits = git.get_commit_history(max_count=limit)
    logger.console(f"Найдено коммитов: {len(commits)}")
    for c in commits:
        logger.console(f"[{c.commit_hash[:8]}] {c.timestamp[:10]} | {c.author} | {c.message}")


def run_index(limit: int = 25) -> None:
    """Запускает инкрементальную индексацию коммитов."""
    git = GitAdapter()
    wiki = WikiAdapter()
    rag = SmartHistoryRAGRetriever()
    commits = git.get_commit_history(max_count=limit)
    total_added = 0
    for c in commits:
        _, changes = git.get_commit_details(c.commit_hash)
        wiki.auto_link_commit(c, changes)
        hunks = []
        for fc in changes[:5]:
            hunks.extend(git.get_diff_hunks(c.commit_hash, fc.file_path))
        added = rag.index_commit(c, hunks)
        total_added += added
    logger.console(f"Индексация завершена. Добавлено новых чанков: {total_added}. Всего в индексе: {len(rag.chunks)}")


def show_status() -> None:
    """Отображает состояние компонентов Git, WikiLLM и RAG."""
    git = GitAdapter()
    wiki = WikiAdapter()
    rag = SmartHistoryRAGRetriever()
    logger.console("=" * 60)
    logger.console("Статус модуля умной истории версий (AI Assistant):")
    logger.console(f"  • Git доступен:       {git.is_git_available()}")
    logger.console(f"  • Текущий HEAD:       {git.get_current_commit()[:12] if git.is_git_available() else 'Н/Д'}")
    logger.console(f"  • База знаний Wiki:   {wiki.db_path}")
    logger.console(f"  • Каталог RAG-индекса: {rag.index_dir}")
    logger.console(f"  • Проиндексировано:    {len(rag.chunks)} чанков")
    logger.console("=" * 60)


def main() -> None:
    """Главная функция разбора аргументов CLI."""
    parser = argparse.ArgumentParser(description="AI Assistant Smart Version History CLI")
    
    # Общие флаги верхнего уровня (для быстрого запуска без обязательной подкоманды serve)
    parser.add_argument("--port", type=int, default=None, help="Порт сервера (по умолчанию из config.json или 8002)")
    parser.add_argument("--host", type=str, default=None, help="Хост сервера")
    parser.add_argument(
        "--engine",
        type=str,
        choices=["electron", "webview2", "browser", "headless"],
        default=None,
        help="Движок графической оболочки (по умолчанию electron)",
    )
    parser.add_argument("--no-gui", action="store_true", help="Запуск без графического интерфейса")
    parser.add_argument("-c", "--connect", action="store_true", help="Подключиться к текущему запущенному процессу и открыть GUI")
    parser.add_argument("-r", "--restart", action="store_true", help="Завершить старый процесс на порту и запустить новый сервер")
    parser.add_argument("--action", type=str, choices=["connect", "restart", "prompt"], default=None, help="Действие при занятом порте")

    subparsers = parser.add_subparsers(dest="command")

    # query
    p_query = subparsers.add_parser("query", help="Выполнить умный запрос по истории")
    p_query.add_argument("text", type=str, help="Текст запроса")
    p_query.add_argument("--top-k", type=int, default=5, help="Количество результатов")

    # commits
    p_commits = subparsers.add_parser("commits", help="Показать недавние коммиты")
    p_commits.add_argument("--limit", type=int, default=20, help="Лимит коммитов")

    # index
    p_index = subparsers.add_parser("index", help="Инкрементальная индексация истории")
    p_index.add_argument("--limit", type=int, default=25, help="Количество коммитов для индексации")

    # status
    subparsers.add_parser("status", help="Отобразить состояние компонентов Git, WikiLLM и RAG")

    # serve
    p_serve = subparsers.add_parser("serve", help="Запустить автономный WebGUI и REST API сервер")
    p_serve.add_argument("--port", type=int, default=8002, help="Порт сервера (по умолчанию 8002)")
    p_serve.add_argument("--host", type=str, default="127.0.0.1", help="Хост сервера")
    p_serve.add_argument(
        "--engine",
        type=str,
        choices=["electron", "webview2", "browser", "headless"],
        default="electron",
        help="Движок графической оболочки (по умолчанию electron)",
    )
    p_serve.add_argument("--no-gui", action="store_true", help="Запуск без графического интерфейса")
    p_serve.add_argument("-c", "--connect", action="store_true", help="Подключиться к текущему процессу и открыть GUI")
    p_serve.add_argument("-r", "--restart", action="store_true", help="Завершить старый процесс и запустить новый")
    p_serve.add_argument("--action", type=str, choices=["connect", "restart", "prompt"], default=None, help="Действие при занятом порте")

    args = parser.parse_args()

    if args.command == "query":
        asyncio.run(run_query(args.text, top_k=args.top_k))
    elif args.command == "commits":
        show_commits(limit=args.limit)
    elif args.command == "index":
        run_index(limit=args.limit)
    elif args.command == "status":
        show_status()
    elif args.command == "serve":
        from apps.ai_assistant.main import run
        selected_action = "restart" if getattr(args, "restart", False) else ("connect" if getattr(args, "connect", False) else getattr(args, "action", None))
        run(
            port=args.port,
            host=args.host,
            engine=args.engine,
            no_gui=getattr(args, "no_gui", False),
            action=selected_action,
        )
    else:
        # Если команда не передана, запускаем веб-сервер и предпочтительный движок (Electron)
        from apps.ai_assistant.main import run
        selected_action = "restart" if getattr(args, "restart", False) else ("connect" if getattr(args, "connect", False) else getattr(args, "action", None))
        run(
            port=getattr(args, "port", None),
            host=getattr(args, "host", None),
            engine=getattr(args, "engine", "electron"),
            no_gui=getattr(args, "no_gui", False),
            action=selected_action,
        )


if __name__ == "__main__":
    main()
