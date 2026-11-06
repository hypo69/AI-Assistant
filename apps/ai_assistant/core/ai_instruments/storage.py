# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Assistant AI Instruments - Hybrid Storage Manager
# =============================================================================
# Description:
#   Менеджер гибридного хранения базы инструментов для цепочек размышлений.
#   Поддерживает режимы:
#     1. Локальный Markdown каталог (data/apps/ai_assistent/toolchain_tools.md)
#     2. Удаленная MariaDB на Hostinger (Direct TCP через PyMySQL)
#     3. Удаленный PHP REST API шлюз на Hostinger (wikillm_hostinger.php)
#     4. Локальная SQLite база (data/ai_instruments/ai_instruments.db)
#   Обеспечивает автоматическую синхронизацию между Markdown и SQLite,
#   а также отказоустойчивость при отсутствии удаленной сети.
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.core.ai_instruments.storage import AIInstrumentsStorage
#
#     storage = AIInstrumentsStorage(md_path="data/apps/ai_assistent/toolchain_tools.md")
#     tool = storage.get_instrument("inst_calc_file_hash")
#
# File: storage.py
# Project: ai-assistant
# Package: apps.ai_assistant.core.ai_instruments
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-03 16:30:00
# =============================================================================

from __future__ import annotations

"""Модуль гибридного хранения базы инструментов (Markdown / SQLite / Hostinger MariaDB)."""

import json
import sqlite3
import ssl
import threading
import time
import urllib.parse
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from header import __root__
from logger import logger
from .default_catalog import DEFAULT_REASONING_INSTRUMENTS
from .markdown_adapter import load_markdown_tools, save_markdown_tools
from .models import AIInstrument, get_current_iso_time

try:
    import pymysql
    import pymysql.cursors

    HAS_PYMYSQL = True
except ImportError:
    HAS_PYMYSQL = False


def resolve_file_path(path_val: str | Path) -> Path:
    """Разрешает абсолютный или относительный путь к файлу проекта."""
    s = str(path_val).replace("\\", "/")
    if s.startswith("/"):
        s = s.lstrip("/")
    p = Path(s)
    if not p.is_absolute():
        return (__root__ / p).resolve()
    return p.resolve()


