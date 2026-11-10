# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Core - Paperless Sync
# =============================================================================
# Description:
#   Синхронизация документов Paperless-ngx в рабочую область AI-Assistant.
#   Рабочая область соответствует тегу Paperless; текст не дублируется в БД
#   (в knowledge_store.db хранятся факты, связи и paperless_id).
#
# Usage Examples:
#   from apps.ai_assistant.core.paperless_sync import sync_workspace_from_paperless
#
#   report = sync_workspace_from_paperless(wm, connector, "default")
#
# File: paperless_sync.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 16:40:00
# =============================================================================

from __future__ import annotations
"""Импорт документов Paperless-ngx в рабочую область по тегу."""

import functools
import time
from typing import Any, Dict, Optional

from logger import logger
from apps.ai_assistant.core.paperless_connector import PaperlessConnector, PaperlessError


class PaperlessTextResolver:
    """Ленивый резолвер paperless_id -> OCR-текст с LRU-кэшем; недоступность Paperless даёт пустую строку."""

    def __init__(self, cache_size: int = 64) -> None:
        """Создаёт резолвер; клиент Paperless создаётся при первом обращении.

        Args:
            cache_size: Максимум документов в кэше текста.
        """
        self._connector: Optional[PaperlessConnector] = None
        self._cached = functools.lru_cache(maxsize=cache_size)(self._fetch)

    def _fetch(self, paperless_id: int) -> str:
        """Загружает текст документа из Paperless (без обработки ошибок, чтобы они не кэшировались)."""
        if self._connector is None:
            self._connector = PaperlessConnector.from_config()
        return self._connector.get_document_content(paperless_id)

    def __call__(self, paperless_id: int) -> str:
        """Возвращает текст документа или пустую строку при недоступности Paperless."""
        try:
            return self._cached(paperless_id)
        except PaperlessError as exc:
            logger.warning(f"[PaperlessTextResolver] Текст документа {paperless_id} недоступен: {exc}")
            return ""


def sync_workspace_from_paperless(wm: Any, connector: PaperlessConnector, workspace_id: str) -> Dict[str, Any]:
    """Индексирует документы с тегом рабочей области из Paperless.

    Args:
        wm: Экземпляр WorkspaceManager.
        connector: Клиент Paperless.
        workspace_id: Идентификатор рабочей области.

    Returns:
        Dict[str, Any]: Отчёт: workspace_id, indexed, failed.
    """
    tag = connector.workspace_tag_name(workspace_id)
    indexed, failed = 0, 0
    for doc in connector.iter_documents(tag_name=tag):
        paperless_id = int(doc["id"])
        try:
            text = connector.get_document_content(paperless_id)
            if not text.strip():
                continue
            wm._persist_and_index_doc(
                workspace_id=workspace_id,
                doc_id=f"paperless/{paperless_id}",
                file_path_str=f"paperless://{paperless_id}",
                content=text,
                commit_hash="",
                commit_message=None,
                language=None,
                force_reanalyze=False,
                t0=time.perf_counter(),
                paperless_id=paperless_id,
            )
            indexed += 1
        except PaperlessError as exc:
            failed += 1
            logger.error(f"[PaperlessSync] Документ {paperless_id}: {exc}")
    return {"workspace_id": workspace_id, "indexed": indexed, "failed": failed}
