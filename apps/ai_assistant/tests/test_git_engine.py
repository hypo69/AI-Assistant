# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Tests - Git Engine & Temporal Graph
# =============================================================================
# Description:
#   Модульные тесты асинхронного Git-движка и темпорального графа знаний кода.
#
# File: test_git_engine.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-27 23:01:00
# =============================================================================

from __future__ import annotations
"""Тестирование GitHistoryEngine и TemporalCodeGraph."""

from pathlib import Path
import subprocess
import pytest
from apps.ai_assistant.core.git_history_engine import GitHistoryEngine
from apps.ai_assistant.core.temporal_code_graph import TemporalCodeGraph


@pytest.fixture
def temp_git_repo(tmp_path: Path) -> Path:
    """Создаёт временный Git-репозиторий с тестовым файлом и коммитом."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True, capture_output=True)
    dummy_file = repo_dir / "config.json"
    dummy_file.write_text('{"name": "test"}', encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, check=True, capture_output=True)
    return repo_dir


@pytest.mark.asyncio
async def test_git_engine_availability(temp_git_repo: Path) -> None:
    """Проверка доступности репозитория Git и чтения истории."""
    engine = GitHistoryEngine(repo_path=temp_git_repo)
    is_avail = engine.is_git_available()
    assert is_avail is True

    # Получение истории коммитов
    commits = await engine.get_file_history(limit=5)
    assert isinstance(commits, list)
    assert len(commits) > 0
    assert commits[0].commit_hash != ""
    assert commits[0].author != ""


@pytest.mark.asyncio
async def test_git_engine_timeline(temp_git_repo: Path) -> None:
    """Проверка построения контрольных точек таймлайна для файла."""
    engine = GitHistoryEngine(repo_path=temp_git_repo)
    timeline = await engine.get_timeline(file_path="config.json", limit=5)
    assert timeline.file_path == "config.json"
    assert timeline.total_checkpoints >= 0
    assert isinstance(timeline.checkpoints, list)


def test_temporal_code_graph_lifecycle() -> None:
    """Проверка создания, чтения и мягкой инвалидации темпоральной связи."""
    graph = TemporalCodeGraph(db_path=":memory:")

    # 1. Добавление связи
    link = graph.add_link(
        source_id="c1a2b3",
        target_id="wiki_sensor_page",
        relation_type="fixes",
        valid_from="c1a2b3",
        confidence=0.95,
        provenance="test_runner",
    )
    assert link.source_id == "c1a2b3"
    assert link.target_id == "wiki_sensor_page"
    assert link.status == "ACTIVE"

    # 2. Проверка активных связей
    active = graph.get_active_links()
    assert len(active) == 1
    assert active[0].status == "ACTIVE"

    # 3. Инвалидация (SUPERSEDED)
    updated = graph.supersede_link(
        source_id="c1a2b3",
        target_id="wiki_sensor_page",
        invalidating_commit="c4d5e6",
    )
    assert updated is True

    # 4. Проверка после инвалидации
    active_after = graph.get_active_links()
    assert len(active_after) == 0

    all_links = graph.get_all_links()
    assert len(all_links) == 1
    assert all_links[0].status == "SUPERSEDED"
    assert all_links[0].valid_to == "c4d5e6"


def test_temporal_code_graph_file_db(tmp_path: Path) -> None:
    """Проверка инициализации схемы и жизненного цикла графа на реальной файловой БД."""
    db_file = tmp_path / "test_knowledge.db"
    graph = TemporalCodeGraph(db_path=db_file)

    link = graph.add_link(
        source_id="f1e2d3",
        target_id="wiki_architecture_page",
        relation_type="documents",
        valid_from="f1e2d3",
        confidence=1.0,
        provenance="file_test",
    )
    assert link.status == "ACTIVE"
    active = graph.get_active_links()
    assert len(active) == 1
    assert active[0].source_id == "f1e2d3"
