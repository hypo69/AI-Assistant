# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Tests - Coreference & Optimizations
# =============================================================================
# Description:
#   Тестовый набор для проверки новых возможностей и архитектурных оптимизаций:
#   - Мультиязычное разрешение кореференции местоимений (RU / HE / EN);
#   - Гибридный векторно-лексический поиск RagFaissEngine (FAISS TextRAG + TF);
#   - Инкрементальное обнаружение изменений во внешних источниках (mtime/size);
#   - Потоковый SSE-эндпоинт вопросов и ответов (/api/v1/ask/stream);
#   - Безопасность SQL-запросов в универсальном роутере панелей (/v1/panel).
#
# File: test_optimizations_and_coreference.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-26 00:10:00
# =============================================================================

from __future__ import annotations
"""Тестирование разрешения кореференции, гибридного FAISS RAG, SSE-стриминга и мониторинга источников."""

import json
from pathlib import Path
import time
import pytest
from httpx import ASGITransport, AsyncClient

from apps.ai_assistant.api.schemas import CommitSummary, DiffHunkItem
from apps.ai_assistant.core.knowledge_store import KnowledgeStore
from apps.ai_assistant.core.nlp_analyzers import AnalyzerRegistry
from apps.ai_assistant.core.qa_engine import KnowledgeQAEngine
from apps.ai_assistant.core.rag_faiss_engine import RagFaissEngine
from apps.ai_assistant.core.temporal_code_graph import TemporalCodeGraph
from apps.ai_assistant.core.workspace_manager import WorkspaceManager
from apps.ai_assistant.main import app


def test_multilingual_coreference_resolution_ru_he_en() -> None:
    """Проверяет разрешение местоимений (кореференции) для русского, иврита и английского языков."""
    registry = AnalyzerRegistry()

    # 1. Русский язык: действие ("Она") и принадлежность ("У него")
    ru_text = "Мама мыла раму. Она открыла окно. У Давида была ферма. У него был дом."
    ru_res = registry.analyze_text(ru_text, document_id="coref_ru.txt", language="ru")
    ru_facts = ru_res["facts"]
    assert len(ru_facts) == 4
    # Второе предложение ("Она открыла окно") должно разрешить субъект в "мама"
    assert ru_facts[1]["subject"]["lemma"] == "мама"
    assert ru_facts[1]["relation"] == "открыть"
    # Четвёртое предложение ("У него был дом") должно разрешить владельца в "давид"
    assert ru_facts[3]["owner"]["lemma"] == "давид"
    assert ru_facts[3]["possessed_entity"]["lemma"] == "дом"

    # 2. Иврит: принадлежность -> действие с местоимением "הוא" и действие -> принадлежность с "לה"
    he_text = "לדוד משה הייתה חווה. הוא בנה בית."
    he_res = registry.analyze_text(he_text, document_id="coref_he.txt", language="he")
    he_facts = he_res["facts"]
    assert len(he_facts) == 2
    assert he_facts[0]["owner"]["text"] == "דוד משה"
    assert he_facts[1]["subject"]["text"] == "דוד משה"
    assert he_facts[1]["relation"] == "בנה"

    # 3. Английский язык: действие -> принадлежность с местоимением "She"
    en_text = "Alice built a server. She owns a database."
    en_res = registry.analyze_text(en_text, document_id="coref_en.txt", language="en")
    en_facts = en_res["facts"]
    assert len(en_facts) == 2
    assert en_facts[1]["owner"]["lemma"] == "alice"
    assert en_facts[1]["possessed_entity"]["lemma"] == "database"


