# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Google Calendar Skill - Create Event CLI
# =============================================================================
# Description:
#   Консольная утилита для создания нового события в Google Calendar.
#
# File: create_event.py
# Package: .agents.skills.google-calendar.scripts
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 18:48:00
# =============================================================================

from __future__ import annotations

"""CLI скрипт создания события в Google Календаре."""

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
    """Точка входа CLI для добавления события."""
    parser = argparse.ArgumentParser(description="Создание события в Google Calendar.")
    parser.add_argument("-s", "--summary", type=str, required=True, help="Название / тема события")
    parser.add_argument("--start", type=str, required=True, help="Время начала в ISO формате (напр. '2026-10-28T14:00:00+02:00') или дата YYYY-MM-DD")
    parser.add_argument("--end", type=str, required=True, help="Время окончания в ISO формате или дата YYYY-MM-DD")
    parser.add_argument("--desc", type=str, default="", help="Описание встречи")
    parser.add_argument("--location", type=str, default="", help="Место проведения или ссылка на конференцию")
    parser.add_argument("-a", "--attendee", action="append", default=[], help="Email участника (можно указывать несколько раз)")
    parser.add_argument("-c", "--calendar-id", type=str, default="primary", help="ID календаря (по умолчанию 'primary')")
    parser.add_argument("--account", type=str, default=None, help="Имя аккаунта Google из пула")
    parser.add_argument("--json", action="store_true", help="Вывод результата строго в формате JSON")

    args = parser.parse_args()

    try:
        client = GoogleCalendarClient(account_name=args.account)
        res = client.create_event(
            summary=args.summary,
            start_time=args.start,
            end_time=args.end,
            description=args.desc,
            location=args.location,
            attendees=args.attendee,
            calendar_id=args.calendar_id,
        )

        if args.json:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            logger.console(f"Событие успешно создано! ID: {res.get('id')}")
            logger.console(f"Ссылка: {res.get('html_link')}")
    except Exception as exc:
        parsed = logger.google_error(exc, context="Google Calendar Create Event")
        if args.json:
            error_payload = parsed.to_dict() if parsed else {"status": "error", "error": str(exc)}
            print(json.dumps(error_payload, ensure_ascii=False, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
