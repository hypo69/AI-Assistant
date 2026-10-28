# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Core - Query Orchestrator
# =============================================================================
# Description:
#   Координатор параллельного 5-этапного гибридного поиска:
#   1. Git History Engine (коммиты, изменения файлов)
#   2. WikiLLM (сущности, статьи, архитектурные решения)
#   3. RAG FAISS Engine (семантический векторный поиск)
#   4. Temporal Code Graph (активные окна валидности связей)
#   5. Слияние и ранжирование результирующего контекста.
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.core.query_orchestrator import QueryOrchestrator
#
#     orchestrator = QueryOrchestrator()
#     response = await orchestrator.search(query="сенсоры температуры", limit=5)
#
# File: query_orchestrator.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 09:38:00
# =============================================================================

from __future__ import annotations
"""Координатор гибридного поиска по Git, WikiLLM и FAISS RAG."""

import asyncio
from typing import Any, Dict, List, Optional

from logger import logger
from apps.ai_assistant.api.schemas import (
    CommitSummary,
    EvidenceLinkSchema,
    QuerySearchRequest,
    QuerySearchResponse,
)
from apps.ai_assistant.core.git_history_engine import GitHistoryEngine
from apps.ai_assistant.core.rag_faiss_engine import RAGFaissEngine
from apps.ai_assistant.core.temporal_code_graph import TemporalCodeGraph
from apps.ai_assistant.core.wikillm_version_linker import WikiLLMVersionLinker


class QueryOrchestrator:
    """Оркестратор параллельного поиска по коду, базе знаний и векторному индексу."""

    def __init__(
        self,
        git_engine: Optional[GitHistoryEngine] = None,
        rag_engine: Optional[RAGFaissEngine] = None,
        temporal_graph: Optional[TemporalCodeGraph] = None,
        wiki_linker: Optional[WikiLLMVersionLinker] = None,
    ) -> None:
        """Инициализирует оркестратор и зависимые подсистемы.

        Args:
            git_engine: Движок истории Git.
            rag_engine: Движок семантического поиска FAISS.
            temporal_graph: Темпоральный граф связей.
            wiki_linker: Линкер базы знаний WikiLLM.
        """
        self.git_engine = git_engine or GitHistoryEngine()
        self.rag_engine = rag_engine or RAGFaissEngine()
        self.temporal_graph = temporal_graph or TemporalCodeGraph()
        self.wiki_linker = wiki_linker or WikiLLMVersionLinker(temporal_graph=self.temporal_graph)

    async def search(self, request: QuerySearchRequest) -> QuerySearchResponse:
        """Выполняет параллельный гибридный поиск по всем подсистемам.

        Args:
            request: Запрос на поиск с фильтрами и параметрами.

        Returns:
            QuerySearchResponse: Агрегированные результаты поиска.
        """
        query = request.query.strip()
        limit = request.limit if request.limit is not None else request.top_k

        # 1. Запуск параллельных задач
        git_task = asyncio.create_task(self._search_git(query, limit))
        rag_task = asyncio.create_task(self._search_rag(query, limit))
        wiki_task = asyncio.create_task(self._search_wiki(query, limit))

        # Ожидаем завершения
        git_results, rag_results, wiki_results = await asyncio.gather(
            git_task, rag_task, wiki_task, return_exceptions=True
        )

        commits: List[CommitSummary] = git_results if isinstance(git_results, list) else []
        rag_chunks: List[Dict[str, Any]] = rag_results if isinstance(rag_results, list) else []
        wiki_entities: List[Dict[str, Any]] = wiki_results if isinstance(wiki_results, list) else []

        # 4. Темпоральные связи графа для найденных коммитов и сущностей
        active_links: List[EvidenceLinkSchema] = []
        try:
            candidate_ids = [c.commit_hash for c in commits] + [w.get("canonical_key", "") for w in wiki_entities]
            candidate_ids = [cid for cid in candidate_ids if cid]
            all_links = self.temporal_graph.get_active_links()
            if candidate_ids:
                active_links = [
                    lnk for lnk in all_links
                    if lnk.source_id in candidate_ids or lnk.target_id in candidate_ids
                ][:limit]
            else:
                active_links = all_links[:limit]
        except Exception as exc:
            logger.error(f"[QueryOrchestrator] Ошибка выборки темпоральных связей: {exc}")

        # 5. Слияние и ранжирование
        total_found = len(commits) + len(rag_chunks) + len(wiki_entities) + len(active_links)

        return QuerySearchResponse(
            query=query,
            total_found=total_found,
            explanation=f"Найдено {total_found} совпадений (коммиты: {len(commits)}, база знаний: {len(wiki_entities)}, RAG: {len(rag_chunks)}).",
            commits=commits,
            rag_chunks=rag_chunks,
            wiki_entities=wiki_entities,
            evidence_links=active_links,
            temporal_links=active_links,
            suggested_quick_questions=[
                "Какие изменения были внесены недавно?",
                "Как связаны компоненты в базе знаний?",
            ],
        )

    async def _search_git(self, query: str, limit: int) -> List[CommitSummary]:
        """Ищет релевантные коммиты через Git log."""
        try:
            return await self.git_engine.get_file_history(search_query=query, limit=limit)
        except Exception as exc:
            logger.warning(f"[QueryOrchestrator] Сбой поиска в Git: {exc}")
            return []

    async def _search_rag(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Ищет чанки в векторном индексе FAISS."""
        try:
            return self.rag_engine.search(query=query, top_k=limit)
        except Exception as exc:
            logger.warning(f"[QueryOrchestrator] Сбой поиска в RAG FAISS: {exc}")
            return []

    async def _search_wiki(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Ищет сущности в WikiLLM."""
        try:
            return self.wiki_linker.find_matching_wiki_entities(text=query, limit=limit)
        except Exception as exc:
            logger.warning(f"[QueryOrchestrator] Сбой поиска в WikiLLM: {exc}")
            return []
