# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Core - WikiLLM Version Linker
# =============================================================================
# Description:
#   Модуль связывания артефактов версионирования (коммиты, блобы, пути файлов)
#   со статьями, решениями (ADR) и сущностями базы знаний WikiLLM.
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.core.wikillm_version_linker import WikiLLMVersionLinker
#
#     linker = WikiLLMVersionLinker()
#     links = linker.auto_link_commit("c1a2b3", ["apps/windows/hardware/sensors.py"], "Fix sensor crash")
#     context = linker.get_context_for_entity("hardware")
#
# File: wikillm_version_linker.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 17:22:00
# =============================================================================

from __future__ import annotations
"""Связывание артефактов версий Git с базой знаний WikiLLM и графом связей."""

import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from logger import logger
from apps.ai_assistant.api.schemas import EvidenceLinkSchema
from apps.ai_assistant.core.temporal_code_graph import TemporalCodeGraph


class WikiLLMVersionLinker:
    """Обеспечивает интеграцию истории изменений Git с базой знаний WikiLLM."""

    def __init__(
        self,
        db_path: Path | str = ":memory:",
        temporal_graph: Optional[TemporalCodeGraph] = None,
    ) -> None:
        """Инициализирует компонент связывания версий.

        Args:
            db_path: Путь к файлу базы данных SQLite базы знаний WikiLLM.
            temporal_graph: Опциональный экземпляр темпорального графа.
        """
        self.db_path = Path(db_path) if str(db_path) != ":memory:" else ":memory:"
        self.graph = temporal_graph or TemporalCodeGraph(db_path=self.db_path)

    def _get_connection(self) -> sqlite3.Connection:
        """Возвращает соединение с базой знаний WikiLLM."""
        conn = sqlite3.connect(str(self.db_path), timeout=10.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def find_matching_wiki_entities(self, text: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Ищет релевантные сущности WikiLLM по фрагменту текста или ключевым словам.

        Args:
            text: Исходный текст (сообщение коммита или имя файла).
            limit: Максимальное число найденных сущностей.

        Returns:
            List[Dict[str, Any]]: Список найденных сущностей WikiLLM.
        """
        if not text:
            return []
        if isinstance(self.db_path, Path) and not self.db_path.exists():
            return []

        results: List[Dict[str, Any]] = []
        conn = self._get_connection()
        try:
            # Извлекаем слова длиной от 4 символов
            words = [w.lower() for w in re.findall(r"[a-zA-Zа-яА-Я0-9_]+", text) if len(w) >= 4]
            if not words:
                return []

            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='entities'")
            if not cursor.fetchone():
                return []

            placeholders = " OR ".join(["canonical_key LIKE ? OR name LIKE ?"] * min(len(words), 5))
            params: List[str] = []
            for w in words[:5]:
                pattern = f"%{w}%"
                params.extend([pattern, pattern])

            query = f"""
                SELECT canonical_key, name, entity_type, summary
                FROM entities
                WHERE {placeholders}
                LIMIT ?
            """
            params.append(str(limit))
            cur = conn.execute(query, params)
            for row in cur.fetchall():
                results.append({
                    "canonical_key": row["canonical_key"],
                    "name": row["name"],
                    "entity_type": row["entity_type"],
                    "summary": row["summary"] or "",
                })
        except Exception as exc:
            logger.debug(f"[WikiLLMVersionLinker] Ошибка поиска сущностей в WikiLLM: {exc}")
        finally:
            conn.close()

        return results

    def auto_link_commit(
        self,
        commit_hash: str,
        files: List[str],
        message: str,
        author: str = "",
    ) -> List[EvidenceLinkSchema]:
        """Автоматически создает темпоральные связи между коммитом, файлами и WikiLLM.

        Args:
            commit_hash: Хэш коммита Git.
            files: Список путей затронутых файлов.
            message: Сообщение коммита.
            author: Автор коммита.

        Returns:
            List[EvidenceLinkSchema]: Созданные связи.
        """
        created: List[EvidenceLinkSchema] = []
        msg_lower = message.lower()

        # 1. Привязка файлов (modifies)
        for fpath in files:
            link = self.graph.add_link(
                source_id=commit_hash,
                target_id=fpath,
                relation_type="modifies",
                valid_from=commit_hash,
                confidence=1.0,
                provenance="git_commit",
            )
            created.append(link)

        # 2. Выявление связи с архитектурными решениями WikiLLM
        wiki_entities = self.find_matching_wiki_entities(f"{message} {' '.join(files)}", limit=3)
        for ent in wiki_entities:
            rel = "fixes" if any(k in msg_lower for k in ["fix", "bug", "исправ", "почин"]) else "documents"
            link = self.graph.add_link(
                source_id=commit_hash,
                target_id=ent["canonical_key"],
                relation_type=rel,
                valid_from=commit_hash,
                confidence=0.8,
                provenance="wiki_linker_heuristic",
            )
            created.append(link)

        # 3. Выявление документации
        if any(w in msg_lower for w in ["doc", "docs", "документ", "readme", "instruction"]):
            link = self.graph.add_link(
                source_id=commit_hash,
                target_id="project_documentation",
                relation_type="documents",
                valid_from=commit_hash,
                confidence=0.9,
                provenance="commit_message",
            )
            created.append(link)

        return created

    def get_context_for_entity(self, entity_key: str) -> Dict[str, Any]:
        """Формирует расширенный контекст сущности из WikiLLM и графа связей.

        Args:
            entity_key: Ключ сущности (canonical_key).

        Returns:
            Dict[str, Any]: Словарь с описанием сущности и привязанными коммитами.
        """
        context: Dict[str, Any] = {
            "entity": None,
            "active_links": [],
            "history_count": 0,
        }

        if isinstance(self.db_path, Path) and not self.db_path.exists():
            return context

        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='entities'")
            if cursor.fetchone():
                cur = conn.execute(
                    "SELECT canonical_key, name, entity_type, summary FROM entities WHERE canonical_key = ?",
                    (entity_key,),
                )
                row = cur.fetchone()
                if row:
                    context["entity"] = {
                        "canonical_key": row["canonical_key"],
                        "name": row["name"],
                        "entity_type": row["entity_type"],
                        "summary": row["summary"] or "",
                    }
        except Exception as exc:
            logger.debug(f"[WikiLLMVersionLinker] Ошибка выборки сущности {entity_key}: {exc}")
        finally:
            conn.close()

        # Подтягиваем связи из графа
        all_links = self.graph.get_active_links()
        active = [lnk for lnk in all_links if lnk.target_id == entity_key or lnk.source_id == entity_key]
        context["active_links"] = active
        context["history_count"] = len(active)

        return context
