# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant - Wiki Adapter
# =============================================================================
# Description:
#   Адаптер интеграции с базой знаний WikiLLM: управление устойчивыми связями
#   (knowledge_links) между коммитами, файлами, описаниями изменений и ошибками.
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.wiki_adapter import WikiAdapter
#
#     adapter = WikiAdapter()
#     adapter.add_link(source_type="commit", source_id="abc1234", relation_type="fixes", target_type="error", target_id="ERR_TELEMETRY")
#     links = adapter.get_links_for_source("commit", "abc1234")
#
# File: wiki_adapter.py
# Project: ai-windows-admin
# Package: apps.ai_assistant
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 16:55:00
# =============================================================================

from __future__ import annotations
"""Адаптер связи с базой знаний WikiLLM и графом связей (knowledge_links)."""

import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from logger import logger
from apps.ai_assistant.models import (
    FileChange,
    GitCommitInfo,
    KnowledgeLink,
    get_utc_now_iso,
)


class WikiAdapter:
    """Адаптер для связывания фактов истории Git с базой знаний WikiLLM."""

    def __init__(self, db_path: Path | str = ":memory:") -> None:
        """Инициализирует адаптер базы знаний.

        Args:
            db_path: Путь к файлу базы данных SQLite или ':memory:'.
        """
        self.db_path = Path(db_path) if str(db_path) != ":memory:" else ":memory:"
        self._mem_conn: Optional[sqlite3.Connection] = None
        if self.db_path == ":memory:":
            self._mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._mem_conn.row_factory = sqlite3.Row
        else:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        """Возвращает активное соединение с базой данных SQLite."""
        if self.db_path == ":memory:" and self._mem_conn:
            return self._mem_conn
        conn = sqlite3.connect(str(self.db_path), timeout=10.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        """Создает таблицы связей и метаданных версий, если они отсутствуют."""
        conn = self._get_connection()
        try:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS knowledge_links (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        source_type TEXT NOT NULL,
                        source_id TEXT NOT NULL,
                        relation_type TEXT NOT NULL,
                        target_type TEXT NOT NULL,
                        target_id TEXT NOT NULL,
                        confidence REAL DEFAULT 1.0,
                        provenance TEXT DEFAULT 'heuristic',
                        created_at TEXT NOT NULL,
                        UNIQUE(source_type, source_id, relation_type, target_type, target_id)
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_klinks_source
                    ON knowledge_links (source_type, source_id)
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_klinks_target
                    ON knowledge_links (target_type, target_id)
                    """
                )
        except Exception as exc:
            logger.error(f"[WikiAdapter] Ошибка инициализации схемы knowledge_links: {exc}")
        finally:
            if self.db_path != ":memory:":
                conn.close()

    def add_link(
        self,
        source_type: str,
        source_id: str,
        relation_type: str,
        target_type: str,
        target_id: str,
        confidence: float = 1.0,
        provenance: str = "heuristic",
    ) -> KnowledgeLink:
        """Добавляет направленную связь между двумя сущностями графа знаний.

        Args:
            source_type: Тип источника ('commit', 'file', 'diff_hunk', 'issue', 'page').
            source_id: Идентификатор источника.
            relation_type: Тип отношения ('modifies', 'documents', 'fixes', 'caused_by', 'supersedes', 'depends_on').
            target_type: Тип целевой сущности ('page', 'commit', 'error', 'solution', 'component').
            target_id: Идентификатор цели.
            confidence: Степень уверенности (от 0.0 до 1.0).
            provenance: Происхождение доказательства.

        Returns:
            KnowledgeLink: Созданная или обновленная связь.
        """
        now = get_utc_now_iso()
        conn = self._get_connection()
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO knowledge_links (
                        source_type, source_id, relation_type, target_type, target_id, confidence, provenance, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source_type, source_id, relation_type, target_type, target_id)
                    DO UPDATE SET confidence = excluded.confidence, provenance = excluded.provenance
                    """,
                    (source_type, source_id, relation_type, target_type, target_id, confidence, provenance, now),
                )
            return KnowledgeLink(
                source_type=source_type,
                source_id=source_id,
                relation_type=relation_type,
                target_type=target_type,
                target_id=target_id,
                confidence=confidence,
                provenance=provenance,
                created_at=now,
            )
        except Exception as exc:
            logger.error(f"[WikiAdapter] Ошибка записи связи: {exc}")
            return KnowledgeLink(
                source_type=source_type,
                source_id=source_id,
                relation_type=relation_type,
                target_type=target_type,
                target_id=target_id,
                confidence=confidence,
                provenance=provenance,
            )
        finally:
            if self.db_path != ":memory:":
                conn.close()

    def get_links_for_source(self, source_type: str, source_id: str) -> List[KnowledgeLink]:
        """Возвращает все исходящие связи для указанной сущности.

        Args:
            source_type: Тип источника.
            source_id: Идентификатор источника.

        Returns:
            List[KnowledgeLink]: Список связей.
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """
                SELECT source_type, source_id, relation_type, target_type, target_id, confidence, provenance, created_at
                FROM knowledge_links
                WHERE source_type = ? AND source_id = ?
                """,
                (source_type, source_id),
            )
            rows = cursor.fetchall()
            return [
                KnowledgeLink(
                    source_type=r["source_type"],
                    source_id=r["source_id"],
                    relation_type=r["relation_type"],
                    target_type=r["target_type"],
                    target_id=r["target_id"],
                    confidence=float(r["confidence"]),
                    provenance=r["provenance"],
                    created_at=r["created_at"],
                )
                for r in rows
            ]
        finally:
            if self.db_path != ":memory:":
                conn.close()

    def get_links_for_target(self, target_type: str, target_id: str) -> List[KnowledgeLink]:
        """Возвращает все входящие связи для указанной целевой сущности.

        Args:
            target_type: Тип целевой сущности.
            target_id: Идентификатор цели.

        Returns:
            List[KnowledgeLink]: Список связей.
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """
                SELECT source_type, source_id, relation_type, target_type, target_id, confidence, provenance, created_at
                FROM knowledge_links
                WHERE target_type = ? AND target_id = ?
                """,
                (target_type, target_id),
            )
            rows = cursor.fetchall()
            return [
                KnowledgeLink(
                    source_type=r["source_type"],
                    source_id=r["source_id"],
                    relation_type=r["relation_type"],
                    target_type=r["target_type"],
                    target_id=r["target_id"],
                    confidence=float(r["confidence"]),
                    provenance=r["provenance"],
                    created_at=r["created_at"],
                )
                for r in rows
            ]
        finally:
            if self.db_path != ":memory:":
                conn.close()

    def get_all_links(self, limit: int = 100) -> List[KnowledgeLink]:
        """Возвращает срез последних связей в графе знаний.

        Args:
            limit: Максимальное количество записей.

        Returns:
            List[KnowledgeLink]: Список связей.
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """
                SELECT source_type, source_id, relation_type, target_type, target_id, confidence, provenance, created_at
                FROM knowledge_links
                ORDER BY id DESC LIMIT ?
                """,
                (limit,),
            )
            return [
                KnowledgeLink(
                    source_type=r["source_type"],
                    source_id=r["source_id"],
                    relation_type=r["relation_type"],
                    target_type=r["target_type"],
                    target_id=r["target_id"],
                    confidence=float(r["confidence"]),
                    provenance=r["provenance"],
                    created_at=r["created_at"],
                )
                for r in cursor.fetchall()
            ]
        finally:
            if self.db_path != ":memory:":
                conn.close()

    def search_wiki_knowledge(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Ищет связанные знания в WikiLLM (сущности, статьи, факты).

        Args:
            query: Поисковый запрос.
            limit: Максимальное количество результатов.

        Returns:
            List[Dict[str, Any]]: Список найденных сущностей или статей.
        """
        conn = self._get_connection()
        results: List[Dict[str, Any]] = []
        try:
            # Проверяем наличие таблицы entities из WikiLLM
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='entities'"
            )
            if cursor.fetchone():
                cur = conn.execute(
                    """
                    SELECT canonical_key AS entity_id, name, entity_type, summary
                    FROM entities
                    WHERE name LIKE ? OR summary LIKE ?
                    LIMIT ?
                    """,
                    (f"%{query}%", f"%{query}%", limit),
                )
                for r in cur.fetchall():
                    results.append({
                        "entity_id": r["entity_id"],
                        "name": r["name"],
                        "type": r["entity_type"],
                        "summary": r["summary"],
                    })
        except Exception as exc:
            logger.debug(f"[WikiAdapter] Поиск в WikiLLM завершился без совпадений: {exc}")
        finally:
            if self.db_path != ":memory:":
                conn.close()

        return results

    def auto_link_commit(self, commit: GitCommitInfo, files: List[FileChange]) -> List[KnowledgeLink]:
        """Автоматически выявляет связи на основе сообщения коммита и затронутых файлов.

        Args:
            commit: Метаданные коммита.
            files: Список изменённых файлов.

        Returns:
            List[KnowledgeLink]: Список созданных связей.
        """
        created_links: List[KnowledgeLink] = []
        msg = commit.message.lower()

        # 1. Привязка файлов к коммиту (modifies)
        for fc in files:
            link = self.add_link(
                source_type="commit",
                source_id=commit.commit_hash,
                relation_type="modifies",
                target_type="file",
                target_id=fc.file_path,
                confidence=1.0,
                provenance="git_tree",
            )
            created_links.append(link)

        # 2. Выявление исправлений (fixes / closes)
        fix_match = re.search(r"(?:fix|fixes|fixed|close|closes|исправл\w*|почин\w*)\s*[:#\s]?\s*([a-zA-Z0-9_\-]+)", msg)
        if fix_match:
            issue_target = fix_match.group(1).strip()
            link = self.add_link(
                source_type="commit",
                source_id=commit.commit_hash,
                relation_type="fixes",
                target_type="error",
                target_id=issue_target,
                confidence=0.85,
                provenance="commit_msg",
            )
            created_links.append(link)

        # 3. Выявление документации (documents)
        if any(w in msg for w in ["doc", "docs", "документ", "readme", "guide"]):
            link = self.add_link(
                source_type="commit",
                source_id=commit.commit_hash,
                relation_type="documents",
                target_type="page",
                target_id="project_documentation",
                confidence=0.9,
                provenance="commit_msg",
            )
            created_links.append(link)

        return created_links
