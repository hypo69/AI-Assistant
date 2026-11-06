# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Assistant AI Instruments - Package Init
# =============================================================================
# Description:
#   Экспорт моделей, хранилища, Markdown адаптера и сервиса базы инструментов
#   для построения цепочек размышлений.
#
# File: __init__.py
# Project: ai-assistant
# Package: apps.ai_assistant.core.ai_instruments
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-03 16:32:00
# =============================================================================

from __future__ import annotations

"""Пакет управления базой инструментов цепочек размышлений."""

from .models import (
    AIInstrument,
    AIInstrumentCreate,
    AIInstrumentExecuteRequest,
    AIInstrumentExecuteResult,
    get_current_iso_time,
)
from .storage import AIInstrumentsStorage
from .service import AIInstrumentsService
from .database_tool import DatabaseInstrumentTool, load_reasoning_tools
from .default_catalog import DEFAULT_REASONING_INSTRUMENTS
from .markdown_adapter import (
    load_markdown_tools,
    save_markdown_tools,
    parse_instruments_from_markdown,
    serialize_instruments_to_markdown,
)

__all__ = [
    "AIInstrument",
    "AIInstrumentCreate",
    "AIInstrumentExecuteRequest",
    "AIInstrumentExecuteResult",
    "AIInstrumentsStorage",
    "AIInstrumentsService",
    "DatabaseInstrumentTool",
    "load_reasoning_tools",
    "DEFAULT_REASONING_INSTRUMENTS",
    "load_markdown_tools",
    "save_markdown_tools",
    "parse_instruments_from_markdown",
    "serialize_instruments_to_markdown",
    "get_current_iso_time",
]
