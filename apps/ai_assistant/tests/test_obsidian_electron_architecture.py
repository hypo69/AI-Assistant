# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Tests - Obsidian & Electron
# =============================================================================
# Description:
#   Набор TDD-тестов для компактного Obsidian Vault внутри каждого рабочего
#   пространства (workspaces/<id>/) и архитектуры двойного движка
#   (Engine Adapter API: Electron + WebView2).
#
#   Проверяет:
#   1. Автоматическую («на лету») генерацию YAML frontmatter, секции фактов
#      с [[wikilinks]] в .md файлах документов и сводного файла _Knowledge_Base.md
#      при импорте и обновлении документов в WorkspaceManager.
#   2. Исключение служебных файлов _Knowledge_Base.md и _Topics/ из рекурсивного
#      переиндексирования, а также исключение .obsidian/ из Git.
#   3. Целенаправленную сборку тематических конспектов (_Topics/<Topic>.md) и
#      принудительную пересборку компактного хранилища Obsidian.
#   4. Сохранение ответов QA «на лету» в раздел вопросов и ответов _Knowledge_Base.md.
#   5. Контракт EngineAdapter (ElectronEngineAdapter, WebView2EngineAdapter,
#      EngineRuntimeManager) и наличие Electron-оболочки (package.json, main.js, preload.js).
#   6. REST API маршруты /api/v1/obsidian/* и /api/v1/engine/*.
#
# File: test_obsidian_electron_architecture.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-26 01:13:00
# =============================================================================

from __future__ import annotations
"""Тесты компактного Obsidian Vault в рабочей области и адаптеров движков Electron / WebView2."""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from apps.ai_assistant.core.knowledge_store import KnowledgeStore
from apps.ai_assistant.core.nlp_analyzers import AnalyzerRegistry
from apps.ai_assistant.core.temporal_code_graph import TemporalCodeGraph
from apps.ai_assistant.core.workspace_manager import WorkspaceManager
from apps.ai_assistant.core.qa_engine import KnowledgeQAEngine
from apps.ai_assistant.core.obsidian_vault import ObsidianVaultBuilder
from apps.ai_assistant.core.engine_adapter import (
    EngineRuntimeManager,
    ElectronEngineAdapter,
    WebView2EngineAdapter,
)
from apps.ai_assistant.main import app


@pytest.fixture()
def obsidian_env(tmp_path: Path):
    """Создаёт изолированное окружение рабочей области с ObsidianVaultBuilder."""
    base_dir = tmp_path / "ai_data"
    registry = AnalyzerRegistry()
    store = KnowledgeStore(db_path=base_dir / "knowledge.db")
    graph = TemporalCodeGraph(db_path=base_dir / "graph.db")
    wm = WorkspaceManager(
        base_dir=base_dir,
        workspaces_dir=base_dir / "workspaces",
        knowledge_store=store,
        analyzer_registry=registry,
        temporal_graph=graph,
    )
    qa = KnowledgeQAEngine(workspace_manager=wm)
    return {
        "tmp_path": tmp_path,
        "wm": wm,
        "qa": qa,
        "store": store,
        "builder": wm.obsidian,
    }


def test_on_the_fly_obsidian_vault_enrichment_on_import(obsidian_env) -> None:
    """Проверяет обогащение документа на лету (YAML frontmatter + [[wikilinks]]) и сводный _Knowledge_Base.md."""
    wm: WorkspaceManager = obsidian_env["wm"]
    ws = wm.create_or_select_workspace("obs_ws", name="Obsidian Workspace")
    ws_id = ws["workspace_id"]
    ws_path = Path(ws["path"])

    # 1. Импортируем документ на русском языке
    wm.import_document(
        workspace_id=ws_id,
        document_id="mama.txt",
        content="Мама мыла раму.",
        commit_message="Добавлен документ про маму",
    )

    # Проверяем, что для .txt создан обогащённый Obsidian-документ mama.md (или обновлён .md)
    doc_md = ws_path / "mama.md"
    assert doc_md.exists(), "Должна автоматически создаваться компактная Markdown-заметка документа"
    md_text = doc_md.read_text(encoding="utf-8")

    # Проверяем YAML frontmatter
    assert md_text.startswith("---\n")
    assert "workspace_id: obs_ws" in md_text
    assert "document_id: mama.txt" in md_text
    assert "language: ru" in md_text

    # Проверяем компактный блок фактов с [[wikilinks]] внутри самой заметки документа
    assert "[[мама|Мама]]" in md_text or "[[Мама]]" in md_text
    assert "[[рама|раму]]" in md_text or "[[рама]]" in md_text

    # 2. Импортируем второй документ на иврите
    wm.import_document(
        workspace_id=ws_id,
        document_id="farm.md",
        content="לדוד משה היתה חווה",
        commit_message="Добавлена ферма Давида Моше",
    )
    farm_md = ws_path / "farm.md"
    assert farm_md.exists()
    farm_text = farm_md.read_text(encoding="utf-8")
    assert "---\n" in farm_text
    assert "לדוד משה היתה חווה" in farm_text
    assert "[[דוד משה]]" in farm_text
    assert "[[חווה]]" in farm_text

    # 3. Проверяем сводный файл базы знаний _Knowledge_Base.md в корне Workspace
    kb_file = ws_path / "_Knowledge_Base.md"
    assert kb_file.exists(), "В корне рабочей области должен автоматически поддерживаться сводный _Knowledge_Base.md"
    kb_text = kb_file.read_text(encoding="utf-8")
    assert "---\n" in kb_text
    assert "[[mama]]" in kb_text or "[[mama.md]]" in kb_text
    assert "[[farm]]" in kb_text or "[[farm.md]]" in kb_text
    assert "```mermaid" in kb_text

    # Проверяем отсутствие мелких файлов под каждую сущность (компактный режим)
    assert not (ws_path / "Entities").exists()

    # 4. Проверяем, что при повторном чтении из KnowledgeStore исходный текст документа не замусорен служебным блоком
    docs = wm.store.list_documents(ws_id)
    farm_doc = next(d for d in docs if d["document_id"] == "farm.md")
    assert farm_doc["content"].strip() == "לדוד משה היתה חווה"


