# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Core - Temporal Code Graph
# =============================================================================
# Description:
#   Темпоральный граф знаний кода (EvidenceLink): управление временными окнами
#   валидности (valid_from / valid_to), мягкая инвалидация (SUPERSEDED) и хранение
#   связей между Git-ревизиями и фактами WikiLLM в SQLite.
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.core.temporal_code_graph import TemporalCodeGraph
#
#     graph = TemporalCodeGraph()
#     link = graph.add_link(source_id="c1a2b3", target_id="wiki_telemetry", relation_type="fixes", valid_from="c1a2b3")
#     graph.supersede_link(source_id="c1a2b3", target_id="wiki_telemetry", invalidating_commit="d4e5f6")
#
# File: temporal_code_graph.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 16:55:00
# =============================================================================

from __future__ import annotations
"""Темпоральный граф связей кода и архитектурных решений WikiLLM."""

import sqlite3
from pathlib import Path
from typing import List, Optional

from logger import logger
from apps.ai_assistant.api.schemas import EvidenceLinkSchema, get_utc_now_iso


class TemporalCodeGraph:
    """Управляет темпоральными связями графа знаний с поддержкой окон валидности."""

    def __init__(
        self,
        db_path: Path | str = ":memory:",
        workspaces_dir: Optional[Path | str] = None,
    ) -> None:
        """Инициализирует подключение к SQLite базе данных темпорального графа.

        Args:
            db_path: Путь к файлу БД SQLite по умолчанию или ':memory:'.
            workspaces_dir: Опциональный каталог рабочих пространств для изоляции БД.
        """
        self.db_path = Path(db_path) if str(db_path) != ":memory:" else ":memory:"
        self.workspaces_dir = Path(workspaces_dir).resolve() if workspaces_dir else None
        self._mem_conn: Optional[sqlite3.Connection] = None
        self._initialized_paths: set[str] = set()
        if self.db_path == ":memory:":
            self._mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._mem_conn.row_factory = sqlite3.Row
            self._init_schema(existing_conn=self._mem_conn)
            self._initialized_paths.add(":memory:")
        else:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._init_schema()

    def _get_target_db_path(self, workspace_id: Optional[str] = None) -> Path | str:
        """Определяет путь к SQLite БД: локально в <ws>/.workspace/temporal_graph.db или глобально."""
        if self.db_path == ":memory:":
            return ":memory:"
        if workspace_id and self.workspaces_dir:
            ws_meta = self.workspaces_dir / workspace_id / ".workspace"
            ws_meta.mkdir(parents=True, exist_ok=True)
            return ws_meta / "temporal_graph.db"
        return self.db_path

    def _get_connection(self, workspace_id: Optional[str] = None) -> sqlite3.Connection:
        """Возвращает активное соединение SQLite (с поддержкой изоляции по workspace_id)."""
        target_path = self._get_target_db_path(workspace_id)
        if target_path == ":memory:" and self._mem_conn:
            return self._mem_conn
        path_str = str(target_path)
        conn = sqlite3.connect(path_str, timeout=10.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        if path_str not in self._initialized_paths:
            self._init_schema(existing_conn=conn)
            self._initialized_paths.add(path_str)
        return conn

    def _close_conn(self, conn: Optional[sqlite3.Connection]) -> None:
        """Закрывает соединение, если база не в памяти."""
        if conn and conn != self._mem_conn:
            try:
                conn.close()
            except Exception:
                pass

    def _init_schema(self, existing_conn: Optional[sqlite3.Connection] = None) -> None:
        """Создает таблицу temporal_evidence_links и индексы."""
        if existing_conn is None:
            conn = self._get_connection()
            self._close_conn(conn)
            return

        try:
            with existing_conn:
                existing_conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS temporal_evidence_links (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        source_id TEXT NOT NULL,
                        target_id TEXT NOT NULL,
                        relation_type TEXT NOT NULL,
                        valid_from TEXT NOT NULL,
                        valid_to TEXT,
                        confidence REAL DEFAULT 1.0,
                        provenance TEXT DEFAULT 'heuristic',
                        status TEXT DEFAULT 'ACTIVE',
                        created_at TEXT NOT NULL,
                        UNIQUE(source_id, target_id, relation_type, valid_from)
                    )
                    """
                )
                existing_conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_temporal_source
                    ON temporal_evidence_links (source_id, status)
                    """
                )
                existing_conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_temporal_target
                    ON temporal_evidence_links (target_id, status)
                    """
                )
        except Exception as exc:
            logger.error(f"[TemporalCodeGraph] Ошибка инициализации схемы: {exc}")

    def add_link(
        self,
        source_id: str,
        target_id: str,
        relation_type: str,
        valid_from: str,
        confidence: float = 1.0,
        provenance: str = "heuristic",
        workspace_id: Optional[str] = None,
    ) -> EvidenceLinkSchema:
        """Регистрирует новую активную темпоральную связь."""
        now = get_utc_now_iso()
        conn = self._get_connection(workspace_id=workspace_id)
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO temporal_evidence_links (
                        source_id, target_id, relation_type, valid_from, valid_to, confidence, provenance, status, created_at
                    ) VALUES (?, ?, ?, ?, NULL, ?, ?, 'ACTIVE', ?)
                    ON CONFLICT(source_id, target_id, relation_type, valid_from)
                    DO UPDATE SET confidence = excluded.confidence, provenance = excluded.provenance, status = 'ACTIVE', valid_to = NULL
                    """,
                    (source_id, target_id, relation_type, valid_from, confidence, provenance, now),
                )
            return EvidenceLinkSchema(
                source_id=source_id,
                target_id=target_id,
                relation_type=relation_type,
                valid_from=valid_from,
                valid_to=None,
                confidence=confidence,
                provenance=provenance,
                status="ACTIVE",
            )
        finally:
            self._close_conn(conn)

    def supersede_link(
        self,
        source_id: str,
        target_id: str,
        invalidating_commit: str,
        workspace_id: Optional[str] = None,
    ) -> bool:
        """Выполняет мягкую инвалидацию конкретной связи (переводит в статус SUPERSEDED)."""
        conn = self._get_connection(workspace_id=workspace_id)
        try:
            with conn:
                cursor = conn.execute(
                    """
                    UPDATE temporal_evidence_links
                    SET status = 'SUPERSEDED', valid_to = ?
                    WHERE source_id = ? AND target_id = ? AND status = 'ACTIVE'
                    """,
                    (invalidating_commit, source_id, target_id),
                )
                return cursor.rowcount > 0
        finally:
            self._close_conn(conn)

    def supersede_links_by_source(
        self,
        source_id: str,
        invalidating_commit: str,
        workspace_id: Optional[str] = None,
    ) -> int:
        """Переводит все прежние активные связи документа/источника в статус SUPERSEDED при обновлении ревизии."""
        conn = self._get_connection(workspace_id=workspace_id)
        try:
            with conn:
                cursor = conn.execute(
                    """
                    UPDATE temporal_evidence_links
                    SET status = 'SUPERSEDED', valid_to = ?
                    WHERE source_id = ? AND status = 'ACTIVE' AND valid_from != ?
                    """,
                    (invalidating_commit, source_id, invalidating_commit),
                )
                return cursor.rowcount
        finally:
            self._close_conn(conn)

    def get_active_links(
        self,
        source_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> List[EvidenceLinkSchema]:
        """Возвращает список только активных связей (не инвалидированных)."""
        conn = self._get_connection(workspace_id=workspace_id)
        try:
            if source_id:
                cursor = conn.execute(
                    """
                    SELECT source_id, target_id, relation_type, valid_from, valid_to, confidence, provenance, status
                    FROM temporal_evidence_links
                    WHERE status = 'ACTIVE' AND source_id = ?
                    """,
                    (source_id,),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT source_id, target_id, relation_type, valid_from, valid_to, confidence, provenance, status
                    FROM temporal_evidence_links
                    WHERE status = 'ACTIVE'
                    ORDER BY id DESC LIMIT 100
                    """
                )

            return [
                EvidenceLinkSchema(
                    source_id=r["source_id"],
                    target_id=r["target_id"],
                    relation_type=r["relation_type"],
                    valid_from=r["valid_from"],
                    valid_to=r["valid_to"],
                    confidence=float(r["confidence"]),
                    provenance=r["provenance"],
                    status=r["status"],
                )
                for r in cursor.fetchall()
            ]
        finally:
            self._close_conn(conn)

    def get_all_links(
        self,
        limit: int = 100,
        workspace_id: Optional[str] = None,
    ) -> List[EvidenceLinkSchema]:
        """Возвращает всю хронологию связей графа, включая SUPERSEDED."""
        conn = self._get_connection(workspace_id=workspace_id)
        try:
            cursor = conn.execute(
                """
                SELECT source_id, target_id, relation_type, valid_from, valid_to, confidence, provenance, status
                FROM temporal_evidence_links
                ORDER BY id DESC LIMIT ?
                """,
                (limit,),
            )
            return [
                EvidenceLinkSchema(
                    source_id=r["source_id"],
                    target_id=r["target_id"],
                    relation_type=r["relation_type"],
                    valid_from=r["valid_from"],
                    valid_to=r["valid_to"],
                    confidence=float(r["confidence"]),
                    provenance=r["provenance"],
                    status=r["status"],
                )
                for r in cursor.fetchall()
            ]
        finally:
            self._close_conn(conn)
