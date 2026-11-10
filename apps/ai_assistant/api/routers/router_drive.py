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
# Updated: 2026-11-10 13:50:00
# =============================================================================

from __future__ import annotations

"""REST API маршрутизатор Google Drive."""

import asyncio
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from apps.ai_assistant.core.skills_bridge import get_drive_client
from header import __root__
from logger import logger

MAX_UPLOAD_BYTES: int = 100 * 1024 * 1024  # 100 МБ
CHUNK_SIZE_BYTES: int = 64 * 1024          # 64 КБ


class DriveFileContentUpdate(BaseModel):
    """Схема запроса на обновление содержимого файла Google Drive."""

    content: str = Field(..., description="Новое содержимое файла")
    mime_type: Optional[str] = Field(default=None, description="MIME тип содержимого")


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

        def _fetch():
            client = get_drive_client(account_name=clean_acc)
            return client.list_files(
                query=clean_q,
                folder_id=clean_folder,
                mime_type=clean_mime,
                max_results=clean_limit,
            )

        files = await asyncio.to_thread(_fetch)
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
    """Загружает переданный файл на Google Диск с защитой от Path Traversal и контролем размера."""
    temp_dir = (__root__ / "scratch" / "uploads").resolve()
    temp_dir.mkdir(parents=True, exist_ok=True)
    raw_name = Path(file.filename or "upload").name
    safe_name = f"{uuid.uuid4().hex[:8]}_{raw_name}"
    temp_path = (temp_dir / safe_name).resolve()

    try:
        temp_path.relative_to(temp_dir)
    except ValueError:
        raise HTTPException(status_code=400, detail="Недопустимое имя файла")

    try:
        total_read = 0
        with open(temp_path, "wb") as out_f:
            while True:
                chunk = await file.read(CHUNK_SIZE_BYTES)
                if not chunk:
                    break
                total_read += len(chunk)
                if total_read > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="Размер загружаемого файла превышает лимит 100 МБ")
                out_f.write(chunk)

        def _do_upload():
            client = get_drive_client(account_name=account_name)
            return client.upload_file(
                local_path=str(temp_path),
                name=raw_name,
                folder_id=folder_id,
                mime_type=file.content_type,
            )

        res = await asyncio.to_thread(_do_upload)
        return res
    except HTTPException:
        raise
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
    """Скачивает файл с Google Диска и отдает клиенту с последующей фоновой очисткой."""
    if not re.fullmatch(r"^[a-zA-Z0-9_-]{1,128}$", file_id.strip()):
        raise HTTPException(status_code=400, detail="Недопустимый идентификатор файла")

    temp_dir = (__root__ / "scratch" / "downloads").resolve()
    temp_dir.mkdir(parents=True, exist_ok=True)
    out_path = (temp_dir / f"download_{uuid.uuid4().hex[:8]}_{file_id.strip()}").resolve()

    try:
        def _do_download():
            client = get_drive_client(account_name=account_name)
            return client.download_file(file_id=file_id, local_output_path=str(out_path))

        res = await asyncio.to_thread(_do_download)
        filename = res.get("name", "downloaded_file")
        return FileResponse(
            path=str(out_path),
            filename=filename,
            background=BackgroundTask(out_path.unlink, missing_ok=True),
        )
    except Exception as exc:
        if out_path.exists():
            out_path.unlink(missing_ok=True)
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

        def _do_get_content():
            client = get_drive_client(account_name=clean_acc)
            return client.get_file_content(file_id=file_id)

        return await asyncio.to_thread(_do_get_content)
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

        def _do_save_content():
            client = get_drive_client(account_name=clean_acc)
            return client.update_file_content(file_id=file_id, content=payload.content, mime_type=payload.mime_type)

        res = await asyncio.to_thread(_do_save_content)
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
        def _do_delete():
            client = get_drive_client(account_name=account_name)
            return client.delete_file(file_id=file_id)

        res = await asyncio.to_thread(_do_delete)
        return res
    except Exception as exc:
        logger.error(f"[RouterDrive] Ошибка удаления файла: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
