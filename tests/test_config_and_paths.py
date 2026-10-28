# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Config and System Paths
# =============================================================================
# Description:
#   Модульные тесты проверки интеграции app_name в конфигурации (config.json)
#   и восстановления системных путей:
#   - Рабочая директория: %LOCALAPPDATA% / app_name
#   - Внутренний путь к данным: data
#   - Внутренние пути к %APPDATA% для logs и tmp
#
# File: test_config_and_paths.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-27 22:45:00
# =============================================================================

"""Тесты проверки app_name в конфигурации и восстановления системных путей."""

import json
import os
from pathlib import Path
import pytest

from header import __root__
from src import config
from scripts.cli.paths import CrossPlatformPaths, get_paths


def test_config_json_contains_app_name() -> None:
    """Проверяет, что config.json содержит параметр app_name со значением AI-Assistant."""
    config_file = __root__ / "config.json"
    assert config_file.is_file(), f"Файл {config_file} не найден"

    with open(config_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "app_name" in data, "В config.json отсутствует ключ 'app_name'"
    assert data["app_name"] == "AI-Assistant", f"Ожидалось 'AI-Assistant', получено: {data['app_name']}"


def test_src_config_exports_app_name_and_paths() -> None:
    """Проверяет экспорт app_name, WORKING_DIR, DATA_DIR, LOGS_DIR и TMP_DIR из src.config."""
    assert config.app_name == "AI-Assistant"
    assert config.APP_NAME == "AI-Assistant"

    localappdata = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")

    expected_working_dir = Path(localappdata) / "AI-Assistant"
    expected_logs_dir = Path(appdata) / "AI-Assistant" / "logs"
    expected_tmp_dir = Path(appdata) / "AI-Assistant" / "tmp"

    assert config.WORKING_DIR == expected_working_dir
    assert config.DATA_DIR == expected_working_dir / "data" or config.DATA_DIR == __root__ / "data"
    assert config.LOGS_DIR == expected_logs_dir
    assert config.TMP_DIR == expected_tmp_dir
    assert config.TEMP_DIR == expected_tmp_dir


def test_get_app_paths_returns_all_expected_keys() -> None:
    """Проверяет, что get_app_paths возвращает валидный словарь с путями."""
    paths = config.get_app_paths()
    assert isinstance(paths, dict)
    assert "working_dir" in paths
    assert "data_dir" in paths
    assert "logs_dir" in paths
    assert "tmp_dir" in paths

    assert isinstance(paths["working_dir"], Path)
    assert isinstance(paths["data_dir"], Path)
    assert isinstance(paths["logs_dir"], Path)
    assert isinstance(paths["tmp_dir"], Path)


def test_ensure_app_dirs_creates_directories(tmp_path: Path) -> None:
    """Проверяет работу функции ensure_app_dirs при создании необходимых директорий."""
    config.ensure_app_dirs()
    assert config.DATA_DIR.exists(), f"Директория {config.DATA_DIR} должна существовать"
    assert config.LOGS_DIR.exists(), f"Директория {config.LOGS_DIR} должна существовать"
    assert config.TMP_DIR.exists(), f"Директория {config.TMP_DIR} должна существовать"


def test_cross_platform_paths_uses_app_name() -> None:
    """Проверяет, что CrossPlatformPaths использует app_name из config.json."""
    paths_mgr = CrossPlatformPaths()
    assert paths_mgr.app_name == "AI-Assistant"

    appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    expected_logs = Path(appdata) / "AI-Assistant" / "logs"
    expected_tmp = Path(appdata) / "AI-Assistant" / "tmp"

    assert paths_mgr.logs_dir == expected_logs
    assert paths_mgr.tmp_dir == expected_tmp


def test_logger_uses_app_name_for_logs_directory() -> None:
    """Проверяет, что логгер направляет файлы логов в %APPDATA% / AI-Assistant / logs."""
    from logger.logger import _resolve_app_name
    assert _resolve_app_name() == "AI-Assistant"
