# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - File Relocation & Tree Panel Tests
# =============================================================================
# Description:
#   Комплексные тесты распознавания переноса файлов без изменений (Git R100 +
#   умная рекомендательная система / база знаний SQLite + FAISS + граф) как во
#   внешних связанных источниках, так и внутри рабочей директории, а также тесты
#   отдельной панели дерева файлов (#panel-tree) на #tab-workspace.
#
# File: test_file_relocation_and_tree_panel.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 18:43:00
# =============================================================================

from __future__ import annotations
"""Тесты бесшовного перемещения файлов (Git R100 + рекомендательная система) и панели дерева файлов."""

import asyncio
from pathlib import Path
import shutil

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.ai_assistant.api.routers import router_knowledge
from apps.ai_assistant.api.routers.router_panel import init_router as init_panel_router
from apps.ai_assistant.core.qa_engine import KnowledgeQAEngine
from apps.ai_assistant.core.workspace_manager import WorkspaceManager


def _create_isolated_wm(tmp_path: Path) -> WorkspaceManager:
    """Создаёт изолированный экземпляр WorkspaceManager во временной директории."""
    return WorkspaceManager(
        base_dir=tmp_path / "ai_data",
        workspaces_dir=tmp_path / "workspaces",
    )


def test_external_linked_file_move_preserves_git_and_recommendations(tmp_path: Path) -> None:
    """Перенос файла без изменений во внешнем источнике распознаётся Git (R100) и сохраняет факты и историю в базе знаний."""
    wm = _create_isolated_wm(tmp_path)
    qa = KnowledgeQAEngine(workspace_manager=wm)
    ws_id = "ext_move_ws"
    wm.create_or_select_workspace(ws_id, "Тест внешних перемещений")

    # Создаём внешнюю папку с подпапками inbox/ и archive/
    ext_root = tmp_path / "external_docs"
    inbox_dir = ext_root / "inbox"
    archive_dir = ext_root / "archive"
    inbox_dir.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)

    src_file = inbox_dir / "mama_note.txt"
    src_file.write_text("Мама мыла раму.", encoding="utf-8")

    # Привязываем внешнюю папку и синхронизируем
    wm.link_source(ws_id, str(ext_root), name="Внешняя папка")
    sync1 = asyncio.run(wm.sync_linked_sources(ws_id))
    assert sync1["total_indexed"] == 1

    # Подтверждаем извлечённый факт (делаем validated), чтобы убедиться, что статус валидации сохранится после переезда файла
    facts_before = wm.store.get_facts(workspace_id=ws_id)
    assert len(facts_before) >= 1
    fact_id = facts_before[0]["fact_id"]
    wm.store.update_fact_status(fact_id, "validated")

    # Переносим файл без изменений из inbox/ в archive/
    moved_file = archive_dir / "mama_note.txt"
    shutil.move(str(src_file), str(moved_file))

    # Проверяем инкрементальный детектор изменений перед синхронизацией
    changes = wm.detect_changed_linked_sources(ws_id)
    assert changes["has_changes"] is True
    assert any(
        m["from"] == "inbox/mama_note.txt" and m["to"] == "archive/mama_note.txt"
        for m in changes.get("moved_files", [])
    )

    # Запускаем синхронизацию связанных источников
    sync2 = asyncio.run(wm.sync_linked_sources(ws_id))
    assert any(
        r["from"] == "inbox/mama_note.txt" and r["to"] == "archive/mama_note.txt"
        for r in sync2.get("relocated_files", [])
    )

    # В базе знаний должен быть ровно 1 документ с новым путём archive/mama_note.txt (без дублирования и потери факта)
    docs_after = wm.store.list_documents(ws_id)
    doc_ids = [d["document_id"] for d in docs_after]
    assert "archive/mama_note.txt" in doc_ids
    assert "inbox/mama_note.txt" not in doc_ids

    # Проверяем, что факт остался валидированным (validated), не стал stale и привязан к новому пути
    facts_after = wm.store.get_facts(workspace_id=ws_id, include_stale=True)
    active_facts = [f for f in facts_after if f["status"] != "stale"]
    assert len(active_facts) == 1
    assert active_facts[0]["fact_id"] == fact_id
    assert active_facts[0]["status"] == "validated"
    assert active_facts[0]["document_id"] == "archive/mama_note.txt"

    # Проверяем, что векторный индекс FAISS и QA-движок отвечают со ссылкой на новый путь
    ans = asyncio.run(qa.ask("Кем была вымыта рама?", workspace_id=ws_id, mode="local_only"))
    assert "Мамой" in ans["answer"]
    assert any(s.get("document_id") == "archive/mama_note.txt" for s in ans.get("sources", []))

    # Проверяем, что в содержимом директории у файла отмечен перенос R100
    dir_contents = wm.get_directory_contents(ws_id)
    moved_item = next((i for i in dir_contents["items"] if i["rel_path"] == "archive/mama_note.txt"), None)
    assert moved_item is not None
    assert moved_item["git_code"] == "R100"
    assert moved_item["moved_from"] == "inbox/mama_note.txt"


