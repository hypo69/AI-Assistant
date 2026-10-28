# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Google Mail Skill - Read Message CLI
# =============================================================================
# Description:
#   Консольная утилита для чтения детального содержимого письма Gmail по ID.
#
# File: read_message.py
# Package: .agents.skills.google-mail.scripts
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-27 16:15:00
# =============================================================================

from __future__ import annotations

"""CLI скрипт просмотра подробностей письма."""

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
    """Точка входа CLI для чтения письма."""
    parser = argparse.ArgumentParser(description="Чтение детального содержимого письма Gmail по ID.")
    parser.add_argument("-i", "--id", type=str, required=True, help="Идентификатор сообщения (message ID)")
    parser.add_argument("--account", type=str, default=None, help="Имя аккаунта Google из пула")
    parser.add_argument("--json", action="store_true", help="Вывод результата строго в формате JSON")

    args = parser.parse_args()

    try:
        client = GoogleMailClient(account_name=args.account)
        msg = client.get_message(message_id=args.id)

        if args.json:
            print(json.dumps({"status": "success", "message": msg}, ensure_ascii=False, indent=2))
        else:
            logger.console("=" * 60)
            logger.console(f"Тема:    {msg.get('subject')}")
            logger.console(f"От:      {msg.get('from')}")
            logger.console(f"Кому:    {msg.get('to')}")
            logger.console(f"Дата:    {msg.get('date')}")
            logger.console(f"Метки:   {', '.join(msg.get('labels', []))}")
            if msg.get("attachments"):
                logger.console(f"Вложения: {[a['filename'] for a in msg['attachments']]}")
            logger.console("-" * 60)
            logger.console("Тело письма:")
            logger.console(msg.get("body_plain", ""))
            logger.console("=" * 60)
    except Exception as exc:
        if args.json:
            print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        else:
            logger.console(f"Ошибка при чтении письма: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
