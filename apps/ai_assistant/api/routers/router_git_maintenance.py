# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant API - Router Git Maintenance
# =============================================================================
# Description:
#   REST API маршрутизатор для управления обслуживанием Git-репозитория:
#   периодический запуск git gc, ручная сборка мусора, чтение метрик,
#   мониторинг активного репозитория, переключение контекста и fsck.
#
# Usage Examples:
#   FastAPI Endpoint:
#     GET  /api/v1/git/maintenance/status
#     GET  /api/v1/git/maintenance/diagnosis?repo_path=.
#     GET  /api/v1/git/maintenance/repositories
#     POST /api/v1/git/maintenance/gc-auto
#
# File: router_git_maintenance.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-27 23:33:00
# =============================================================================

from __future__ import annotations
"""Маршрутизатор API управления оптимизацией репозитория и расписанием git gc."""

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from logger import logger
from apps.ai_assistant.core.git_maintenance import git_maintenance_service
from apps.ai_assistant.core.git_maintenance_analyzer import (
    git_maintenance_analyzer,
    DiagnosisResult,
)
from apps.ai_assistant.core.repo_resolver import resolve_repo_path

router = APIRouter(prefix="/api/v1/git/maintenance", tags=["Git Maintenance & GC"])


def _resolve_target_path(repo_path: Optional[str] = None, workspace_id: Optional[str] = None) -> Optional[str]:
    """Разрешает путь к целевому репозиторию с поддержкой workspace_id."""
    if repo_path:
        return repo_path
    if workspace_id:
        target = resolve_repo_path(workspace_id=workspace_id)
        return str(target)
    return None


class ScheduleConfigRequest(BaseModel):
    """Схема настройки расписания git gc."""
    auto_gc_enabled: bool = Field(True, description="Флаг включения периодического выполнения git gc")
    gc_interval_hours: int = Field(24, ge=1, le=720, description="Интервал в часах между запусками (1-720)")
    aggressive: bool = Field(False, description="Агрессивная перепаковка объектов")
    auto_prune: bool = Field(True, description="Удаление недостижимых объектов (--prune=now)")


class ActiveRepoSetRequest(BaseModel):
    """Схема глобальной установки активного Git-репозитория."""
    repo_path: str = Field(..., description="Абсолютный путь к целевому Git-репозиторию")
    workspace_id: Optional[str] = Field(None, description="Опциональный идентификатор рабочей области")


class GcRunRequest(BaseModel):
    """Схема параметров ручного запуска git gc."""
    aggressive: bool = Field(False, description="Выполнять ли агрессивную сборку")
    prune: bool = Field(True, description="Удалять ли недостижимые объекты немедленно")
    repo_path: Optional[str] = Field(None, description="Опциональный путь к целевому репозиторию")


@router.get("/status", summary="Получение статуса обслуживания Git и метрик объектов")
async def get_maintenance_status() -> Dict[str, Any]:
    """Возвращает текущие параметры расписания, метрики loose-объектов и дату последнего git gc."""
    return await asyncio.to_thread(git_maintenance_service.get_status)


@router.get("/repositories", summary="Список доступных Git-репозиториев (только рабочие пространства)")
async def get_repositories() -> List[Dict[str, str]]:
    """Возвращает список репозиториев исключительно рабочих пространств из data/workspaces."""
    return await asyncio.to_thread(git_maintenance_analyzer.get_available_repos)


@router.get("/active-repo", summary="Получение глобально активного Git-репозитория")
async def get_active_repo() -> Dict[str, Any]:
    """Возвращает информацию о текущем глобально активном репозитории и рабочей области."""
    from apps.ai_assistant.core.workspace_manager import WorkspaceManager
    from apps.ai_assistant.api.routers.router_knowledge import _workspace_manager as wm
    saved = wm.store.get_active_repo()
    repo_path = saved.get("repo_path")
    workspace_id = saved.get("workspace_id")
    resolved_path = resolve_repo_path(workspace_id=workspace_id, repo_path=repo_path)
    from apps.ai_assistant.core.workspace_registry import WorkspaceRegistry, resolve_workspaces_dir
    ws_dir = resolve_workspaces_dir()
    workspaces = WorkspaceRegistry(ws_dir).list_workspaces()
    if (not repo_path or not resolved_path.exists()) and workspaces:
        active_ws_id = wm.store.get_active_workspace_id()
        selected_ws = next((w for w in workspaces if w["workspace_id"] == active_ws_id), workspaces[0])
        resolved_path = Path(selected_ws["path"]).resolve()
        workspace_id = selected_ws["workspace_id"]
        wm.store.set_active_repo(str(resolved_path), workspace_id)
    meta = git_maintenance_analyzer.get_repo_meta(resolved_path)
    return {
        "status": "ok",
        "repo_path": str(resolved_path).replace("\\", "/"),
        "workspace_id": workspace_id or "",
        "repo_name": meta.get("repo_name", ""),
        "current_branch": meta.get("current_branch", ""),
        "current_commit": meta.get("current_commit", ""),
    }


