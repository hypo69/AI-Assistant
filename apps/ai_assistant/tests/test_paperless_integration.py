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
# Updated: 2026-11-11 19:44:00
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


def test_is_supported_file_extensions() -> None:
    """Проверяет классификацию расширений для Paperless."""
    assert PaperlessConnector.is_supported_file("document.pdf") is True
    assert PaperlessConnector.is_supported_file("scan.PNG") is True
    assert PaperlessConnector.is_supported_file("invoice.docx") is True
    assert PaperlessConnector.is_supported_file("data.txt") is True
    assert PaperlessConnector.is_supported_file("audio.mp3") is False
    assert PaperlessConnector.is_supported_file("script.py") is False


def test_workspace_tag_name_is_workspace_name() -> None:
    """Обязательный тег для Paperless — читаемое имя рабочей области (например, 'דוד משה')."""
    c = PaperlessConnector("http://pl:8000/", "tok", 10, 1.0, 2.0, 3.0, 0, "")
    tag = c.workspace_tag_name("דוד_משה", workspace_name="דוד משה")
    assert tag == "דוד משה"


def test_wait_for_task_success(monkeypatch) -> None:
    """Опрос задачи возвращает ID созданного документа при статусе success."""
    c = _connector()
    monkeypatch.setattr(
        c, "get_task_status",
        MagicMock(return_value={"status": "success", "related_document_ids": [42]}),
    )
    doc_id = c.wait_for_task("task-123", timeout=2.0, poll_interval=0.01)
    assert doc_id == 42


def test_wait_for_task_failure_raises_error(monkeypatch) -> None:
    """Сбойная задача в Paperless выбрасывает PaperlessError."""
    c = _connector()
    monkeypatch.setattr(
        c, "get_task_status",
        MagicMock(return_value={"status": "failure", "result": "OCR error"}),
    )
    with pytest.raises(PaperlessError, match="OCR error"):
        c.wait_for_task("task-123", timeout=2.0, poll_interval=0.01)


def test_ingest_file_workflow(monkeypatch, tmp_path) -> None:
    """Полный цикл импорта документа через PaperlessConnector.ingest_file."""
    c = _connector()
    test_file = tmp_path / "contract.pdf"
    test_file.write_bytes(b"%PDF-1.4 fake")

    monkeypatch.setattr(c, "ensure_workspace_tag", MagicMock(return_value=101))
    monkeypatch.setattr(c, "upload_document", MagicMock(return_value="uuid-abc"))
    monkeypatch.setattr(c, "wait_for_task", MagicMock(return_value=77))
    monkeypatch.setattr(c, "get_document_content", MagicMock(return_value="Распознанный текст договора"))
    monkeypatch.setattr(c, "get_document_metadata", MagicMock(return_value={"id": 77, "title": "contract.pdf"}))

    res = c.ingest_file(test_file, workspace_id="ws_test", timeout=5.0)
    assert res is not None
    assert res["paperless_id"] == 77
    assert res["content"] == "Распознанный текст договора"
    assert res["workspace_tag_id"] == 101


@pytest.mark.asyncio
async def test_process_file_with_paperless_ingest(monkeypatch, tmp_path) -> None:
    """WorkspaceItemsTracker направляет релевантный файл в Paperless и сохраняет paperless_id в базе знаний."""
    from apps.ai_assistant.core.workspace_manager import WorkspaceManager
    from apps.ai_assistant.core.workspace_items_tracker import WorkspaceItemsTracker

    wm = WorkspaceManager(base_dir=tmp_path / "data_ai", workspaces_dir=tmp_path / "workspaces")
    ws_id = "test_pl_ws"
    wm.create_or_select_workspace(ws_id, name="Тест Paperless")

    fake_conn = _connector()
    monkeypatch.setattr(PaperlessConnector, "from_config", MagicMock(return_value=fake_conn))
    monkeypatch.setattr(fake_conn, "ping", MagicMock(return_value=True))
    monkeypatch.setattr(
        fake_conn, "ingest_file",
        MagicMock(return_value={"paperless_id": 88, "content": "Текст из Paperless OCR", "metadata": {}}),
    )

    tracker = WorkspaceItemsTracker(wm)
    ws, ws_path = tracker._resolve_workspace_path(ws_id)
    doc_path = ws_path / "assets" / "scan.pdf"
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_bytes(b"%PDF-1.4 test")

    file_info = await tracker._process_and_commit_file(
        workspace_id=ws_id,
        ws_path=ws_path,
        dest_file=doc_path,
        doc_id="assets/scan.pdf",
    )

    assert file_info["paperless_id"] == 88
    # Проверяем, что в SQLite документ зафиксирован с paperless_id и без дублирования текста
    docs = wm.store.list_documents(ws_id)
    assert len(docs) == 1
    assert docs[0]["paperless_id"] == 88


