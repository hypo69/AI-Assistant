# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant - Data Models
# =============================================================================
# Description:
#   Модели данных DTO и сущностей для умной истории версий (Git + WikiLLM + RAG).
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.models import GitCommitInfo, QueryRequest, QueryResponse
#
# File: models.py
# Project: ai-windows-admin
# Package: apps.ai_assistant
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 07:15:00
# =============================================================================

from __future__ import annotations
"""Модели данных и схемы DTO для модуля умной истории версий."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def get_utc_now_iso() -> str:
    """Возвращает текущую метку времени UTC в формате ISO 8601.

    Returns:
        str: Строка времени в формате ISO.
    """
    return datetime.now(timezone.utc).isoformat()


@dataclass
class GitCommitInfo:
    """Сведения о коммите из репозитория Git.

    Attributes:
        commit_hash: Полный хэш коммита SHA-1.
        parent_hash: Хэш родительского коммита.
        author: Автор коммита (имя и email).
        timestamp: Дата и время коммита в формате ISO.
        message: Сообщение коммита.
        files_changed_count: Количество изменённых файлов в коммите.
    """
    commit_hash: str
    parent_hash: str = ""
    author: str = ""
    timestamp: str = ""
    message: str = ""
    files_changed_count: int = 0


@dataclass
class FileChange:
    """Описание изменения отдельного файла в рамках коммита.

    Attributes:
        file_path: Относительный путь к файлу.
        change_type: Тип изменения ('A' - добавлен, 'M' - изменён, 'D' - удалён, 'R' - переименован).
        old_path: Прежний путь при переименовании файла.
        blob_hash: Git blob хэш нового содержимого.
        old_blob_hash: Git blob хэш старого содержимого.
    """
    file_path: str
    change_type: str = "M"
    old_path: str = ""
    blob_hash: str = ""
    old_blob_hash: str = ""


@dataclass
class DiffHunk:
    """Фрагмент (hunk) текстового diff между ревизиями.

    Attributes:
        file_path: Путь к файлу.
        commit_hash: Хэш коммита.
        old_start: Начальная строка в старой версии.
        old_lines: Число строк в старой версии.
        new_start: Начальная строка в новой версии.
        new_lines: Число строк в новой версии.
        hunk_text: Текст дифференциального фрагмента (с префиксами + / -).
    """
    file_path: str
    commit_hash: str
    old_start: int = 0
    old_lines: int = 0
    new_start: int = 0
    new_lines: int = 0
    hunk_text: str = ""


@dataclass
class FileRevision:
    """Снимок содержимого файла на указанной ревизии коммита.

    Attributes:
        file_path: Относительный путь к файлу.
        commit_hash: Хэш коммита, на котором получен снимок.
        blob_hash: Хэш Git blob.
        content: Полный текст файла на ревизии.
        size_bytes: Размер файла в байтах.
        timestamp: Метка времени фиксации ревизии.
    """
    file_path: str
    commit_hash: str
    blob_hash: str = ""
    content: str = ""
    size_bytes: int = 0
    timestamp: float = 0.0


@dataclass
class KnowledgeLink:
    """Связь графа знаний между Git-изменением, артефактом WikiLLM и решением.

    Attributes:
        source_type: Тип источника ('commit', 'file', 'diff_hunk', 'issue', 'page').
        source_id: Идентификатор источника.
        relation_type: Тип отношения ('modifies', 'documents', 'fixes', 'caused_by', 'supersedes', 'depends_on').
        target_type: Тип целевой сущности ('page', 'commit', 'error', 'solution', 'component').
        target_id: Идентификатор целевой сущности.
        confidence: Достоверность вывода от 0.0 до 1.0.
        provenance: Источник происхождения связи ('commit_msg', 'wikillm', 'user', 'heuristic').
        created_at: Время создания связи.
    """
    source_type: str
    source_id: str
    relation_type: str
    target_type: str
    target_id: str
    confidence: float = 1.0
    provenance: str = "heuristic"
    created_at: str = field(default_factory=get_utc_now_iso)


@dataclass
class HistoryDocumentChunk:
    """Фрагмент истории для RAG-индексации с метаданными версионирования.

    Attributes:
        chunk_id: Устойчивый идентификатор формата 'doc#chunk_idx#vX'.
        repo_id: Идентификатор репозитория.
        source_type: Тип содержимого ('file_revision', 'diff_hunk', 'commit_message', 'wiki_page', 'error_event', 'decision_record').
        commit_hash: Хэш коммита.
        file_path: Путь к файлу.
        blob_hash: Git blob хэш.
        content_hash: SHA-256 хэш содержимого для дедупликации.
        text: Текстовое содержимое чанка.
        version: Целочисленный номер версии.
        version_timestamp: Unix-время модификации.
        is_latest: Флаг актуальности версии.
        meta: Дополнительные произвольные метаданные.
    """
    chunk_id: str
    repo_id: str = "ai-windows-admin"
    source_type: str = "diff_hunk"
    commit_hash: str = ""
    file_path: str = ""
    blob_hash: str = ""
    content_hash: str = ""
    text: str = ""
    version: int = 1
    version_timestamp: float = 0.0
    is_latest: bool = True
    meta: Dict[str, Any] = field(default_factory=dict)


class QueryRequest(BaseModel):
    """Модель входящего запроса на умный поиск по истории версий."""
    query: str = Field(..., description="Вопрос на естественном языке об истории изменений и архитектуре")
    top_k: int = Field(5, ge=1, le=50, description="Максимальное количество возвращаемых артефактов")
    version_filter: str = Field("all", description="Режим фильтрации: 'latest', 'all', или номер версии")
    include_diff: bool = Field(True, description="Включать ли извлечение точного diff из Git")
    include_wiki: bool = Field(True, description="Подключать ли статьи и связи из базы знаний WikiLLM")
    file_path: Optional[str] = Field(None, description="Ограничение поиска конкретным путем к файлу")


class EvidenceItem(BaseModel):
    """Элемент доказательной базы (Evidence), найденный координатором."""
    source_type: str = Field(..., description="Тип источника: commit, diff, wiki, chunk")
    title: str = Field(..., description="Заголовок или краткое описание источника")
    snippet: str = Field(..., description="Фрагмент текста или кода")
    commit_hash: str = Field("", description="Хэш связанного коммита")
    file_path: str = Field("", description="Путь к связанному файлу")
    score: float = Field(0.0, description="Оценка релевантности")
    provenance: str = Field("", description="Происхождение доказательства")


class QueryResponse(BaseModel):
    """Итоговый ответ координатора умной истории версий для пользователя и LLM."""
    query: str = Field(..., description="Исходный запрос")
    explanation: str = Field(..., description="Развернутое экспертное объяснение от LLM или синтезатора")
    suggested_quick_questions: List[str] = Field(default_factory=list, description="Динамические быстрые вопросы для продолжения диалога")
    evidence: List[EvidenceItem] = Field(default_factory=list, description="Проверенные доказательства и источники")
    commits: List[Dict[str, Any]] = Field(default_factory=list, description="Найденные коммиты с метаданными")
    diffs: Dict[str, str] = Field(default_factory=dict, description="Извлеченные точные diff для файлов")
    knowledge_links: List[Dict[str, Any]] = Field(default_factory=list, description="Связи в графе знаний WikiLLM")
    status: str = Field("ok", description="Статус выполнения запроса")


class IndexingStatus(BaseModel):
    """Статус подсистемы инкрементальной RAG-индексации истории версий."""
    total_commits: int = Field(0, description="Всего коммитов в репозитории")
    indexed_chunks: int = Field(0, description="Количество проиндексированных чанков")
    skipped_chunks: int = Field(0, description="Пропущено неизмененных чанков (zero-token)")
    last_indexed_commit: str = Field("", description="Хэш последнего обработанного коммита")
    updated_at: str = Field(default_factory=get_utc_now_iso, description="Время последнего обновления индекса")
