# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Google Calendar Skill - Delete Event CLI
# =============================================================================
# Description:
#   Консольная утилита для удаления события из Google Calendar по ID.
#
# File: delete_event.py
# Package: .agents.skills.google-calendar.scripts
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 18:48:00
# =============================================================================

from __future__ import annotations

"""CLI скрипт удаления события из Google Календаря."""

import argparse
import json
import sys
from pathlib import Path

_CURRENT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _CURRENT_DIR.parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from calendar_client import GoogleCalendarClient  # noqa: E402
from logger import logger  # noqa: E402


def main() -> None:
    """Точка входа CLI для удаления события."""
    parser = argparse.ArgumentParser(description="Удаление события из Google Calendar.")
    parser.add_argument("-i", "--event-id", type=str, required=True, help="ID события для удаления")
    parser.add_argument("-c", "--calendar-id", type=str, default="primary", help="ID календаря (по умолчанию 'primary')")
    parser.add_argument("--account", type=str, default=None, help="Имя аккаунта Google из пула")
    parser.add_argument("--json", action="store_true", help="Вывод результата строго в формате JSON")

    args = parser.parse_args()

    try:
        client = GoogleCalendarClient(account_name=args.account)
        res = client.delete_event(event_id=args.event_id, calendar_id=args.calendar_id)

        if args.json:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            logger.console(f"Событие {args.event_id} успешно удалено!")
    except Exception as exc:
        parsed = logger.google_error(exc, context="Google Calendar Delete Event")
        if args.json:
            error_payload = parsed.to_dict() if parsed else {"status": "error", "error": str(exc)}
            print(json.dumps(error_payload, ensure_ascii=False, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