def test_local_workspace_file_move_via_api_and_tree_panel(tmp_path: Path, monkeypatch) -> None:
    """Перемещение локального файла через API /items/move выполняет git mv и мигрирует базу знаний, а панель дерева возвращает иерархию."""
    wm = _create_isolated_wm(tmp_path)
    monkeypatch.setattr(router_knowledge, "_workspace_manager", wm)
    import apps.ai_assistant.api.routers.router_panel as router_panel_mod
    monkeypatch.setattr(router_panel_mod, "_workspace_manager", wm)

    app = FastAPI()
    app.include_router(router_knowledge.router)
    app.include_router(init_panel_router())
    client = TestClient(app)

    ws_id = "local_move_ws"
    wm.create_or_select_workspace(ws_id, "Локальный перенос")
    wm.import_document(
        workspace_id=ws_id,
        document_id="notes/farm.txt",
        content="לדוד משה היתה חווה",
        commit_message="Создан notes/farm.txt",
    )

    # Переносим файл в подпапку archive/farm_moved.txt через REST API
    move_res = client.post(
        f"/api/v1/workspaces/{ws_id}/items/move",
        json={
            "old_rel_path": "notes/farm.txt",
            "new_rel_path": "archive/farm_moved.txt",
            "commit_message": "Перенос farm.txt в архив",
        },
    )
    assert move_res.status_code == 200
    payload = move_res.json()
    assert payload["status"] == "ok"
    assert payload["old_rel_path"] == "notes/farm.txt"
    assert payload["new_rel_path"] == "archive/farm_moved.txt"
    assert payload["relocated_in_store"] is True

    # Проверяем, что в БД документ переехал на archive/farm_moved.txt с сохранением фактов
    docs = wm.store.list_documents(ws_id)
    assert [d["document_id"] for d in docs] == ["archive/farm_moved.txt"]
    facts = wm.store.get_facts(workspace_id=ws_id)
    assert len(facts) >= 1
    assert facts[0]["document_id"] == "archive/farm_moved.txt"

    # Проверяем работу REST эндпоинта панели дерева файлов /v1/panel/panel-tree
    panel_res = client.get(f"/v1/panel/panel-tree?workspace_id={ws_id}")
    assert panel_res.status_code == 200
    panel_json = panel_res.json()
    assert panel_json["status"] == "ok"
    assert any(item["rel_path"] == "archive/farm_moved.txt" for item in panel_json["data"])