@router.post("/active-repo", summary="Глобальная установка активного Git-репозитория")
async def set_active_repo(req: ActiveRepoSetRequest) -> Dict[str, Any]:
    """Глобально фиксирует активный Git-репозиторий и связанную рабочую область."""
    from apps.ai_assistant.core.workspace_manager import WorkspaceManager
    p = Path(req.repo_path).resolve()
    if not p.exists() or not p.is_dir():
        raise HTTPException(status_code=400, detail=f"Путь репозитория не существует: {req.repo_path}")
    norm_path = str(p).replace("\\", "/")
    from apps.ai_assistant.api.routers.router_knowledge import _workspace_manager as wm
    wm.store.set_active_repo(norm_path, req.workspace_id)
    meta = git_maintenance_analyzer.get_repo_meta(p)
    return {
        "status": "ok",
        "repo_path": norm_path,
        "workspace_id": req.workspace_id or "",
        "repo_name": meta.get("repo_name", ""),
        "current_branch": meta.get("current_branch", ""),
        "current_commit": meta.get("current_commit", ""),
        "message": f"Активный репозиторий успешно установлен: {meta.get('repo_name', norm_path)}",
    }


@router.get("/diagnosis", response_model=DiagnosisResult, summary="Интеллектуальная диагностика состояния Git")
async def get_maintenance_diagnosis(
    repo_path: Optional[str] = Query(None, description="Путь к целевому репозиторию (или репозиторий проекта по умолчанию)"),
    workspace_id: Optional[str] = Query(None, description="Идентификатор рабочей области"),
) -> DiagnosisResult:
    """Выполняет оценку показателей активного репозитория и возвращает вердикт: Норма / Наблюдение / Обслуживание."""
    resolved = _resolve_target_path(repo_path, workspace_id)
    return await asyncio.to_thread(git_maintenance_analyzer.diagnose, resolved)


@router.get("/history", summary="История диагностических срезов репозитория")
async def get_maintenance_history(limit: int = 20) -> List[Dict[str, Any]]:
    """Возвращает журнал предыдущих диагностических замеров и принятых решений."""
    return await asyncio.to_thread(git_maintenance_analyzer.get_history, limit)


@router.post("/gc-auto", summary="Запуск штатного обслуживания git gc --auto")
async def run_gc_auto(
    repo_path: Optional[str] = Query(None, description="Опциональный путь к целевому репозиторию"),
    workspace_id: Optional[str] = Query(None, description="Идентификатор рабочей области"),
) -> Dict[str, Any]:
    """Запускает git gc --auto, принимающий решение на основе встроенных порогов Git."""
    resolved = _resolve_target_path(repo_path, workspace_id)
    return await asyncio.to_thread(git_maintenance_analyzer.run_gc_auto, resolved)


@router.post("/fsck", summary="Проверка доступности и целостности объектов git fsck")
async def run_fsck(
    repo_path: Optional[str] = Query(None, description="Опциональный путь к целевому репозиторию"),
    workspace_id: Optional[str] = Query(None, description="Идентификатор рабочей области"),
) -> Dict[str, Any]:
    """Запускает git fsck --full для проверки целостности всех объектов базы данных Git."""
    resolved = _resolve_target_path(repo_path, workspace_id)
    return await asyncio.to_thread(git_maintenance_analyzer.run_fsck, resolved)


@router.post("/schedule", summary="Настройка периодического выполнения git gc")
async def update_maintenance_schedule(request: ScheduleConfigRequest) -> Dict[str, Any]:
    """Сохраняет настройки автоматического запуска git gc в config.json."""
    updated = await asyncio.to_thread(
        git_maintenance_service.update_config,
        auto_gc_enabled=request.auto_gc_enabled,
        gc_interval_hours=request.gc_interval_hours,
        aggressive=request.aggressive,
        auto_prune=request.auto_prune,
    )
    logger.info(f"[RouterGitMaintenance] Обновлено расписание git gc: enabled={request.auto_gc_enabled}, interval={request.gc_interval_hours}h")
    return updated


@router.post("/gc-now", summary="Немедленный запуск оптимизации репозитория git gc")
async def run_git_gc_now(request: GcRunRequest) -> Dict[str, Any]:
    """Запускает сборку мусора и оптимизацию Git в отдельном рабочем потоке."""
    status = git_maintenance_service.get_status()
    if status.get("is_running"):
        raise HTTPException(status_code=409, detail="Оптимизация git gc уже выполняется в данный момент")

    result = await asyncio.to_thread(
        git_maintenance_service.run_gc,
        aggressive=request.aggressive,
        prune=request.prune,
    )
    if not result.get("success", False):
        raise HTTPException(status_code=500, detail=result.get("error", "Ошибка выполнения git gc"))

    return result
