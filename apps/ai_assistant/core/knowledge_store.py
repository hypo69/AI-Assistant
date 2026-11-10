# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Core - Knowledge Store SQLite
# =============================================================================
# Description:
#   Реляционное хранилище знаний SQLite (ТЗ раздел 7).
#   Объединяет модульные репозитории таблиц из apps.ai_assistant.core.store:
#   WorkspaceRepoMixin, DocumentFactRepoMixin и TelemetryRepoMixin.
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.core.knowledge_store import KnowledgeStore
#
#     store = KnowledgeStore()
#     stats = store.get_workspace_stats("default")
#
# File: knowledge_store.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 16:40:00
# =============================================================================

from __future__ import annotations
"""Фасад SQLite-хранилища структурированных знаний, документов, версий и телеметрии."""

from pathlib import Path
import sqlite3
import threading
from typing import Callable, Optional

from logger import logger
from apps.ai_assistant.core.store import (
    DocumentFactRepoMixin,
    KNOWLEDGE_STORE_DDL,
    TelemetryRepoMixin,
    WorkspaceRepoMixin,
    compute_sha256,
    get_utc_now_iso,
)

MAX_INITIALIZED_PATHS_CACHE = 512


class KnowledgeStore(WorkspaceRepoMixin, DocumentFactRepoMixin, TelemetryRepoMixin):
    """Управляет SQLite-базой структурированных знаний и метаданных рабочих областей с поддержкой локального хранения в .workspace/."""

    def __init__(
        self,
        db_path: Path | str = ":memory:",
        workspaces_dir: Optional[Path | str] = "",
        text_resolver: Optional[Callable[[int], str]] = None,
    ) -> None:
        """Инициализирует подключение и схему SQLite базы знаний.

        Args:
            db_path: Путь к файлу SQLite по умолчанию или ':memory:'.
            workspaces_dir: Опциональный каталог рабочих пространств для изоляции БД.
            text_resolver: Функция paperless_id -> полный текст (Paperless API) для документов без копии текста в БД.
        """
        self.text_resolver = text_resolver
        self.db_path = Path(db_path) if str(db_path) != ":memory:" else ":memory:"
        self.workspaces_dir = Path(workspaces_dir).resolve() if workspaces_dir else None
        self._lock = threading.RLock()
        self._mem_conn: Optional[sqlite3.Connection] = None
        self._initialized_paths: set[str] = set()
        if self.db_path == ":memory:":
            self._mem_conn = sqlite3.connect(":memory:", timeout=15.0, check_same_thread=False)
            self._mem_conn.row_factory = sqlite3.Row
            self._mem_conn.execute("PRAGMA busy_timeout=15000;")
            self._mem_conn.execute("PRAGMA foreign_keys=ON;")
        else:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_schema()

    def _get_target_db_path(self, workspace_id: Optional[str] = "") -> Path | str:
        """Определяет путь к SQLite БД: локально в <ws>/.workspace/knowledge_store.db или глобально."""
        if self.db_path == ":memory:":
            return ":memory:"
        if workspace_id and self.workspaces_dir:
            ws_dir = (self.workspaces_dir / str(workspace_id)).resolve()
            try:
                ws_dir.relative_to(self.workspaces_dir)
            except ValueError as exc:
                raise ValueError(f"Недопустимый идентификатор рабочего пространства: {workspace_id}") from exc
            ws_meta = ws_dir / ".workspace"
            ws_meta.mkdir(parents=True, exist_ok=True)
            return ws_meta / "knowledge_store.db"
        return self.db_path

    def _get_conn(self, workspace_id: Optional[str] = "") -> sqlite3.Connection:
        """Открывает или возвращает соединение SQLite с гарантированным закрытием при сбое инициализации."""
        target_path = self._get_target_db_path(workspace_id)
        if target_path == ":memory:" and self._mem_conn:
            return self._mem_conn

        path_str = str(target_path)
        conn = sqlite3.connect(path_str, timeout=15.0, check_same_thread=False)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA busy_timeout=15000;")
            conn.execute("PRAGMA foreign_keys=ON;")

            with self._lock:
                if path_str not in self._initialized_paths:
                    if len(self._initialized_paths) >= MAX_INITIALIZED_PATHS_CACHE:
                        self._initialized_paths.clear()
                    self._init_schema(existing_conn=conn)
                    self._initialized_paths.add(path_str)
            return conn
        except Exception:
            conn.close()
            raise

    def _close_conn(self, conn: sqlite3.Connection) -> bool:
        """Закрывает соединение, если база не в памяти."""
        if conn != self._mem_conn:
            try:
                conn.close()
            except Exception as exc:
                logger.debug(f"[KnowledgeStore] Ошибка закрытия соединения SQLite: {exc}")
                return False
        return True

    def close(self) -> bool:
        """Явно закрывает in-memory соединение при выгрузке хранилища из кэша."""
        with self._lock:
            if self._mem_conn:
                try:
                    self._mem_conn.close()
                except Exception as exc:
                    logger.debug(f"[KnowledgeStore] Ошибка закрытия in-memory БД: {exc}")
                finally:
                    self._mem_conn = None
        return True

    def _init_schema(self, existing_conn: Optional[sqlite3.Connection] = None) -> None:
        """Создаёт все таблицы модели данных согласно разделу 7 ТЗ."""
        conn = existing_conn or self._get_conn()
        try:
            with conn:
                conn.executescript(KNOWLEDGE_STORE_DDL)
                for col_ddl in (
                    "ALTER TABLE documents ADD COLUMN host_name TEXT DEFAULT ''",
                    "ALTER TABLE documents ADD COLUMN qualified_path TEXT DEFAULT ''",
                    "ALTER TABLE documents ADD COLUMN paperless_id INTEGER DEFAULT NULL",
                ):
                    try:
                        conn.execute(col_ddl)
                    except sqlite3.OperationalError:
                        pass
        except Exception as exc:
            logger.error(f"[KnowledgeStore] Ошибка создания схемы SQLite: {exc}")
        finally:
            if not existing_conn:
                self._close_conn(conn)


__all__ = [
    "KnowledgeStore",
    "compute_sha256",
    "get_utc_now_iso",
]
