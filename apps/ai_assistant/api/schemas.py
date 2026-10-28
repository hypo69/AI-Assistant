# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant API - Schemas
# =============================================================================
# Description:
#   Pydantic v2 схемы данных для REST API микросервиса умной истории версий:
#   история коммитов, diff, blame, темпоральный граф и двухшаговая верификация.
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.api.schemas import HistoryItem, DiffResponse, AnnotationRequest
#
# File: schemas.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.api
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 09:37:00
# =============================================================================

from __future__ import annotations
"""Pydantic v2 схемы запросов и ответов для REST API модуля AI Assistant."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def get_utc_now_iso() -> str:
    """Возвращает текущую метку времени UTC в формате ISO 8601."""
    return datetime.now(timezone.utc).isoformat()


class CommitSummary(BaseModel):
    """Краткая информация о коммите."""
    commit_hash: str = Field(..., description="Хэш коммита SHA-1")
    parent_hash: str = Field("", description="Хэш родительского коммита")
    author: str = Field(..., description="Имя и email автора")
    timestamp: str = Field(..., description="Метка времени фиксации коммита")
    message: str = Field(..., description="Сообщение коммита")
    files_changed: int = Field(0, description="Количество измененных файлов")


class FileChangeItem(BaseModel):
    """Изменение конкретного файла в коммите."""
    file_path: str = Field(..., description="Путь к файлу")
    status: str = Field("M", description="Статус: A (добавлен), M (изменен), D (удален), R (переименован)")
    old_path: Optional[str] = Field(None, description="Прежний путь при переименовании")
    blob_hash: Optional[str] = Field(None, description="Хэш blob-объекта Git")


class FileHistoryResponse(BaseModel):
    """Ответ со списком истории коммитов по файлу или репозиторию."""
    file_path: Optional[str] = Field(None, description="Целевой файл")
    total_commits: int = Field(..., description="Количество найденных коммитов")
    commits: List[CommitSummary] = Field(default_factory=list, description="Список коммитов")


class DiffHunkItem(BaseModel):
    """Срез измененного блока diff."""
    old_start: int = Field(..., description="Начальная строка в старой ревизии")
    old_lines: int = Field(..., description="Число строк в старой ревизии")
    new_start: int = Field(..., description="Начальная строка в новой ревизии")
    new_lines: int = Field(..., description="Число строк в новой ревизии")
    hunk_text: str = Field(..., description="Текст фрагмента diff")


class DiffResponse(BaseModel):
    """Ответ с результатами сравнения двух коммитов или снимка коммита."""
    commit_a: str = Field(..., description="Хэш исходного коммита")
    commit_b: Optional[str] = Field(None, description="Хэш целевого коммита")
    file_path: Optional[str] = Field(None, description="Целевой файл")
    diff_text: str = Field(..., description="Текст unified diff")
    hunks: List[DiffHunkItem] = Field(default_factory=list, description="Разобранные блоки diff")
    files_changed: List[str] = Field(default_factory=list, description="Список затронутых файлов")


class BlameLine(BaseModel):
    """Строка аннотации Git Blame."""
    line_number: int = Field(..., description="Номер строки")
    commit_hash: str = Field(..., description="Хэш коммита автора строки")
    author: str = Field(..., description="Автор изменения")
    timestamp: str = Field(..., description="Дата фиксации строки")
    code: str = Field(..., description="Исходный текст строки")
    wiki_context: Optional[str] = Field(None, description="Связанный архитектурный факт из WikiLLM (Smart Blame)")


class BlameResponse(BaseModel):
    """Ответ с построчной аннотацией файла (Smart Blame)."""
    file_path: str = Field(..., description="Путь к файлу")
    commit_hash: str = Field(..., description="Ревизия файла")
    lines: List[BlameLine] = Field(default_factory=list, description="Построчные сведения")


class TimelineEvent(BaseModel):
    """Событие на интерактивной шкале времени файла."""
    commit_hash: str = Field(..., description="Хэш коммита")
    timestamp: str = Field(..., description="Метка времени события")
    author: str = Field(..., description="Автор")
    message: str = Field(..., description="Сообщение коммита")
    diff_stat: str = Field("", description="Краткая статистика (+/- строк)")
    status: str = Field("M", description="Тип изменения файла")
    related_wiki_facts: List[str] = Field(default_factory=list, description="Ключи связанных фактов WikiLLM")


class TimelineResponse(BaseModel):
    """Ответ со шкалой времени изменений файла."""
    file_path: str = Field(..., description="Путь к файлу")
    events: List[TimelineEvent] = Field(default_factory=list, description="События таймлайна")
    checkpoints: List[TimelineEvent] = Field(default_factory=list, description="Контрольные точки (алиас)")
    total_checkpoints: int = Field(0, description="Общее количество точек")


class EvidenceLinkSchema(BaseModel):
    """Связь в темпоральном графе знаний кода."""
    source_id: str = Field(..., description="Идентификатор источника (commit_hash / blob_hash)")
    target_id: str = Field(..., description="Идентификатор цели (page_id / fact_id / error_id)")
    relation_type: str = Field(..., description="Тип связи: modifies, documents, fixes, caused_by, supersedes")
    valid_from: str = Field(..., description="Хэш коммита или метка времени начала действия")
    valid_to: Optional[str] = Field(None, description="Хэш коммита инвалидации или None, если активен")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Достоверность связи")
    provenance: str = Field("heuristic", description="Происхождение: git_tree, commit_msg, wikillm, user")
    status: str = Field("ACTIVE", description="Статус связи: ACTIVE или SUPERSEDED")


class AnnotationRequest(BaseModel):
    """Запрос на добавление аннотации к коммиту или ревизии (Шаг 1: Candidate Proposal)."""
    commit_hash: Optional[str] = Field(None, description="Хэш коммита")
    source_id: Optional[str] = Field(None, description="Идентификатор источника")
    file_path: Optional[str] = Field(None, description="Опциональный путь к файлу")
    target_id: Optional[str] = Field(None, description="Идентификатор целевой сущности WikiLLM")
    fact_title: Optional[str] = Field(None, description="Заголовок архитектурного факта/решения")
    fact_description: Optional[str] = Field(None, description="Описание причины изменения")
    summary: Optional[str] = Field(None, description="Краткое резюме факта")
    valid_from: Optional[str] = Field(None, description="Хэш коммита или дата начала действия")
    relation_type: str = Field("documents", description="Тип отношения: documents, fixes, modifies, supersedes")
    confidence: float = Field(0.9, ge=0.0, le=1.0, description="Степень уверенности")
    provenance: str = Field("manual", description="Происхождение аннотации")
    user_id: int = Field(1, description="Идентификатор пользователя")


class AnnotationResponse(BaseModel):
    """Ответ валидации и сохранения аннотации (Шаг 2: Validation Pipeline)."""
    success: bool = Field(True, description="Успешность операции")
    status: str = Field("verified_and_saved", description="Статус операции")
    message: str = Field("Факт успешно валидирован и зафиксирован", description="Пояснение валидации")
    verification_passed: bool = Field(True, description="Флаг прохождения проверок безопасности")
    sanitized_fact_id: Optional[str] = Field(None, description="Идентификатор созданного факта в базе")
    link: Optional[EvidenceLinkSchema] = Field(None, description="Зарегистрированная темпоральная связь")


class QuerySearchRequest(BaseModel):
    """Запрос на интеллектуальный поиск по истории версий."""
    query: str = Field(..., description="Вопрос на естественном языке")
    file_path: Optional[str] = Field(None, description="Ограничение поиска по файлу")
    top_k: int = Field(5, ge=1, le=50, description="Количество возвращаемых результатов")
    limit: Optional[int] = Field(None, description="Алиас для top_k")
    include_diff: bool = Field(True, description="Извлекать ли точный diff")


class QuerySearchResponse(BaseModel):
    """Ответ координатора поиска с ИИ-анализом и быстрыми вопросами."""
    query: str = Field(..., description="Исходный запрос")
    total_found: int = Field(0, description="Общее число совпадений")
    explanation: str = Field("", description="Синтезированное экспертное объяснение")
    commits: List[CommitSummary] = Field(default_factory=list, description="Найденные релевантные коммиты")
    rag_chunks: List[Dict[str, Any]] = Field(default_factory=list, description="Найденные векторные чанки")
    wiki_entities: List[Dict[str, Any]] = Field(default_factory=list, description="Сущности WikiLLM")
    diff_snippets: Dict[str, str] = Field(default_factory=dict, description="Фрагменты diff по коммитам")
    evidence_links: List[EvidenceLinkSchema] = Field(default_factory=list, description="Темпоральные связи")
    temporal_links: List[EvidenceLinkSchema] = Field(default_factory=list, description="Темпоральные связи (алиас)")
    suggested_quick_questions: List[str] = Field(default_factory=list, description="Рекомендованные быстрые вопросы")