@pytest.mark.asyncio
async def test_on_the_fly_qa_logging_to_obsidian_knowledge_base(obsidian_env) -> None:
    """Проверяет, что при ответе на вопрос через QA Engine знание автоматически попадает в _Knowledge_Base.md."""
    wm: WorkspaceManager = obsidian_env["wm"]
    qa: KnowledgeQAEngine = obsidian_env["qa"]
    ws = wm.create_or_select_workspace("qa_obs_ws", name="QA Obsidian")
    ws_id = ws["workspace_id"]
    ws_path = Path(ws["path"])

    wm.import_document(
        workspace_id=ws_id,
        document_id="mama.txt",
        content="Мама мыла раму.",
    )

    ans = await qa.ask(
        question="Кем была вымыта рама?",
        workspace_id=ws_id,
        mode="local_only",
    )
    assert ans["status"] == "success"
    assert ans["answer"].lower().rstrip(".") == "мамой"

    kb_file = ws_path / "_Knowledge_Base.md"
    kb_text = kb_file.read_text(encoding="utf-8")
    assert "Кем была вымыта рама?" in kb_text
    assert "Мамой." in kb_text


def test_targeted_topic_dossier_compilation(obsidian_env) -> None:
    """Проверяет целенаправленную сборку знаний по теме/запросу в _Topics/<Тема>.md."""
    wm: WorkspaceManager = obsidian_env["wm"]
    builder: ObsidianVaultBuilder = obsidian_env["builder"]

    ws = wm.create_or_select_workspace("topic_ws", name="Topic Workspace")
    ws_id = ws["workspace_id"]
    ws_path = Path(ws["path"])

    wm.import_document(ws_id, "doc1.md", "Мама мыла раму.")
    wm.import_document(ws_id, "doc2.md", "לדוד משה היתה חווה")

    res = builder.compile_topic_note(
        workspace_id=ws_id,
        topic="Рама и уборка",
        query="рама мама",
    )
    assert res["status"] == "ok"
    topic_path = Path(res["note_path"])
    assert topic_path.exists()
    assert topic_path.parent == ws_path / "_Topics"

    topic_content = topic_path.read_text(encoding="utf-8")
    assert "---\n" in topic_content
    assert "Рама и уборка" in topic_content
    assert "[[doc1]]" in topic_content or "doc1.md" in topic_content


def test_engine_adapter_contract_electron_and_webview2(tmp_path: Path) -> None:
    """Проверяет архитектуру Engine Adapter API: поддержку Electron и WebView2 с общим контрактом."""
    electron_dir = Path(__file__).resolve().parent.parent / "electron"
    assert (electron_dir / "package.json").exists(), "Должен существовать package.json для Electron-оболочки"
    assert (electron_dir / "main.js").exists(), "Должен существовать главный процесс Electron (main.js)"
    assert (electron_dir / "preload.js").exists(), "Должен существовать preload-скрипт моста IPC (preload.js)"

    mgr = EngineRuntimeManager(preferred_engine="electron")
    status = mgr.get_status()
    assert status["preferred_engine"] == "electron"
    assert "electron" in status["engines"]
    assert "webview2" in status["engines"]

    el_adapter: ElectronEngineAdapter = mgr.get_adapter("electron")
    wv_adapter: WebView2EngineAdapter = mgr.get_adapter("webview2")

    assert el_adapter.engine_id == "electron"
    assert wv_adapter.engine_id == "webview2"

    # Проверка единого контракта построения команды/URI открытия хранилища Obsidian
    vault_dir = tmp_path / "sample_vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    obs_uri = el_adapter.build_obsidian_uri(vault_dir, note_name="_Knowledge_Base.md")
    assert obs_uri.startswith("obsidian://open?")
    assert "_Knowledge_Base" in obs_uri