def test_panel_tree_present_in_workspace_webgui() -> None:
    """Проверяет наличие отдельной панели дерева файлов (#panel-tree) в HTML, роутинге и оркестраторе."""
    webgui_dir = Path(__file__).resolve().parents[1] / "api" / "webgui" / "tab_workspace"
    html_text = (webgui_dir / "index.html").read_text(encoding="utf-8")
    main_js = (webgui_dir / "main.js").read_text(encoding="utf-8")
    ui_utils_js = (webgui_dir / "common" / "ui_utils.js").read_text(encoding="utf-8")
    tree_panel_js = (webgui_dir / "panel_tree" / "panel.js").read_text(encoding="utf-8")

    assert 'id="subtab-ws-tree-btn"' in html_text
    assert 'data-panel-id="panel-tree"' in html_text
    assert 'id="subpane-ws-tree"' in html_text
    assert 'id="panel-tree"' in html_text
    assert 'id="ws-tree-viewport"' in html_text

    assert "panel-tree" in main_js
    assert "loadWorkspaceTreePanel" in main_js
    assert "panel-tree" in ui_utils_js
    assert "buildHierarchyTree" in tree_panel_js
    assert "btn-ws-tree-revise-taxonomy" in html_text
    assert "ws-tree-revision-strategy" in html_text


def test_virtual_tree_combines_local_and_external_files_and_supports_model_revision(tmp_path: Path, monkeypatch) -> None:
    """Проверяет построение виртуального дерева категорий по содержимому (локальные + внешние файлы) и ревизию категорий моделью."""
    wm = _create_isolated_wm(tmp_path)
    monkeypatch.setattr(router_knowledge, "_workspace_manager", wm)
    app = FastAPI()
    app.include_router(router_knowledge.router)
    client = TestClient(app)

    ws_id = "virtual_tax_ws"
    wm.create_or_select_workspace(ws_id, "Виртуальные категории")

    # 1. Локальный файл в рабочей директории
    wm.import_document(
        workspace_id=ws_id,
        document_id="mama.txt",
        content="Мама мыла раму.",
        commit_message="Локальный документ о маме",
    )

    # 2. Внешний файл ВНЕ рабочей директории, за которым следит Git
    ext_dir = tmp_path / "external_storage" / "sub_a"
    ext_dir.mkdir(parents=True, exist_ok=True)
    ext_file = ext_dir / "david_farm.txt"
    ext_file.write_text("לדוד משה היתה חווה", encoding="utf-8")

    wm.link_source(ws_id, str(tmp_path / "external_storage"), name="Внешнее хранилище")
    asyncio.run(wm.sync_linked_sources(ws_id))

    # Запрашиваем виртуальное дерево через REST API
    res1 = client.get(f"/api/v1/workspaces/{ws_id}/virtual-tree")
    assert res1.status_code == 200
    vtree1 = res1.json()
    items1 = [i for i in vtree1["items"] if not i["is_dir"]]
    assert len(items1) == 2

    mama_item = next(i for i in items1 if i["name"] == "mama.txt")
    farm_item = next(i for i in items1 if i["name"] == "david_farm.txt")
    assert mama_item["source_mode"] == "local"
    assert farm_item["source_mode"] == "linked"
    assert "Быт" in mama_item["virtual_category"]
    assert "Имущество" in farm_item["virtual_category"]
    assert vtree1["virtual_taxonomy"]["revision_num"] == 1

    # 3. Запускаем ревизию со сменой логики построения категорий на структуру фактов (fact_semantics)
    res2 = client.post(
        f"/api/v1/workspaces/{ws_id}/virtual-tree/revise",
        json={
            "strategy": "fact_semantics",
            "instruction": "",
            "use_model": False,
        },
    )
    assert res2.status_code == 200
    vtree2 = res2.json()
    assert vtree2["virtual_taxonomy"]["revision_num"] == 2
    items2 = {i["name"]: i for i in vtree2["items"] if not i["is_dir"]}
    assert "Action" in items2["mama.txt"]["virtual_category"]
    assert "Possession" in items2["david_farm.txt"]["virtual_category"]

    # 4. Запускаем ревизию через ИИ-модель (подключаем тестовую фабрику модели), которая переоценивает логику категорий
    class _DummyModel:
        async def ask(self, q: str, attempts: int = 1, temperature: float = 0.1) -> str:
            return (
                '{"taxonomy_logic": "Переоценка ИИ: группировка по жизненным сферам и активам",'
                ' "assignments": {'
                '   "mama.txt": {"virtual_category": "Семья и Дом / Уборка", "semantic_summary": "Мытьё оконной рамы", "semantic_tags": ["семья", "дом"], "confidence": 0.99, "classification_rationale": "Сюжет домашней уборки"},'
                '   "sub_a/david_farm.txt": {"virtual_category": "Агробизнес / Землевладение", "semantic_summary": "Фермерское хозяйство Давида Моше", "semantic_tags": ["агро", "ферма"], "confidence": 0.98, "classification_rationale": "Описание сельскохозяйственного актива"}'
                ' }}'
            )

    wm.virtual_tree_engine.chat_model_factory = lambda **kwargs: _DummyModel()
    res3 = client.post(
        f"/api/v1/workspaces/{ws_id}/virtual-tree/revise",
        json={
            "strategy": "semantic_domain",
            "instruction": "Раздели на семейный быт и агробизнес",
            "use_model": True,
        },
    )
    assert res3.status_code == 200
    vtree3 = res3.json()
    assert vtree3["virtual_taxonomy"]["revision_num"] == 3
    assert "жизненным сферам" in vtree3["virtual_taxonomy"]["taxonomy_logic"]
    items3 = {i["name"]: i for i in vtree3["items"] if not i["is_dir"]}
    assert items3["mama.txt"]["virtual_category"] == "Семья и Дом / Уборка"
    assert items3["david_farm.txt"]["virtual_category"] == "Агробизнес / Землевладение"

    # 5. Переносим внешний файл без изменений в другую внешнюю папку sub_b — виртуальная категория сохраняется по content_hash!
    ext_dir_b = tmp_path / "external_storage" / "sub_b"
    ext_dir_b.mkdir(parents=True, exist_ok=True)
    shutil.move(str(ext_file), str(ext_dir_b / "david_farm.txt"))
    asyncio.run(wm.sync_linked_sources(ws_id))

    res4 = client.get(f"/api/v1/workspaces/{ws_id}/virtual-tree")
    items4 = {i["name"]: i for i in res4.json()["items"] if not i["is_dir"]}
    assert items4["david_farm.txt"]["rel_path"] == "sub_b/david_farm.txt"
    assert items4["david_farm.txt"]["virtual_category"] == "Агробизнес / Землевладение"


