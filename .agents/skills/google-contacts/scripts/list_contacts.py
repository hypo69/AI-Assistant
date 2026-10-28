# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Google Contacts Skill - List Contacts CLI
# =============================================================================
# Description:
#   Консольная утилита для поиска и вывода списка контактов и телефонов из Google Contacts.
#
# File: list_contacts.py
# Package: .agents.skills.google-contacts.scripts
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-27 16:15:00
# =============================================================================

from __future__ import annotations

"""CLI скрипт поиска и выборки контактов из Google People API."""

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
    """Точка входа CLI для получения контактов."""
    parser = argparse.ArgumentParser(description="Поиск и вывод контактов из телефонной книги Google Contacts.")
    parser.add_argument("-q", "--query", type=str, default=None, help="Поисковый запрос (имя, телефон или email)")
    parser.add_argument("-n", "--limit", type=int, default=30, help="Максимальное количество контактов (по умолчанию 30)")
    parser.add_argument("--account", type=str, default=None, help="Имя аккаунта Google из пула")
    parser.add_argument("--json", action="store_true", help="Вывод результата строго в формате JSON")

    args = parser.parse_args()

    try:
        client = GoogleContactsClient(account_name=args.account)
        contacts = client.list_contacts(query=args.query, max_results=args.limit)

        if args.json:
            print(json.dumps({"status": "success", "count": len(contacts), "contacts": contacts}, ensure_ascii=False, indent=2))
        else:
            logger.console(f"Контакты Google (найдено: {len(contacts)}):")
            for idx, c in enumerate(contacts, 1):
                phones_str = ", ".join([p["value"] for p in c.get("phones", [])]) or "Нет телефона"
                emails_str = ", ".join([e["value"] for e in c.get("emails", [])]) or "Нет email"
                logger.console(f"[{idx}] {c.get('display_name')}")
                logger.console(f"    Resource: {c.get('resource_name')}")
                logger.console(f"    Телефоны: {phones_str}")
                logger.console(f"    Email:    {emails_str}")
                if c.get("organizations"):
                    orgs = [o["name"] for o in c["organizations"] if o.get("name")]
                    if orgs:
                        logger.console(f"    Организация: {', '.join(orgs)}")
                logger.console("-" * 60)
    except Exception as exc:
        if args.json:
            print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        else:
            logger.console(f"Ошибка при получении контактов: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
