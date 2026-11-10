# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Assistant AI Instruments - Data Models
# =============================================================================
# Description:
#   Модели данных для базы инструментов ИИ-ассистента и цепочек размышлений
#   (ai_instruments). Хранит исполняемые скрипты, Python-функции, утилиты
#   и команды, используемые моделью при построении пошаговых планов и рассуждений.
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.core.ai_instruments.models import AIInstrument, AIInstrumentCreate
#
#     inst = AIInstrument(
#         tool_id="inst_summarize_table",
#         name="Резюмирование структуры таблицы",
#         tool_type="python",
#         command="import pandas as pd...",
#         description="Анализирует столбцы и типы данных",
#         target_entity="knowledge:table"
#     )
#
# File: models.py
# Project: ai-assistant
# Package: apps.ai_assistant.core.ai_instruments
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 13:55:00
# =============================================================================

from __future__ import annotations

"""Модели данных для базы инструментов ИИ-ассистента и цепочек размышлений."""

import datetime
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def get_current_iso_time() -> str:
    """Возвращает текущую дату и время в формате ISO 8601 UTC.

    Returns:
        Строковое представление времени в формате ISO 8601.
    """
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class AIInstrument(BaseModel):
    """Сущность инструмента для цепочек размышлений и агента."""

    tool_id: str = Field(
        default_factory=lambda: f"inst_{uuid.uuid4().hex[:12]}",
        description="Уникальный идентификатор инструмента",
    )
    name: str = Field(
        ...,
        description="Понятное название инструмента или скрипта на русском языке",
    )
    tool_type: str = Field(
        default="python",
        description="Тип среды выполнения: python, powershell, cmd, utility, api, sql",
    )
    command: str = Field(
        ...,
        description="Исполняемая команда, код Python или текст скрипта автоматизации",
    )
    description: str = Field(
        default="",
        description="Назначение инструмента и рекомендации модели по применению в цепочке",
    )
    target_entity: str = Field(
        default="system",
        description="Связанная сущность или домен (например, knowledge:table, file:pdf, system:network)",
    )
    parameters_schema: Dict[str, Any] = Field(
        default_factory=dict,
        description="JSON-схема аргументов и параметров запуска инструмента",
    )
    risk_level: str = Field(
        default="safe",
        description="Уровень риска операции: safe, caution, danger",
    )
    author_agent: str = Field(
        default="reasoning_chain",
        description="Источник создания инструмента: reasoning_chain, cot_planner, gemini, admin",
    )
    tags: List[str] = Field(
        default_factory=lambda: ["#agent_tool", "#reasoning"],
        description="Теги для семантической фильтрации и группировки",
    )
    execution_count: int = Field(
        default=0,
        description="Счётчик успешных запусков инструмента в цепочках рассуждений",
    )
    last_executed_at: Optional[str] = Field(
        default="",
        description="Временная метка последнего запуска в формате ISO 8601",
    )
    created_at: str = Field(
        default_factory=get_current_iso_time,
        description="Временная метка создания инструмента",
    )
    updated_at: str = Field(
        default_factory=get_current_iso_time,
        description="Временная метка последнего обновления",
    )


class AIInstrumentCreate(BaseModel):
    """Схема запроса создания нового инструмента."""

    tool_id: Optional[str] = Field(default="", description="Желаемый идентификатор инструмента")
    name: str = Field(..., description="Название инструмента")
    tool_type: str = Field(default="python", description="Тип: python, powershell, cmd, utility, api, sql")
    command: str = Field(..., description="Исполняемый код или шаблон команды")
    description: Optional[str] = Field(default="", description="Описание назначения и ожидаемых результатов")
    target_entity: Optional[str] = Field(default="system", description="Связанная сущность или домен")
    parameters_schema: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Схема параметров")
    risk_level: Optional[str] = Field(default="safe", description="Уровень риска: safe, caution, danger")
    author_agent: Optional[str] = Field(default="reasoning_chain", description="Автор или модуль создания")
    tags: Optional[List[str]] = Field(default_factory=lambda: ["#agent_tool", "#reasoning"], description="Теги")


class AIInstrumentExecuteRequest(BaseModel):
    """Схема запроса на запуск инструмента."""

    tool_id: str = Field(..., description="Идентификатор инструмента")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Параметры подстановки")
    timeout_sec: int = Field(default=30, description="Таймаут выполнения команды в секундах")
    as_admin: bool = Field(default=False, description="Флаг повышенных привилегий (если применимо)")


class AIInstrumentExecuteResult(BaseModel):
    """Схема результата выполнения инструмента."""

    success: bool = Field(..., description="Успешность выполнения операции")
    exit_code: int = Field(..., description="Код возврата процесса")
    stdout: str = Field(default="", description="Стандартный вывод")
    stderr: str = Field(default="", description="Поток ошибок")
    duration_ms: int = Field(default=0, description="Время выполнения в миллисекундах")
    tool_id: str = Field(..., description="Идентификатор выполненного инструмента")
    command_executed: str = Field(default="", description="Фактически выполненная команда")
