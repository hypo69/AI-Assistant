# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Assistant AI Instruments - Reasoning Chain Tool Adapter
# =============================================================================
# Description:
#   Адаптер инструментов базы ai_instruments для построения цепочек
#   размышлений (Chain of Thought). Оборачивает инструменты в вызываемые объекты
#   с валидацией схемы аргументов, замером времени и фиксацией счетчика запусков.
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.core.ai_instruments.database_tool import load_reasoning_tools
#
#     tools = load_reasoning_tools()
#     res = await tools[0].execute(file_path="sample.txt")
#
# File: database_tool.py
# Project: ai-assistant
# Package: apps.ai_assistant.core.ai_instruments
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-03 16:20:00
# =============================================================================

from __future__ import annotations

"""Адаптер инструментов базы данных для цепочек размышлений и агента."""

import asyncio
from typing import Any, Dict, List, Optional

from logger import logger
from .models import AIInstrument
from .service import AIInstrumentsService
from .storage import AIInstrumentsStorage


class DatabaseInstrumentTool:
    """Обертка инструмента из базы данных для шагов цепочки размышлений."""

    def __init__(self, instrument: AIInstrument, service: AIInstrumentsService) -> None:
        """Инициализация инструмента.

        Args:
            instrument: Объект инструмента из базы данных.
            service: Экземпляр сервиса исполнения.
        """
        self.instrument = instrument
        self.service = service
        self.name = instrument.tool_id
        self.title = instrument.name
        self.description = f"[{instrument.target_entity.upper()}] {instrument.description or instrument.name}"
        self.parameters_schema = instrument.parameters_schema
        self.tool_type = instrument.tool_type
        self.risk_level = instrument.risk_level

    async def execute(self, **kwargs: Any) -> Dict[str, Any]:
        """Асинхронно исполняет инструмент в цепочке размышлений."""
        return await asyncio.to_thread(
            self.service.execute_instrument,
            tool_id=self.instrument.tool_id,
            parameters=kwargs,
            timeout_sec=30,
        )


def load_reasoning_tools(
    storage: Optional[AIInstrumentsStorage] = None,
    limit: int = 100,
    target_entity: Optional[str] = None,
) -> List[DatabaseInstrumentTool]:
    """Загружает инструменты из базы данных для использования в цепочках размышлений.

    Args:
        storage: Экземпляр хранилища или None для значения по умолчанию.
        limit: Максимальное количество инструментов.
        target_entity: Фильтр по домену или сущности.

    Returns:
        Список объектов DatabaseInstrumentTool.
    """
    srv = AIInstrumentsService(storage=storage)
    items = srv.list_instruments(limit=limit, target_entity=target_entity)
    return [DatabaseInstrumentTool(inst, srv) for inst in items]
