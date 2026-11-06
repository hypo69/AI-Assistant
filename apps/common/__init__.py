# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Assistant Apps Common - Package Init
# =============================================================================
# Description:
#   Общие вспомогательные утилиты для приложений Windows.
#
# File: __init__.py
# Project: ai-assistant
# Package: apps.common
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 18:30:50
# =============================================================================

from __future__ import annotations
"""Общие компоненты и утилиты приложений."""

from apps.common.webgui import SmartMultiDirStaticFiles, COMMON_WEBGUI_DIR

__all__ = [
    'SmartMultiDirStaticFiles',
    'COMMON_WEBGUI_DIR',
]

