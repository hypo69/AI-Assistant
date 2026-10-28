# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Google Contacts Skill - Delete Contact CLI
# =============================================================================
# Description:
#   Консольная утилита для удаления контакта из Google Contacts по resourceName.
#
# File: delete_contact.py
# Package: .agents.skills.google-contacts.scripts
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-27 16:15:00
# =============================================================================

from __future__ import annotations

"""CLI скрипт удаления контакта из Google People API."""

import argparse
import json
import sys
from pathlib import Path

_CURRENT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _CURRENT_DIR.parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from contacts_client import GoogleContactsClient  # noqa: E402
from logger import logger  # noqa: E402


def main() -> None:
    """Точка входа CLI для удаления контакта."""
    parser = argparse.ArgumentParser(description="Удаление контакта из Google Contacts.")
    parser.add_argument("-r", "--resource-name", type=str, required=True, help="Идентификатор контакта (например, 'people/c1234567890')")
    parser.add_argument("--account", type=str, default=None, help="Имя аккаунта Google из пула")
    parser.add_argument("--json", action="store_true", help="Вывод результата строго в формате JSON")

    args = parser.parse_args()

    try:
        client = GoogleContactsClient(account_name=args.account)
        res = client.delete_contact(resource_name=args.resource_name)

        if args.json:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            logger.console(f"Контакт {args.resource_name} успешно удален!")
    except Exception as exc:
        if args.json:
            print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        else:
            logger.console(f"Ошибка при удалении контакта: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
