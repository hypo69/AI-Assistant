# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-assistant Common File Tree - FastAPI Router
# =============================================================================
# Description:
#   REST API маршрутизатор древовидного проводника файлов и папок
#   (apps/common/file_tree).
#   Предоставляет эндпоинты для:
#   - Обзора и рекурсивного сканирования выбранной директории (/browse).
#   - Быстрой аналитической сводки по файлу (/summary).
#   - Создания новых файлов и папок в выбранной директории (/create).
#   - Получения списка каталогов для навигации (/directories).
#
# File: router.py
# Project: ai-assistant
# Package: apps.common.file_tree
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 19:55:00
# =============================================================================

from __future__ import annotations
"""FastAPI роутер модуля проводника дерева файлов `/api/v1/file-tree`."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query

from logger import logger
from apps.common.file_tree.models import (
    CreateItemRequest,
    CreateItemResponse,
    DirectoryBrowseResponse,
    FileSummaryResponse,
)
from apps.common.file_tree.service import FileTreeService

router = APIRouter(prefix="/api/v1/file-tree", tags=["Common File Tree Explorer"])
_tree_service = FileTreeService()


@router.get("/browse", response_model=DirectoryBrowseResponse, summary="Обзор файлов и папок выбранной директории")
async def browse_directory(
    dir_path: str = Query(default="", description="Относительный путь к директории (пусто для корня)"),
    workspace_id: Optional[str] = Query(default=None, description="Идентификатор рабочей области"),
    max_depth: int = Query(default=8, ge=1, le=20, description="Максимальная глубина рекурсии"),
) -> DirectoryBrowseResponse:
    """Возвращает дерево файлов, цепочку хлебных крошек и родительский каталог для выбранной директории."""
    try:
        return _tree_service.browse_directory(
            dir_path=dir_path,
            workspace_id=workspace_id,
            max_depth=max_depth,
        )
    except FileNotFoundError as fnf:
        raise HTTPException(status_code=404, detail=str(fnf))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        logger.error(f"[FileTreeRouter] Ошибка обзора директории '{dir_path}': {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/summary", response_model=FileSummaryResponse, summary="Краткая аналитическая сводка о файле")
async def get_file_summary(
    rel_path: str = Query(..., description="Относительный путь к файлу в рабочей области"),
    workspace_id: Optional[str] = Query(default=None, description="Идентификатор рабочей области"),
) -> FileSummaryResponse:
    """Возвращает метаданные, количество строк, тип файла и краткое описание сути для контекстного меню."""
    try:
        return _tree_service.get_file_summary(
            rel_path=rel_path,
            workspace_id=workspace_id,
        )
    except FileNotFoundError as fnf:
        raise HTTPException(status_code=404, detail=str(fnf))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        logger.error(f"[FileTreeRouter] Ошибка получения сводки по файлу '{rel_path}': {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/create", response_model=CreateItemResponse, summary="Создание файла или директории в целевом каталоге")
async def create_file_or_directory(
    req: CreateItemRequest,
) -> CreateItemResponse:
    """Создает новый файл или каталог строго в той директории, где был совершен вызов/клик."""
    try:
        return _tree_service.create_item(req)
    except FileNotFoundError as fnf:
        raise HTTPException(status_code=404, detail=str(fnf))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        logger.error(f"[FileTreeRouter] Ошибка создания объекта '{req.name}': {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/directories", summary="Список доступных каталогов рабочей области")
async def list_available_directories(
    workspace_id: Optional[str] = Query(default=None, description="Идентификатор рабочей области"),
) -> List[Dict[str, str]]:
    """Возвращает список всех каталогов для быстрого перехода в навигации."""
    try:
        return _tree_service.list_directories(workspace_id=workspace_id)
    except Exception as exc:
        logger.error(f"[FileTreeRouter] Ошибка получения списка каталогов: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
