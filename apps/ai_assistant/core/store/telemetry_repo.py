# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Core Store - Telemetry Repo
# =============================================================================
# Description:
#   Управление таблицами query_history, model_usage, embedding_registry
#   и агрегация метрик качества и производительности (ТЗ п. 8, 9.2, 10.2)
#   с расчётом перцентилей p50/p95/p99 и метрик RED (SYSTEM_ENGINEERING § 6.3).
#
# File: core/store/telemetry_repo.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.core.store
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 13:52:00
# =============================================================================

from __future__ import annotations
"""Репозиторий телеметрии запросов, вызовов моделей ИИ и реестра FAISS."""

from typing import Any, Dict, Optional

from apps.ai_assistant.core.store.workspace_repo import get_utc_now_iso


class TelemetryRepoMixin:
    """Миксин логирования истории вопросов, вызовов моделей и реестра эмбеддингов."""

    def log_query(
        self,
        workspace_id: str,
        question: str,
        language: str,
        mode: str,
        answer: str,
        status: str,
        cloud_used: bool,
        latency_ms: float,
    ) -> bool:
        """Фиксирует выполненный поисковый вопрос в журнале query_history."""
        conn = self._get_conn(workspace_id=workspace_id)
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO query_history (
                        workspace_id, question, language, mode, answer, status, cloud_used, latency_ms, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        workspace_id,
                        question,
                        language,
                        mode,
                        answer,
                        status,
                        1 if cloud_used else 0,
                        round(latency_ms, 2),
                        get_utc_now_iso(),
                    ),
                )
            return True
        finally:
            self._close_conn(conn)

    def log_model_usage(
        self,
        workspace_id: str,
        provider: str,
        model_name: str,
        operation: str,
        status: str,
        latency_ms: float,
        prompt_chars: int = 0,
        response_chars: int = 0,
        error_message: str = "",
    ) -> bool:
        """Фиксирует вызов локальной или облачной модели ИИ в таблице model_usage."""
        conn = self._get_conn(workspace_id=workspace_id)
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO model_usage (
                        workspace_id, provider, model_name, operation, status,
                        latency_ms, prompt_chars, response_chars, error_message, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        workspace_id,
                        provider,
                        model_name,
                        operation,
                        status,
                        round(latency_ms, 2),
                        prompt_chars,
                        response_chars,
                        error_message[:500],
                        get_utc_now_iso(),
                    ),
                )
            return True
        finally:
            self._close_conn(conn)

    def update_embedding_registry(
        self,
        workspace_id: str,
        model_name: str,
        dimension: int,
        index_path: str,
        total_vectors: int,
    ) -> bool:
        """Обновляет сведения о векторном индексе FAISS для рабочей области."""
        conn = self._get_conn(workspace_id=workspace_id)
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO embedding_registry (workspace_id, model_name, dimension, index_path, total_vectors, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(workspace_id) DO UPDATE SET
                        model_name = excluded.model_name,
                        dimension = excluded.dimension,
                        index_path = excluded.index_path,
                        total_vectors = excluded.total_vectors,
                        updated_at = excluded.updated_at
                    """,
                    (workspace_id, model_name, dimension, index_path, total_vectors, get_utc_now_iso()),
                )
            return True
        finally:
            self._close_conn(conn)

    def get_metrics(self, workspace_id: Optional[str] = "") -> Dict[str, Any]:
        """Возвращает агрегированную статистику качества, перцентилей задержек (p50/p95/p99) и вызовов ИИ."""
        conn = self._get_conn(workspace_id=workspace_id)
        try:
            ws_filter = "WHERE workspace_id = ?" if workspace_id else ""
            params = (workspace_id,) if workspace_id else ()

            docs_cnt = int(conn.execute(f"SELECT COUNT(*) FROM documents {ws_filter}", params).fetchone()[0])
            facts_row = conn.execute(
                f"""
                SELECT
                    COALESCE(SUM(CASE WHEN status != 'stale' THEN 1 ELSE 0 END), 0),
                    COALESCE(SUM(CASE WHEN status = 'stale' THEN 1 ELSE 0 END), 0)
                FROM facts {ws_filter}
                """,
                params,
            ).fetchone()
            facts_active = int(facts_row[0]) if facts_row else 0
            facts_stale = int(facts_row[1]) if facts_row else 0

            lat_rows = conn.execute(
                f"SELECT latency_ms, status FROM query_history {ws_filter} ORDER BY latency_ms ASC",
                params,
            ).fetchall()
            queries_cnt = len(lat_rows)
            latencies = [float(r["latency_ms"]) for r in lat_rows]
            err_queries = sum(1 for r in lat_rows if str(r["status"]).lower() in ("error", "failed"))

            avg_q_lat = round(sum(latencies) / queries_cnt, 2) if queries_cnt else 0.0
            p50_lat = round(latencies[int(queries_cnt * 0.50)], 2) if queries_cnt else 0.0
            p95_lat = round(latencies[min(queries_cnt - 1, int(queries_cnt * 0.95))], 2) if queries_cnt else 0.0
            p99_lat = round(latencies[min(queries_cnt - 1, int(queries_cnt * 0.99))], 2) if queries_cnt else 0.0
            error_rate_pct = round((err_queries / queries_cnt) * 100.0, 2) if queries_cnt else 0.0

            cloud_calls = int(conn.execute(f"SELECT COUNT(*) FROM model_usage {ws_filter}", params).fetchone()[0])

            recent_queries = [
                dict(r)
                for r in conn.execute(
                    f"SELECT * FROM query_history {ws_filter} ORDER BY id DESC LIMIT 15",
                    params,
                ).fetchall()
            ]
            recent_models = [
                dict(r)
                for r in conn.execute(
                    f"SELECT * FROM model_usage {ws_filter} ORDER BY id DESC LIMIT 15",
                    params,
                ).fetchall()
            ]

            return {
                "documents_total": docs_cnt,
                "facts_active": facts_active,
                "facts_stale": facts_stale,
                "queries_total": queries_cnt,
                "avg_query_latency_ms": avg_q_lat,
                "p50_query_latency_ms": p50_lat,
                "p95_query_latency_ms": p95_lat,
                "p99_query_latency_ms": p99_lat,
                "query_error_rate_pct": error_rate_pct,
                "cloud_model_calls": cloud_calls,
                "recent_queries": recent_queries,
                "recent_model_usage": recent_models,
            }
        finally:
            self._close_conn(conn)
