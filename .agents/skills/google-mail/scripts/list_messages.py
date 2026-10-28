# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Google Mail Skill - List Messages CLI
# =============================================================================
# Description:
#   Консольная утилита для поиска и вывода списка писем из почтового ящика Gmail.
#
# File: list_messages.py
# Package: .agents.skills.google-mail.scripts
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-27 16:15:00
# =============================================================================

from __future__ import annotations

"""CLI скрипт поиска и выборки писем из Gmail."""

import argparse
import json
import sys
from pathlib import Path

_CURRENT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _CURRENT_DIR.parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from mail_client import GoogleMailClient  # noqa: E402
from logger import logger  # noqa: E402


def main() -> None:
    """Точка входа CLI для получения списка писем."""
    parser = argparse.ArgumentParser(description="Поиск и вывод списка писем Gmail.")
    parser.add_argument("-q", "--query", type=str, default="", help="Поисковый запрос Gmail (например: 'from:support', 'is:unread')")
    parser.add_argument("-l", "--label", type=str, default=None, help="Фильтрация по метке (например: INBOX, SENT, STARRED)")
    parser.add_argument("-n", "--limit", type=int, default=10, help="Максимальное количество сообщений (по умолчанию 10)")
    parser.add_argument("--unread-only", action="store_true", help="Выбирать только непрочитанные письма")
    parser.add_argument("--account", type=str, default=None, help="Имя аккаунта Google из пула")
    parser.add_argument("--json", action="store_true", help="Вывод результата строго в формате JSON")

    args = parser.parse_args()

    try:
        client = GoogleMailClient(account_name=args.account)
        labels = [args.label] if args.label else []
        if args.unread_only:
            labels.append("UNREAD")

        messages = client.list_messages(query=args.query, label_ids=labels if labels else None, max_results=args.limit)

        if args.json:
            print(json.dumps({"status": "success", "count": len(messages), "messages": messages}, ensure_ascii=False, indent=2))
        else:
            logger.console(f"Найдено писем: {len(messages)}")
            for idx, msg in enumerate(messages, 1):
                logger.console(f"[{idx}] ID: {msg.get('id')}")
                logger.console(f"    От: {msg.get('from')}")
                logger.console(f"    Тема: {msg.get('subject')}")
                logger.console(f"    Дата: {msg.get('date')}")
                logger.console(f"    Сниппет: {msg.get('snippet')}")
                logger.console("-" * 60)
    except Exception as exc:
        if args.json:
            print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        else:
            logger.console(f"Ошибка при получении писем: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