def test_ping_returns_false_without_connect_retries_or_error_log(monkeypatch) -> None:
    """Проверка ping() не повторяет connect-ошибки и не спамит ERROR в лог."""
    import requests
    from apps.ai_assistant.core import paperless_connector as pc

    c = PaperlessConnector("http://127.0.0.1:8000", "tok", 10, 1.0, 2.0, 3.0, 3, "ws-")
    adapter = c._session.get_adapter("http://127.0.0.1:8000")
    assert adapter.max_retries.connect == 0

    mock_req = MagicMock(side_effect=requests.ConnectionError("refused"))
    mock_err = MagicMock()
    monkeypatch.setattr(c._session, "request", mock_req)
    monkeypatch.setattr(pc.logger, "error", mock_err)

    assert c.ping() is False
    assert mock_req.call_count == 1
    mock_err.assert_not_called()


def test_is_docker_running_checks_daemon(monkeypatch) -> None:
    """is_docker_running возвращает False при остановленном Docker daemon или ошибке."""
    import subprocess
    from apps.ai_assistant.core import paperless_bootstrap as pb

    monkeypatch.setattr(pb, "find_docker", lambda: None)
    assert pb.is_docker_running() is False

    monkeypatch.setattr(pb, "find_docker", lambda: r"C:\docker.exe")
    monkeypatch.setattr(pb.subprocess, "run", lambda *a, **kw: MagicMock(returncode=1))
    assert pb.is_docker_running() is False

    def _timeout(*a, **kw):
        raise subprocess.TimeoutExpired(cmd="docker info", timeout=1)

    monkeypatch.setattr(pb.subprocess, "run", _timeout)
    assert pb.is_docker_running() is False

    monkeypatch.setattr(pb.subprocess, "run", lambda *a, **kw: MagicMock(returncode=0))
    assert pb.is_docker_running() is True


def test_ensure_paperless_running_skips_wait_when_docker_stopped(monkeypatch) -> None:
    """При выключенном Docker daemon ensure_paperless_running не открывает окно и не ждёт таймаут."""
    from apps.ai_assistant.core import paperless_bootstrap as pb
    from apps.ai_assistant.core.paperless_connector import PaperlessConnector

    fake_conn = _connector()
    monkeypatch.setattr(fake_conn, "ping", MagicMock(return_value=False))
    monkeypatch.setattr(PaperlessConnector, "from_config", MagicMock(return_value=fake_conn))
    monkeypatch.setattr(pb, "load_paperless_config", lambda: {"autostart": True, "startup_timeout_sec": 180, "startup_poll_sec": 5})
    monkeypatch.setattr(pb, "is_docker_running", lambda: False)
    launch_mock = MagicMock()
    monkeypatch.setattr(pb, "launch_in_new_terminal", launch_mock)
    monkeypatch.setenv("AI_ASSISTANT_PAPERLESS_WINDOW_LAUNCHED", "1")

    assert pb.ensure_paperless_running() is False
    launch_mock.assert_not_called()


def test_ensure_paperless_running_async_runs_in_daemon_thread(monkeypatch) -> None:
    """ensure_paperless_running_async запускает bootstrap в фоновом потоке без блокировки."""
    import threading
    from apps.ai_assistant.core import paperless_bootstrap as pb

    called = threading.Event()

    def _fake_ensure() -> bool:
        called.set()
        return False

    monkeypatch.setattr(pb, "ensure_paperless_running", _fake_ensure)
    t = pb.ensure_paperless_running_async()
    assert t.daemon is True
    assert called.wait(timeout=2.0)
    t.join(timeout=2.0)

