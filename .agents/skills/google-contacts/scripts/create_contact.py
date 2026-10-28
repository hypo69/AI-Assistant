# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Google Contacts Skill - Create Contact CLI
# =============================================================================
# Description:
#   Консольная утилита для создания нового контакта в Google Contacts.
#
# File: create_contact.py
# Package: .agents.skills.google-contacts.scripts
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-27 16:15:00
# =============================================================================

from __future__ import annotations

"""CLI скрипт создания контакта в Google People API."""

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
    """Точка входа CLI для добавления контакта."""
    parser = argparse.ArgumentParser(description="Создание контакта в Google Contacts.")
    parser.add_argument("-n", "--name", type=str, required=True, help="Имя контакта")
    parser.add_argument("--family-name", type=str, default="", help="Фамилия контакта")
    parser.add_argument("-p", "--phone", type=str, default=None, help="Номер телефона")
    parser.add_argument("-e", "--email", type=str, default=None, help="Email адрес")
    parser.add_argument("--org", type=str, default=None, help="Компания / организация")
    parser.add_argument("--title", type=str, default=None, help="Должность")
    parser.add_argument("--notes", type=str, default=None, help="Заметки")
    parser.add_argument("--account", type=str, default=None, help="Имя аккаунта Google из пула")
    parser.add_argument("--json", action="store_true", help="Вывод результата строго в формате JSON")

    args = parser.parse_args()

    try:
        client = GoogleContactsClient(account_name=args.account)
        res = client.create_contact(
            given_name=args.name,
            family_name=args.family_name,
            phone=args.phone,
            email=args.email,
            organization=args.org,
            title=args.title,
            notes=args.notes,
        )

        if args.json:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            c = res.get("contact", {})
            logger.console("Контакт успешно создан!")
            logger.console(f"Имя:      {c.get('display_name')}")
            logger.console(f"Resource: {c.get('resource_name')}")
    except Exception as exc:
        if args.json:
            print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        else:
            logger.console(f"Ошибка при создании контакта: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