class AIInstrumentsStorage:
    """Универсальное хранилище инструментов цепочек размышлений."""

    def __init__(
        self,
        db_path: str | Path = "data/ai_instruments/ai_instruments.db",
        engine: str = "sqlite",
        hostinger_config: Optional[Dict[str, Any]] = None,
        md_path: str | Path = "data/apps/ai_assistent/toolchain_tools.md",
    ) -> None:
        """Инициализирует менеджер хранилища инструментов.

        Args:
            db_path: Путь к файлу SQLite базы или ':memory:'.
            engine: Тип предпочтительного движка ('markdown', 'sqlite', 'mariadb', 'hostinger').
            hostinger_config: Словарь настроек соединения с сервером Hostinger.
            md_path: Путь к основному локальному Markdown файлу базы инструментов.
        """
        self._lock = threading.RLock()
        self.engine = engine.lower()
        self.hostinger_config = dict(hostinger_config or {})
        self.db_path = Path(db_path) if str(db_path) != ":memory:" else ":memory:"
        self.md_path = resolve_file_path(md_path)
        self._mem_conn: Optional[sqlite3.Connection] = None
        self._mariadb_conn: Optional[Any] = None

        if self.db_path == ":memory:":
            self._mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._mem_conn.row_factory = sqlite3.Row
        elif isinstance(self.db_path, Path):
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_sqlite_db()
        self._init_markdown_db()

        if self.engine in ("mariadb", "hostinger"):
            self._init_remote_db()

    @property
    def is_remote(self) -> bool:
        """Возвращает True, если активен удаленный движок."""
        return self.engine in ("mariadb", "hostinger")

    @property
    def conn_type(self) -> str:
        """Возвращает тип удаленного соединения ('direct' или 'php_api')."""
        return str(self.hostinger_config.get("connection_type", "direct")).lower()

    @contextmanager
    def _connect_sqlite(self) -> Generator[sqlite3.Connection, None, None]:
        """Контекстный менеджер подключения к SQLite."""
        if self._mem_conn is not None:
            try:
                yield self._mem_conn
                self._mem_conn.commit()
            except Exception:
                self._mem_conn.rollback()
                raise
        else:
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def _init_sqlite_db(self) -> None:
        """Создает таблицы и индексы в SQLite базе данных."""
        with self._connect_sqlite() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_instruments (
                    tool_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    tool_type TEXT NOT NULL DEFAULT 'python',
                    command TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    target_entity TEXT DEFAULT 'system',
                    parameters_schema TEXT DEFAULT '{}',
                    risk_level TEXT DEFAULT 'safe',
                    author_agent TEXT DEFAULT 'reasoning_chain',
                    tags TEXT DEFAULT '["#agent_tool", "#reasoning"]',
                    execution_count INTEGER DEFAULT 0,
                    last_executed_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_inst_target ON ai_instruments(target_entity)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_inst_type ON ai_instruments(tool_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_inst_name ON ai_instruments(name)")

    def _init_markdown_db(self) -> None:
        """Инициализирует локальный файл toolchain_tools.md и синхронизирует с SQLite."""
        with self._lock:
            # 1. Если Markdown файл уже существует — считываем инструменты в SQLite
            if self.md_path.is_file():
                md_tools = load_markdown_tools(self.md_path)
                if md_tools:
                    for t in md_tools:
                        self._save_to_sqlite(t)
                    return

            # 2. Если Markdown файла нет — проверяем SQLite
            existing = self.list_instruments(limit=200)
            if not existing:
                # Наполняем стандартным каталогом
                now = get_current_iso_time()
                for raw in DEFAULT_REASONING_INSTRUMENTS:
                    inst = AIInstrument(
                        tool_id=raw["tool_id"],
                        name=raw["name"],
                        tool_type=raw.get("tool_type", "python"),
                        command=raw["command"],
                        description=raw.get("description", ""),
                        target_entity=raw.get("target_entity", "system"),
                        parameters_schema=raw.get("parameters_schema", {}),
                        risk_level=raw.get("risk_level", "safe"),
                        author_agent=raw.get("author_agent", "cot_planner"),
                        tags=raw.get("tags", ["#agent_tool"]),
                        created_at=now,
                        updated_at=now,
                    )
                    self._save_to_sqlite(inst)
                    existing.append(inst)

            # Сохраняем в toolchain_tools.md
            try:
                save_markdown_tools(existing, self.md_path)
            except Exception as exc:
                logger.warning(f"[AIInstrumentsStorage] Не удалось создать {self.md_path}: {exc}")

    def _sync_to_markdown(self) -> None:
        """Синхронизирует актуальное состояние SQLite базы в файл toolchain_tools.md."""
        try:
            all_items = self.list_instruments(limit=2000)
            save_markdown_tools(all_items, self.md_path)
        except Exception as exc:
            logger.warning(f"[AIInstrumentsStorage] Сбой синхронизации в Markdown: {exc}")

    def _save_to_sqlite(self, inst: AIInstrument) -> None:
        """Внутреннее сохранение инструмента в SQLite."""
        tags_str = json.dumps(inst.tags, ensure_ascii=False)
        params_str = json.dumps(inst.parameters_schema, ensure_ascii=False)
        with self._connect_sqlite() as conn:
            conn.execute(
                """
                INSERT INTO ai_instruments
                    (tool_id, name, tool_type, command, description, target_entity,
                     parameters_schema, risk_level, author_agent, tags,
                     execution_count, last_executed_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tool_id) DO UPDATE SET
                    name = excluded.name,
                    tool_type = excluded.tool_type,
                    command = excluded.command,
                    description = excluded.description,
                    target_entity = excluded.target_entity,
                    parameters_schema = excluded.parameters_schema,
                    risk_level = excluded.risk_level,
                    author_agent = excluded.author_agent,
                    tags = excluded.tags,
                    execution_count = excluded.execution_count,
                    last_executed_at = excluded.last_executed_at,
                    updated_at = excluded.updated_at
                """,
                (
                    inst.tool_id,
                    inst.name,
                    inst.tool_type,
                    inst.command,
                    inst.description,
                    inst.target_entity,
                    params_str,
                    inst.risk_level,
                    inst.author_agent,
                    tags_str,
                    inst.execution_count,
                    inst.last_executed_at,
                    inst.created_at,
                    inst.updated_at,
                ),
            )

    def _get_mariadb_conn(self) -> Any:
        """Возвращает прямое TCP соединение с Hostinger MariaDB."""
        if not HAS_PYMYSQL:
            raise RuntimeError("Пакет 'pymysql' не установлен в окружении.")

        with self._lock:
            if self._mariadb_conn is not None:
                try:
                    self._mariadb_conn.ping()
                    return self._mariadb_conn
                except Exception:
                    self._mariadb_conn = None

            cfg = self.hostinger_config
            host = cfg.get("host", "srv1502.hstgr.io")
            port = int(cfg.get("port", 3306))
            user = cfg.get("user", "u177424397_davidka")
            password = cfg.get("password", "")
            database = cfg.get("database", "u177424397_comp_knowledge")
            timeout = int(cfg.get("connect_timeout", 10))
            ip_fallback = cfg.get("ip_fallback", "77.37.35.16")

            try:
                self._mariadb_conn = pymysql.connect(
                    host=host,
                    port=port,
                    user=user,
                    password=password,
                    database=database,
                    charset="utf8mb4",
                    connect_timeout=timeout,
                    cursorclass=pymysql.cursors.DictCursor,
                    autocommit=True,
                )
                return self._mariadb_conn
            except Exception as conn_err:
                if ip_fallback and ip_fallback != host:
                    try:
                        self._mariadb_conn = pymysql.connect(
                            host=ip_fallback,
                            port=port,
                            user=user,
                            password=password,
                            database=database,
                            charset="utf8mb4",
                            connect_timeout=timeout,
                            cursorclass=pymysql.cursors.DictCursor,
                            autocommit=True,
                        )
                        return self._mariadb_conn
                    except Exception as fb_err:
                        raise RuntimeError(f"Сбой MariaDB ({host} / {ip_fallback}): {fb_err}") from fb_err
                raise RuntimeError(f"Сбой MariaDB ({host}:{port}): {conn_err}") from conn_err

    def _call_php_api(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Отправляет HTTP POST запрос к удаленному PHP REST API шлюзу Hostinger."""
        url = self.hostinger_config.get("php_api_url", "https://srv1502.hstgr.io/wikillm_hostinger.php")
        api_key = self.hostinger_config.get("php_api_key", "")
        data_dict = {"action": action, "token": api_key, **payload}
        raw_body = json.dumps(data_dict, ensure_ascii=False).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=raw_body,
            headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": "AI-Assistant/1.0"},
            method="POST",
        )
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        with urllib.request.urlopen(req, context=ctx, timeout=12) as resp:
            body = resp.read().decode("utf-8")
            res = json.loads(body)
            if not res.get("ok"):
                raise RuntimeError(f"Hostinger PHP API вернул ошибку: {res.get('error')}")
            return res

    def _execute_remote(self, action: str, sql: str, params: Optional[List[Any]] = None) -> Dict[str, Any]:
        """Исполняет SQL запрос на сервере Hostinger."""
        if self.conn_type == "php_api" and self.hostinger_config.get("php_api_url"):
            try:
                return self._call_php_api(action, {"sql": sql, "params": params or []})
            except Exception as api_err:
                if HAS_PYMYSQL and self.hostinger_config.get("host") and self.hostinger_config.get("user"):
                    logger.info(f"[AIInstrumentsStorage] PHP API недоступен ({api_err}), пробуем прямой TCP MariaDB.")
                    self.hostinger_config["connection_type"] = "direct"
                else:
                    raise

        conn = self._get_mariadb_conn()
        mysql_sql = sql.replace("?", "%s")
        with self._lock:
            with conn.cursor() as cur:
                affected = cur.execute(mysql_sql, tuple(params or []))
                if action == "query":
                    rows = cur.fetchall()
                    return {"ok": True, "rows": list(rows) if rows else []}
                return {"ok": True, "affected_rows": int(affected or 0)}

    def _init_remote_db(self) -> None:
        """Создает таблицу ai_instruments на удаленном сервере Hostinger при необходимости."""
        sql_init = """
        CREATE TABLE IF NOT EXISTS ai_instruments (
            tool_id VARCHAR(255) PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            tool_type VARCHAR(50) NOT NULL DEFAULT 'python',
            command LONGTEXT NOT NULL,
            description MEDIUMTEXT,
            target_entity VARCHAR(255) DEFAULT 'system',
            parameters_schema_json LONGTEXT,
            risk_level VARCHAR(50) NOT NULL DEFAULT 'safe',
            author_agent VARCHAR(100) NOT NULL DEFAULT 'reasoning_chain',
            tags_json LONGTEXT,
            execution_count INT NOT NULL DEFAULT 0,
            last_executed_at VARCHAR(100),
            created_at VARCHAR(100) NOT NULL,
            updated_at VARCHAR(100) NOT NULL,
            INDEX idx_ai_inst_target (target_entity),
            INDEX idx_ai_inst_type (tool_type)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
        try:
            self._execute_remote("execute", sql_init)
            logger.info("[AIInstrumentsStorage] Таблица ai_instruments на сервере Hostinger верифицирована.")
        except Exception as exc:
            logger.warning(f"[AIInstrumentsStorage] Сбой Hostinger MariaDB: {exc}. Переключение на SQLite.")
            self.engine = "sqlite"

    def save_instrument(self, inst: AIInstrument) -> AIInstrument:
        """Сохраняет инструмент в базе данных и актуализирует Markdown файл."""
        tags_str = json.dumps(inst.tags, ensure_ascii=False)
        params_str = json.dumps(inst.parameters_schema, ensure_ascii=False)

        if self.is_remote:
            try:
                sql_mysql = """
                INSERT INTO ai_instruments
                    (tool_id, name, tool_type, command, description, target_entity,
                     parameters_schema_json, risk_level, author_agent, tags_json,
                     execution_count, last_executed_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON DUPLICATE KEY UPDATE
                    name = VALUES(name),
                    tool_type = VALUES(tool_type),
                    command = VALUES(command),
                    description = VALUES(description),
                    target_entity = VALUES(target_entity),
                    parameters_schema_json = VALUES(parameters_schema_json),
                    risk_level = VALUES(risk_level),
                    author_agent = VALUES(author_agent),
                    tags_json = VALUES(tags_json),
                    execution_count = VALUES(execution_count),
                    last_executed_at = VALUES(last_executed_at),
                    updated_at = VALUES(updated_at);
                """
                params = [
                    inst.tool_id,
                    inst.name,
                    inst.tool_type,
                    inst.command,
                    inst.description,
                    inst.target_entity,
                    params_str,
                    inst.risk_level,
                    inst.author_agent,
                    tags_str,
                    inst.execution_count,
                    inst.last_executed_at,
                    inst.created_at,
                    inst.updated_at,
                ]
                self._execute_remote("execute", sql_mysql, params)
            except Exception as exc:
                logger.error(f"[AIInstrumentsStorage] Ошибка записи в Hostinger ({exc}).")

        self._save_to_sqlite(inst)
        self._sync_to_markdown()
        return inst

    def get_instrument(self, tool_id: str) -> Optional[AIInstrument]:
        """Возвращает инструмент по идентификатору."""
        if self.is_remote:
            try:
                res = self._execute_remote("query", "SELECT * FROM ai_instruments WHERE tool_id = ? LIMIT 1", [tool_id])
                rows = res.get("rows", [])
                if rows:
                    return self._map_row(rows[0])
            except Exception:
                pass

        with self._connect_sqlite() as conn:
            cur = conn.execute("SELECT * FROM ai_instruments WHERE tool_id = ? LIMIT 1", (tool_id,))
            row = cur.fetchone()
            if row:
                return self._map_row(dict(row))
        return None

    def list_instruments(
        self,
        limit: int = 50,
        offset: int = 0,
        tool_type: Optional[str] = None,
        target_entity: Optional[str] = None,
    ) -> List[AIInstrument]:
        """Возвращает список инструментов с пагинацией и фильтрацией."""
        where_clauses: List[str] = []
        params: List[Any] = []

        if tool_type:
            where_clauses.append("tool_type = ?")
            params.append(tool_type.lower())
        if target_entity:
            where_clauses.append("target_entity = ?")
            params.append(target_entity)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        if self.is_remote:
            try:
                sql = f"SELECT * FROM ai_instruments {where_sql} ORDER BY execution_count DESC, updated_at DESC LIMIT ? OFFSET ?"
                res = self._execute_remote("query", sql, params + [limit, offset])
                return [self._map_row(r) for r in res.get("rows", [])]
            except Exception:
                pass

        with self._connect_sqlite() as conn:
            sql = f"SELECT * FROM ai_instruments {where_sql} ORDER BY execution_count DESC, updated_at DESC LIMIT ? OFFSET ?"
            cur = conn.execute(sql, tuple(params + [limit, offset]))
            return [self._map_row(dict(r)) for r in cur.fetchall()]

    def search_instruments(self, query: str, limit: int = 20) -> List[AIInstrument]:
        """Ищет инструменты по подстроке в названии, описании или сущности."""
        q = f"%{query.strip()}%"
        if self.is_remote:
            try:
                sql = """
                SELECT * FROM ai_instruments
                WHERE name LIKE ? OR description LIKE ? OR target_entity LIKE ?
                ORDER BY execution_count DESC LIMIT ?
                """
                res = self._execute_remote("query", sql, [q, q, q, limit])
                return [self._map_row(r) for r in res.get("rows", [])]
            except Exception:
                pass

        with self._connect_sqlite() as conn:
            sql = """
            SELECT * FROM ai_instruments
            WHERE name LIKE ? OR description LIKE ? OR target_entity LIKE ?
            ORDER BY execution_count DESC LIMIT ?
            """
            cur = conn.execute(sql, (q, q, q, limit))
            return [self._map_row(dict(r)) for r in cur.fetchall()]

    def delete_instrument(self, tool_id: str) -> bool:
        """Удаляет инструмент из базы данных и файла Markdown."""
        if self.is_remote:
            try:
                self._execute_remote("execute", "DELETE FROM ai_instruments WHERE tool_id = ?", [tool_id])
            except Exception:
                pass

        with self._connect_sqlite() as conn:
            res = conn.execute("DELETE FROM ai_instruments WHERE tool_id = ?", (tool_id,))
            deleted = res.rowcount > 0

        if deleted:
            self._sync_to_markdown()
        return deleted

    def record_execution(self, tool_id: str) -> bool:
        """Инкрементирует счётчик запусков инструмента и обновляет Markdown файл."""
        now = get_current_iso_time()
        if self.is_remote:
            try:
                self._execute_remote(
                    "execute",
                    "UPDATE ai_instruments SET execution_count = execution_count + 1, last_executed_at = ? WHERE tool_id = ?",
                    [now, tool_id],
                )
            except Exception:
                pass

        with self._connect_sqlite() as conn:
            conn.execute(
                "UPDATE ai_instruments SET execution_count = execution_count + 1, last_executed_at = ? WHERE tool_id = ?",
                (now, tool_id),
            )

        self._sync_to_markdown()
        return True

    def count_instruments(self) -> int:
        """Возвращает общее количество инструментов."""
        with self._connect_sqlite() as conn:
            cur = conn.execute("SELECT COUNT(*) FROM ai_instruments")
            return int(cur.fetchone()[0])

    def test_connection(self) -> Dict[str, Any]:
        """Тестирует доступность удаленной базы Hostinger, локального SQLite и Markdown файла."""
        results: Dict[str, Any] = {
            "engine": self.engine,
            "markdown_file": {
                "path": str(self.md_path),
                "exists": self.md_path.is_file(),
                "instruments_count": len(load_markdown_tools(self.md_path)) if self.md_path.is_file() else 0,
            },
            "sqlite": {"status": "ok", "path": str(self.db_path)},
            "hostinger": {"status": "disabled"},
        }
        if self.is_remote:
            t0 = time.time()
            try:
                self._execute_remote("query", "SELECT 1 as ping")
                lat = round((time.time() - t0) * 1000, 2)
                results["hostinger"] = {
                    "status": "ok",
                    "latency_ms": lat,
                    "connection_type": self.conn_type,
                    "host": self.hostinger_config.get("host", "srv1502.hstgr.io"),
                    "database": self.hostinger_config.get("database", "u177424397_comp_knowledge"),
                }
            except Exception as exc:
                results["hostinger"] = {
                    "status": "error",
                    "error": str(exc),
                    "connection_type": self.conn_type,
                }
        return results

    def _map_row(self, row: Dict[str, Any]) -> AIInstrument:
        """Преобразует строку базы данных в сущность AIInstrument."""
        tags_raw = row.get("tags") or row.get("tags_json") or "[]"
        params_raw = row.get("parameters_schema") or row.get("parameters_schema_json") or "{}"

        tags = json.loads(tags_raw) if isinstance(tags_raw, str) else list(tags_raw)
        params = json.loads(params_raw) if isinstance(params_raw, str) else dict(params_raw)

        return AIInstrument(
            tool_id=str(row["tool_id"]),
            name=str(row["name"]),
            tool_type=str(row.get("tool_type", "python")),
            command=str(row["command"]),
            description=str(row.get("description", "")),
            target_entity=str(row.get("target_entity", "system")),
            parameters_schema=params,
            risk_level=str(row.get("risk_level", "safe")),
            author_agent=str(row.get("author_agent", "reasoning_chain")),
            tags=tags,
            execution_count=int(row.get("execution_count", 0)),
            last_executed_at=row.get("last_executed_at"),
            created_at=str(row.get("created_at", get_current_iso_time())),
            updated_at=str(row.get("updated_at", get_current_iso_time())),
        )