def test_rag_faiss_engine_hybrid_vector_indexing(tmp_path: Path) -> None:
    """Проверяет гибридную индексацию (FAISS TextRAG + лексический индекс) в RagFaissEngine."""
    engine = RagFaissEngine(index_dir=tmp_path / "rag_hybrid")
    commit = CommitSummary(
        commit_hash="a1b2c3d4e5f60123456789abcdef0123456789ab",
        author="Developer",
        timestamp="2026-10-25T20:00:00Z",
        message="Оптимизация векторного индекса FAISS и SQLite WAL",
    )
    hunks = [
        DiffHunkItem(
            old_start=10,
            old_lines=2,
            new_start=10,
            new_lines=5,
            hunk_text="+ conn.execute('PRAGMA journal_mode=WAL;')\n+ conn.execute('PRAGMA synchronous=NORMAL;')",
        )
    ]

    added = engine.index_commit(commit, hunks, file_path="core/knowledge_store.py")
    assert added == 2
    assert engine.faiss_rag.count() == 2

    hits = engine.search("оптимизация SQLite WAL", top_k=3)
    assert len(hits) >= 1
    assert any(h["commit_hash"] == commit.commit_hash for h in hits)


@pytest.mark.asyncio
async def test_incremental_linked_sources_change_detection(tmp_path: Path) -> None:
    """Проверяет инкрементальное обнаружение изменений во внешних связанных источниках по mtime и размеру."""
    base_dir = tmp_path / "ws_data"
    wm = WorkspaceManager(
        base_dir=base_dir,
        workspaces_dir=base_dir / "workspaces",
        knowledge_store=KnowledgeStore(db_path=base_dir / "ks.db"),
        temporal_graph=TemporalCodeGraph(db_path=base_dir / "tg.db"),
    )

    ext_dir = tmp_path / "external_docs"
    ext_dir.mkdir(parents=True, exist_ok=True)
    doc_file = ext_dir / "notes.txt"
    doc_file.write_text("Мама мыла раму.", encoding="utf-8")

    ws_id = "ws_watch_test"
    wm.create_or_select_workspace(ws_id, name="Watch Workspace")
    wm.link_source(ws_id, str(ext_dir), name="External Docs")

    # До первой синхронизации файл определяется как новый
    pre_changes = wm.detect_changed_linked_sources(ws_id)
    assert pre_changes["has_changes"] is True
    assert "notes.txt" in pre_changes["new_files"]

    # После синхронизации изменений нет
    await wm.sync_linked_sources(ws_id)
    post_changes = wm.detect_changed_linked_sources(ws_id)
    assert post_changes["has_changes"] is False
    assert "notes.txt" in post_changes["unchanged_files"]

    # Модифицируем файл на диске
    time.sleep(0.02)
    doc_file.write_text("Мама мыла раму. Она открыла окно.", encoding="utf-8")
    mod_changes = wm.detect_changed_linked_sources(ws_id)
    assert mod_changes["has_changes"] is True
    assert "notes.txt" in mod_changes["changed_files"]


