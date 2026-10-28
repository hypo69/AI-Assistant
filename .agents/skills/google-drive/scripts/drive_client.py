# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Google Drive Skill - Core Client Module
# =============================================================================
# Description:
#   Базовый клиент для взаимодействия с Google Drive API v3 через OAuth 2.0.
#   Предоставляет методы для поиска файлов и папок, загрузки локальных документов,
#   скачивания файлов и управления структурой диска.
#
# File: drive_client.py
# Package: .agents.skills.google-drive.scripts
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 19:00:00
# =============================================================================

from __future__ import annotations

"""Модуль клиента Google Drive API для навыка google-drive."""

import io
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import header  # noqa: F401
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload, MediaIoBaseUpload
from logger import logger
from src.ai.google_accounts_state import get_account_info, load_account_credentials


class GoogleDriveClient:
    """Клиент для выполнения операций с Google Drive API v3."""

    def __init__(self, account_name: Optional[str] = None) -> None:
        """Инициализирует клиент Google Диска.

        Args:
            account_name: Имя аккаунта Google из настроенного пула.
        """
        self._account_name = account_name or self._resolve_default_account()
        self._service: Optional[Any] = None

    def _resolve_default_account(self) -> str:
        """Определяет активный аккаунт по умолчанию."""
        info = get_account_info()
        return info.get("name", "davidka") if info else "davidka"

    def get_service(self) -> Any:
        """Возвращает экземпляр сервиса Google Drive API.

        Raises:
            RuntimeError: При отсутствии авторизационных данных.
        """
        if self._service is not None:
            return self._service

        creds = load_account_credentials(self._account_name)
        if not creds:
            raise RuntimeError(
                f"Не удалось получить авторизационные данные для аккаунта '{self._account_name}'. "
                "Проверьте наличие токена или выполните авторизацию через /auth/google."
            )

        self._service = build("drive", "v3", credentials=creds, cache_discovery=False)
        return self._service

    def list_files(
        self,
        query: Optional[str] = None,
        folder_id: Optional[str] = None,
        mime_type: Optional[str] = None,
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """Ищет и возвращает список файлов на Google Диске.

        Args:
            query: Произвольный поисковый запрос (например: "name contains 'report'").
            folder_id: ID родительской папки для выборки внутри нее.
            mime_type: Фильтрация по MIME-типу.
            max_results: Максимальное количество файлов.

        Returns:
            Список словарей с метаданными файлов.
        """
        service = self.get_service()
        q_parts: List[str] = ["trashed = false"]

        if folder_id:
            q_parts.append(f"'{folder_id}' in parents")
        if mime_type:
            q_parts.append(f"mimeType = '{mime_type}'")
        if query:
            q_parts.append(f"({query})")

        full_q = " and ".join(q_parts)
        res = (
            service.files()
            .list(
                q=full_q,
                pageSize=min(max(1, max_results), 100),
                fields="files(id, name, mimeType, size, modifiedTime, webViewLink, shared)",
                orderBy="modifiedTime desc",
            )
            .execute()
        )
        return res.get("files", [])

    def get_file_metadata(self, file_id: str) -> Dict[str, Any]:
        """Возвращает метаданные файла по его ID.

        Args:
            file_id: Уникальный ID файла на Диске.

        Returns:
            Словарь метаданных файла.
        """
        service = self.get_service()
        return (
            service.files()
            .get(
                fileId=file_id,
                fields="id, name, mimeType, size, createdTime, modifiedTime, webViewLink, parents, owners, shared",
            )
            .execute()
        )

    def upload_file(
        self,
        local_path: str,
        name: Optional[str] = None,
        folder_id: Optional[str] = None,
        mime_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Загружает локальный файл на Google Диск.

        Args:
            local_path: Путь к локальному файлу на диске.
            name: Имя файла на Google Drive (по умолчанию имя локального файла).
            folder_id: ID целевой папки на Google Drive.
            mime_type: Опциональный MIME-тип загружаемого файла.

        Returns:
            Словарь загруженного файла с id, name, webViewLink.
        """
        service = self.get_service()
        p = Path(local_path)
        if not p.is_file():
            raise FileNotFoundError(f"Локальный файл не найден: {local_path}")

        file_metadata: Dict[str, Any] = {"name": name or p.name}
        if folder_id:
            file_metadata["parents"] = [folder_id]

        media = MediaFileUpload(str(p), mimetype=mime_type, resumable=True)
        uploaded = (
            service.files()
            .create(body=file_metadata, media_body=media, fields="id, name, mimeType, size, webViewLink")
            .execute()
        )
        return {"status": "success", "file": uploaded}

    def download_file(self, file_id: str, local_output_path: str) -> Dict[str, Any]:
        """Скачивает файл с Google Диска на локальный диск.

        Args:
            file_id: ID файла на Google Drive.
            local_output_path: Путь сохранения файла на локальной машине.

        Returns:
            Словарь с результатом скачивания (status, path, size).
        """
        service = self.get_service()
        out_p = Path(local_output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)

        meta = self.get_file_metadata(file_id)
        mime = meta.get("mimeType", "")

        # Для Google Docs/Sheets/Slides требуется экспорт
        if mime.startswith("application/vnd.google-apps."):
            export_mime = "application/pdf"
            if "spreadsheet" in mime:
                export_mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            elif "document" in mime:
                export_mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            req = service.files().export_media(fileId=file_id, mimeType=export_mime)
        else:
            req = service.files().get_media(fileId=file_id)

        with io.FileIO(str(out_p), "wb") as fh:
            downloader = MediaIoBaseDownload(fh, req)
            done = False
            while not done:
                _, done = downloader.next_chunk()

        return {
            "status": "success",
            "file_id": file_id,
            "name": meta.get("name"),
            "saved_to": str(out_p.resolve()),
            "size": out_p.stat().st_size,
        }

    def get_file_content(self, file_id: str) -> Dict[str, Any]:
        """Получает и возвращает текстовое или бинарное содержимое файла с Google Диска.

        Args:
            file_id: Уникальный ID файла на Google Drive.

        Returns:
            Словарь с метаданными и содержимым:
            status, file_id, name, mime_type, content, is_binary, size, web_view_link.
        """
        service = self.get_service()
        meta = self.get_file_metadata(file_id)
        mime = meta.get("mimeType", "")
        name = meta.get("name", "file")
        web_view_link = meta.get("webViewLink")

        # Если это Google Docs / Sheets
        if mime.startswith("application/vnd.google-apps."):
            export_mime = "text/plain"
            if "spreadsheet" in mime:
                export_mime = "text/csv"
            elif "document" in mime:
                export_mime = "text/plain"
            elif "presentation" in mime:
                export_mime = "text/plain"
            else:
                export_mime = "text/plain"
            try:
                req = service.files().export_media(fileId=file_id, mimeType=export_mime)
                buf = io.BytesIO()
                downloader = MediaIoBaseDownload(buf, req)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
                raw_bytes = buf.getvalue()
                text_content = raw_bytes.decode("utf-8", errors="replace")
                return {
                    "status": "success",
                    "file_id": file_id,
                    "name": name,
                    "mime_type": mime,
                    "content": text_content,
                    "is_binary": False,
                    "size": len(raw_bytes),
                    "web_view_link": web_view_link,
                }
            except Exception as exp_err:
                logger.warning(f"[GoogleDriveClient] Экспорт Google App файла не удался: {exp_err}")
                return {
                    "status": "success",
                    "file_id": file_id,
                    "name": name,
                    "mime_type": mime,
                    "content": None,
                    "is_binary": True,
                    "size": int(meta.get("size", 0) or 0),
                    "web_view_link": web_view_link,
                }

        # Обычный файл: скачиваем буфер
        req = service.files().get_media(fileId=file_id)
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, req)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        raw_bytes = buf.getvalue()

        # Проверка на бинарность (наличие нулевого байта или ошибки декодирования)
        is_binary = b"\x00" in raw_bytes[:1024]
        text_content: Optional[str] = None
        if not is_binary:
            try:
                text_content = raw_bytes.decode("utf-8")
            except UnicodeDecodeError:
                is_binary = True

        return {
            "status": "success",
            "file_id": file_id,
            "name": name,
            "mime_type": mime,
            "content": text_content if not is_binary else None,
            "is_binary": is_binary,
            "size": len(raw_bytes),
            "web_view_link": web_view_link,
        }

    def update_file_content(
        self,
        file_id: str,
        content: str | bytes,
        mime_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Обновляет содержимое файла на Google Диске.

        Args:
            file_id: Уникальный ID файла.
            content: Новое строковое или байтовое содержимое файла.
            mime_type: Опциональный MIME-тип содержимого.

        Returns:
            Словарь с метаданными обновленного файла.
        """
        service = self.get_service()
        raw_bytes = content.encode("utf-8") if isinstance(content, str) else content
        media = MediaIoBaseUpload(io.BytesIO(raw_bytes), mimetype=mime_type or "text/plain", resumable=True)
        updated = (
            service.files()
            .update(
                fileId=file_id,
                media_body=media,
                fields="id, name, mimeType, size, modifiedTime, webViewLink",
            )
            .execute()
        )
        return {"status": "success", "file": updated}

    def delete_file(self, file_id: str) -> Dict[str, Any]:
        """Удаляет файл с Google Диска.

        Args:
            file_id: ID удаляемого файла.

        Returns:
            Словарь со статусом операции.
        """
        service = self.get_service()
        service.files().delete(fileId=file_id).execute()
        return {"status": "success", "file_id": file_id, "deleted": True}
