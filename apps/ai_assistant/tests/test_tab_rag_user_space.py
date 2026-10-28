# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Tests - User Space RAG Tests
# =============================================================================
# Description:
#   Комплексный тест функционала RAG в пользовательском пространстве:
#   - Хранилище чанков документов KnowledgeStore (document_chunks).
#   - Панель /v1/panel/panel-rag-chunks с привязкой к workspace_id.
#   - 5-этапный поиск /api/v1/query по пользовательской базе знаний.
#   - Раздача статики и шаблонов WebGUI tab_rag.
#
# File: test_tab_rag_user_space.py
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-23 19:25:00
# =============================================================================

from __future__ import annotations
"""Тестирование конвейера RAG пользовательского пространства и вкладки tab_rag."""

import pytest
from httpx import ASGITransport, AsyncClient

from apps.ai_assistant.core.knowledge_store import KnowledgeStore
from apps.ai_assistant.core.workspace_manager import WorkspaceManager
from apps.ai_assistant.main import app


@pytest.mark.asyncio
async def test_knowledge_store_document_chunks_retrieval(tmp_path) -> None:
    """Проверяет сохранение и выборку чанков документов через KnowledgeStore."""
    db_file = tmp_path / "test_rag_ks.db"
    store = KnowledgeStore(db_path=db_file)

    # Сохраняем тестовый документ
    analysis_mock = {
        "language": "ru",
        "analyzer": "RussianMorphoSyntacticAnalyzer",
        "sentences": [
            {"sentence_index": 0, "text": "Мама мыла раму.", "char_start": 0, "char_end": 15},
            {"sentence_index": 1, "text": "Окно стало чистым.", "char_start": 16, "char_end": 34},
        ],
        "entities": [
            {"text": "мама", "normalized": "мама", "lemma": "мама", "entity_type": "entity", "language": "ru"},
            {"text": "раму", "normalized": "рама", "lemma": "рама", "entity_type": "entity", "language": "ru"},
        ],
        "facts": [
            {
                "fact_type": "action",
                "relation": "мыть",
                "language": "ru",
                "subject": {"text": "мама", "lemma": "мама"},
                "predicate": {"text": "мыла", "lemma": "мыть", "verb_form": "мыла"},
                "object": {"text": "раму", "lemma": "рама"},
                "source": {"sentence_index": 0, "char_start": 0, "char_end": 15, "quote": "Мама мыла раму."},
                "confidence": 0.98,
            }
        ],
    }

    store.store_document_and_facts(
        workspace_id="test_ws_rag",
        document_id="mama.txt",
        file_path="mama.txt",
        raw_content="Мама мыла раму.\nОкно стало чистым.",
        commit_hash="abc12345",
        analysis_result=analysis_mock,
    )

    chunks = store.get_document_chunks("test_ws_rag")
    assert len(chunks) == 2
    assert any("Мама мыла раму" in c["text"] for c in chunks)
    assert any("Окно стало чистым" in c["text"] for c in chunks)


@pytest.mark.asyncio
async def test_panel_rag_chunks_api_with_workspace() -> None:
    """Проверяет эндпоинт /v1/panel/panel-rag-chunks для рабочей области."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Проверяем получение чанков для активной или default области
        res = await client.get("/v1/panel/panel-rag-chunks?limit=10")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert data["panel_id"] == "panel-rag-chunks"
        assert isinstance(data["data"], list)

        # Проверяем метаданные SQL
        res_sql = await client.get("/v1/panel/panel-rag-chunks/sql")
        assert res_sql.status_code == 200
        sql_data = res_sql.json()
        assert "document_chunks" in sql_data["sql"] or "rag_chunks" in sql_data["sql"]


@pytest.mark.asyncio
async def test_execute_rag_query_endpoint() -> None:
    """Проверяет 5-этапный эндпоинт POST /api/v1/query по базе знаний."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Импортируем документ в рабочую область
        import_payload = {
            "workspace_id": "ws_rag_query_test",
            "document_id": "test_doc.txt",
            "content": "Мама вымыла раму вчера вечером.",
            "commit_message": "Тестовый документ для RAG",
            "force_reanalyze": True,
        }
        res_import = await client.post("/api/v1/documents/import", json=import_payload)
        assert res_import.status_code == 200

        # 2. Выполняем RAG запрос
        query_payload = {
            "query": "Кем была вымыта рама?",
            "workspace_id": "ws_rag_query_test",
            "top_k": 5,
            "mode": "local_first",
        }
        res_query = await client.post("/api/v1/query", json=query_payload)
        assert res_query.status_code == 200
        q_data = res_query.json()

        assert q_data["status"] == "ok"
        assert q_data["workspace_id"] == "ws_rag_query_test"
        assert "мам" in q_data["answer"].lower()
        assert "sources" in q_data
        assert "suggested_quick_questions" in q_data
        assert isinstance(q_data["suggested_quick_questions"], list)


@pytest.mark.asyncio
async def test_tab_rag_static_assets_serving() -> None:
    """Проверяет доступность разметки и JS-скриптов вкладки tab_rag."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # index.html
        res_html = await client.get("/html/tab_rag/index.html")
        assert res_html.status_code == 200
        assert "rag-workspace-select" in res_html.text
        assert "panel-rag-chunks" in res_html.text

        # main.js
        res_main = await client.get("/html/tab_rag/main.js")
        assert res_main.status_code == 200
        assert "initRagTab" in res_main.text

        # panel.js
        res_panel = await client.get("/html/tab_rag/panel_rag/panel.js")
        assert res_panel.status_code == 200
        assert "renderRagChunksPanel" in res_panel.text
        assert "executeHybridSearch" in res_panel.text
