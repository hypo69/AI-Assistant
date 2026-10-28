# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Tests - Chromium Storage Paths
# =============================================================================
# Description:
#   Тестирование корректности разрешения путей хранения пользовательского профиля,
#   дискового кэша и локальных баз данных браузера Chromium / WebView2 / Electron.
#   Гарантирует, что данные хранятся строго в корневом каталоге data/chromium/,
#   а не в подкаталогах приложений.
#
# Usage Examples:
#   CLI:
#     pytest apps/ai_assistant/tests/test_chromium_storage_paths.py -v
#
# File: test_chromium_storage_paths.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 17:20:00
# =============================================================================

from __future__ import annotations
"""Тесты валидации путей хранения кэша и базы данных браузера Chromium."""

from pathlib import Path
import pytest

from header import __root__
from apps.ai_assistant.main import load_app_config, resolve_app_path
from apps.ai_assistant.core.engine_adapter import ElectronEngineAdapter


def test_chromium_config_paths_resolution() -> None:
    """Проверяет, что пути к профилю и кэшу Chromium разрешаются в единый каталог data/chromium."""
    cfg = load_app_config()
    chromium_cfg = cfg.get("chromium", {})

    profile_dir_raw = chromium_cfg.get("profile_dir", "data/chromium/profiles")
    cache_dir_raw = chromium_cfg.get("cache_dir", "data/chromium/cache")

    resolved_profile = resolve_app_path(profile_dir_raw)
    resolved_cache = resolve_app_path(cache_dir_raw)

    expected_profile = (__root__ / "data" / "chromium" / "profiles").resolve()
    expected_cache = (__root__ / "data" / "chromium" / "cache").resolve()

    assert resolved_profile == expected_profile, (
        f"Путь профиля Chromium должен быть {expected_profile}, получено: {resolved_profile}"
    )
    assert resolved_cache == expected_cache, (
        f"Путь дискового кэша Chromium должен быть {expected_cache}, получено: {resolved_cache}"
    )


def test_electron_adapter_receives_chromium_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Проверяет, что адаптер Electron передает аргументы и переменные окружения для путей Chromium."""
    adapter = ElectronEngineAdapter()
    captured_env: dict = {}
    captured_cmd: list = []

    test_profile = tmp_path / "data" / "chromium" / "profiles"
    test_cache = tmp_path / "data" / "chromium" / "cache"

    def mock_popen(cmd, cwd=None, env=None, stdout=None, stderr=None):
        nonlocal captured_cmd, captured_env
        captured_cmd = cmd
        captured_env = env or {}
        class MockProcess:
            pid = 99999
            def poll(self):
                return None
        return MockProcess()

    monkeypatch.setattr("subprocess.Popen", mock_popen)
    monkeypatch.setattr(adapter, "_find_electron_binary", lambda: "mock_electron.exe")

    res = adapter.launch_shell(
        url="http://127.0.0.1:8002",
        profile_path=test_profile,
        cache_path=test_cache,
    )

    assert res.get("status") == "launched"
    assert captured_env.get("AI_ASSISTANT_CHROMIUM_PROFILE") == str(test_profile.resolve())
    assert captured_env.get("AI_ASSISTANT_CHROMIUM_CACHE") == str(test_cache.resolve())

    # Проверка аргументов командной строки Electron
    cmd_str = " ".join(captured_cmd)
    assert f"--user-data-dir={test_profile.resolve()}" in cmd_str
    assert f"--disk-cache-dir={test_cache.resolve()}" in cmd_str


def test_electron_adapter_default_fallback_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет, что при отсутствии явных путей адаптер автоматически выбирает корневые data/chromium/."""
    adapter = ElectronEngineAdapter()
    captured_env: dict = {}
    captured_cmd: list = []

    expected_profile = (__root__ / "data" / "chromium" / "profiles").resolve()
    expected_cache = (__root__ / "data" / "chromium" / "cache").resolve()

    def mock_popen(cmd, cwd=None, env=None, stdout=None, stderr=None):
        nonlocal captured_cmd, captured_env
        captured_cmd = cmd
        captured_env = env or {}

        class MockProcess:
            pid = 88888

            def poll(self):
                return None

        return MockProcess()

    monkeypatch.setattr("subprocess.Popen", mock_popen)
    monkeypatch.setattr(adapter, "_find_electron_binary", lambda: "mock_electron.exe")

    res = adapter.launch_shell(url="http://127.0.0.1:8002")

    assert res.get("status") == "launched"
    assert captured_env.get("AI_ASSISTANT_CHROMIUM_PROFILE") == str(expected_profile)
    assert captured_env.get("AI_ASSISTANT_CHROMIUM_CACHE") == str(expected_cache)

    cmd_str = " ".join(captured_cmd)
    assert f"--user-data-dir={expected_profile}" in cmd_str
    assert f"--disk-cache-dir={expected_cache}" in cmd_str
