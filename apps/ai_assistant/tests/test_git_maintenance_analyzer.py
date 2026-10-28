# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant - Test Git Maintenance Analyzer
# =============================================================================
# Description:
#   Модульные тесты интеллектуального анализатора GitMaintenanceAnalyzer:
#   проверка пороговых правил (Норма, Наблюдение, Обслуживание),
#   формирование обоснования и REST API эндпоинты диагностики.
#
# File: test_git_maintenance_analyzer.py
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-22 14:39:00
# =============================================================================

from __future__ import annotations
"""Тесты логики диагностики и принятия решений GitMaintenanceAnalyzer."""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from apps.ai_assistant.core.git_maintenance_analyzer import (
    GitMaintenanceAnalyzer,
    MaintenanceVerdict,
    RepoMetrics,
)
from apps.ai_assistant.main import app


@pytest.fixture
def analyzer(tmp_path):
    """Изолированный экземпляр анализатора с временным путем истории."""
    history_file = tmp_path / "git_diagnostics_history.json"
    return GitMaintenanceAnalyzer(repo_path=tmp_path, history_path=history_file)


def test_analyzer_verdict_normal(analyzer):
    """Проверяет вердикт НОРМА при небольшом количестве loose-объектов."""
    metrics = RepoMetrics(
        loose_count=500,
        loose_size_kib=15000,
        in_pack_count=4000,
        packs_count=3,
        pack_size_kib=85000,
        prune_packable=0,
        garbage_count=0,
        garbage_size_kib=0,
        dangling_count=5,
        connectivity_ok=True,
    )
    result = analyzer.evaluate(metrics)
    assert result.verdict == MaintenanceVerdict.NORMAL
    assert result.action_type == "none"
    assert "Ничего не делать" in result.recommendation


def test_analyzer_verdict_observation(analyzer):
    """Проверяет вердикт НАБЛЮДЕНИЕ при умеренном накоплении объектов или мусора."""
    metrics = RepoMetrics(
        loose_count=3200,
        loose_size_kib=35000,
        in_pack_count=4000,
        packs_count=3,
        pack_size_kib=85000,
        prune_packable=60,
        garbage_count=2,
        garbage_size_kib=10,
        dangling_count=100,
        connectivity_ok=True,
    )
    result = analyzer.evaluate(metrics)
    assert result.verdict == MaintenanceVerdict.OBSERVATION
    assert result.action_type == "observe"
    assert "Повторить измерение" in result.recommendation


def test_analyzer_verdict_maintenance_required(analyzer):
    """Проверяет вердикт ОБСЛУЖИВАНИЕ при превышении порога loose-объектов."""
    metrics = RepoMetrics(
        loose_count=7200,
        loose_size_kib=80000,
        in_pack_count=5000,
        packs_count=4,
        pack_size_kib=100000,
        prune_packable=0,
        garbage_count=0,
        garbage_size_kib=0,
        dangling_count=20,
        connectivity_ok=True,
    )
    result = analyzer.evaluate(metrics)
    assert result.verdict == MaintenanceVerdict.MAINTENANCE_REQUIRED
    assert result.action_type == "gc_auto"
    assert "git gc --auto" in result.recommendation


def test_api_diagnosis_and_gc_auto():
    """Проверяет REST API маршруты /diagnosis и /gc-auto."""
    client = TestClient(app)

    # 1. Диагностика
    resp = client.get("/api/v1/git/maintenance/diagnosis")
    assert resp.status_code == 200
    data = resp.json()
    assert "verdict" in data
    assert "verdict_title" in data
    assert "recommendation" in data
    assert "metrics" in data
    assert "repo_name" in data
    assert "repo_path" in data
    assert "current_branch" in data
    assert "current_commit" in data
    assert "available_repos" in data

    # 1.1 Репозитории
    repos_resp = client.get("/api/v1/git/maintenance/repositories")
    assert repos_resp.status_code == 200
    repos = repos_resp.json()
    assert len(repos) >= 1
    assert "name" in repos[0]
    assert "path" in repos[0]

    # 2. История
    hist_resp = client.get("/api/v1/git/maintenance/history")
    assert hist_resp.status_code == 200
    assert isinstance(hist_resp.json(), list)

    # 3. Штатный запуск gc-auto (с моком)
    with patch.object(client.app, "state", create=True):
        auto_resp = client.post("/api/v1/git/maintenance/gc-auto")
        assert auto_resp.status_code == 200
        assert auto_resp.json()["command"] == "git gc --auto"
