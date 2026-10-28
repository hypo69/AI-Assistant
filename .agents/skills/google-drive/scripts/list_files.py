# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Google Drive Skill - List Files CLI
# =============================================================================
# Description:
#   Консольная утилита для поиска и вывода списка файлов на Google Диске.
#
# File: list_files.py
# Package: .agents.skills.google-drive.scripts
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-27 16:15:00
# =============================================================================

from __future__ import annotations

"""CLI скрипт поиска и просмотра файлов на Google Drive."""

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
    """Точка входа CLI для получения файлов."""
    parser = argparse.ArgumentParser(description="Поиск и вывод списка файлов Google Drive.")
    parser.add_argument("-q", "--query", type=str, default=None, help="Поисковый фильтр (например: \"name contains 'report'\")")
    parser.add_argument("-f", "--folder-id", type=str, default=None, help="ID папки на Диске для фильтрации")
    parser.add_argument("-m", "--mime-type", type=str, default=None, help="Фильтрация по MIME-типу (например: 'application/pdf')")
    parser.add_argument("-n", "--limit", type=int, default=20, help="Максимальное количество файлов (по умолчанию 20)")
    parser.add_argument("--account", type=str, default=None, help="Имя аккаунта Google из пула")
    parser.add_argument("--json", action="store_true", help="Вывод результата строго в формате JSON")

    args = parser.parse_args()

    try:
        client = GoogleDriveClient(account_name=args.account)
        files = client.list_files(
            query=args.query,
            folder_id=args.folder_id,
            mime_type=args.mime_type,
            max_results=args.limit,
        )

        if args.json:
            print(json.dumps({"status": "success", "count": len(files), "files": files}, ensure_ascii=False, indent=2))
        else:
            logger.console(f"Файлы Google Drive (найдено: {len(files)}):")
            for idx, f in enumerate(files, 1):
                logger.console(f"[{idx}] {f.get('name')}")
                logger.console(f"    ID:       {f.get('id')}")
                logger.console(f"    Тип:      {f.get('mimeType')}")
                logger.console(f"    Размер:   {f.get('size', 'N/A')} байт")
                logger.console(f"    Изменен:  {f.get('modifiedTime')}")
                logger.console(f"    Ссылка:   {f.get('webViewLink')}")
                logger.console("-" * 60)
    except Exception as exc:
        if args.json:
            print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        else:
            logger.console(f"Ошибка при получении файлов Google Drive: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
