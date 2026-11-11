# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Core - RAG FAISS Engine
# =============================================================================
# Description:
#   Инкрементальный векторный RAG-движок на основе FAISS и контентных хэшей SHA-256:
#   индексация коммитов, фрагментов diff и семантический поиск по истории изменений.
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.core.rag_faiss_engine import RagFaissEngine
#
#     engine = RagFaissEngine()
#     added = engine.index_commit(commit_obj, hunks)
#     hits = engine.search("исправление утечки памяти", top_k=5)
#
# File: rag_faiss_engine.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 19:28:00
# =============================================================================

from __future__ import annotations
"""Инкрементальный FAISS RAG-движок для семантического поиска по истории версий."""

from collections import Counter
import hashlib
import json
import os
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from logger import logger
from src.ai.rag.text_rag import TextRAG
from apps.ai_assistant.api.schemas import CommitSummary, DiffHunkItem


def compute_sha256(text: str) -> str:
    """Вычисляет хэш SHA-256 для текста."""
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


class RagFaissEngine:
    """Векторный RAG-движок с дедупликацией и инкрементальным хранилищем."""

    def __init__(self, index_dir: Path | str = "data/rag_index/smart_history") -> None:
        """Инициализирует директорию индекса и загружает метаданные.

        Args:
            index_dir: Путь к директории хранения чанков и индекса.
        """
        self.index_dir = Path(index_dir)
        self.chunks_file = self.index_dir / "chunks.json"
        self.chunks: List[Dict[str, Any]] = []
        self._indexed_hashes: Set[str] = set()
        self._faiss_rag: Optional[TextRAG] = None
        self._lock = threading.RLock()
        if self.index_dir.exists():
            self._load()

    @property
    def faiss_rag(self) -> TextRAG:
        """Ленивая инициализация TextRAG при фактическом обращении."""
        with self._lock:
            if self._faiss_rag is None:
                self.index_dir.mkdir(parents=True, exist_ok=True)
                self._faiss_rag = TextRAG(db_path=self.index_dir / "faiss_vectors", dimension=256)
            return self._faiss_rag

    def _load(self) -> None:
        """Загружает сохраненные чанки."""
        with self._lock:
            if self.chunks_file.is_file():
                try:
                    with open(self.chunks_file, "r", encoding="utf-8") as f:
                        self.chunks = json.load(f)
                    self._indexed_hashes = {c["content_hash"] for c in self.chunks if "content_hash" in c}
                except Exception as exc:
                    logger.warning(f"[RagFaissEngine] Ошибка чтения {self.chunks_file}: {exc}")
                    self.chunks = []
                    self._indexed_hashes = set()

    def _save(self) -> None:
        """Потокобезопасно и атомарно сохраняет метаданные чанков."""
        with self._lock:
            tmp_file: Optional[Path] = None
            try:
                self.index_dir.mkdir(parents=True, exist_ok=True)
                tmp_file = self.chunks_file.parent / f".{self.chunks_file.name}.{uuid.uuid4().hex[:8]}.tmp"
                serializable_chunks = [
                    {k: v for k, v in c.items() if not k.startswith("_")}
                    for c in self.chunks
                ]
                with open(tmp_file, "w", encoding="utf-8") as f:
                    json.dump(serializable_chunks, f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())

                for attempt in range(5):
                    try:
                        os.replace(tmp_file, self.chunks_file)
                        tmp_file = None
                        break
                    except (PermissionError, OSError):
                        if attempt == 4:
                            raise
                        time.sleep(0.05 * (attempt + 1))
            except Exception as exc:
                logger.error(f"[RagFaissEngine] Ошибка сохранения {self.chunks_file}: {exc}")
            finally:
                if tmp_file and tmp_file.exists():
                    try:
                        tmp_file.unlink()
                    except OSError:
                        pass

    def index_commit(self, commit: CommitSummary, hunks: List[DiffHunkItem], file_path: Optional[str] = None) -> int:
        """Инкрементально индексирует коммит и связанные diff hunks.

        Args:
            commit: Метаданные коммита.
            hunks: Список дифференциальных блоков.
            file_path: Путь к затронутому файлу.

        Returns:
            int: Количество добавленных новых блоков.
        """
        with self._lock:
            added = 0

            # 1. Индексация текста коммита
            msg_hash = compute_sha256(f"{commit.commit_hash}:{commit.message}")
            if msg_hash not in self._indexed_hashes:
                text_val = f"Коммит: {commit.commit_hash[:8]} | Автор: {commit.author} | {commit.message}"
                tokens = self._tokenize(text_val)
                chunk = {
                    "chunk_id": f"commit_{commit.commit_hash[:8]}",
                    "source_type": "commit_message",
                    "commit_hash": commit.commit_hash,
                    "file_path": file_path or "",
                    "content_hash": msg_hash,
                    "text": text_val,
                    "timestamp": commit.timestamp,
                    "_token_counts": Counter(tokens),
                    "_total_tokens": len(tokens),
                }
                self.chunks.append(chunk)
                self._indexed_hashes.add(msg_hash)
                added += 1

            # 2. Индексация блоков diff
            for idx, hunk in enumerate(hunks):
                hunk_hash = compute_sha256(f"{commit.commit_hash}:{file_path}:{hunk.hunk_text}")
                if hunk_hash in self._indexed_hashes:
                    continue

                text_val = f"Файл: {file_path}\nКоммит: {commit.commit_hash[:8]}\n{hunk.hunk_text}"
                tokens = self._tokenize(text_val)
                chunk = {
                    "chunk_id": f"diff_{commit.commit_hash[:8]}_{idx}",
                    "source_type": "diff_hunk",
                    "commit_hash": commit.commit_hash,
                    "file_path": file_path or "",
                    "content_hash": hunk_hash,
                    "text": text_val,
                    "timestamp": commit.timestamp,
                    "_token_counts": Counter(tokens),
                    "_total_tokens": len(tokens),
                }
                self.chunks.append(chunk)
                self._indexed_hashes.add(hunk_hash)
                added += 1

            if added > 0:
                self._save()
                new_docs = [
                    {
                        "id": c["chunk_id"],
                        "text": c["text"],
                        "meta": {
                            "chunk_id": c["chunk_id"],
                            "source_type": c["source_type"],
                            "commit_hash": c["commit_hash"],
                            "file_path": c.get("file_path", ""),
                        },
                    }
                    for c in self.chunks[-added:]
                ]
                self.faiss_rag.add_documents(new_docs)

            return added

    def _tokenize(self, text: str) -> List[str]:
        """Токенизирует строку на слова для лексического анализа."""
        return [w.lower() for w in re.findall(r"\w{3,}", text)]

    def search(
        self,
        query: str,
        top_k: int = 5,
        file_path: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Выполняет поиск релевантных фрагментов истории по запросу.

        Args:
            query: Текст запроса на естественном языке.
            top_k: Максимальное количество результатов.
            file_path: Опциональный фильтр пути к файлу.

        Returns:
            List[Dict[str, Any]]: Список ранжированных совпадений.
        """
        q_tokens = self._tokenize(query)
        with self._lock:
            if not q_tokens or not self.chunks:
                return []
            chunks_snapshot = list(self.chunks)

        faiss_scores: Dict[str, float] = {}
        try:
            if self.faiss_rag.count() > 0:
                vec_hits = self.faiss_rag.search(query, top_k=max(top_k * 2, 10))
                for vh in vec_hits:
                    faiss_scores[vh["id"]] = float(vh.get("score", 0.0))
        except Exception as exc:
            logger.debug(f"[RagFaissEngine] Ошибка векторного поиска FAISS: {exc}")

        scored: List[Tuple[float, Dict[str, Any]]] = []
        file_path_lower = file_path.lower() if file_path else None

        for chunk in chunks_snapshot:
            c_file = chunk.get("file_path", "")
            c_file_lower = c_file.lower() if c_file else ""
            if file_path_lower and file_path_lower not in c_file_lower:
                continue

            token_counts = chunk.get("_token_counts")
            total_tokens = chunk.get("_total_tokens", 0)
            if token_counts is None:
                c_tokens = self._tokenize(chunk.get("text", ""))
                token_counts = Counter(c_tokens)
                total_tokens = len(c_tokens)
                chunk["_token_counts"] = token_counts
                chunk["_total_tokens"] = total_tokens

            if not total_tokens:
                continue

            lex_score = 0.0
            for token in q_tokens:
                cnt = token_counts.get(token, 0)
                if cnt > 0:
                    tf = cnt / total_tokens
                    boost = 2.0 if (c_file_lower and token in c_file_lower) else 1.0
                    lex_score += tf * boost

            vec_score = faiss_scores.get(chunk.get("chunk_id", ""), 0.0)
            combined_score = lex_score + (vec_score * 0.5 if lex_score > 0 else (vec_score * 0.35 if vec_score >= 0.45 else 0.0))

            if combined_score > 0.0:
                scored.append((combined_score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)

        return [
            {
                "score": round(score, 4),
                "chunk_id": item["chunk_id"],
                "source_type": item["source_type"],
                "commit_hash": item["commit_hash"],
                "file_path": item.get("file_path", ""),
                "snippet": item["text"][:350] + ("..." if len(item["text"]) > 350 else ""),
                "text": item["text"],
            }
            for score, item in scored[:top_k]
        ]


# Алиас для унификации экспорта
RAGFaissEngine = RagFaissEngine
