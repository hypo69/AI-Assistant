# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-assistant Common File Tree - Data Models
# =============================================================================
# Description:
#   Pydantic-модели и структуры данных для древовидного проводника файлов
#   и директорий (apps/common/file_tree).
#   Определяет узлы дерева, параметры навигации, запросы создания объектов
#   и сводку краткой информации о файлах.
#
# File: models.py
# Project: ai-assistant
# Package: apps.common.file_tree
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 19:55:00
# =============================================================================

from __future__ import annotations
"""Модели данных для модуля иерархического дерева файлов и директорий."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class BreadcrumbItem(BaseModel):
    """Элемент пути навигационной цепочки (Breadcrumbs)."""

    name: str = Field(..., description="Отображаемое имя сегмента пути")
    path: str = Field(..., description="Относительный путь сегмента от корня")
    is_current: bool = Field(default=False, description="Признак текущей активной директории")


class FileTreeNode(BaseModel):
    """Иерархический узел дерева файлов и папок."""

    name: str = Field(..., description="Имя файла или папки")
    rel_path: str = Field(..., description="Относительный путь внутри рабочей области")
    is_dir: bool = Field(default=False, description="Признак директории")
    size: int = Field(default=0, description="Размер в байтах")
    size_formatted: str = Field(default="0 B", description="Человекочитаемый размер")
    extension: str = Field(default="", description="Расширение файла с точкой")
    modified_at: str = Field(default="", description="ISO-строка времени последнего изменения")
    tracked_by_git: bool = Field(default=False, description="Отслеживается ли системой Git")
    git_code: Optional[str] = Field(default=None, description="Код статуса Git (M, A, D, R, ??)")
    git_status: Optional[str] = Field(default=None, description="Словесное описание статуса Git")
    children_count: int = Field(default=0, description="Количество прямых потомков для папок")
    children: List[FileTreeNode] = Field(default_factory=list, description="Список вложенных узлов")
    language_id: Optional[str] = Field(default=None, description="Идентификатор языка редактора VS Code")


class DirectoryBrowseResponse(BaseModel):
    """Ответ сервиса при навигации и обзоре выбранной директории."""

    status: str = Field(default="ok", description="Статус операции")
    workspace_id: str = Field(..., description="Идентификатор рабочей области")
    current_dir: str = Field(default="", description="Текущий относительный путь выбранной директории")
    parent_dir: Optional[str] = Field(default=None, description="Путь к родительской директории (для кнопки Вверх)")
    breadcrumbs: List[BreadcrumbItem] = Field(default_factory=list, description="Цепочка сегментов навигации")
    total_files: int = Field(default=0, description="Общее число файлов в дереве")
    total_dirs: int = Field(default=0, description="Общее число директорий в дереве")
    total_size_bytes: int = Field(default=0, description="Суммарный размер файлов")
    tree: List[FileTreeNode] = Field(default_factory=list, description="Корневой список узлов выбранной директории")


class FileSummaryResponse(BaseModel):
    """Краткая аналитическая сводка о выбранном файле."""

    status: str = Field(default="ok", description="Статус операции")
    workspace_id: str = Field(..., description="Идентификатор рабочей области")
    rel_path: str = Field(..., description="Относительный путь к файлу")
    name: str = Field(..., description="Имя файла")
    extension: str = Field(default="", description="Расширение файла")
    size: int = Field(default=0, description="Размер в байтах")
    size_formatted: str = Field(default="0 B", description="Форматированный размер")
    is_binary: bool = Field(default=False, description="Признак бинарного содержимого")
    lines_count: Optional[int] = Field(default=None, description="Количество строк для текстовых файлов")
    language_id: str = Field(default="plaintext", description="Языковой режим VS Code")
    summary: str = Field(default="", description="Краткая суть содержимого или первые строки")
    preview: str = Field(default="", description="Текстовый фрагмент начала файла")
    modified_at: str = Field(default="", description="Время изменения файла")
    tags: List[str] = Field(default_factory=list, description="Семантические теги содержимого")


class CreateItemRequest(BaseModel):
    """Запрос создания нового файла или подкаталога в выбранной директории."""

    workspace_id: Optional[str] = Field(default=None, description="Идентификатор рабочей области")
    target_dir: str = Field(default="", description="Относительный путь к директории, где создаётся объект")
    name: str = Field(..., description="Имя создаваемого файла или подкаталога")
    is_dir: bool = Field(default=False, description="True для директории, False для файла")
    content: str = Field(default="", description="Начальное текстовое содержимое для нового файла")
    commit_message: Optional[str] = Field(default=None, description="Пользовательское сообщение для Git-коммита")


class CreateItemResponse(BaseModel):
    """Результат создания нового файла или подкаталога."""

    status: str = Field(default="ok", description="Статус операции")
    workspace_id: str = Field(..., description="Идентификатор рабочей области")
    rel_path: str = Field(..., description="Полный относительный путь созданного объекта")
    target_dir: str = Field(default="", description="Директория размещения объекта")
    name: str = Field(..., description="Имя созданного объекта")
    is_dir: bool = Field(..., description="Признак директории")
    size: int = Field(default=0, description="Размер созданного файла")
    message: str = Field(default="", description="Информационное сообщение о фиксации в Git")
