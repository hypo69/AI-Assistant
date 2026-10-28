# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Core NLP Package
# =============================================================================
# Description:
#   Пакет подключаемых мультиязычных морфолого-синтаксических анализаторов
#   (русский язык, иврит, английский язык).
#
# File: core/nlp/__init__.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.core.nlp
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-20 12:15:00
# =============================================================================

from __future__ import annotations
"""Экспорт языковых анализаторов пакета apps.ai_assistant.core.nlp."""

from apps.ai_assistant.core.nlp.english import EnglishAnalyzer
from apps.ai_assistant.core.nlp.hebrew import HebrewAnalyzer, normalize_hebrew, strip_hebrew_article
from apps.ai_assistant.core.nlp.russian import RussianAnalyzer, RussianMorphology

__all__ = [
    "RussianMorphology",
    "RussianAnalyzer",
    "HebrewAnalyzer",
    "normalize_hebrew",
    "strip_hebrew_article",
    "EnglishAnalyzer",
]
