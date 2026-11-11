# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant - Document Categorizer REST Router
# =============================================================================
# Description:
#   FastAPI маршрутизатор управления интеллектуальной категоризацией
#   документов, очередью подтверждения Human-in-the-Loop и семантическим RAG-поиском.
#
# Usage Examples:
#   POST /api/v1/documents/scan
#   GET  /api/v1/documents/status
#
# File: router_doc_categorizer.py
# Package: apps.ai_assistant.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 19:56:00
# =============================================================================

from __future__ import annotations

"""REST API маршрутизатор интеллектуальной категоризации документов."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from apps.ai_assistant.core.doc_categorizer import (
    DEFAULT_CATEGORIES,
    doc_categorizer_service
)
from logger import logger

router = APIRouter(prefix="/api/v1/documents", tags=["Smart Document Categorizer"])


class ScanRequest(BaseModel):
    """Схема запроса на сканирование документов."""
    mode: str = Field("auto", description="Режим: 'auto' (библиотеки ОС) или 'explicit' (указанный путь)")
    custom_path: Optional[str] = Field(None, description="Путь к директории при явном режиме")


class ResolveRequest(BaseModel):
    """Схема подтверждения категории пользователем."""
    doc_id: str = Field(..., description="Идентификатор документа")
    category: str = Field(..., description="Выбранная категория")
    create_rule: bool = Field(False, description="Создать ли постоянное правило для похожих файлов")
    rule_pattern: Optional[str] = Field(None, description="Подстрока пути или имени для авто-применения")


class SearchRequest(BaseModel):
    """Схема семантического поиска RAG."""
    query: str = Field(..., description="Поисковый запрос на естественном языке")
    limit: int = Field(10, ge=1, le=50, description="Максимум результатов")


@router.get("/status", summary="Статус сканирования и распределение категорий")
async def get_categorizer_status() -> Dict[str, Any]:
    """Возвращает текущую статистику категоризации и RAG-индекса."""
    try:
        return doc_categorizer_service.get_status()
    except Exception as exc:
        logger.warning(f"[DocRouter] Ошибка получения статуса: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/scan", summary="Запуск фонового сканирования документов")
async def trigger_scan(req: ScanRequest) -> Dict[str, Any]:
    """Запускает фоновый поиск и категоризацию файлов."""
    started = doc_categorizer_service.start_scan(mode=req.mode, custom_path=req.custom_path)
    if not started:
        return {"status": "busy", "message": "Сканирование уже выполняется"}
    return {"status": "started", "mode": req.mode, "custom_path": req.custom_path}


@router.get("/items", summary="Пагинированный список документов")
async def get_documents_list(
    category: Optional[str] = Query(None, description="Фильтр по ключу категории"),
    status: Optional[str] = Query(None, description="Фильтр по статусу ('classified'/'uncertain')"),
    query: Optional[str] = Query(None, description="Поисковая подстрока"),
    limit: int = Query(50, ge=1, le=100, description="Лимит на страницу"),
    offset: int = Query(0, ge=0, description="Смещение")
) -> Dict[str, Any]:
    """Возвращает документы с фильтрами по статусу и категории."""
    return doc_categorizer_service.list_documents(
        category=category,
        status=status,
        query=query,
        limit=limit,
        offset=offset
    )


@router.get("/uncertain", summary="Спорные документы для уточнения у пользователя")
async def get_uncertain_queue(limit: int = Query(20, ge=1, le=50)) -> List[Dict[str, Any]]:
    """Возвращает очередь файлов с низкой уверенностью для интерактивного выбора."""
    return doc_categorizer_service.get_uncertain_documents(limit=limit)


@router.post("/resolve", summary="Применение решения пользователя по документу")
async def resolve_document(req: ResolveRequest) -> Dict[str, Any]:
    """Фиксирует выбранную категорию и обучает правила классификации."""
    success = doc_categorizer_service.resolve_uncertain(
        doc_id=req.doc_id,
        category=req.category,
        create_rule=req.create_rule,
        rule_pattern=req.rule_pattern
    )
    return {"status": "ok", "doc_id": req.doc_id, "resolved": success}


@router.post("/search", summary="Семантический RAG-поиск по базе документов")
async def search_documents_rag(req: SearchRequest) -> Dict[str, Any]:
    """Выполняет полнотекстовый поиск по содержимому и именам документов."""
    results = doc_categorizer_service.search_rag(query=req.query, limit=req.limit)
    return {"query": req.query, "total": len(results), "hits": results}
