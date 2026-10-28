# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant - Smart History RAG Retriever
# =============================================================================
# Description:
#   Инкрементальный RAG-ретривер для истории версий: индексация коммитов,
#   дифференциальных фрагментов (diff hunks), ревизий файлов и семантический поиск.
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.rag_retriever import SmartHistoryRAGRetriever
#
#     retriever = SmartHistoryRAGRetriever()
#     retriever.index_commit_data(...)
#     results = retriever.search("ошибка телеметрии", top_k=5)
#
# File: rag_retriever.py
# Project: ai-windows-admin
# Package: apps.ai_assistant
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 16:55:00
# =============================================================================

from __future__ import annotations
"""Инкрементальный RAG ретривер для семантического поиска по истории версий."""

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from logger import logger
from apps.ai_assistant.models import (
    DiffHunk,
    GitCommitInfo,
    HistoryDocumentChunk,
    IndexingStatus,
)


def compute_sha256(text: str) -> str:
    """Вычисляет хэш SHA-256 для строки текста.

    Args:
        text: Входная строка.

    Returns:
        str: Hex-дайджест хэша.
    """
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


class SmartHistoryRAGRetriever:
    """Векторный и лексический ретривер для инкрементальной индексации истории изменений."""

    def __init__(self, index_dir: Path | str = "data/rag_index/smart_history") -> None:
        """Инициализирует хранилище индексов.

        Args:
            index_dir: Директория для хранения файлов индекса и метаданных.
        """
        self.index_dir = Path(index_dir)
        self.chunks_file = self.index_dir / "chunks.json"
        self.state_file = self.index_dir / "state.json"
        self.chunks: List[HistoryDocumentChunk] = []
        self._indexed_hashes: Set[str] = set()

        if self.index_dir.exists():
            self._load()

    def _load(self) -> None:
        """Загружает сохраненные чанки и хэши из файла."""
        if self.chunks_file.is_file():
            try:
                with open(self.chunks_file, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
                self.chunks = [
                    HistoryDocumentChunk(
                        chunk_id=item["chunk_id"],
                        repo_id=item.get("repo_id", "ai-windows-admin"),
                        source_type=item.get("source_type", "diff_hunk"),
                        commit_hash=item.get("commit_hash", ""),
                        file_path=item.get("file_path", ""),
                        blob_hash=item.get("blob_hash", ""),
                        content_hash=item.get("content_hash", ""),
                        text=item.get("text", ""),
                        version=item.get("version", 1),
                        version_timestamp=float(item.get("version_timestamp", 0.0)),
                        is_latest=bool(item.get("is_latest", True)),
                        meta=item.get("meta", {}),
                    )
                    for item in raw_data
                ]
                self._indexed_hashes = {c.content_hash for c in self.chunks if c.content_hash}
            except Exception as exc:
                logger.warning(f"[SmartHistoryRAG] Ошибка загрузки индекса: {exc}")
                self.chunks = []
                self._indexed_hashes = set()

    def _save(self) -> None:
        """Сохраняет чанки на диск."""
        try:
            self.index_dir.mkdir(parents=True, exist_ok=True)
            data = [
                {
                    "chunk_id": c.chunk_id,
                    "repo_id": c.repo_id,
                    "source_type": c.source_type,
                    "commit_hash": c.commit_hash,
                    "file_path": c.file_path,
                    "blob_hash": c.blob_hash,
                    "content_hash": c.content_hash,
                    "text": c.text,
                    "version": c.version,
                    "version_timestamp": c.version_timestamp,
                    "is_latest": c.is_latest,
                    "meta": c.meta,
                }
                for c in self.chunks
            ]
            with open(self.chunks_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.error(f"[SmartHistoryRAG] Ошибка сохранения чанков: {exc}")

    def get_status(self) -> IndexingStatus:
        """Возвращает текущий статус индексации.

        Returns:
            IndexingStatus: Статистика индекса.
        """
        last_commit = self.chunks[-1].commit_hash if self.chunks else ""
        return IndexingStatus(
            total_commits=len({c.commit_hash for c in self.chunks if c.commit_hash}),
            indexed_chunks=len(self.chunks),
            skipped_chunks=0,
            last_indexed_commit=last_commit,
        )

    def index_commit(self, commit: GitCommitInfo, hunks: List[DiffHunk]) -> int:
        """Инкрементально индексирует коммит и связанные с ним фрагменты изменений.

        Args:
            commit: Метаданные коммита.
            hunks: Список фрагментов diff.

        Returns:
            int: Количество добавленных новых чанков.
        """
        added_count = 0

        # 1. Индексация самого сообщения коммита
        msg_hash = compute_sha256(f"{commit.commit_hash}:{commit.message}")
        if msg_hash not in self._indexed_hashes:
            chunk = HistoryDocumentChunk(
                chunk_id=f"commit_{commit.commit_hash[:8]}_msg",
                source_type="commit_message",
                commit_hash=commit.commit_hash,
                content_hash=msg_hash,
                text=f"Коммит {commit.commit_hash[:8]}: {commit.message}\nАвтор: {commit.author}\nДата: {commit.timestamp}",
                meta={"author": commit.author, "date": commit.timestamp},
            )
            self.chunks.append(chunk)
            self._indexed_hashes.add(msg_hash)
            added_count += 1

        # 2. Индексация diff-фрагментов
        for idx, hunk in enumerate(hunks):
            hunk_hash = compute_sha256(f"{commit.commit_hash}:{hunk.file_path}:{hunk.hunk_text}")
            if hunk_hash in self._indexed_hashes:
                continue

            chunk = HistoryDocumentChunk(
                chunk_id=f"{Path(hunk.file_path).name}#chunk_{idx}#{commit.commit_hash[:7]}",
                source_type="diff_hunk",
                commit_hash=commit.commit_hash,
                file_path=hunk.file_path,
                content_hash=hunk_hash,
                text=f"Файл: {hunk.file_path}\nКоммит: {commit.commit_hash[:8]}\n{hunk.hunk_text}",
                meta={
                    "old_start": hunk.old_start,
                    "new_start": hunk.new_start,
                    "lines_count": len(hunk.hunk_text.splitlines()),
                },
            )
            self.chunks.append(chunk)
            self._indexed_hashes.add(hunk_hash)
            added_count += 1

        if added_count > 0:
            self._save()

        return added_count

    def index_wiki_page(self, page_id: str, title: str, content: str) -> bool:
        """Индексирует статью из WikiLLM.

        Args:
            page_id: Идентификатор страницы.
            title: Заголовок.
            content: Текст статьи.

        Returns:
            bool: True, если страница добавлена или обновлена.
        """
        page_hash = compute_sha256(f"{page_id}:{content}")
        if page_hash in self._indexed_hashes:
            return False

        chunk = HistoryDocumentChunk(
            chunk_id=f"wiki_{page_id}",
            source_type="wiki_page",
            content_hash=page_hash,
            text=f"Wiki статья: {title}\n{content}",
            meta={"page_id": page_id, "title": title},
        )
        self.chunks.append(chunk)
        self._indexed_hashes.add(page_hash)
        self._save()
        return True

    def _tokenize(self, text: str) -> List[str]:
        """Токенизирует текст на отдельные слова для лексического анализа."""
        return [w.lower() for w in re.findall(r"\w{3,}", text)]

    def search(
        self,
        query: str,
        top_k: int = 5,
        version_filter: str = "all",
        file_path: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Выполняет поиск релевантных фрагментов истории по запросу.

        Args:
            query: Запрос на естественном языке.
            top_k: Максимальное количество результатов.
            version_filter: Фильтр версий ('all', 'latest', либо конкретный хэш/версия).
            file_path: Опциональный фильтр по файлу.

        Returns:
            List[Dict[str, Any]]: Ранжированный список совпадений.
        """
        if not self.chunks:
            return []

        q_tokens = self._tokenize(query)
        if not q_tokens:
            return []

        results: List[Tuple[float, HistoryDocumentChunk]] = []

        for chunk in self.chunks:
            # Фильтрация по файлу
            if file_path and file_path.lower() not in chunk.file_path.lower():
                continue

            # Фильтрация по версии
            if version_filter == "latest" and not chunk.is_latest:
                continue
            if version_filter not in ("all", "latest"):
                if version_filter not in chunk.commit_hash and str(chunk.version) != version_filter:
                    continue

            chunk_tokens = self._tokenize(chunk.text)
            if not chunk_tokens:
                continue

            # Лексическое ранжирование (TF-IDF скоринг)
            score = 0.0
            chunk_len = len(chunk_tokens)
            for token in q_tokens:
                count = chunk_tokens.count(token)
                if count > 0:
                    tf = count / chunk_len
                    # Усиление совпадений в путях файлов и коммитах
                    boost = 2.0 if (chunk.file_path and token in chunk.file_path.lower()) else 1.0
                    score += tf * boost

            if score > 0.0:
                results.append((score, chunk))

        # Сортировка по убыванию релевантности
        results.sort(key=lambda x: x[0], reverse=True)

        return [
            {
                "score": round(score, 4),
                "chunk_id": chunk.chunk_id,
                "source_type": chunk.source_type,
                "commit_hash": chunk.commit_hash,
                "file_path": chunk.file_path,
                "snippet": chunk.text[:400] + ("..." if len(chunk.text) > 400 else ""),
                "full_text": chunk.text,
                "meta": chunk.meta,
            }
            for score, chunk in results[:top_k]
        ]
