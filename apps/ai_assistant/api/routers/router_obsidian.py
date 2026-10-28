# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant API - Router Obsidian & Engine
# =============================================================================
# Description:
#   REST API маршрутизатор для управления компактным хранилищем Obsidian Vault
#   внутри рабочих областей (`workspaces/<id>/`) и адаптерами двойного движка
#   оболочки (Engine Adapter API: Electron + WebView2).
#
# Usage Examples:
#   FastAPI Endpoint:
#     GET  /api/v1/workspaces/{workspace_id}/obsidian/status
#     POST /api/v1/workspaces/{workspace_id}/obsidian/build
#     POST /api/v1/workspaces/{workspace_id}/obsidian/topic
#     POST /api/v1/workspaces/{workspace_id}/obsidian/open
#     GET  /api/v1/engine/status
#     POST /api/v1/engine/select
#
# File: router_obsidian.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-23 19:03:00
# =============================================================================

from __future__ import annotations
"""REST API роутер компактного Obsidian Vault и управления движками (Electron / WebView2)."""

from pathlib import Path
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from logger import logger
from apps.ai_assistant.api.routers import router_knowledge
from apps.ai_assistant.core.engine_adapter import EngineRuntimeManager

router = APIRouter(prefix="/api/v1", tags=["Obsidian Vault & Dual-Engine Adapter"])

_engine_manager = EngineRuntimeManager(preferred_engine="electron")


def _get_wm():
    """Возвращает активный экземпляр WorkspaceManager (с учётом тестовых переопределений)."""
    return router_knowledge._workspace_manager


class ObsidianBuildRequest(BaseModel):
    """Запрос на принудительную сборку компактного хранилища Obsidian в рабочей области."""
    commit_to_git: bool = Field(True, description="Зафиксировать обновлённые .md файлы в Git рабочей области")


class ObsidianTopicRequest(BaseModel):
    """Запрос на целенаправленную сборку тематического конспекта в `_Topics/<Тема>.md`."""
    topic: str = Field(..., description="Название темы или досье (например: Ферма Давида)")
    query: Optional[str] = Field(None, description="Поисковый фильтр/запрос для отбора фактов и чанков FAISS")
    commit_to_git: bool = Field(True, description="Зафиксировать конспект в Git рабочей области")


class ObsidianOpenRequest(BaseModel):
    """Запрос на открытие хранилища или конкретной заметки в Obsidian."""
    note_name: Optional[str] = Field("_Knowledge_Base.md", description="Имя файла заметки для открытия")
    engine: Optional[str] = Field(None, description="Предпочтительный движок ('electron' или 'webview2')")


class EngineSelectRequest(BaseModel):
    """Запрос на переключение приоритетного движка оболочки."""
    engine: str = Field(..., description="Идентификатор движка: 'electron' или 'webview2'")


@router.get("/workspaces/{workspace_id}/obsidian/status", summary="Статус компактного Obsidian Vault в рабочей области")
async def get_obsidian_vault_status(workspace_id: str) -> Dict[str, Any]:
    """Возвращает метаданные компактного хранилища Obsidian, список `.md` файлов и URI протокола `obsidian://`."""
    try:
        wm = _get_wm()
        return wm.obsidian.get_vault_status(workspace_id)
    except Exception as exc:
        logger.error(f"[RouterObsidian] Ошибка получения статуса Obsidian Vault для {workspace_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/workspaces/{workspace_id}/obsidian/build", summary="Собрать / обновить компактный Obsidian Vault")
async def build_obsidian_vault(workspace_id: str, req: Optional[ObsidianBuildRequest] = None) -> Dict[str, Any]:
    """Обогащает все документы рабочей области блоками YAML + [[wikilinks]] и пересобирает `_Knowledge_Base.md`."""
    try:
        wm = _get_wm()
        commit_flag = req.commit_to_git if req is not None else True
        return wm.obsidian.build_workspace_vault(workspace_id=workspace_id, commit_to_git=commit_flag)
    except Exception as exc:
        logger.error(f"[RouterObsidian] Ошибка сборки Obsidian Vault в {workspace_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/workspaces/{workspace_id}/obsidian/topic", summary="Целенаправленная сборка тематического конспекта Obsidian")
async def compile_obsidian_topic(workspace_id: str, req: ObsidianTopicRequest) -> Dict[str, Any]:
    """Собирает знания по заданной теме или поисковому запросу в заметку `_Topics/<Тема>.md`."""
    if not req.topic or not req.topic.strip():
        raise HTTPException(status_code=422, detail="Название темы не может быть пустым")
    try:
        wm = _get_wm()
        return wm.obsidian.compile_topic_note(
            workspace_id=workspace_id,
            topic=req.topic,
            query=req.query,
            commit_to_git=req.commit_to_git,
        )
    except Exception as exc:
        logger.error(f"[RouterObsidian] Ошибка сборки тематического конспекта '{req.topic}': {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/workspaces/{workspace_id}/obsidian/open", summary="Открыть рабочую область как Vault в Obsidian")
async def open_obsidian_vault(workspace_id: str, req: Optional[ObsidianOpenRequest] = None) -> Dict[str, Any]:
    """Открывает папку рабочей области (`workspaces/<id>/`) в приложении Obsidian через Engine Adapter."""
    try:
        wm = _get_wm()
        ws, ws_path = wm._get_or_create_workspace(workspace_id)
        wm.obsidian.ensure_vault_config(ws_path)
        if not (ws_path / "_Knowledge_Base.md").exists():
            wm.obsidian.rebuild_knowledge_base_index(workspace_id)

        note_name = req.note_name if req else "_Knowledge_Base.md"
        adapter = _engine_manager.get_adapter(req.engine if req else None)
        return adapter.open_obsidian_vault(ws_path, note_name=note_name)
    except Exception as exc:
        logger.error(f"[RouterObsidian] Ошибка открытия Obsidian Vault {workspace_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/engine/status", summary="Статус движков оболочки (Electron и WebView2)")
async def get_engine_status() -> Dict[str, Any]:
    """Возвращает состояние адаптеров обоих движков (Electron + WebView2) и выбранный движок."""
    return _engine_manager.get_status()


@router.post("/engine/select", summary="Выбор активного движка оболочки (Electron или WebView2)")
async def select_engine(req: EngineSelectRequest) -> Dict[str, Any]:
    """Переключает приоритетный движок оболочки между `electron` и `webview2`."""
    try:
        return _engine_manager.set_preferred_engine(req.engine)
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))
