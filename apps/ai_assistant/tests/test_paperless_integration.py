# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Tests - Paperless Integration
# =============================================================================
# Description:
#   Тесты PaperlessConnector (на моках HTTP), единой БД рабочей области
#   и отказа от дублирования текста при наличии paperless_id.
#
# File: test_paperless_integration.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 16:15:00
# =============================================================================

from __future__ import annotations
"""Тесты интеграции Paperless-ngx."""

import gc
from unittest.mock import MagicMock

import pytest

from apps.ai_assistant.core.knowledge_store import KnowledgeStore
from apps.ai_assistant.core.paperless_connector import PaperlessConnector, PaperlessError
from apps.ai_assistant.core.temporal_code_graph import TemporalCodeGraph


def _connector() -> PaperlessConnector:
    """Создаёт клиент с тестовыми параметрами."""
    return PaperlessConnector("http://pl:8000/", "tok", 10, 1.0, 2.0, 3.0, 0, "ws-")


def _response(payload) -> MagicMock:
    """Фабрика мок-ответа requests."""
    resp = MagicMock()
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    return resp


def test_connector_requires_token() -> None:
    """Без токена клиент не создаётся (Fail-Fast)."""
    with pytest.raises(PaperlessError):
        PaperlessConnector("http://pl:8000", "", 10, 1, 1, 1, 0, "ws-")


def test_iter_documents_paginates(monkeypatch) -> None:
    """Пагинация следует полю next и не теряет документы."""
    c = _connector()
    pages = [
        _response({"results": [{"id": 1}], "next": "http://pl:8000/api/documents/?page=2"}),
        _response({"results": [{"id": 2}], "next": None}),
    ]
    monkeypatch.setattr(c._session, "request", MagicMock(side_effect=pages))
    assert [d["id"] for d in c.iter_documents(tag_name="ws-a")] == [1, 2]


def test_ensure_tag_creates_when_missing(monkeypatch) -> None:
    """Отсутствующий тег создаётся через POST."""
    c = _connector()
    monkeypatch.setattr(
        c._session, "request",
        MagicMock(side_effect=[_response({"results": []}), _response({"id": 7})]),
    )
    assert c.ensure_workspace_tag("a") == 7


def test_graph_and_store_share_one_db(tmp_path) -> None:
    """Граф и хранилище знаний области используют один файл БД."""
    store = KnowledgeStore(db_path=tmp_path / "x.db", workspaces_dir=tmp_path)
    graph = TemporalCodeGraph(db_path=tmp_path / "g.db", workspaces_dir=tmp_path)
    assert store._get_target_db_path("ws") == graph._get_target_db_path("ws")


def test_legacy_graph_db_is_absorbed(tmp_path) -> None:
    """Устаревший temporal_graph.db переносится в единую БД и удаляется."""
    meta = tmp_path / "ws" / ".workspace"
    meta.mkdir(parents=True)
    legacy_graph = TemporalCodeGraph(db_path=meta / "temporal_graph.db")
    legacy_graph.add_link("a", "b", "REL", "2026-01-01T00:00:00+00:00")
    del legacy_graph
    gc.collect()
    graph = TemporalCodeGraph(db_path=tmp_path / "g.db", workspaces_dir=tmp_path)
    conn = graph._get_connection("ws")
    try:
        assert conn.execute("SELECT COUNT(*) FROM temporal_evidence_links").fetchone()[0] == 1
    finally:
        graph._close_conn(conn)
    assert not (meta / "temporal_graph.db").exists()


def test_paperless_document_text_not_duplicated() -> None:
    """При paperless_id полный текст версии не сохраняется в БД."""
    store = KnowledgeStore()
    analysis = {"language": "ru", "sentences": [], "entities": [], "facts": []}
    store.store_document_and_facts("ws", "paperless/5", "paperless://5", "очень длинный текст", "", analysis, paperless_id=5)
    conn = store._get_conn("ws")
    row = conn.execute("SELECT raw_content FROM document_versions").fetchone()
    doc = conn.execute("SELECT paperless_id FROM documents").fetchone()
    assert row[0] == "" and doc[0] == 5


def test_chunk_text_not_stored_and_hydrated_from_paperless() -> None:
    """Текст чанков не хранится в БД и восстанавливается из Paperless по смещениям."""
    text = "Мама мыла раму."
    analysis = {
        "language": "ru",
        "sentences": [{"sentence_index": 0, "text": text, "char_start": 0, "char_end": len(text)}],
        "entities": [],
        "facts": [],
    }
    store = KnowledgeStore(text_resolver=lambda pid: text if pid == 9 else "")
    store.store_document_and_facts("ws", "paperless/9", "paperless://9", text, "", analysis, paperless_id=9)
    raw = store._get_conn("ws").execute("SELECT text FROM document_chunks").fetchone()[0]
    assert raw == ""
    assert store.get_document_chunks("ws")[0]["text"] == text
    assert store.list_documents("ws")[0]["content"] == text


def test_chunk_hydration_rejects_changed_paperless_text() -> None:
    """При изменении текста в Paperless устаревшие смещения не подставляют чужой фрагмент."""
    text = "Мама мыла раму."
    analysis = {
        "language": "ru",
        "sentences": [{"sentence_index": 0, "text": text, "char_start": 0, "char_end": len(text)}],
        "entities": [],
        "facts": [],
    }
    store = KnowledgeStore(text_resolver=lambda pid: "Совсем другой текст!")
    store.store_document_and_facts("ws", "paperless/9", "paperless://9", text, "", analysis, paperless_id=9)
    assert store.get_document_chunks("ws")[0]["text"] == ""


def test_launch_in_new_terminal_opens_separate_window(monkeypatch) -> None:
    """Запуск Paperless открывает отдельное окно терминала с compose up и логами."""
    from apps.ai_assistant.core import paperless_bootstrap as pb

    popen = MagicMock()
    monkeypatch.setattr(pb, "find_docker", lambda: r"C:\docker.exe")
    monkeypatch.setattr(pb.subprocess, "Popen", popen)
    assert pb.launch_in_new_terminal() is True
    cmd = popen.call_args[0][0]
    assert "compose up -d" in cmd[-1] and "logs -f" in cmd[-1]
    assert "-w" in cmd or popen.call_args[1].get("creationflags")


def test_launch_in_new_terminal_fails_without_docker(monkeypatch) -> None:
    """Без Docker окно не открывается."""
    from apps.ai_assistant.core import paperless_bootstrap as pb

    monkeypatch.setattr(pb, "find_docker", lambda: None)
    assert pb.launch_in_new_terminal() is False
