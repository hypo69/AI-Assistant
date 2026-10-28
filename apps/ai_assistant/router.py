# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant - REST API Router
# =============================================================================
# Description:
#   FastAPI REST API роутер для модуля умной истории версий: эндпоинты
#   оркестрации запросов, извлечения коммитов, diff, ревизий и связей WikiLLM.
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.router import init_router
#
#     router = init_router()
#     app.include_router(router)
#
# File: router.py
# Project: ai-windows-admin
# Package: apps.ai_assistant
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 16:55:00
# =============================================================================

from __future__ import annotations
"""FastAPI роутер умной истории версий (Git + WikiLLM + RAG)."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from logger import logger
from apps.ai_assistant.git_adapter import GitAdapter
from apps.ai_assistant.models import (
    IndexingStatus,
    KnowledgeLink,
    QueryRequest,
    QueryResponse,
)
from apps.ai_assistant.orchestrator import SmartHistoryOrchestrator
from apps.ai_assistant.rag_retriever import SmartHistoryRAGRetriever
from apps.ai_assistant.wiki_adapter import WikiAdapter

router = APIRouter(
    prefix="/api/v1/ai-assistant/version-history",
    tags=["AI Assistant Version History"],
)

# Ленивая инициализация координатора умной истории (без создания глобальных директорий)
_git_adapter: Optional[GitAdapter] = None
_wiki_adapter: Optional[WikiAdapter] = None
_rag_retriever: Optional[SmartHistoryRAGRetriever] = None
_orchestrator: Optional[SmartHistoryOrchestrator] = None

def get_git_adapter() -> GitAdapter:
    global _git_adapter
    if _git_adapter is None:
        _git_adapter = GitAdapter()
    return _git_adapter

def get_wiki_adapter() -> WikiAdapter:
    global _wiki_adapter
    if _wiki_adapter is None:
        _wiki_adapter = WikiAdapter()
    return _wiki_adapter

def get_rag_retriever() -> SmartHistoryRAGRetriever:
    global _rag_retriever
    if _rag_retriever is None:
        _rag_retriever = SmartHistoryRAGRetriever()
    return _rag_retriever

def get_orchestrator() -> SmartHistoryOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = SmartHistoryOrchestrator(
            git_adapter=get_git_adapter(),
            wiki_adapter=get_wiki_adapter(),
            rag_retriever=get_rag_retriever(),
        )
    return _orchestrator


@router.post(
    "/query",
    response_model=QueryResponse,
    summary="Интеллектуальный запрос по истории изменений",
    description="Запускает 5-этапный конвейер поиска в Git, WikiLLM и RAG с верификацией доказательств.",
)
async def query_version_history(req: QueryRequest) -> QueryResponse:
    """Выполняет умный поиск и анализ эволюции кодовой базы."""
    try:
        return await get_orchestrator().execute_query(req)
    except Exception as exc:
        logger.error(f"[AI Assistant Router] Ошибка выполнения запроса истории: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обработки запроса: {exc}",
        )


@router.get(
    "/commits",
    summary="Список коммитов с фильтрацией",
    description="Возвращает историю коммитов Git с поддержкой фильтра по пути к файлу и поисковому запросу.",
)
async def list_commits(
    max_count: int = Query(30, ge=1, le=200, description="Количество коммитов"),
    file_path: Optional[str] = Query(None, description="Фильтр по пути к файлу"),
    search: Optional[str] = Query(None, description="Поиск по тексту коммита"),
) -> Dict[str, Any]:
    """Возвращает список коммитов репозитория."""
    commits = get_git_adapter().get_commit_history(max_count=max_count, file_path=file_path, search_query=search)
    return {
        "status": "ok",
        "count": len(commits),
        "commits": [
            {
                "commit_hash": c.commit_hash,
                "author": c.author,
                "timestamp": c.timestamp,
                "message": c.message,
            }
            for c in commits
        ],
    }


@router.get(
    "/diff",
    summary="Получение точного diff",
    description="Извлекает унифицированный diff для указанного коммита или конкретного файла.",
)
async def get_commit_diff(
    commit_hash: str = Query(..., description="Хэш коммита"),
    file_path: Optional[str] = Query(None, description="Опциональный путь к файлу"),
) -> Dict[str, Any]:
    """Возвращает точный diff коммита из Git."""
    diff_text = get_git_adapter().get_file_diff(commit_hash, file_path=file_path)
    if not diff_text:
        return {
            "status": "not_found",
            "commit_hash": commit_hash,
            "file_path": file_path,
            "diff": "",
        }
    return {
        "status": "ok",
        "commit_hash": commit_hash,
        "file_path": file_path,
        "diff": diff_text,
    }


@router.get(
    "/file-revision",
    summary="Получение содержимого файла на ревизии",
    description="Восстанавливает точное содержимое файла на указанном коммите Git.",
)
async def get_file_revision(
    commit_hash: str = Query(..., description="Хэш коммита"),
    file_path: str = Query(..., description="Относительный путь к файлу"),
) -> Dict[str, Any]:
    """Возвращает снимок файла на ревизии."""
    revision = get_git_adapter().get_file_revision(commit_hash, file_path)
    if not revision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Файл '{file_path}' не найден на ревизии {commit_hash}",
        )
    return {
        "status": "ok",
        "commit_hash": revision.commit_hash,
        "file_path": revision.file_path,
        "blob_hash": revision.blob_hash,
        "size_bytes": revision.size_bytes,
        "content": revision.content,
    }


@router.post(
    "/index",
    response_model=IndexingStatus,
    summary="Инкрементальная индексация истории",
    description="Сканирует недавние коммиты и добавляет новые фрагменты diff и сообщения в RAG-индекс.",
)
async def index_git_history(
    max_commits: int = Query(25, ge=1, le=100, description="Количество коммитов для индексации"),
) -> IndexingStatus:
    """Запускает инкрементальное обновление RAG-индекса истории."""
    commits = get_git_adapter().get_commit_history(max_count=max_commits)
    total_added = 0
    for c in commits:
        _, changes = get_git_adapter().get_commit_details(c.commit_hash)
        get_wiki_adapter().auto_link_commit(c, changes)
        hunks: List[Any] = []
        for fc in changes[:5]:
            hunks.extend(get_git_adapter().get_diff_hunks(c.commit_hash, fc.file_path))
        added = get_rag_retriever().index_commit(c, hunks)
        total_added += added

    status_obj = get_rag_retriever().get_status()
    status_obj.indexed_chunks = len(get_rag_retriever().chunks)
    return status_obj


@router.get(
    "/knowledge-links",
    summary="Срез связей графа знаний",
    description="Возвращает список связей knowledge_links между коммитами, файлами и статьями WikiLLM.",
)
async def get_knowledge_links(
    limit: int = Query(50, ge=1, le=200, description="Количество связей"),
) -> Dict[str, Any]:
    """Возвращает связи графа знаний."""
    links = get_wiki_adapter().get_all_links(limit=limit)
    return {
        "status": "ok",
        "count": len(links),
        "links": [
            {
                "source_type": l.source_type,
                "source_id": l.source_id,
                "relation_type": l.relation_type,
                "target_type": l.target_type,
                "target_id": l.target_id,
                "confidence": l.confidence,
                "provenance": l.provenance,
                "created_at": l.created_at,
            }
            for l in links
        ],
    }


@router.post(
    "/link",
    summary="Добавление пользовательской связи",
    description="Создаёт связь в графе знаний между коммитом, файлом, ошибкой или статьей WikiLLM.",
)
async def create_knowledge_link(
    source_type: str = Query(..., description="Тип источника (commit, file, issue)"),
    source_id: str = Query(..., description="Идентификатор источника"),
    relation_type: str = Query(..., description="Тип связи (fixes, modifies, documents)"),
    target_type: str = Query(..., description="Тип цели (error, solution, page)"),
    target_id: str = Query(..., description="Идентификатор цели"),
    confidence: float = Query(1.0, ge=0.0, le=1.0, description="Уверенность"),
) -> Dict[str, Any]:
    """Добавляет связь в knowledge_links."""
    link = get_wiki_adapter().add_link(
        source_type=source_type,
        source_id=source_id,
        relation_type=relation_type,
        target_type=target_type,
        target_id=target_id,
        confidence=confidence,
        provenance="user_api",
    )
    return {"status": "ok", "link": link.__dict__}


@router.get(
    "/status",
    summary="Статус модуля умной истории",
    description="Проверяет доступность Git, базы связей WikiLLM и RAG-индекса.",
)
async def get_module_status() -> Dict[str, Any]:
    """Возвращает статус здоровья компонентов модуля."""
    git_ok = get_git_adapter().is_git_available()
    current_head = get_git_adapter().get_current_commit() if git_ok else ""
    rag_status = get_rag_retriever().get_status()

    return {
        "status": "ok",
        "git_available": git_ok,
        "current_head": current_head,
        "indexed_chunks": rag_status.indexed_chunks,
        "rag_index_dir": str(get_rag_retriever().index_dir),
        "wiki_db_path": str(get_wiki_adapter().db_path),
    }


def init_router() -> APIRouter:
    """Инициализирует и возвращает экземпляр APIRouter для авто-обнаружения."""
    return router