@pytest.mark.asyncio
async def test_ask_stream_sse_and_sql_injection_guard() -> None:
    """Проверяет потоковый SSE-эндпоинт /api/v1/ask/stream и защиту от SQL-инъекции в /v1/panel."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Импортируем документ с местоимением и проверяем SSE-стриминг ответа
        await client.post(
            "/api/v1/documents/import",
            json={
                "workspace_id": "ws_stream_test",
                "document_id": "story.txt",
                "content": "Мама вымыла раму. Она открыла окно.",
                "force_reanalyze": True,
            },
        )

        res_stream = await client.post(
            "/api/v1/ask/stream",
            json={
                "question": "Кто открыл окно?",
                "workspace_id": "ws_stream_test",
                "mode": "local_only",
            },
        )
        assert res_stream.status_code == 200
        assert "text/event-stream" in res_stream.headers.get("content-type", "")

        events = [
            json.loads(line[6:])
            for line in res_stream.text.splitlines()
            if line.startswith("data: ")
        ]
        assert any(e.get("type") == "stage" for e in events)
        assert any(e.get("type") == "token" for e in events)
        done_events = [e for e in events if e.get("type") == "done"]
        assert len(done_events) == 1
        assert "мама" in done_events[0]["result"]["answer"].lower()

        # 2. Проверяем эндпоинт /api/v1/workspaces/{id}/sources/changes
        res_changes = await client.get("/api/v1/workspaces/ws_stream_test/sources/changes")
        assert res_changes.status_code == 200
        assert "has_changes" in res_changes.json()

        # 3. Проверяем защиту от SQL-инъекции в произвольном идентификаторе панели
        res_sqli = await client.get("/v1/panel/users;DROP TABLE facts;--")
        assert res_sqli.status_code == 200
        assert res_sqli.json()["data"] == []


@pytest.mark.asyncio
async def test_default_in_place_git_tracking_without_copying(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет, что без явного указания на копирование файлы отслеживаются Git на диске без копирования."""
    import os
    import tempfile
    from apps.ai_assistant.main import app
    from apps.ai_assistant.api.routers import router_knowledge

    with tempfile.TemporaryDirectory() as tmp:
        base_dir = Path(tmp)
        wm = WorkspaceManager(
            base_dir=base_dir,
            workspaces_dir=base_dir / "workspaces",
        )
        monkeypatch.setattr(router_knowledge, "_workspace_manager", wm)

        ws = wm.create_or_select_workspace("ws_in_place_default", name="InPlace Default")
        ws_path = Path(ws["path"])

        ext_dir = base_dir / "external_source"
        ext_dir.mkdir(parents=True)
        ext_file = ext_dir / "external_notes.txt"
        ext_file.write_text("Внешний документ остаётся на своём месте.", encoding="utf-8")

        copied_src = ext_dir / "copied_notes.txt"
        copied_src.write_text("Этот документ явно скопирован в рабочую область.", encoding="utf-8")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Вызов без copy_to_workspace -> по умолчанию False (не копирует в ws_path, но отслеживает в Git)
            res_default = await client.post(
                "/api/v1/workspaces/ws_in_place_default/items",
                json={"items": [str(ext_file)]},
            )
            assert res_default.status_code == 200
            assert not (ws_path / "external_notes.txt").exists(), "Без явного указания файл не должен копироваться в папку рабочей области"

            # 2. Вызов с явным copy_to_workspace=True -> физически копирует файл в ws_path
            res_copy = await client.post(
                "/api/v1/workspaces/ws_in_place_default/items",
                json={"items": [str(copied_src)], "copy_to_workspace": True},
            )
            assert res_copy.status_code == 200
            assert (ws_path / "copied_notes.txt").exists(), "При явном copy_to_workspace=True файл должен быть скопирован"

            # 3. Оба файла отображаются в содержимом директории Git с корректным source_mode
            contents = wm.get_directory_contents("ws_in_place_default")
            by_name = {i["name"]: i for i in contents["items"]}
            assert "external_notes.txt" in by_name
            assert by_name["external_notes.txt"]["source_mode"] == "linked"
            assert by_name["external_notes.txt"]["tracked_by_git"] is True
            assert by_name["copied_notes.txt"]["source_mode"] == "local"

            # 4. Внешний отслеживаемый файл открывается через open_workspace_file по его реальному пути на диске
            opened = []
            monkeypatch.setattr(os, "startfile", lambda p: opened.append(str(p)), raising=False)
            open_res = wm.open_workspace_file("ws_in_place_default", "external_notes.txt")
            assert open_res["opened"] is True
            assert Path(opened[-1]).resolve() == ext_file.resolve()

        # 5. Проверяем наличие переключателя в UI tab_workspace
        webgui_dir = Path(__file__).resolve().parent.parent / "api" / "webgui"
        ws_html = (webgui_dir / "tab_workspace" / "index.html").read_text(encoding="utf-8")
        panel_js = (webgui_dir / "tab_workspace" / "panel_workspace_select" / "panel.js").read_text(encoding="utf-8")
        assert 'id="ws-track-copy-checkbox"' in ws_html
        assert "ws-track-copy-checkbox" in panel_js


