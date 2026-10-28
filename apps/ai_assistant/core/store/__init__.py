# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Core Store Package
# =============================================================================
# Description:
#   Пакет модульных репозиториев SQLite для KnowledgeStore.
#
# File: core/store/__init__.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.core.store
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-20 12:20:00
# =============================================================================

from __future__ import annotations
"""Экспорт компонентов пакета apps.ai_assistant.core.store."""

from apps.ai_assistant.core.store.document_fact_repo import DocumentFactRepoMixin, compute_sha256
from apps.ai_assistant.core.store.schema import KNOWLEDGE_STORE_DDL
from apps.ai_assistant.core.store.telemetry_repo import TelemetryRepoMixin
from apps.ai_assistant.core.store.workspace_repo import WorkspaceRepoMixin, get_utc_now_iso

__all__ = [
    "KNOWLEDGE_STORE_DDL",
    "WorkspaceRepoMixin",
    "DocumentFactRepoMixin",
    "TelemetryRepoMixin",
    "compute_sha256",
    "get_utc_now_iso",
]
