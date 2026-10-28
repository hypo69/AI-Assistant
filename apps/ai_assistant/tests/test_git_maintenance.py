# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant - Test Git Maintenance
# =============================================================================
# Description:
#   Модульные тесты сервиса обслуживания Git и периодического запуска git gc.
#   Проверяет чтение метрик репозитория, обновление расписания и API эндпоинты.
#
# File: test_git_maintenance.py
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-22 14:31:00
# =============================================================================

from __future__ import annotations
"""Тесты обслуживания репозитория и периодического выполнения git gc."""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from apps.ai_assistant.core.git_maintenance import GitMaintenanceService
from apps.ai_assistant.main import app


@pytest.fixture
def maintenance_service(tmp_path):
    """Фикстура изолированного сервиса обслуживания Git."""
    service = GitMaintenanceService(repo_path=tmp_path)
    return service


def test_git_maintenance_parse_objects_info(maintenance_service):
    """Проверяет парсинг вывода git count-objects -vH."""
    sample_output = """count: 120
size: 15.40 MiB
in-pack: 3500
packs: 2
size-pack: 85.10 MiB
prune-packable: 0
garbage: 0
size-garbage: 0 bytes
"""
    with patch.object(maintenance_service, "_run_git", return_value=sample_output):
        info = maintenance_service.get_repo_info()
        assert info["loose_objects"] == 120
        assert info["loose_size"] == "15.40 MiB"
        assert info["pack_size"] == "85.10 MiB"
        assert info["packs_count"] == 2


def test_git_maintenance_config_update(maintenance_service, tmp_path):
    """Проверяет сохранение параметров расписания git gc."""
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text('{"git_maintenance": {"auto_gc_enabled": false}}', encoding="utf-8")
    maintenance_service.config_path = cfg_file

    updated = maintenance_service.update_config(auto_gc_enabled=True, gc_interval_hours=12)
    assert updated["auto_gc_enabled"] is True
    assert updated["gc_interval_hours"] == 12


def test_git_maintenance_run_gc_mocked(maintenance_service):
    """Проверяет запуск команды git gc с корректными параметрами."""
    with patch.object(maintenance_service, "_run_git", return_value="Counting objects: 100%, done.\n") as mock_git:
        res = maintenance_service.run_gc(aggressive=False, prune=True)
        assert res["success"] is True
        assert mock_git.call_count == 2
        first_call_args = mock_git.call_args_list[0][0][0]
        assert "gc" in first_call_args
        assert "--prune=now" in first_call_args


def test_api_git_maintenance_status_and_schedule():
    """Проверяет REST API маршруты статуса и настройки расписания git gc."""
    client = TestClient(app)

    # 1. Получение статуса
    resp = client.get("/api/v1/git/maintenance/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "auto_gc_enabled" in data
    assert "gc_interval_hours" in data

    # 2. Обновление расписания
    post_resp = client.post("/api/v1/git/maintenance/schedule", json={
        "auto_gc_enabled": True,
        "gc_interval_hours": 48,
        "aggressive": False,
        "auto_prune": True
    })
    assert post_resp.status_code == 200
    post_data = post_resp.json()
    assert post_data["auto_gc_enabled"] is True
    assert post_data["gc_interval_hours"] == 48