@pytest.mark.asyncio
async def test_portable_usb_host_qualified_paths_across_computers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет носимый (USB-флешка) режим: хранение полного пути с именем компьютера и перенос между ПК."""
    import os
    import tempfile

    with tempfile.TemporaryDirectory() as usb_drive_tmp, tempfile.TemporaryDirectory() as pc1_disk, tempfile.TemporaryDirectory() as pc2_disk:
        usb_root = Path(usb_drive_tmp)
        wm = WorkspaceManager(
            base_dir=usb_root / "data",
            workspaces_dir=usb_root / "workspaces",
        )
        ws_id = "portable_usb_ws"
        ws = wm.create_or_select_workspace(ws_id, name="Portable USB Workspace")
        ws_path = Path(ws["path"])

        # --- ШАГ 1: Работаем на первом компьютере OFFICE-PC ---
        monkeypatch.setenv("COMPUTERNAME", "OFFICE-PC")
        pc1_file = (Path(pc1_disk) / "shared_name.txt").resolve()
        pc1_file.write_text("Мама мыла раму.", encoding="utf-8")

        res_pc1 = await wm.add_items_to_workspace(
            workspace_id=ws_id,
            paths=[str(pc1_file)],
            copy_to_workspace=False,
        )
        assert res_pc1["status"] == "ok"
        expected_qual_pc1 = f"\\\\OFFICE-PC\\{pc1_file}"
        assert res_pc1["tracked_files"][0]["host_name"] == "OFFICE-PC"
        assert res_pc1["tracked_files"][0]["qualified_path"] == expected_qual_pc1

        # Проверяем запись в реестре источников (.workspace/config.json)
        sources_pc1 = wm.list_sources(ws_id)
        assert len(sources_pc1) == 1
        assert sources_pc1[0]["host_name"] == "OFFICE-PC"
        assert sources_pc1[0]["qualified_path"] == expected_qual_pc1
        assert sources_pc1[0]["is_current_host"] is True

        # Проверяем запись в SQLite documents
        docs_pc1 = wm.store.list_documents(ws_id)
        assert len(docs_pc1) == 1
        assert docs_pc1[0]["host_name"] == "OFFICE-PC"
        assert docs_pc1[0]["qualified_path"] == expected_qual_pc1

        # --- ШАГ 2: Переносим флешку на второй компьютер HOME-LAPTOP (файла с первого ПК нет на диске) ---
        pc1_file.unlink()
        monkeypatch.setenv("COMPUTERNAME", "HOME-LAPTOP")

        # 2.1. В содержимом директории файл отображается со статусом 'На другом ПК (OFFICE-PC)' и полным путём \\OFFICE-PC\...
        contents_pc2 = wm.get_directory_contents(ws_id)
        assert contents_pc2["current_host"] == "HOME-LAPTOP"
        item_pc1 = next(i for i in contents_pc2["items"] if i["name"] == "shared_name.txt")
        assert item_pc1["host_name"] == "OFFICE-PC"
        assert item_pc1["qualified_path"] == expected_qual_pc1
        assert item_pc1["is_current_host"] is False
        assert item_pc1["git_status"] == "На другом ПК (OFFICE-PC)"

        # 2.2. Мониторинг изменений относит файл к other_host_files, а не к missing_files
        changes_pc2 = wm.detect_changed_linked_sources(ws_id)
        assert changes_pc2["missing_files"] == []
        assert expected_qual_pc1 in changes_pc2["other_host_files"]

        # 2.3. Синхронизация на втором ПК не ломает источник с первого ПК (status == 'other_host')
        sync_pc2 = await wm.sync_linked_sources(ws_id)
        assert sync_pc2["sources"][0]["status"] == "other_host"

        # 2.4. Клик по файлу с первого ПК на втором ПК открывает сохранённый на флешке слепок .snapshot
        opened_paths = []
        monkeypatch.setattr(os, "startfile", lambda p: opened_paths.append(str(p)), raising=False)
        open_snap = wm.open_workspace_file(ws_id, "shared_name.txt")
        assert open_snap["opened"] is True
        assert ".extracted_snapshots" in opened_paths[-1]

        # 2.5. Добавляем одноимённый файл shared_name.txt на втором ПК HOME-LAPTOP — оба файла сосуществуют без перезаписи!
        pc2_file = (Path(pc2_disk) / "shared_name.txt").resolve()
        pc2_file.write_text("לדוד משה היתה חווה", encoding="utf-8")
        await wm.add_items_to_workspace(workspace_id=ws_id, paths=[str(pc2_file)], copy_to_workspace=False)

        docs_both = wm.store.list_documents(ws_id)
        assert len(docs_both) == 2
        qual_paths = {d["qualified_path"] for d in docs_both}
        assert expected_qual_pc1 in qual_paths
        assert f"\\\\HOME-LAPTOP\\{pc2_file}" in qual_paths


