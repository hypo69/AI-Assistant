# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Root - Header
# =============================================================================
# Description:
#   Определение корневого каталога проекта (__root__) и нормализация системных путей.
#
#   Зачем нужен этот модуль:
#     1. Единый источник истины для импортов: гарантирует корректную загрузку внутренних
#        пакетов (src, apps, logger) независимо от рабочей директории, из которой запущен скрипт.
#     2. Кроссплатформенная нормализация: выравнивает переменные окружения USERPROFILE/HOME
#        и добавляет __root__ в sys.path.
#     3. Поддержка внешних переопределений: считывает переменную AIWINDOWSADMIN_DIR при наличии.
#
# Usage Examples:
#   Python API:
#     import header
#     from header import __root__
#
#     config_path = __root__ / "config.json"
#
# File: header.py
# Project: ai-windows-admin
# Package: root
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-27 22:45:00
# =============================================================================

import os
import sys
from pathlib import Path
if 'USERPROFILE' not in os.environ and 'HOME' in os.environ:
    os.environ['USERPROFILE'] = os.environ['HOME']
elif 'HOME' not in os.environ and 'USERPROFILE' in os.environ:
    os.environ['HOME'] = os.environ['USERPROFILE']
elif 'USERPROFILE' not in os.environ and 'HOME' not in os.environ:
    try:
        _home = str(Path.home())
    except Exception:
        _home = str(Path(__file__).resolve().parent)
    os.environ['USERPROFILE'] = _home
    os.environ['HOME'] = _home

#marker_files: list = ['__root__', '.git']
marker_files: list = ['__root__']
def set_project_root(marker_files=marker_files) -> Path:
    """
    Finds the root directory of the project starting from the current file's directory,
    searching upwards and stopping at the first directory containing any of the marker files.
    Also respects the AIWINDOWSADMIN_DIR environment variable if present.

    Args:
        marker_files (tuple): Filenames or directory names to identify the project root.
    
    Returns:
        Path: Path to the root directory if found, otherwise the directory where the script is located.
    """
    env_dir = os.environ.get('AIWINDOWSADMIN_DIR', '')
    if env_dir:
        env_path = Path(env_dir).resolve()
        if env_path.exists() and (env_path / 'config.json').exists():
            if str(env_path) not in sys.path:
                sys.path.insert(0, str(env_path))
            return env_path
    __root__: Path
    current_path: Path = Path(__file__).resolve().parent
    __root__ = current_path
    found = False
    for parent in [current_path] + list(current_path.parents):
        if any(((parent / marker).exists() for marker in marker_files)):
            __root__ = parent
            found = True
            break
    if not found:
        local_app = os.environ.get('LOCALAPPDATA')
        if local_app:
            candidate = Path(local_app) / 'AI-Assistant'
            if candidate.exists() and any(((candidate / marker).exists() for marker in marker_files)):
                __root__ = candidate
    if str(__root__) not in sys.path:
        sys.path.insert(0, str(__root__))
    return __root__
__root__: Path = set_project_root()
'__root__ (Path): Path to the root directory of the project'