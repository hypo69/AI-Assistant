# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant - Smart History Orchestrator
# =============================================================================
# Description:
#   Координатор умной истории версий: пятиэтапный конвейер объединения Git,
#   WikiLLM и RAG для ответов на запросы об эволюции кодовой базы и причинах изменений.
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.orchestrator import SmartHistoryOrchestrator
#
#     orchestrator = SmartHistoryOrchestrator()
#     response = await orchestrator.execute_query(QueryRequest(query="Когда исправили телеметрию?"))
#
# File: orchestrator.py
# Project: ai-windows-admin
# Package: apps.ai_assistant
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 07:25:00
# =============================================================================

from __future__ import annotations
"""Координатор умного поиска и сопоставления истории версий (Git + WikiLLM + RAG)."""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from logger import logger
from apps.ai_assistant.git_adapter import GitAdapter
from apps.ai_assistant.models import (
    EvidenceItem,
    GitCommitInfo,
    KnowledgeLink,
    QueryRequest,
    QueryResponse,
)
from apps.ai_assistant.rag_retriever import SmartHistoryRAGRetriever
from apps.ai_assistant.wiki_adapter import WikiAdapter


class SmartHistoryOrchestrator:
    """Главный оркестратор конвейера умной истории версий.

    Реализует 5 этапов обработки:
    1. Разбор намерения и извлечение сущностей (файлы, хэши, ключевые слова).
    2. Многоканальный параллельный поиск в Git, WikiLLM и RAG.
    3. Разрешение перекрёстных связей по идентификаторам сущностей.
    4. Верификация доказательств (извлечение точного diff и ревизий из Git).
    5. Синтез экспертного ответа с точными ссылками и быстрыми вопросами.
    """

    def __init__(
        self,
        git_adapter: Optional[GitAdapter] = None,
        wiki_adapter: Optional[WikiAdapter] = None,
        rag_retriever: Optional[SmartHistoryRAGRetriever] = None,
    ) -> None:
        """Инициализирует оркестратор с зависимостями.

        Args:
            git_adapter: Экземпляр адаптера Git.
            wiki_adapter: Экземпляр адаптера WikiLLM.
            rag_retriever: Экземпляр ретривера RAG.
        """
        self.git = git_adapter or GitAdapter()
        self.wiki = wiki_adapter or WikiAdapter()
        self.rag = rag_retriever or SmartHistoryRAGRetriever()

    def _extract_entities(self, query: str) -> Dict[str, Any]:
        """Этап 1: Извлекает ключевые слова, пути файлов, хэши коммитов и намерения.

        Args:
            query: Запрос пользователя.

        Returns:
            Dict[str, Any]: Словарь с распарсенными сущностями.
        """
        q_lower = query.lower()

        # Поиск возможных хэшей коммитов (7-40 символов hex)
        commit_matches = re.findall(r"\b([0-9a-f]{7,40})\b", q_lower)

        # Поиск путей файлов (.py, .js, .json, .html, .css, .md, .ps1)
        file_matches = re.findall(r"[\w/\\]+\.(?:py|js|json|html|css|md|ps1|ts|txt)\b", query)

        # Определение намерения
        needs_diff = any(w in q_lower for w in ["diff", "разниц", "дифф", "изменен", "строк"])
        needs_why = any(w in q_lower for w in ["почему", "зачем", "причин", "обоснован"])
        needs_when = any(w in q_lower for w in ["когда", "верси", "коммит", "истори"])

        return {
            "query": query,
            "commit_hashes": commit_matches,
            "file_paths": file_matches,
            "needs_diff": needs_diff,
            "needs_why": needs_why,
            "needs_when": needs_when,
        }

    async def execute_query(self, req: QueryRequest) -> QueryResponse:
        """Выполняет полный 5-этапный конвейер умного поиска по истории.

        Args:
            req: Параметры входящего запроса.

        Returns:
            QueryResponse: Структурированный ответ с объяснением и доказательствами.
        """
        entities = self._extract_entities(req.query)
        target_file = req.file_path or (entities["file_paths"][0] if entities["file_paths"] else None)

        # Этап 2: Параллельный/многоканальный поиск
        # 2.1 Поиск в RAG
        rag_hits = self.rag.search(
            query=req.query,
            top_k=req.top_k,
            version_filter=req.version_filter,
            file_path=target_file,
        )

        # 2.2 Поиск в Git (по сообщению или пути к файлу)
        git_commits: List[GitCommitInfo] = []
        if entities["commit_hashes"]:
            for h in entities["commit_hashes"]:
                c_info, _ = self.git.get_commit_details(h)
                if c_info:
                    git_commits.append(c_info)

        if not git_commits:
            # Ищем коммиты по тексту запроса
            words = [w for w in req.query.split() if len(w) > 3][:3]
            search_term = " ".join(words) if words else None
            git_commits = self.git.get_commit_history(
                max_count=req.top_k,
                file_path=target_file,
                search_query=search_term,
            )

        # Если поиск по grep не дал результатов, берем последние коммиты по файлу
        if not git_commits and target_file:
            git_commits = self.git.get_commit_history(max_count=req.top_k, file_path=target_file)

        # 2.3 Поиск в WikiLLM
        wiki_hits = self.wiki.search_wiki_knowledge(req.query, limit=req.top_k) if req.include_wiki else []

        # Этап 3: Разрешение ссылок и формирование Evidence
        evidence_items: List[EvidenceItem] = []
        found_commit_hashes: Set[str] = {c.commit_hash for c in git_commits}
        knowledge_links: List[KnowledgeLink] = []

        # Добавляем RAG результаты в Evidence
        for hit in rag_hits:
            c_hash = hit.get("commit_hash", "")
            f_path = hit.get("file_path", "")
            if c_hash:
                found_commit_hashes.add(c_hash)
            evidence_items.append(
                EvidenceItem(
                    source_type=hit.get("source_type", "chunk"),
                    title=f"RAG совпадение ({hit.get('source_type')})",
                    snippet=hit.get("snippet", ""),
                    commit_hash=c_hash,
                    file_path=f_path,
                    score=hit.get("score", 0.0),
                    provenance="rag_index",
                )
            )

        # Сбор связей из WikiLLM для найденных коммитов
        for c_hash in list(found_commit_hashes)[:5]:
            links = self.wiki.get_links_for_source("commit", c_hash)
            knowledge_links.extend(links)
            for link in links:
                evidence_items.append(
                    EvidenceItem(
                        source_type="wiki_link",
                        title=f"Связь знаний: {link.relation_type} -> {link.target_id}",
                        snippet=f"Коммит {c_hash[:8]} {link.relation_type} {link.target_type}:{link.target_id} (уверенность: {link.confidence})",
                        commit_hash=c_hash,
                        score=link.confidence,
                        provenance=link.provenance,
                    )
                )

        # Добавляем статьи Wiki
        for w in wiki_hits:
            evidence_items.append(
                EvidenceItem(
                    source_type="wiki_page",
                    title=f"Статья Wiki: {w.get('name')}",
                    snippet=w.get("summary", ""),
                    score=0.8,
                    provenance="wikillm",
                )
            )

        # Этап 4: Верификация и извлечение точного diff из Git
        diff_map: Dict[str, str] = {}
        if req.include_diff:
            for c_hash in list(found_commit_hashes)[:3]:
                raw_diff = self.git.get_file_diff(c_hash, file_path=target_file)
                if raw_diff:
                    # Ограничиваем diff первыми 150 строками для экономии контекста
                    diff_lines = raw_diff.splitlines()[:150]
                    diff_map[c_hash[:8]] = "\n".join(diff_lines)

        # Этап 5: Синтез ответа и динамических быстрых вопросов
        explanation = self._synthesize_explanation(
            query=req.query,
            commits=git_commits,
            evidence=evidence_items,
            diff_map=diff_map,
            entities=entities,
        )

        quick_questions = self._generate_quick_questions(
            commits=git_commits,
            target_file=target_file,
            entities=entities,
        )

        commits_dto = [
            {
                "commit_hash": c.commit_hash,
                "author": c.author,
                "timestamp": c.timestamp,
                "message": c.message,
                "files_changed_count": c.files_changed_count,
            }
            for c in git_commits
        ]

        links_dto = [
            {
                "source_type": l.source_type,
                "source_id": l.source_id,
                "relation_type": l.relation_type,
                "target_type": l.target_type,
                "target_id": l.target_id,
                "confidence": l.confidence,
            }
            for l in knowledge_links
        ]

        return QueryResponse(
            query=req.query,
            explanation=explanation,
            suggested_quick_questions=quick_questions,
            evidence=evidence_items,
            commits=commits_dto,
            diffs=diff_map,
            knowledge_links=links_dto,
            status="ok",
        )

    def _synthesize_explanation(
        self,
        query: str,
        commits: List[GitCommitInfo],
        evidence: List[EvidenceItem],
        diff_map: Dict[str, str],
        entities: Dict[str, Any],
    ) -> str:
        """Синтезирует связное объяснение на основе проверенных фактов без галлюцинаций.

        Args:
            query: Запрос пользователя.
            commits: Найденные коммиты.
            evidence: Собранные доказательства.
            diff_map: Карта извлеченных diff.
            entities: Сущности запроса.

        Returns:
            str: Текст ответа в формате Markdown.
        """
        lines: List[str] = []
        lines.append(f"### 🔍 Анализ истории изменений по запросу: *«{query}»*")

        if commits:
            lines.append("\n**Найденные коммиты и ревизии:**")
            for c in commits[:4]:
                lines.append(f"- **`{c.commit_hash[:8]}`** ({c.timestamp[:10]}) — *{c.message}* (автор: {c.author})")
        else:
            lines.append("\nПрямых коммитов по точному совпадению текста не найдено. Анализируются косвенные фрагменты.")

        if diff_map:
            lines.append("\n**Точные изменения (Diff) из репозитория:**")
            for h_short, d_text in diff_map.items():
                first_lines = "\n".join(d_text.splitlines()[:15])
                lines.append(f"```diff\n# Ревизия {h_short}\n{first_lines}\n```")

        if evidence:
            lines.append(f"\n**Источники доказательной базы:** подтверждено {len(evidence)} фактами из Git, RAG и связей WikiLLM.")

        lines.append("\n> [!NOTE]\n> Все ревизии и diff извлечены напрямую из репозитория Git без искажений языковой моделью.")

        return "\n".join(lines)

    def _generate_quick_questions(
        self,
        commits: List[GitCommitInfo],
        target_file: Optional[str],
        entities: Dict[str, Any],
    ) -> List[str]:
        """Генерирует динамические быстрые вопросы (suggested_quick_questions).

        Args:
            commits: Найденные коммиты.
            target_file: Затронутый файл.
            entities: Сущности.

        Returns:
            List[str]: Список рекомендованных вопросов.
        """
        questions: List[str] = []
        if commits:
            top_hash = commits[0].commit_hash[:8]
            questions.append(f"Показать полный diff коммита {top_hash}")
            questions.append(f"Какие файлы были затронуты в {top_hash}?")
        if target_file:
            clean_name = Path(target_file).name
            questions.append(f"Показать всю историю изменений {clean_name}")
            questions.append(f"Восстановить версию {clean_name} до изменения")
        else:
            questions.append("Сравнить последнюю версию с предыдущей")
            questions.append("Какие ошибки исправлялись в недавних коммитах?")

        return questions[:4]
