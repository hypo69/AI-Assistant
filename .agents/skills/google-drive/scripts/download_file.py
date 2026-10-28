# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Google Drive Skill - Download File CLI
# =============================================================================
# Description:
#   Консольная утилита для скачивания файла с Google Диска на локальную машину.
#
# File: download_file.py
# Package: .agents.skills.google-drive.scripts
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-27 16:15:00
# =============================================================================

from __future__ import annotations

"""CLI скрипт скачивания файла с Google Drive."""

import argparse
import json
import sys
from pathlib import Path

_CURRENT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _CURRENT_DIR.parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from drive_client import GoogleDriveClient  # noqa: E402
from logger import logger  # noqa: E402


def main() -> None:
    """Точка входа CLI для скачивания файла."""
    parser = argparse.ArgumentParser(description="Скачивание файла с Google Drive.")
    parser.add_argument("-i", "--file-id", type=str, required=True, help="ID файла на Google Drive")
    parser.add_argument("-o", "--output", type=str, required=True, help="Локальный путь для сохранения файла")
    parser.add_argument("--account", type=str, default=None, help="Имя аккаунта Google из пула")
    parser.add_argument("--json", action="store_true", help="Вывод результата строго в формате JSON")

    args = parser.parse_args()

    try:
        client = GoogleDriveClient(account_name=args.account)
        res = client.download_file(file_id=args.file_id, local_output_path=args.output)

        if args.json:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            logger.console(f"Файл успешно скачан!")
            logger.console(f"Имя:     {res.get('name')}")
            logger.console(f"Путь:    {res.get('saved_to')}")
            logger.console(f"Размер:  {res.get('size')} байт")
    except Exception as exc:
        if args.json:
            print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        else:
            logger.console(f"Ошибка при скачивании файла: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