def test_hebrew_workspace_virtual_tree_and_language_parameter(tmp_path: Path, monkeypatch) -> None:
    """Проверяет создание рабочего пространства с указанием языка (иврит he) и генерацию категорий на иврите."""
    wm = _create_isolated_wm(tmp_path)
    monkeypatch.setattr(router_knowledge, "_workspace_manager", wm)
    app = FastAPI()
    app.include_router(router_knowledge.router)
    client = TestClient(app)

    # Создаём пространство через REST API с явным указанием языка 'he'
    ws_id = "hebrew_project"
    res_create = client.post(
        "/api/v1/workspaces",
        json={
            "workspace_id": ws_id,
            "name": "פרויקט עברית",
            "description": "מרחב עבודה בעברית",
            "language": "he",
        },
    )
    assert res_create.status_code == 200
    created_ws = res_create.json()["workspace"]
    assert created_ws["language"] == "he"

    # Импортируем документ на иврите
    wm.import_document(
        workspace_id=ws_id,
        document_id="david_moshe.txt",
        content="לדוד מושה היתה חווה",
        commit_message="שיר דוד משה",
    )

    # Получаем виртуальное дерево
    res_tree = client.get(f"/api/v1/workspaces/{ws_id}/virtual-tree")
    assert res_tree.status_code == 200
    vtree = res_tree.json()
    items = [i for i in vtree["items"] if not i["is_dir"]]
    assert len(items) == 1
    doc_item = items[0]

    # Проверяем, что виртуальная категория и теги сгенерированы на иврите (без русского винегрета)
    assert any(h_word in doc_item["virtual_category"] for h_word in ["נכסים ומשק", "חקלאות ובעלות"])
    assert "בעלות" in doc_item["semantic_tags"]
    assert "התוכן עוסק בבעלות על נכסים" in doc_item["classification_rationale"]


