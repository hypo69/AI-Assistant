# -*- coding: utf-8 -*-
"""
=============================================================================
Process Name: Test AI Assistant Workspace Prompt Generator
=============================================================================
Description:
    Модульные тесты для сервиса генерации контекстных вопросов (WorkspacePromptGenerator):
    проверка мультиязычной генерации (ru, en, he, uk), работа на основе реальных
    Git-коммитов, файлов, документов, извлечённых сущностей и корректный fallback.

File: test_workspace_prompt_generator.py
Package: apps/ai_assistant/tests
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-11-10 17:15:00
=============================================================================
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from apps.ai_assistant.core.workspace_prompt_generator import WorkspacePromptGenerator, FALLBACK_PROMPTS


@pytest.mark.asyncio
async def test_fallback_prompts_for_all_languages() -> None:
    """Проверяет fallback-подсказки для всех поддерживаемых языков при пустой рабочей области."""
    mock_wm = MagicMock()
    mock_wm.get_workspace_commits = AsyncMock(return_value=[])
    mock_wm.store.list_documents.return_value = []
    mock_wm.store.list_entities.return_value = []

    generator = WorkspacePromptGenerator(mock_wm)

    for lang in ("ru", "en", "he", "uk"):
        res = await generator.generate_prompts("empty_ws", language=lang, limit=3)
        assert res["status"] == "ok"
        assert res["language"] == lang
        assert res["source"] == "fallback"
        assert len(res["prompts"]) == 3
        assert res["prompts"] == FALLBACK_PROMPTS[lang]


@pytest.mark.asyncio
async def test_prompts_generated_from_commits_and_docs() -> None:
    """Проверяет динамическое формирование вопросов на основе коммитов и документов."""
    mock_wm = MagicMock()
    mock_wm.get_workspace_commits = AsyncMock(return_value=[
        {
            "commit_hash": "a1b2c3d4e5",
            "message": "fix(core): update engine",
            "files": ["engine.py"],
        }
    ])
    mock_wm.store.list_documents.return_value = [
        {"document_id": "doc1", "filename": "architecture.pdf", "title": "Архитектура ядра"},
    ]
    mock_wm.store.list_entities.return_value = [
        {"entity_id": "ent1", "text": "KnowledgeStore", "lemma": "KnowledgeStore"},
    ]

    generator = WorkspacePromptGenerator(mock_wm)

    # Проверка на иврите (he)
    res_he = await generator.generate_prompts("ws_active", language="he", limit=3)
    assert res_he["status"] == "ok"
    assert res_he["source"] == "content"
    prompts_he = res_he["prompts"]
    assert len(prompts_he) == 3

    # Проверяем наличие вопросов по файлу, документу и сущности
    assert any("engine.py" in p["text"] for p in prompts_he)
    assert any("Архитектура ядра" in p["text"] or "architecture.pdf" in p["text"] for p in prompts_he)
    assert any("KnowledgeStore" in p["text"] for p in prompts_he)


@pytest.mark.asyncio
async def test_follow_up_prompts_generation() -> None:
    """Проверяет генерацию уточняющих вопросов после ответа модели."""
    mock_wm = MagicMock()
    generator = WorkspacePromptGenerator(mock_wm)

    sources = [{"document_id": "manual.docx", "quote": "Цитата"}]
    entities = [{"lemma": "TemporalGraph"}]

    follow_ups = generator.generate_follow_up_prompts(sources=sources, entities=entities, language="ru")
    assert len(follow_ups) == 2
    assert "manual.docx" in follow_ups[0]["text"]
    assert "TemporalGraph" in follow_ups[1]["text"]


@pytest.mark.asyncio
async def test_prompts_generated_when_workspace_database_uninitialized(tmp_path) -> None:
    """Проверяет генерацию подсказок при пустой/нераскатанной БД (no such table) без сбоев."""
    import sqlite3
    from apps.ai_assistant.core.knowledge_store import KnowledgeStore

    # Создаём физическую директорию рабочего пространства с пустой БД без таблиц
    ws_meta = tmp_path / "workspaces" / "דוד_משה" / ".workspace"
    ws_meta.mkdir(parents=True, exist_ok=True)
    empty_db = ws_meta / "knowledge_store.db"
    conn = sqlite3.connect(str(empty_db))
    conn.close()

    mock_wm = MagicMock()
    mock_wm.get_workspace_commits = AsyncMock(return_value=[])
    # Реальное хранилище на базе KnowledgeStore
    mock_wm.store = KnowledgeStore(db_path=tmp_path / "global.db", workspaces_dir=tmp_path / "workspaces")

    generator = WorkspacePromptGenerator(mock_wm)
    res = await generator.generate_prompts("דוד_משה", language="he", limit=3)
    assert res["status"] == "ok"
    assert res["source"] == "fallback"
    assert len(res["prompts"]) == 3

