# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Google Drive Skill - Upload File CLI
# =============================================================================
# Description:
#   Консольная утилита для загрузки локального файла на Google Диск.
#
# File: upload_file.py
# Package: .agents.skills.google-drive.scripts
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-27 16:15:00
# =============================================================================

from __future__ import annotations

"""CLI скрипт загрузки файла на Google Drive."""

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
    """Точка входа CLI для выгрузки файла на Google Drive."""
    parser = argparse.ArgumentParser(description="Загрузка локального файла на Google Drive.")
    parser.add_argument("-f", "--file", type=str, required=True, help="Путь к локальному файлу для загрузки")
    parser.add_argument("--name", type=str, default=None, help="Имя файла на Диске (по умолчанию оригинальное)")
    parser.add_argument("--folder-id", type=str, default=None, help="ID целевой папки на Google Drive")
    parser.add_argument("--mime-type", type=str, default=None, help="MIME-тип файла")
    parser.add_argument("--account", type=str, default=None, help="Имя аккаунта Google из пула")
    parser.add_argument("--json", action="store_true", help="Вывод результата строго в формате JSON")

    args = parser.parse_args()

    try:
        client = GoogleDriveClient(account_name=args.account)
        res = client.upload_file(
            local_path=args.file,
            name=args.name,
            folder_id=args.folder_id,
            mime_type=args.mime_type,
        )

        if args.json:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            file_data = res.get("file", {})
            logger.console(f"Файл успешно загружен на Google Drive!")
            logger.console(f"ID:      {file_data.get('id')}")
            logger.console(f"Имя:     {file_data.get('name')}")
            logger.console(f"Ссылка:  {file_data.get('webViewLink')}")
    except Exception as exc:
        if args.json:
            print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        else:
            logger.console(f"Ошибка при загрузке файла: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
