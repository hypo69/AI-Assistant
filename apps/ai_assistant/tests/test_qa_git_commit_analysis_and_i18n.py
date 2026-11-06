# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-assistant Apps AI_Assistant Tests - QA Git Commit Analysis & i18n
# =============================================================================
# Description:
#   Модульные и интеграционные тесты глубокого анализа Git-коммитов через QAEngine,
#   проверки парсинга интента git_commit_query и строгой локализации системных
#   промптов (RU, HE, EN).
#
# Usage Examples:
#   pytest apps/ai_assistant/tests/test_qa_git_commit_analysis_and_i18n.py -v
#
# File: tests/test_qa_git_commit_analysis_and_i18n.py
# Project: ai-assistant
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-03 17:00:00
# =============================================================================

from __future__ import annotations
"""Тесты распознавания коммитов Git и локализации промптов в QAEngine."""

import pytest
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

from apps.ai_assistant.core.nlp.intent_parser import QuestionIntentParser
from apps.ai_assistant.core.qa_prompts import get_qa_prompts, get_insufficient_data_message
from apps.ai_assistant.core.qa_git_resolver import QaGitResolver
from apps.ai_assistant.core.qa_engine import KnowledgeQAEngine
from apps.ai_assistant.core.workspace_manager import WorkspaceManager


def test_intent_parser_recognizes_hebrew_and_russian_git_queries():
    """Проверяет распознавание хэша коммита и намерения git_commit_query."""
    q_he = "אילו שינויים נרשמו ב-commit 147b0eb?"
    parsed_he = QuestionIntentParser.parse_question(q_he)
    assert parsed_he["language"] == "he"
    assert parsed_he["intent"] == "git_commit_query"
    assert parsed_he["commit_hash"] == "147b0eb"
    assert parsed_he["is_git_query"] is True

    q_ru = "Какие файлы были изменены в коммите a1b2c3d?"
    parsed_ru = QuestionIntentParser.parse_question(q_ru)
    assert parsed_ru["language"] == "ru"
    assert parsed_ru["intent"] == "git_commit_query"
    assert parsed_ru["commit_hash"] == "a1b2c3d"
    assert parsed_ru["is_git_query"] is True


def test_qa_prompts_i18n_hebrew_isolation():
    """Проверяет отсутствие русского языка в системной инструкции и промпте для иврита."""
    sys_p, user_p = get_qa_prompts(language="he", context="diff details", question="אילו שינויים בוצעו?")
    # Проверяем наличие ключевых ивритских маркеров
    assert "מודול רב-לשוני מדויק" in sys_p
    assert "הקשר מסמכים ונתונים:" in user_p
    assert "שאלה (he):" in user_p
    assert "תשובה מדויקת ומפורטת:" in user_p

    # Проверяем полное отсутствие русских слов в ивритском промпте
    assert "Контекст документов:" not in user_p
    assert "Вопрос" not in user_p
    assert "Краткий точный ответ:" not in user_p
    assert "Ты — точный" not in sys_p


@pytest.mark.asyncio
async def test_qa_git_resolver_extracts_commit_details(tmp_path: Path):
    """Проверяет извлечение реальных данных коммита через QaGitResolver."""
    repo_dir = tmp_path / "repo_ws"
    repo_dir.mkdir()

    # Инициализация временного Git-репозитория
    subprocess.run(["git", "init"], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "TestUser"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "config", "user.email", "test@test.local"], cwd=str(repo_dir), check=True)

    f1 = repo_dir / "file.txt"
    f1.write_text("Hello world", encoding="utf-8")
    subprocess.run(["git", "add", "file.txt"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "commit", "-m", "Initial test commit"], cwd=str(repo_dir), check=True)

    c_hash = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(repo_dir), text=True).strip()
    short_hash = c_hash[:7]

    mock_wm = MagicMock()
    mock_wm.registry.get_workspace.return_value = {"path": str(repo_dir)}

    parsed_q = {
        "is_git_query": True,
        "commit_hash": short_hash,
        "intent": "git_commit_query",
    }

    git_ctx, sources, fallback = await QaGitResolver.resolve(mock_wm, "test_ws", parsed_q, language="he")
    assert git_ctx is not None
    assert "=== GIT COMMIT DETAILS ===" in git_ctx
    assert "Initial test commit" in git_ctx
    assert "file.txt" in git_ctx
    assert len(sources) == 1
    assert sources[0]["commit_hash"] == c_hash
    assert short_hash in fallback
    assert "שונו הקבצים: file.txt" in fallback
