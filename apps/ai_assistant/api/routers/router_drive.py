# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant - Google Drive REST Router
# =============================================================================
# Description:
#   FastAPI маршрутизатор управления Google Диском через навык google-drive.
#   Предоставляет endpoints для листинга файлов, выгрузки, скачивания и удаления.
#
# File: router_drive.py
# Package: apps.ai_assistant.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 19:00:00
# =============================================================================

from __future__ import annotations

"""REST API маршрутизатор Google Drive."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from apps.ai_assistant.core.skills_bridge import get_drive_client
from header import __root__
from logger import logger

class DriveFileContentUpdate(BaseModel):
    """Схема запроса на обновление содержимого файла Google Drive."""

    content: str = Field(..., description="Новое содержимое файла")
    mime_type: Optional[str] = Field(None, description="MIME тип содержимого")


router = APIRouter(prefix="/api/v1/drive", tags=["Google Drive"])


@router.get("/files", summary="Список файлов и папок")
async def list_files(
    q: Optional[str] = Query(None, description="Поисковый запрос (name contains ...)"),
    folder_id: Optional[str] = Query(None, description="ID родительской папки"),
    mime_type: Optional[str] = Query(None, description="Фильтр по MIME типу"),
    limit: int = Query(30, ge=1, le=100, description="Лимит файлов"),
    account_name: Optional[str] = Query(None, description="Имя аккаунта"),
) -> Dict[str, Any]:
    """Возвращает список файлов на Google Диске."""
    try:
        clean_q = q if isinstance(q, str) and q.strip() else None
        clean_folder = folder_id if isinstance(folder_id, str) and folder_id.strip() else None
        clean_mime = mime_type if isinstance(mime_type, str) and mime_type.strip() else None
        clean_limit = limit if isinstance(limit, int) else 30
        clean_acc = account_name if isinstance(account_name, str) and account_name.strip() else None

        client = get_drive_client(account_name=clean_acc)
        files = client.list_files(
            query=clean_q,
            folder_id=clean_folder,
            mime_type=clean_mime,
            max_results=clean_limit,
        )
        return {"status": "success", "count": len(files), "files": files}
    except Exception as exc:
        logger.error(f"[RouterDrive] Ошибка получения файлов: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/upload", summary="Загрузка файла на Google Drive")
async def upload_file(
    file: UploadFile = File(...),
    folder_id: Optional[str] = Form(None),
    account_name: Optional[str] = Form(None),
) -> Dict[str, Any]:
    """Загружает переданный файл на Google Диск."""
    temp_dir = __root__ / "scratch" / "uploads"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / file.filename

    try:
        content = await file.read()
        temp_path.write_bytes(content)

        client = get_drive_client(account_name=account_name)
        res = client.upload_file(
            local_path=str(temp_path),
            name=file.filename,
            folder_id=folder_id,
            mime_type=file.content_type,
        )
        return res
    except Exception as exc:
        logger.error(f"[RouterDrive] Ошибка выгрузки файла: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)


@router.get("/download/{file_id}", summary="Скачивание файла с Google Drive")
async def download_file(
    file_id: str,
    account_name: Optional[str] = Query(None, description="Имя аккаунта"),
) -> FileResponse:
    """Скачивает файл с Google Диска и отдает клиенту."""
    temp_dir = __root__ / "scratch" / "downloads"
    temp_dir.mkdir(parents=True, exist_ok=True)
    out_path = temp_dir / f"download_{file_id}"

    try:
        client = get_drive_client(account_name=account_name)
        res = client.download_file(file_id=file_id, local_output_path=str(out_path))
        filename = res.get("name", "downloaded_file")
        return FileResponse(path=str(out_path), filename=filename)
    except Exception as exc:
        logger.error(f"[RouterDrive] Ошибка скачивания файла: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/files/{file_id}/content", summary="Получение содержимого файла")
async def get_file_content(
    file_id: str,
    account_name: Optional[str] = Query(None, description="Имя аккаунта"),
) -> Dict[str, Any]:
    """Возвращает текстовое содержимое или статус бинарного файла с Google Drive."""
    try:
        clean_acc = account_name if isinstance(account_name, str) and account_name.strip() else None
        client = get_drive_client(account_name=clean_acc)
        return client.get_file_content(file_id=file_id)
    except Exception as exc:
        logger.error(f"[RouterDrive] Ошибка чтения содержимого файла {file_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/files/{file_id}/content", summary="Сохранение содержимого файла")
async def save_file_content(
    file_id: str,
    payload: DriveFileContentUpdate,
    account_name: Optional[str] = Query(None, description="Имя аккаунта"),
) -> Dict[str, Any]:
    """Сохраняет отредактированное текстовое содержимое файла на Google Drive."""
    try:
        clean_acc = account_name if isinstance(account_name, str) and account_name.strip() else None
        client = get_drive_client(account_name=clean_acc)
        res = client.update_file_content(file_id=file_id, content=payload.content, mime_type=payload.mime_type)
        return res
    except Exception as exc:
        logger.error(f"[RouterDrive] Ошибка сохранения содержимого файла {file_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/files/{file_id}", summary="Удаление файла")
async def delete_file(
    file_id: str,
    account_name: Optional[str] = Query(None, description="Имя аккаунта"),
) -> Dict[str, Any]:
    """Удаляет файл с Google Диска."""
    try:
        client = get_drive_client(account_name=account_name)
        res = client.delete_file(file_id=file_id)
        return res
    except Exception as exc:
        logger.error(f"[RouterDrive] Ошибка удаления файла: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
