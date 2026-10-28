# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant API - Router Git WikiLLM
# =============================================================================
# Description:
#   REST API маршрутизатор для связи истории Git с базой знаний WikiLLM:
#   двухшаговая верификация фактов (/annotate), мягкая инвалидация (/supersede),
#   ИИ-суммаризация диффов (/insights) и параллельный гибридный поиск (/query).
#
# Usage Examples:
#   FastAPI Endpoint:
#     POST /api/v1/annotate
#     POST /api/v1/query
#     POST /api/v1/insights
#     GET /api/v1/knowledge-links
#
# File: router_git_wikillm.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-25 23:06:00
# =============================================================================

from __future__ import annotations
"""Маршрутизатор интеграции Git, WikiLLM и RAG."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from logger import logger
from apps.ai_assistant.api.schemas import (
    AnnotationRequest,
    AnnotationResponse,
    EvidenceLinkSchema,
    QuerySearchRequest,
    QuerySearchResponse,
)
from apps.ai_assistant.core.ai_diff_summarizer import AIDiffSummarizer
from apps.ai_assistant.core.git_history_engine import GitHistoryEngine
from apps.ai_assistant.core.query_orchestrator import QueryOrchestrator
from apps.ai_assistant.core.temporal_code_graph import TemporalCodeGraph
from apps.ai_assistant.core.wikillm_version_linker import WikiLLMVersionLinker

router = APIRouter(prefix="/api/v1", tags=["Git WikiLLM & RAG"])

_graph = TemporalCodeGraph()
_linker = WikiLLMVersionLinker(temporal_graph=_graph)
_summarizer = AIDiffSummarizer()
_git_engine = GitHistoryEngine()
_orchestrator = QueryOrchestrator(temporal_graph=_graph, wiki_linker=_linker, git_engine=_git_engine)


class SupersedeRequest(BaseModel):
    """Схема запроса инвалидации связи."""
    source_id: str = Field(..., description="Идентификатор источника")
    target_id: str = Field(..., description="Идентификатор цели")
    invalidating_commit: str = Field(..., description="Хэш отменяющего коммита")


class InsightsRequest(BaseModel):
    """Схема запроса ИИ-суммаризации диффа."""
    commit_hash: str = Field(..., description="Хэш коммита")
    file_path: Optional[str] = Field(None, description="Опциональный путь к файлу")


@router.post("/annotate", response_model=AnnotationResponse, summary="Двухшаговая запись архитектурной связи")
async def create_annotation(request: AnnotationRequest) -> AnnotationResponse:
    """Выполняет двухшаговую верификацию (Candidate Proposal -> Validation Pipeline) и запись связи."""
    # 1. Формирование кандидата
    source_id = request.source_id or request.commit_hash or ""
    target_id = request.target_id or request.fact_title or request.file_path or ""
    valid_from = request.valid_from or source_id or "HEAD"
    summary = request.summary or request.fact_description or ""

    candidate = {
        "source_id": source_id,
        "target_id": target_id,
        "relation_type": request.relation_type,
        "valid_from": valid_from,
        "summary": summary,
        "confidence": request.confidence,
        "provenance": request.provenance,
    }

    # 2. Валидация и санитизация
    is_valid, sanitized, error_msg = _summarizer.validate_candidate(candidate)
    if not is_valid:
        logger.warning(f"[RouterGitWikiLLM] Кандидат отклонен верификатором: {error_msg}")
        raise HTTPException(status_code=422, detail=f"Ошибка валидации: {error_msg}")

    # 3. Фиксация в темпоральном графе
    link = _graph.add_link(
        source_id=sanitized["source_id"],
        target_id=sanitized["target_id"],
        relation_type=sanitized["relation_type"],
        valid_from=sanitized["valid_from"],
        confidence=sanitized["confidence"],
        provenance=sanitized["provenance"],
    )

    return AnnotationResponse(
        status="verified_and_saved",
        link=link,
        verification_passed=True,
    )


@router.post("/supersede", summary="Мягкая инвалидация связи (SUPERSEDED)")
async def supersede_annotation(request: SupersedeRequest) -> Dict[str, Any]:
    """Переводит устаревшую связь в статус SUPERSEDED с фиксацией коммита инвалидации."""
    updated = _graph.supersede_link(
        source_id=request.source_id,
        target_id=request.target_id,
        invalidating_commit=request.invalidating_commit,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Активная связь не найдена для инвалидации")

    return {
        "status": "superseded",
        "source_id": request.source_id,
        "target_id": request.target_id,
        "invalidating_commit": request.invalidating_commit,
    }


@router.get("/knowledge-links", response_model=List[EvidenceLinkSchema], summary="Список связей темпорального графа")
async def get_knowledge_links(
    source_id: Optional[str] = Query(None, description="Фильтр по источнику (коммит или файл)"),
    status: str = Query("ACTIVE", description="Статус связей: ACTIVE или ALL"),
) -> List[EvidenceLinkSchema]:
    """Возвращает срез темпоральных связей графа с поддержкой фильтрации."""
    if status.upper() == "ALL":
        links = _graph.get_all_links()
        if source_id:
            links = [l for l in links if l.source_id == source_id]
        return links
    return _graph.get_active_links(source_id=source_id)


@router.post("/insights", summary="ИИ-анализ диффа и архитектурных последствий")
async def get_diff_insights(request: InsightsRequest) -> Dict[str, Any]:
    """Выполняет суммаризацию diff коммита и формирует предложения связей с WikiLLM."""
    try:
        diff_resp = await _git_engine.get_diff(commit_hash=request.commit_hash, file_path=request.file_path)
        summary = _summarizer.summarize_diff(diff_resp.diff_text, file_path=request.file_path or "")
        wiki_entities = _linker.find_matching_wiki_entities(f"{summary} {request.file_path or ''}")

        return {
            "commit_hash": request.commit_hash,
            "file_path": request.file_path,
            "summary": summary,
            "matched_entities": wiki_entities,
            "truncated": diff_resp.truncated,
        }
    except Exception as exc:
        logger.error(f"[RouterGitWikiLLM] Ошибка генерации инсайтов: {exc}")
        raise HTTPException(status_code=500, detail=f"Ошибка генерации инсайтов: {exc}")


@router.post("/git-wikillm/query", response_model=QuerySearchResponse, summary="Параллельный гибридный поиск (Git + Wiki + RAG)")
async def search_query(request: QuerySearchRequest) -> QuerySearchResponse:
    """Координирует параллельный поиск по всем подсистемам через QueryOrchestrator."""
    try:
        return await _orchestrator.search(request)
    except Exception as exc:
        logger.error(f"[RouterGitWikiLLM] Ошибка выполнения оркестрированного поиска: {exc}")
        raise HTTPException(status_code=500, detail=f"Ошибка гибридного поиска: {exc}")