def test_obsidian_and_engine_rest_api_endpoints() -> None:
    """Проверяет REST API эндпоинты управления Obsidian Vault и движками (Electron / WebView2)."""
    client = TestClient(app)

    # 1. Засеиваем демо-область
    seed_res = client.post("/api/v1/workspaces/seed-demo?workspace_id=default")
    assert seed_res.status_code == 200

    # 2. Проверяем статус Obsidian Vault для рабочей области
    st_res = client.get("/api/v1/workspaces/default/obsidian/status")
    assert st_res.status_code == 200
    st_data = st_res.json()
    assert st_data["status"] == "ok"
    assert st_data["knowledge_base_exists"] is True
    assert st_data["obsidian_uri"].startswith("obsidian://open?")

    # 3. Принудительная сборка компактного Vault
    build_res = client.post(
        "/api/v1/workspaces/default/obsidian/build",
        json={"commit_to_git": True},
    )
    assert build_res.status_code == 200
    b_data = build_res.json()
    assert b_data["status"] == "ok"
    assert b_data["documents_enriched"] >= 3

    # 4. Целенаправленная сборка тематического конспекта
    topic_res = client.post(
        "/api/v1/workspaces/default/obsidian/topic",
        json={
            "topic": "Ферма Давида",
            "query": "חווה דוד משה",
        },
    )
    assert topic_res.status_code == 200
    t_data = topic_res.json()
    assert t_data["status"] == "ok"
    assert "_Topics" in t_data["note_path"]

    # 5. Проверяем статус движков оболочки (Electron + WebView2)
    eng_res = client.get("/api/v1/engine/status")
    assert eng_res.status_code == 200
    eng_data = eng_res.json()
    assert eng_data["status"] == "ok"
    assert eng_data["preferred_engine"] == "electron"
    assert "electron" in eng_data["engines"]
    assert "webview2" in eng_data["engines"]


def test_electron_active_workspace_persistence_and_routing(tmp_path: Path) -> None:
    """Проверяет сохранение и каноническую маршрутизацию активного рабочего пространства в Electron."""
    electron_dir = Path(__file__).resolve().parent.parent / "electron"
    main_js_content = (electron_dir / "main.js").read_text(encoding="utf-8")

    # Проверяем наличие логики сохранения и восстановления состояния
    assert "saveActiveWorkspaceId" in main_js_content
    assert "loadSavedWorkspaceId" in main_js_content
    assert "resolveInitialActiveWorkspace" in main_js_content
    assert "electron_state.json" in main_js_content
    assert "#tab-workspace#panel-files#workspace=" in main_js_content

    # Проверяем запуск на весь экран, одиночный экземпляр и сворачивание в трей при закрытии [X]
    assert "mainWindow.maximize()" in main_js_content, "Окно должно максимизироваться на весь экран"
    assert "showMainWindow" in main_js_content, "Должна быть функция развёртывания окна на весь экран"
    assert "requestSingleInstanceLock" in main_js_content, "Оболочка должна использовать одиночный экземпляр"
    assert "mainWindow.hide()" in main_js_content, "Закрытие окна [X] должно только сворачивать окно в трей"
    assert "tray.on('click'" in main_js_content or "tray.on('double-click'" in main_js_content

    # Проверяем передачу переменной окружения AI_ASSISTANT_ACTIVE_WORKSPACE в ElectronEngineAdapter
    adapter = ElectronEngineAdapter(electron_app_dir=tmp_path / "mock_electron")
    (tmp_path / "mock_electron").mkdir(parents=True, exist_ok=True)
    (tmp_path / "mock_electron" / "package.json").write_text("{}", encoding="utf-8")

    import os
    from unittest.mock import patch

    with patch("subprocess.Popen") as mock_popen, patch.object(adapter, "_find_electron_binary", return_value="electron"), patch.object(adapter, "terminate_running_instances", return_value=1) as mock_term:
        mock_popen.return_value.pid = 12345
        os.environ["ELECTRON_RUN_AS_NODE"] = "1"
        try:
            res = adapter.launch_shell(
                url="http://127.0.0.1:8002/#tab-workspace#panel-files#workspace=my_special_workspace",
                force_fresh=True,
            )
            assert res["status"] == "launched"
            mock_term.assert_called_once()
            # Проверяем переданные переменные окружения и очистку ELECTRON_RUN_AS_NODE
            called_env = mock_popen.call_args[1].get("env", {})
            assert called_env.get("AI_ASSISTANT_ACTIVE_WORKSPACE") == "my_special_workspace"
            assert "ELECTRON_RUN_AS_NODE" not in called_env
        finally:
            os.environ.pop("ELECTRON_RUN_AS_NODE", None)


