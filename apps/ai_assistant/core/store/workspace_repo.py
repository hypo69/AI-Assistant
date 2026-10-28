# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Core Store - Workspace Repo
# =============================================================================
# Description:
#   Состояние активного пространства/репозитория (app_settings) и статистика
#   индекса знаний. Реестр самих пространств — файловый (WorkspaceRegistry).
#
# File: core/store/workspace_repo.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.core.store
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 02:35:00
# =============================================================================

from __future__ import annotations
"""Репозиторий состояния активного пространства и статистики индекса знаний."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from logger import logger


def get_utc_now_iso() -> str:
    """Возвращает текущее время UTC в формате ISO 8601."""
    return datetime.now(timezone.utc).isoformat()


class WorkspaceRepoMixin:
    """Миксин операций с app_settings (активное пространство) и статистикой документов/фактов."""

    def get_workspace_stats(self, workspace_id: str) -> Dict[str, int]:
        """Возвращает статистику индекса знаний рабочего пространства.

        Returns:
            Dict[str, int]: Ключи documents_count и active_facts_count.
        """
        default_stats = {"documents_count": 0, "active_facts_count": 0}
        try:
            conn = self._get_conn(workspace_id=workspace_id)
            try:
                docs = conn.execute(
                    "SELECT COUNT(*) FROM documents WHERE workspace_id = ?", (workspace_id,)
                ).fetchone()[0]
                facts = conn.execute(
                    "SELECT COUNT(*) FROM facts WHERE workspace_id = ? AND status != 'stale'", (workspace_id,)
                ).fetchone()[0]
                return {"documents_count": int(docs), "active_facts_count": int(facts)}
            finally:
                self._close_conn(conn)
        except Exception as exc:
            logger.warning(f"[WorkspaceRepoMixin] Не удалось получить статистику для '{workspace_id}': {exc}")
            return default_stats

    def set_active_workspace(self, workspace_id: str) -> bool:
        """Сохраняет идентификатор активной рабочей области в app_settings."""
        now = get_utc_now_iso()
        conn = self._get_conn()
        try:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS app_settings (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO app_settings (key, value, updated_at)
                    VALUES ('active_workspace_id', ?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                    """,
                    (workspace_id, now),
                )
                return True
        finally:
            self._close_conn(conn)

    def get_active_workspace_id(self) -> Optional[str]:
        """Возвращает идентификатор активной рабочей области из app_settings."""
        try:
            conn = self._get_conn()
            try:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS app_settings (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                cur = conn.execute("SELECT value FROM app_settings WHERE key = 'active_workspace_id'")
                row = cur.fetchone()
                return str(row["value"]) if row else None
            finally:
                self._close_conn(conn)
        except Exception as exc:
            logger.warning(f"[WorkspaceRepoMixin] Ошибка чтения active_workspace_id: {exc}")
            return None

    def set_active_repo(self, repo_path: str, workspace_id: Optional[str] = None) -> bool:
        """Сохраняет глобально активный Git-репозиторий и связанную рабочую область в app_settings."""
        now = get_utc_now_iso()
        conn = self._get_conn()
        try:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS app_settings (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO app_settings (key, value, updated_at)
                    VALUES ('active_repo_path', ?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                    """,
                    (repo_path, now),
                )
                if workspace_id is not None:
                    conn.execute(
                        """
                        INSERT INTO app_settings (key, value, updated_at)
                        VALUES ('active_workspace_id', ?, ?)
                        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                        """,
                        (workspace_id, now),
                    )
                return True
        finally:
            self._close_conn(conn)

    def get_active_repo(self) -> Dict[str, Optional[str]]:
        """Возвращает сохранённый глобально активный репозиторий и рабочую область."""
        conn = self._get_conn()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            cur = conn.execute("SELECT key, value FROM app_settings WHERE key IN ('active_repo_path', 'active_workspace_id')")
            rows = dict(cur.fetchall())
            return {
                "repo_path": rows.get("active_repo_path"),
                "workspace_id": rows.get("active_workspace_id"),
            }
        finally:
            self._close_conn(conn)
