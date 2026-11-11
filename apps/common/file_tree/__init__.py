# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-assistant Common File Tree - Package Init
# =============================================================================
# Description:
#   Экспорт публичных интерфейсов модуля древовидного проводника файлов
#   и директорий (apps/common/file_tree).
#
# File: __init__.py
# Project: ai-assistant
# Package: apps.common.file_tree
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 19:55:00
# =============================================================================

from __future__ import annotations
"""Экспорт сервиса, маршрутизатора и моделей проводника дерева файлов."""

from apps.common.file_tree.models import (
    BreadcrumbItem,
    CreateItemRequest,
    CreateItemResponse,
    DirectoryBrowseResponse,
    FileSummaryResponse,
    FileTreeNode,
)
from apps.common.file_tree.router import router as file_tree_router
from apps.common.file_tree.service import FileTreeService

__all__ = [
    "BreadcrumbItem",
    "CreateItemRequest",
    "CreateItemResponse",
    "DirectoryBrowseResponse",
    "FileSummaryResponse",
    "FileTreeNode",
    "FileTreeService",
    "file_tree_router",
]
