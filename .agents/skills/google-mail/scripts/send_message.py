# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Google Mail Skill - Send Message CLI
# =============================================================================
# Description:
#   Консольная утилита для отправки электронного письма через Gmail API.
#
# File: send_message.py
# Package: .agents.skills.google-mail.scripts
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-27 16:15:00
# =============================================================================

from __future__ import annotations

"""CLI скрипт отправки электронного письма через Gmail."""

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
    """Точка входа CLI для отправки письма."""
    parser = argparse.ArgumentParser(description="Отправка письма через Gmail API.")
    parser.add_argument("-t", "--to", type=str, required=True, help="Email получателя")
    parser.add_argument("-s", "--subject", type=str, required=True, help="Тема письма")
    parser.add_argument("-b", "--body", type=str, default="", help="Текст письма")
    parser.add_argument("--html", type=str, default=None, help="HTML содержимое письма")
    parser.add_argument("-a", "--attach", action="append", default=[], help="Путь к файлу-вложению (можно указывать несколько раз)")
    parser.add_argument("--cc", type=str, default=None, help="Email для копии (CC)")
    parser.add_argument("--bcc", type=str, default=None, help="Email для скрытой копии (BCC)")
    parser.add_argument("--account", type=str, default=None, help="Имя аккаунта Google из пула")
    parser.add_argument("--json", action="store_true", help="Вывод результата строго в формате JSON")

    args = parser.parse_args()

    try:
        client = GoogleMailClient(account_name=args.account)
        res = client.send_message(
            to=args.to,
            subject=args.subject,
            body_plain=args.body,
            body_html=args.html,
            attachments=args.attach,
            cc=args.cc,
            bcc=args.bcc,
        )

        if args.json:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            logger.console(f"Письмо успешно отправлено! ID: {res.get('id')}")
    except Exception as exc:
        if args.json:
            print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        else:
            logger.console(f"Ошибка при отправке письма: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
