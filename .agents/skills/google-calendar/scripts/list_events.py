# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Google Calendar Skill - List Events CLI
# =============================================================================
# Description:
#   Консольная утилита для получения списка предстоящих событий Google Calendar.
#
# File: list_events.py
# Package: .agents.skills.google-calendar.scripts
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 18:48:00
# =============================================================================

from __future__ import annotations

"""CLI скрипт просмотра событий Google Календаря."""

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_CURRENT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _CURRENT_DIR.parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from calendar_client import GoogleCalendarClient  # noqa: E402
from logger import logger  # noqa: E402


def main() -> None:
    """Точка входа CLI для получения событий."""
    parser = argparse.ArgumentParser(description="Получение расписания и событий Google Calendar.")
    parser.add_argument("-d", "--days", type=int, default=7, help="Количество дней вперед для выборки событий (по умолчанию 7)")
    parser.add_argument("-q", "--query", type=str, default=None, help="Фильтр по названию или описанию")
    parser.add_argument("-n", "--limit", type=int, default=15, help="Максимальное число событий (по умолчанию 15)")
    parser.add_argument("-c", "--calendar-id", type=str, default="primary", help="ID календаря (по умолчанию 'primary')")
    parser.add_argument("--account", type=str, default=None, help="Имя аккаунта Google из пула")
    parser.add_argument("--json", action="store_true", help="Вывод результата строго в формате JSON")

    args = parser.parse_args()

    try:
        now = datetime.now(timezone.utc)
        time_max = (now + timedelta(days=args.days)).isoformat()

        client = GoogleCalendarClient(account_name=args.account)
        events = client.list_events(
            calendar_id=args.calendar_id,
            time_min=now.isoformat(),
            time_max=time_max,
            query=args.query,
            max_results=args.limit,
        )

        if args.json:
            print(json.dumps({"status": "success", "count": len(events), "events": events}, ensure_ascii=False, indent=2))
        else:
            logger.console(f"События календаря на ближайшие {args.days} дн. (найдено: {len(events)}):")
            for idx, ev in enumerate(events, 1):
                logger.console(f"[{idx}] {ev.get('summary')}")
                logger.console(f"    ID:      {ev.get('id')}")
                logger.console(f"    Время:   {ev.get('start')} -> {ev.get('end')}")
                if ev.get("location"):
                    logger.console(f"    Место:   {ev.get('location')}")
                if ev.get("attendees"):
                    logger.console(f"    Участники: {', '.join(ev.get('attendees'))}")
                logger.console("-" * 60)
    except Exception as exc:
        parsed = logger.google_error(exc, context="Google Calendar List Events")
        if args.json:
            error_payload = parsed.to_dict() if parsed else {"status": "error", "error": str(exc)}
            print(json.dumps(error_payload, ensure_ascii=False, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
