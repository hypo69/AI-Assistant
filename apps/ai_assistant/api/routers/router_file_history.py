# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant API - Router File History
# =============================================================================
# Description:
#   REST API маршрутизатор для доступа к истории версий Git: коммиты,
#   построчный diff с фильтрацией бинарных файлов, blame и таймлайн.
#
# Usage Examples:
#   FastAPI Endpoint:
#     GET /api/v1/history?file_path=apps/windows/main.py&limit=10
#     GET /api/v1/diff?commit_hash=a1b2c3&file_path=apps/windows/main.py
#     GET /api/v1/timeline?file_path=apps/windows/main.py
#     GET /api/v1/blame?file_path=apps/windows/main.py
#
# File: router_file_history.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-22 16:15:00
# =============================================================================

from __future__ import annotations
"""Маршрутизатор эндпоинтов истории Git, диффов и таймлайна с поддержкой рабочих областей."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query

from logger import logger
from apps.ai_assistant.api.schemas import (
    BlameResponse,
    CommitSummary,
    DiffResponse,
    TimelineResponse,
)
from apps.ai_assistant.core.git_history_engine import GitHistoryEngine
from apps.ai_assistant.core.repo_resolver import resolve_repo_path

router = APIRouter(prefix="/api/v1", tags=["File History"])
_default_git_engine = GitHistoryEngine()


def _get_engine(workspace_id: Optional[str] = None, repo_path: Optional[str] = None) -> GitHistoryEngine:
    """Возвращает движок истории Git для указанной рабочей области или репозитория по умолчанию."""
    if not workspace_id and not repo_path:
        return _default_git_engine
    target = resolve_repo_path(workspace_id=workspace_id, repo_path=repo_path)
    return GitHistoryEngine(repo_path=target)


@router.get("/history", response_model=List[CommitSummary], summary="История коммитов файла или проекта")
async def get_history(
    file_path: Optional[str] = Query(None, description="Относительный путь к файлу"),
    limit: int = Query(50, ge=1, le=200, description="Максимальное число коммитов"),
    search: Optional[str] = Query(None, description="Поисковый запрос по сообщениям коммитов"),
    workspace_id: Optional[str] = Query(None, description="Идентификатор рабочей области"),
    repo_path: Optional[str] = Query(None, description="Путь к репозиторию Git"),
) -> List[CommitSummary]:
    """Возвращает структурированный список коммитов с информацией об авторе и изменениях."""
    try:
        engine = _get_engine(workspace_id=workspace_id, repo_path=repo_path)
        return await engine.get_file_history(file_path=file_path, limit=limit, search_query=search)
    except Exception as exc:
        logger.error(f"[RouterFileHistory] Ошибка получения истории: {exc}")
        raise HTTPException(status_code=500, detail=f"Ошибка чтения истории Git: {exc}")


@router.get("/diff", response_model=DiffResponse, summary="Получение diff изменений коммита")
async def get_diff(
    commit_hash: str = Query(..., description="Хэш коммита"),
    file_path: Optional[str] = Query(None, description="Путь к файлу (опционально)"),
    parent_hash: Optional[str] = Query(None, description="Хэш родительского коммита (опционально)"),
    workspace_id: Optional[str] = Query(None, description="Идентификатор рабочей области"),
    repo_path: Optional[str] = Query(None, description="Путь к репозиторию Git"),
) -> DiffResponse:
    """Возвращает diff изменений между ревизиями с защитой от переполнения буфера."""
    try:
        engine = _get_engine(workspace_id=workspace_id, repo_path=repo_path)
        return await engine.get_diff(commit_hash=commit_hash, file_path=file_path, parent_hash=parent_hash)
    except Exception as exc:
        logger.error(f"[RouterFileHistory] Ошибка формирования diff: {exc}")
        raise HTTPException(status_code=500, detail=f"Ошибка формирования diff: {exc}")


@router.get("/timeline", response_model=TimelineResponse, summary="Таймлайн жизненного цикла файла")
async def get_timeline(
    file_path: str = Query(..., description="Путь к файлу в репозитории"),
    limit: int = Query(50, ge=1, le=200, description="Количество точек шкалы времени"),
    workspace_id: Optional[str] = Query(None, description="Идентификатор рабочей области"),
    repo_path: Optional[str] = Query(None, description="Путь к репозиторию Git"),
) -> TimelineResponse:
    """Формирует хронологическую шкалу контрольных точек изменений файла."""
    try:
        engine = _get_engine(workspace_id=workspace_id, repo_path=repo_path)
        return await engine.get_timeline(file_path=file_path, limit=limit)
    except Exception as exc:
        logger.error(f"[RouterFileHistory] Ошибка формирования таймлайна: {exc}")
        raise HTTPException(status_code=500, detail=f"Ошибка формирования таймлайна: {exc}")


@router.get("/blame", response_model=BlameResponse, summary="Построчная аннотация авторства (blame)")
async def get_blame(
    file_path: str = Query(..., description="Путь к файлу"),
    commit_hash: Optional[str] = Query(None, description="Срез репозитория на конкретный коммит"),
    workspace_id: Optional[str] = Query(None, description="Идентификатор рабочей области"),
    repo_path: Optional[str] = Query(None, description="Путь к репозиторию Git"),
) -> BlameResponse:
    """Возвращает построчный blame для детального аудита изменений строк кода."""
    try:
        commit = commit_hash or "HEAD"
        engine = _get_engine(workspace_id=workspace_id, repo_path=repo_path)
        return await engine.get_blame(file_path=file_path, commit_hash=commit)
    except Exception as exc:
        logger.error(f"[RouterFileHistory] Ошибка построения blame: {exc}")
        raise HTTPException(status_code=500, detail=f"Ошибка чтения git blame: {exc}")


@router.get("/content", summary="Получение содержимого файла на указанный коммит")
async def get_file_content(
    file_path: str = Query(..., description="Путь к файлу"),
    commit_hash: str = Query("HEAD", description="Хэш коммита или ветка"),
    workspace_id: Optional[str] = Query(None, description="Идентификатор рабочей области"),
    repo_path: Optional[str] = Query(None, description="Путь к репозиторию Git"),
) -> Dict[str, Any]:
    """Возвращает текстовое содержимое файла в выбранной ревизии."""
    try:
        engine = _get_engine(workspace_id=workspace_id, repo_path=repo_path)
        content = await engine.get_file_content(commit_hash=commit_hash, file_path=file_path)
        blob_hash = await engine.get_blob_hash(commit_hash=commit_hash, file_path=file_path)
        return {
            "file_path": file_path,
            "commit_hash": commit_hash,
            "blob_hash": blob_hash,
            "content": content,
            "lines_count": len(content.splitlines()),
        }
    except Exception as exc:
        logger.error(f"[RouterFileHistory] Ошибка чтения содержимого файла: {exc}")
        raise HTTPException(status_code=500, detail=f"Ошибка чтения файла: {exc}")
