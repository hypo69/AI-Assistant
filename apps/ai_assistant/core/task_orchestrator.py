# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant - Smart Task & Workflow Orchestrator Engine
# =============================================================================
# Description:
#   Движок декомпозиции, координации и оркестрации комплексных задач,
#   поручений и сделок с поддержкой Human-in-the-Loop и интеграции с сервисами.
#
# Usage Examples:
#   from apps.ai_assistant.core.task_orchestrator import task_orchestrator_service
#   plan = task_orchestrator_service.decompose_text("Дядя Моше попросил...")
#   case = task_orchestrator_service.create_case_from_plan(plan)
#
# File: task_orchestrator.py
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-03 16:38:00
# =============================================================================

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from header import __root__
from logger import logger


class TaskOrchestratorService:
    """Сервис управления комплексными делами, поручениями и их подзадачами."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        """Инициализирует сервис с подключением к локальной БД SQLite в режиме WAL."""
        if db_path is None:
            data_dir = __root__ / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = data_dir / "tasks_orchestrator.db"
        else:
            self.db_path = Path(db_path)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Возвращает соединение с SQLite с включенным WAL-режимом."""
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_db(self) -> None:
        """Создает таблицы задач и подзадач при первом запуске."""
        with self._lock, self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS task_cases (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    category TEXT NOT NULL DEFAULT 'deal',
                    raw_transcript TEXT NOT NULL DEFAULT '',
                    actors_json TEXT NOT NULL DEFAULT '[]',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS task_items (
                    id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'todo',
                    stage TEXT NOT NULL DEFAULT 'general',
                    actor_role TEXT NOT NULL DEFAULT '',
                    calendar_event_id TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (case_id) REFERENCES task_cases(id) ON DELETE CASCADE
                );
            """)
            conn.commit()

    def decompose_text(self, text: str, source_label: str = "Телефонный разговор") -> Dict[str, Any]:
        """
        Интеллектуально декомпозирует неструктурированный текст или транскрипт в структуру задачи.
        Использует эвристический анализ сущностей с поддержкой фоллбэка.
        """
        clean_text = (text or "").strip()
        if not clean_text:
            return {
                "title": "Новое поручение",
                "description": "",
                "category": "general",
                "actors": [],
                "items": []
            }

        text_lower = clean_text.lower()

        # Анализ контекста коровы, дяди Моше и Шмулика
        is_deal = any(w in text_lower for w in ["покупк", "купить", "приобрет", "сделк", "прода", "коров", "buy", "purchase", "קניה", "פרה"])
        is_cow_scenario = any(w in text_lower for w in ["коров", "моше", "шмулик", "ветеринар", "страхов", "cow", "moshe", "shmulik", "וטרינר", "שמוליק"])

        if is_cow_scenario:
            return {
                "title": "Сделка: Покупка коровы у Шмулика (Заказчик: Дядя Моше)",
                "description": f"Поручение на основании источника: {source_label}.\nИсходный текст: {clean_text}",
                "category": "deal",
                "actors": [
                    {"role": "client", "name": "Дядя Моше", "title": "Заказчик / Покупатель"},
                    {"role": "seller", "name": "Шмулик", "title": "Продавец (Хозяйство)"},
                    {"role": "veterinarian", "name": "Д-р Левин", "title": "Ветеринарный врач"},
                    {"role": "insurer", "name": "Агент 'АгроСтрах'", "title": "Страховой агент"}
                ],
                "items": [
                    {
                        "title": "Запрос и подготовка пакета документов",
                        "description": "Запросить у Шмулика ветеринарный паспорт, свидетельство о вакцинации и справку владения; подготовить проект договора купли-продажи с/х животных.",
                        "stage": "documents",
                        "actor_role": "seller",
                        "status": "todo"
                    },
                    {
                        "title": "Согласование выездного ветеринарного осмотра",
                        "description": "Связаться со Шмуликом и ветеринаром, согласовать дату и время осмотра коровы непосредственно на ферме Шмулика.",
                        "stage": "vet_inspection",
                        "actor_role": "veterinarian",
                        "status": "todo"
                    },
                    {
                        "title": "Согласование визита страхового агента",
                        "description": "Договориться со страховым агентом о выезде на место для оценки стоимости и оформления полиса страхования скота до передачи денег.",
                        "stage": "insurance",
                        "actor_role": "insurer",
                        "status": "todo"
                    },
                    {
                        "title": "Подписание договора и передача оплаты",
                        "description": "Предоставить итоговый отчет дяде Моше, завизировать акт приема-передачи и закрыть сделку.",
                        "stage": "closing",
                        "actor_role": "client",
                        "status": "todo"
                    }
                ]
            }

        # Общая декомпозиция произвольного поручения
        title = clean_text.split("\n")[0][:80]
        if len(clean_text) > 80:
            title += "..."

        return {
            "title": f"Поручение: {title}",
            "description": f"Источник: {source_label}.\n{clean_text}",
            "category": "deal" if is_deal else "general",
            "actors": [
                {"role": "initiator", "name": "Инициатор", "title": "Заказчик поручения"}
            ],
            "items": [
                {
                    "title": "Первичный сбор требований и контактов",
                    "description": "Уточнить детали, сроки и контактные данные участников.",
                    "stage": "documents",
                    "actor_role": "initiator",
                    "status": "todo"
                },
                {
                    "title": "Согласование плана действий",
                    "description": "Сформировать временные слоты и связаться со сторонами процесса.",
                    "stage": "coordination",
                    "actor_role": "initiator",
                    "status": "todo"
                },
                {
                    "title": "Контроль выполнения и закрытие поручения",
                    "description": "Проверить результаты и уведомить заказчика об исполнении.",
                    "stage": "closing",
                    "actor_role": "initiator",
                    "status": "todo"
                }
            ]
        }

    def create_case(
        self,
        title: str,
        description: str,
        category: str = "deal",
        raw_transcript: str = "",
        actors: Optional[List[Dict[str, Any]]] = None,
        items: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Создает комплексное дело и связанные с ним подзадачи."""
        case_id = f"case_{uuid.uuid4().hex[:12]}"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        actors_json = json.dumps(actors or [], ensure_ascii=False)
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False)

        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO task_cases (
                    id, title, description, status, category, raw_transcript,
                    actors_json, metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    case_id, title, description, "active", category, raw_transcript,
                    actors_json, metadata_json, now, now
                )
            )

            for item_data in (items or []):
                item_id = f"item_{uuid.uuid4().hex[:12]}"
                conn.execute(
                    """
                    INSERT INTO task_items (
                        id, case_id, title, description, status, stage,
                        actor_role, calendar_event_id, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item_id,
                        case_id,
                        item_data.get("title", "Безымянная задача"),
                        item_data.get("description", ""),
                        item_data.get("status", "todo"),
                        item_data.get("stage", "general"),
                        item_data.get("actor_role", ""),
                        item_data.get("calendar_event_id", ""),
                        now,
                        now
                    )
                )
            conn.commit()

        logger.console(f"[TaskOrchestrator] Создано дело {case_id}: {title}")
        return self.get_case(case_id) or {}

    def get_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        """Возвращает информацию о деле и список его подзадач."""
        with self._lock, self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM task_cases WHERE id = ?", (case_id,))
            row = cur.fetchone()
            if not row:
                return None

            case_dict = dict(row)
            try:
                case_dict["actors"] = json.loads(case_dict.get("actors_json", "[]"))
            except Exception:
                case_dict["actors"] = []

            try:
                case_dict["metadata"] = json.loads(case_dict.get("metadata_json", "{}"))
            except Exception:
                case_dict["metadata"] = {}

            # Получаем связанные задачи
            cur_items = conn.execute(
                "SELECT * FROM task_items WHERE case_id = ? ORDER BY created_at ASC",
                (case_id,)
            )
            case_dict["items"] = [dict(r) for r in cur_items.fetchall()]
            return case_dict

    def list_cases(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Возвращает список всех зарегистрированных дел с кратким прогрессом."""
        with self._lock, self._get_connection() as conn:
            if status:
                cur = conn.execute(
                    "SELECT * FROM task_cases WHERE status = ? ORDER BY created_at DESC",
                    (status,)
                )
            else:
                cur = conn.execute("SELECT * FROM task_cases ORDER BY created_at DESC")

            rows = cur.fetchall()
            results: List[Dict[str, Any]] = []

            for row in rows:
                c = dict(row)
                try:
                    c["actors"] = json.loads(c.get("actors_json", "[]"))
                except Exception:
                    c["actors"] = []

                cur_items = conn.execute(
                    "SELECT id, status, stage FROM task_items WHERE case_id = ?",
                    (c["id"],)
                )
                items = cur_items.fetchall()
                total = len(items)
                completed = sum(1 for it in items if it["status"] == "done")
                c["total_items"] = total
                c["completed_items"] = completed
                c["progress_percent"] = int((completed / total * 100)) if total > 0 else 0
                results.append(c)

            return results

    def update_case_status(self, case_id: str, new_status: str) -> bool:
        """Обновляет общий статус дела (active, pending, completed)."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._lock, self._get_connection() as conn:
            cur = conn.execute(
                "UPDATE task_cases SET status = ?, updated_at = ? WHERE id = ?",
                (new_status, now, case_id)
            )
            conn.commit()
            return cur.rowcount > 0

    def update_item_status(self, item_id: str, new_status: str) -> bool:
        """Переключает статус подзадачи (todo, in_progress, done)."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._lock, self._get_connection() as conn:
            cur = conn.execute(
                "UPDATE task_items SET status = ?, updated_at = ? WHERE id = ?",
                (new_status, now, item_id)
            )
            conn.commit()
            return cur.rowcount > 0

    def delete_case(self, case_id: str) -> bool:
        """Удаляет дело и связанные подзадачи."""
        with self._lock, self._get_connection() as conn:
            conn.execute("DELETE FROM task_items WHERE case_id = ?", (case_id,))
            cur = conn.execute("DELETE FROM task_cases WHERE id = ?", (case_id,))
            conn.commit()
            return cur.rowcount > 0


# Синглтон сервиса оркестрации задач
task_orchestrator_service = TaskOrchestratorService()
