# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Tests - Workspace Items Tracker
# =============================================================================
# Description:
#   Модульные тесты для трекера добавления директорий и файлов в рабочую область:
#   проверка немедленного запуска Git-отслеживания (git commit, git HEAD),
#   индексации в базе знаний и вызова через REST API.
#
# Usage Examples:
#   pytest apps/ai_assistant/tests/test_workspace_items_tracker.py -v
#
# File: test_workspace_items_tracker.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 19:05:00
# =============================================================================

from __future__ import annotations
"""Тестирование добавления директорий и файлов в рабочую область с контролем Git."""

import io
from pathlib import Path
import tempfile
import pytest
from httpx import ASGITransport, AsyncClient

from apps.ai_assistant.core.workspace_manager import WorkspaceManager
from apps.ai_assistant.core.workspace_items_tracker import WorkspaceItemsTracker
from apps.ai_assistant.main import app


@pytest.fixture
def temp_workspace_manager():
    """Создает изолированный менеджер рабочих областей во временном каталоге."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        wm = WorkspaceManager(base_dir=tmp_dir, workspaces_dir=Path(tmp_dir) / "workspaces")
        yield wm


@pytest.mark.asyncio
async def test_tracker_add_disk_files(temp_workspace_manager: WorkspaceManager):
    """Проверяет добавление отдельных файлов с диска и немедленный запуск отслеживания Git."""
    wm = temp_workspace_manager
    ws_id = "test_files_ws"
    wm.create_or_select_workspace(workspace_id=ws_id, name="Test Files")

    with tempfile.TemporaryDirectory() as src_dir:
        p1 = Path(src_dir) / "notes.txt"
        p1.write_text("Важные рабочие заметки о проекте.", encoding="utf-8")

        p2 = Path(src_dir) / "data.csv"
        p2.write_text("id,val\n1,alpha\n2,beta", encoding="utf-8")

        tracker = WorkspaceItemsTracker(wm)
        res = await tracker.add_disk_items(
            workspace_id=ws_id,
            paths=[str(p1), str(p2)],
            copy_to_workspace=True,
        )

        assert res["status"] == "ok"
        assert res["files_added"] == 2
        assert len(res["git_head"]) >= 7
        assert res["git_head"] != "init"

        # Проверяем, что Git зафиксировал файлы в истории
        commits = await wm.get_workspace_commits(workspace_id=ws_id)
        assert len(commits) >= 1
        assert any("notes.txt" in c["message"] or "data.csv" in c["message"] or "Git" in c["message"] for c in commits)

        # Проверяем наличие документов в хранилище знаний
        docs = wm.store.list_documents(ws_id)
        doc_ids = {d["document_id"] for d in docs}
        assert any("notes.txt" in d for d in doc_ids)
        assert any("data.csv" in d for d in doc_ids)
        ws_path = wm.registry.workspace_path(ws_id)
        assert (ws_path / "assets" / "notes.txt").exists()
        assert (ws_path / "assets" / "data.csv").exists()


@pytest.mark.asyncio
async def test_tracker_add_disk_directory(temp_workspace_manager: WorkspaceManager):
    """Проверяет рекурсивное добавление директории в рабочую область и отслеживание всех ее файлов."""
    wm = temp_workspace_manager
    ws_id = "test_dir_ws"
    wm.create_or_select_workspace(workspace_id=ws_id, name="Test Dir")

    with tempfile.TemporaryDirectory() as src_dir:
        sub_folder = Path(src_dir) / "sub_project"
        sub_folder.mkdir(parents=True, exist_ok=True)
        (sub_folder / "readme.md").write_text("# Документация проекта\nТекст документа.", encoding="utf-8")
        (sub_folder / "config.json").write_text('{"env": "production"}', encoding="utf-8")

        tracker = WorkspaceItemsTracker(wm)
        res = await tracker.add_disk_items(
            workspace_id=ws_id,
            paths=[str(sub_folder)],
            copy_to_workspace=True,
        )

        assert res["status"] == "ok"
        assert res["files_added"] >= 2
        assert len(res["git_head"]) >= 7

        commits = await wm.get_workspace_commits(workspace_id=ws_id)
        assert len(commits) >= 1

        docs = wm.store.list_documents(ws_id)
        assert len(docs) >= 2


@pytest.mark.asyncio
async def test_tracker_add_uploaded_files(temp_workspace_manager: WorkspaceManager):
    """Проверяет загрузку бинарных/текстовых файлов и фиксацию их в репозитории Git."""
    wm = temp_workspace_manager
    ws_id = "test_upload_ws"
    wm.create_or_select_workspace(workspace_id=ws_id, name="Test Upload")

    tracker = WorkspaceItemsTracker(wm)
    uploaded = [
        ("report.txt", "Содержимое отчета для индексации.".encode("utf-8")),
        ("summary.md", "# Сводка\nДанные проверены.".encode("utf-8")),
    ]

    res = await tracker.add_uploaded_files(
        workspace_id=ws_id,
        files_data=uploaded,
        commit_message="Загрузка тестовых отчетов",
    )

    assert res["status"] == "ok"
    assert res["files_added"] == 2
    assert len(res["git_head"]) >= 7

    commits = await wm.get_workspace_commits(workspace_id=ws_id)
    assert len(commits) >= 1
    assert any("Git" in c["message"] or "assets" in c["message"] for c in commits)


@pytest.mark.asyncio
async def test_rest_api_add_items_and_upload():
    """Проверяет вызов серверных эндпоинтов добавления путей и загрузки файлов через REST API."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Создаем рабочую область
        create_res = await client.post("/api/v1/workspaces", json={
            "workspace_id": "api_test_ws",
            "name": "API Test Workspace",
        })
        assert create_res.status_code == 200

        with tempfile.TemporaryDirectory() as tmp_dir:
            fpath = Path(tmp_dir) / "api_doc.txt"
            fpath.write_text("Проверка добавления через REST API эндпоинт.", encoding="utf-8")

            # Добавляем файл по локальному пути
            items_res = await client.post("/api/v1/workspaces/api_test_ws/items", json={
                "items": [str(fpath)],
                "copy_to_workspace": True,
                "commit_message": "Коммит через API",
            })
            assert items_res.status_code == 200
            data = items_res.json()
            assert data["status"] == "ok"
            assert data["files_added"] >= 1
            assert "git_head" in data

        # Загружаем файл через multipart upload
        file_content = b"Content of uploaded file for git tracking."
        files = {
            "files": ("upload_test.txt", io.BytesIO(file_content), "text/plain"),
        }
        data_payload = {
            "commit_message": "Upload via multipart",
        }
        upload_res = await client.post(
            "/api/v1/workspaces/api_test_ws/files/upload",
            files=files,
            data=data_payload,
        )
        assert upload_res.status_code == 200
        up_data = upload_res.json()
        assert up_data["status"] == "ok"
        assert up_data["files_added"] >= 1
        assert "git_head" in up_data


@pytest.mark.asyncio
async def test_index_html_contains_workspace_menu_item_and_modal():
    """Проверяет интеграцию пункта создания рабочей области в меню и наличие модального окна в index.html."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/")
        assert res.status_code == 200
        html = res.text

        # Проверяем наличие пункта в меню навигации
        assert "Создать рабочую область" in html
        assert "Дать ей имя" in html or "Дать ей" in html
        assert 'id="menu-btn-create-workspace"' in html

        # Проверяем наличие модального мастера
        assert 'id="modal-create-workspace-wizard"' in html
        assert 'id="ws-wizard-step1-block"' in html
        assert 'id="ws-wizard-step2-block"' in html
        assert 'id="ws-wizard-target-path-input"' in html
        assert 'id="ws-wizard-files-input"' in html

        # Проверяем раздачу скрипта мастера
        script_res = await client.get("/html/js/workspace_wizard.js")
        assert script_res.status_code == 200
        assert "initWorkspaceWizard" in script_res.text


@pytest.mark.asyncio
async def test_tab_create_workspace_assets_and_navigation():
    """Проверяет перенос кнопок в боковое меню, верхнюю кнопку Создать новое пространство и ассеты вкладки."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/")
        assert res.status_code == 200
        html = res.text

        # 1. Верхняя панель навигации: современный центр управления и отсутствие устаревшего контейнера
        assert 'id="ide-command-center"' in html
        assert 'id="top-workspace-control-container"' not in html
        assert 'data-tab="tab-create-workspace"' in html
        assert "Создать рабочее пространство" in html or "Создать новое пространство" in html

        # 2. Боковое меню (offcanvas): все кнопки разделов навигации
        assert 'data-bs-target="#leftSideNavOffcanvas"' in html
        assert 'data-tab="tab-workspace"' in html
        assert 'data-tab="tab-create-workspace"' in html
        assert 'data-tab="tab-timeline"' in html
        assert 'data-tab="tab-commits"' in html
        assert 'data-tab="tab-diff"' in html
        assert 'data-tab="tab-wikillm"' in html
        assert 'data-tab="tab-graph"' in html
        assert 'data-tab="tab-models"' in html
        assert 'data-tab="tab-rag"' in html
        assert 'data-tab="tab-verification"' in html
        assert 'data-tab="tab-status"' in html
        assert 'data-tab="tab-theme-editor"' in html

        # 3. Контейнер вкладки
        assert 'id="tab-create-workspace"' in html

        # 4. Раздача статических ассетов вкладки tab_create_workspace
        html_tab_res = await client.get("/html/tab_create_workspace/index.html")
        assert html_tab_res.status_code == 200
        tab_html = html_tab_res.text
        # Проверяем поля ввода имени, описания, пути с кнопкой выбора директории
        assert 'id="create-ws-name-input"' in tab_html
        assert 'id="create-ws-path-input"' in tab_html
        assert 'id="btn-browse-ws-path"' in tab_html
        assert 'id="picker-create-ws-path"' in tab_html
        assert 'id="create-ws-desc-input"' in tab_html
        assert 'id="btn-create-ws-submit"' in tab_html
        assert 'id="input-watch-directory-path"' in tab_html
        assert 'id="btn-browse-watch-dir"' in tab_html
        assert 'id="input-watch-file-path"' in tab_html
        assert 'id="btn-browse-watch-file"' in tab_html
        assert 'id="create-ws-sources-list"' in tab_html
        assert "Файлы и директории остаются на своих местах" in tab_html

        js_tab_res = await client.get("/html/tab_create_workspace/main.js")
        assert js_tab_res.status_code == 200
        assert "initCreateWorkspaceTab" in js_tab_res.text
        assert "copy_to_workspace: false" in js_tab_res.text
        assert "browse-folder" in js_tab_res.text
        assert "btn-browse-ws-path" in js_tab_res.text

        # 5. Раздача компонента выпадающего списка пространств
        top_dropdown_res = await client.get("/html/js/top_workspace_dropdown.js")
        assert top_dropdown_res.status_code == 200
        assert "updateTopWorkspaceDropdown" in top_dropdown_res.text
        assert "Мои пространства" in top_dropdown_res.text
        assert "Добавить новое" in top_dropdown_res.text


@pytest.mark.asyncio
async def test_browse_folder_endpoint(monkeypatch):
    """Проверяет работу эндпоинта выбора директории на компьютере."""
    import apps.ai_assistant.api.routers.router_knowledge as rk
    monkeypatch.setattr(rk, "_open_folder_dialog", lambda *a, **kw: "C:/MockProjects/MyTargetFolder")
    monkeypatch.setattr(rk, "_open_file_dialog", lambda *a, **kw: "C:/MockProjects/MyTargetFolder/notes.txt")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/v1/workspaces/browse-folder?initial_dir=C:/")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert data["path"] == "C:/MockProjects/MyTargetFolder"

        res_file = await client.post("/api/v1/workspaces/browse-file")
        assert res_file.status_code == 200
        file_data = res_file.json()
        assert file_data["status"] == "ok"
        assert file_data["path"] == "C:/MockProjects/MyTargetFolder/notes.txt"


@pytest.mark.asyncio
async def test_create_workspace_with_in_place_tracking_without_moving(temp_workspace_manager: WorkspaceManager):
    """Проверяет создание пространства и подключение файлов и папок без их перемещения."""
    wm = temp_workspace_manager
    ws_id = "in_place_ws"

    # 1. Создание пространства с описанием в каталоге workspaces/<id>
    ws = wm.create_or_select_workspace(
        workspace_id=ws_id,
        name="In-Place Tracking Workspace",
        description="Пространство для слежения за внешними файлами без их перемещения",
    )
    assert ws["workspace_id"] == ws_id
    assert (wm.workspaces_dir / ws_id / ".git").exists()  # Проверяем git init

    # 2. Создаем внешнюю папку и файл, которые ДОЛЖНЫ остаться на своих местах
    with tempfile.TemporaryDirectory() as external_data_dir:
        ext_dir = Path(external_data_dir) / "docs"
        ext_dir.mkdir(parents=True)
        doc_file = ext_dir / "architecture.md"
        doc_file.write_text("# Архитектура\nСлежение за файлами без перемещения.", encoding="utf-8")

        single_file = Path(external_data_dir) / "extra.txt"
        single_file.write_text("Отдельный файл на исходном месте.", encoding="utf-8")

        tracker = WorkspaceItemsTracker(wm)

        # Подключаем папку и файл с copy_to_workspace = False
        res = await tracker.add_disk_items(
            workspace_id=ws_id,
            paths=[str(ext_dir), str(single_file)],
            copy_to_workspace=False,
            commit_message="Привязка внешних путей на месте",
        )
        assert res["status"] == "ok"
        assert res["files_added"] >= 2

        # Проверяем, что исходные файлы ОСТАЛИСЬ на своих местах
        assert doc_file.exists()
        assert doc_file.read_text(encoding="utf-8").startswith("# Архитектура")
        assert single_file.exists()

        # Проверяем, что источники зарегистрированы в пространстве
        sources = wm.list_sources(ws_id)
        assert len(sources) >= 2
        source_paths = [s["source_path"] for s in sources]
        assert str(ext_dir) in source_paths
        assert str(single_file) in source_paths


@pytest.mark.asyncio
async def test_workspace_folder_status_and_ensure(temp_workspace_manager: WorkspaceManager):
    """Проверяет статус отсутствующей папки и её создание в workspaces/<id> с Git и config.json."""
    wm = temp_workspace_manager
    ws_id = "folder_test_ws"
    ws_folder = wm.workspaces_dir / ws_id

    # 1. Папки ещё нет - пространство не найдено
    status_before = wm.check_workspace_folder(ws_id)
    assert status_before["exists"] is False
    assert status_before["has_git"] is False
    assert wm.get_workspace(ws_id) is None

    # 2. ensure_workspace_folder создаёт папку, .git и .workspace/config.json
    status_after = wm.ensure_workspace_folder(ws_id)
    assert status_after["exists"] is True
    assert status_after["is_dir"] is True
    assert status_after["has_git"] is True
    assert (ws_folder / ".git").exists()
    assert (ws_folder / ".workspace" / "config.json").exists()

    # 3. Пространство обнаруживается сканированием каталога
    assert ws_id in [w["workspace_id"] for w in wm.list_workspaces()]


@pytest.mark.asyncio
async def test_workspace_folder_rest_endpoints(temp_workspace_manager: WorkspaceManager, monkeypatch: pytest.MonkeyPatch):
    """Тестирует REST API эндпоинты проверки, создания и редактирования рабочей папки."""
    from apps.ai_assistant.api.routers import router_knowledge
    monkeypatch.setattr(router_knowledge, "_workspace_manager", temp_workspace_manager)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Создаём пространство
        create_res = await ac.post("/api/v1/workspaces", json={
            "workspace_id": "api_folder_ws",
            "name": "API Folder WS",
        })
        assert create_res.status_code == 200

        # 1. GET /folder-status
        status_res = await ac.get("/api/v1/workspaces/api_folder_ws/folder-status")
        assert status_res.status_code == 200
        status_data = status_res.json()["folder_status"]
        assert status_data["exists"] is True
        assert status_data["has_git"] is True

        # 2. POST /ensure-folder
        ensure_res = await ac.post("/api/v1/workspaces/api_folder_ws/ensure-folder")
        assert ensure_res.status_code == 200
        ensure_data = ensure_res.json()["folder_status"]
        assert ensure_data["exists"] is True
        assert Path(ensure_data["path"]).resolve() == (temp_workspace_manager.workspaces_dir / "api_folder_ws").resolve()


def test_ui_markup_and_routing_scripts_for_folder_and_url_hash():
    """Проверяет UI элементы управления папкой и поддержку хеша #tab-workspace#panel-files#workspace=<id>."""
    base_gui = Path(__file__).resolve().parent.parent / "api" / "webgui"
    index_html = (base_gui / "tab_workspace" / "index.html").read_text(encoding="utf-8")
    top_dropdown_js = (base_gui / "js" / "top_workspace_dropdown.js").read_text(encoding="utf-8")
    main_js = (base_gui / "js" / "main.js").read_text(encoding="utf-8")
    panel_js = (base_gui / "tab_workspace" / "panel_workspace_select" / "panel.js").read_text(encoding="utf-8")

    # 1. Проверяем элементы управления рабочей папкой в HTML
    assert 'id="ws-folder-badge"' in index_html
    assert 'id="btn-ws-create-folder"' in index_html
    assert 'id="btn-ws-edit-path"' not in index_html
    assert 'id="ws-edit-path-form"' not in index_html

    # 2. Проверяем добавление ID рабочего пространства к URL в top_workspace_dropdown.js
    assert '#tab-workspace#panel-files#workspace=' in top_dropdown_js
    assert 'panel-documents' in top_dropdown_js  # Переход к управлению документами

    # 3. Проверяем обработку хеша URL в main.js
    assert 'targetWsId' in main_js
    assert 'workspace=' in main_js
    assert 'selectWorkspaceInTab' in main_js
    assert 'hashchange' in main_js

    # 4. Проверяем функции в panel.js
    assert 'workspace=' in panel_js
    assert '#tab-workspace#panel-files#workspace=' in panel_js
    assert 'checkAndDisplayFolderStatus' in panel_js
    assert '/ensure-folder' in panel_js
    assert '/update-path' not in panel_js

    # 5. Проверяем наличие подпункта demo и группы рабочих пространств в боковом меню
    main_index = (base_gui / "index.html").read_text(encoding="utf-8")
    assert 'id="drawer-workspaces-group"' in main_index
    assert 'id="drawer-workspaces-list"' in main_index
    assert 'data-ws-id="demo"' in main_index
    assert 'первый опыт работы с workspace' in main_index


def test_workspaces_storage_dir_from_config() -> None:
    """Проверяет, что WorkspaceManager считывает workspaces_dir из config.json."""
    wm = WorkspaceManager()
    assert "data" in str(wm.workspaces_dir).lower()
    assert wm.workspaces_dir.exists()


@pytest.mark.asyncio
async def test_directory_contents_endpoint_and_tracker(temp_workspace_manager: WorkspaceManager, monkeypatch: pytest.MonkeyPatch):
    """Тестирует получение содержимого директории Git и REST API эндпоинт."""
    from apps.ai_assistant.api.routers import router_knowledge
    monkeypatch.setattr(router_knowledge, "_workspace_manager", temp_workspace_manager)

    wm = temp_workspace_manager
    ws_id = "test_dir_contents_ws"
    wm.create_or_select_workspace(workspace_id=ws_id, name="Contents WS")

    # Добавляем тестовый файл
    tracker = WorkspaceItemsTracker(wm)
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("Тестовый контент для директории")
        temp_file = Path(f.name)

    try:
        await tracker.add_disk_items(workspace_id=ws_id, paths=[str(temp_file)])

        # Проверяем метод tracker.get_directory_contents
        contents = tracker.get_directory_contents(ws_id)
        assert contents["workspace_id"] == ws_id
        assert contents["total_files"] >= 1
        assert any(item["name"] == temp_file.name for item in contents["items"])

        # Проверяем REST API GET /workspaces/{id}/directory-contents
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.get(f"/api/v1/workspaces/{ws_id}/directory-contents")
            assert res.status_code == 200
            data = res.json()
            assert data["workspace_id"] == ws_id
            assert data["total_files"] >= 1
            assert "items" in data
            assert any(i["name"] == temp_file.name for i in data["items"])
    finally:
        if temp_file.exists():
            temp_file.unlink()


@pytest.mark.asyncio
async def test_add_items_with_conversion_options(temp_workspace_manager: WorkspaceManager):
    """Проверяет передачу опций конвертации (pdf_mode, ocr_mode, audio_mode) при добавлении файлов."""
    wm = temp_workspace_manager
    ws_id = "test_conv_options_ws"
    wm.create_or_select_workspace(workspace_id=ws_id, name="Conversion Options WS")
    tracker = WorkspaceItemsTracker(wm)

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("Пример текста с конвертацией")
        t_file = Path(f.name)

    try:
        res = await tracker.add_disk_items(
            workspace_id=ws_id,
            paths=[str(t_file)],
            pdf_mode="local",
            ocr_mode="local",
            audio_mode="model",
        )
        assert res["status"] == "ok"
        assert res["files_added"] == 1
    finally:
        if t_file.exists():
            t_file.unlink()


@pytest.mark.asyncio
async def test_workspace_default_gitignore_and_media_exclusion(temp_workspace_manager: WorkspaceManager):
    """Проверяет создание .gitignore по умолчанию с игнорированием PDF и медиа, сохранением .md."""
    wm = temp_workspace_manager
    ws_id = "test_gitignore_ws"
    ws = wm.create_or_select_workspace(workspace_id=ws_id, name="Gitignore WS")
    ws_path = Path(ws["path"])

    gitignore_file = ws_path / ".gitignore"
    assert gitignore_file.exists(), ".gitignore должен автоматически создаваться в репозитории пространства"
    gi_content = gitignore_file.read_text(encoding="utf-8")
    assert "*.pdf" in gi_content
    assert "*.mp3" in gi_content
    assert "*.wav" in gi_content
    assert "*.png" in gi_content
    assert "!*.md" in gi_content

    # Проверяем список файлов в директории через трекер
    tracker = WorkspaceItemsTracker(wm)
    contents = tracker.get_directory_contents(ws_id)
    assert contents["workspace_id"] == ws_id
    # .gitignore должен быть зафиксирован в Git
    gi_entry = next((i for i in contents["items"] if i["name"] == ".gitignore"), None)
    assert gi_entry is not None
    assert gi_entry["tracked_by_git"] is True


@pytest.mark.asyncio
async def test_audio_raw_vs_converted_mode_and_converters_ui_block(temp_workspace_manager: WorkspaceManager, monkeypatch: pytest.MonkeyPatch):
    """Проверяет сохранение сырого аудио без транскрибации vs конвертированного .md и скрытый блок в UI."""
    wm = temp_workspace_manager
    ws_id = "test_audio_modes_ws"
    ws = wm.create_or_select_workspace(workspace_id=ws_id, name="Audio Modes WS")
    ws_path = Path(ws["path"])
    tracker = WorkspaceItemsTracker(wm)

    # 1. Добавление аудиофайла в режиме 'raw' (сохранить сырой)
    with tempfile.NamedTemporaryFile("wb", suffix=".mp3", delete=False) as f:
        f.write(b"MOCK_RAW_AUDIO_BYTES_FOR_TESTING")
        raw_audio_file = Path(f.name)

    try:
        res_raw = await tracker.add_disk_items(
            workspace_id=ws_id,
            paths=[str(raw_audio_file)],
            audio_mode="raw",
        )
        assert res_raw["status"] == "ok"
        assert res_raw["files_added"] == 1

        # Для сырого режима НЕ создается .md компаньон
        md_companion = ws_path / f"{raw_audio_file.name}.md"
        assert not md_companion.exists()

        # Сырой файл принудительно отслеживается Git (даже при наличии в .gitignore)
        raw_in_ws = (ws_path / "assets" / raw_audio_file.name) if (ws_path / "assets" / raw_audio_file.name).exists() else (ws_path / raw_audio_file.name)
        assert raw_in_ws.exists()
        dir_contents = tracker.get_directory_contents(ws_id)
        raw_entry = next((i for i in dir_contents["items"] if i["name"] == raw_audio_file.name), None)
        assert raw_entry is not None
        assert raw_entry["tracked_by_git"] is True
    finally:
        if raw_audio_file.exists():
            raw_audio_file.unlink()

    # 2. Проверяем UI разметку tab_workspace: блок конвертеров скрыт по умолчанию
    base_gui = Path(__file__).resolve().parent.parent / "api" / "webgui"
    index_html = (base_gui / "tab_workspace" / "index.html").read_text(encoding="utf-8")
    assert 'id="ws-converters-block"' in index_html
    assert 'class="border rounded p-2.5 bg-body mb-3 d-none"' in index_html
    assert 'id="ws-conv-section-audio"' in index_html
    assert 'name="ws-conv-audio-mode"' in index_html
    assert 'id="ws-conv-audio-raw"' in index_html
    assert 'value="raw"' in index_html

    panel_js = (base_gui / "tab_workspace" / "panel_workspace_select" / "panel.js").read_text(encoding="utf-8")
    assert 'updateConvertersVisibility' in panel_js
    assert 'ws-conv-audio-mode' in panel_js

@pytest.mark.asyncio
async def test_open_workspace_file_in_editor(temp_workspace_manager, monkeypatch):
    """Тестирует открытие файла рабочей области в редакторе по умолчанию у пользователя (метод, API и UI)."""
    wm = temp_workspace_manager
    ws_id = "test_open_editor_ws"
    ws = wm.create_or_select_workspace(workspace_id=ws_id, name="Open Editor WS")
    ws_path = Path(ws["path"])
    tracker = WorkspaceItemsTracker(wm)

    # 1. Создаем тестовый текстовый файл внутри рабочей области
    sample_file = ws_path / "notes.txt"
    sample_file.write_text("Hello workspace file", encoding="utf-8")

    # Мокаем os.startfile, чтобы зафиксировать вызов без открытия реального окна
    opened_paths = []
    import os
    monkeypatch.setattr(os, "startfile", lambda path: opened_paths.append(str(path)), raising=False)

    # Успешное открытие существующего файла
    res = tracker.open_workspace_file(ws_id, "notes.txt")
    assert res["status"] == "ok"
    assert res["rel_path"] == "notes.txt"
    assert res["opened"] is True
    assert len(opened_paths) == 1
    assert Path(opened_paths[0]).resolve() == sample_file.resolve()

    # Ошибка: несуществующий файл
    with pytest.raises(FileNotFoundError):
        tracker.open_workspace_file(ws_id, "non_existent.txt")

    # Ошибка: передача каталога
    sub_dir = ws_path / "sub_folder"
    sub_dir.mkdir(exist_ok=True)
    with pytest.raises(ValueError):
        tracker.open_workspace_file(ws_id, "sub_folder")

    # Ошибка: path traversal (выход за пределы рабочей области)
    with pytest.raises(ValueError):
        tracker.open_workspace_file(ws_id, "../outside.txt")

    # 2. Проверка через REST API эндпоинт POST /api/v1/workspaces/{workspace_id}/open-file
    from apps.ai_assistant.api.routers import router_knowledge
    monkeypatch.setattr(router_knowledge, "_workspace_manager", wm)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        api_res = await ac.post(f"/api/v1/workspaces/{ws_id}/open-file", json={
            "rel_path": "notes.txt"
        })
        assert api_res.status_code == 200
        assert api_res.json()["status"] == "ok"
        assert len(opened_paths) == 2

        # 404 для несуществующего файла
        res_404 = await ac.post(f"/api/v1/workspaces/{ws_id}/open-file", json={
            "rel_path": "missing.txt"
        })
        assert res_404.status_code == 404

    # 3. Проверка клиентского кода в panel.js
    base_gui = Path(__file__).resolve().parent.parent / "api" / "webgui"
    panel_js = (base_gui / "tab_workspace" / "panel_workspace_select" / "panel.js").read_text(encoding="utf-8")

    assert 'file-row cursor-pointer' in panel_js
    assert 'openWorkspaceFileInEditor' in panel_js
    assert '/open-file' in panel_js
    assert 'ws-directory-contents-table-body' in panel_js


@pytest.mark.asyncio
async def test_workspace_assets_directory_and_storage_path(temp_workspace_manager: WorkspaceManager):
    """Проверяет, что рабочее пространство создается в workspaces/, содержит папку assets/ и загружает туда исходники."""
    wm = temp_workspace_manager
    ws_id = "test_custom_assets_ws"
    ws = wm.create_or_select_workspace(workspace_id=ws_id, name="Custom Assets Space")
    ws_path = Path(ws["path"])

    # 1. Проверяем, что путь находится внутри workspaces_dir (data/workspaces)
    assert wm.workspaces_dir == ws_path.parent
    assert ws_path.exists()
    assert (ws_path / ".git").exists()

    # 2. Проверяем гарантированное создание папки assets
    assets_dir = ws_path / "assets"
    assert assets_dir.exists()
    assert assets_dir.is_dir()

    # 3. Проверяем загрузку исходников именно в директорию assets
    tracker = WorkspaceItemsTracker(wm)
    uploaded = [("source_code.py", b"print('hello assets')")]
    res = await tracker.add_uploaded_files(workspace_id=ws_id, files_data=uploaded)

    assert res["status"] == "ok"
    assert (assets_dir / "source_code.py").exists()
    assert (assets_dir / "source_code.py").read_text(encoding="utf-8") == "print('hello assets')"

    # 4. Проверяем чтение через WorkspaceFileOps из assets
    from apps.ai_assistant.core.workspace_file_ops import WorkspaceFileOps
    content_data = WorkspaceFileOps.get_content(wm, ws_id, "source_code.py")
    assert content_data["content"] == "print('hello assets')"

    # 5. Проверяем, что каталог assets/ исключен из Git
    gi_text = (ws_path / ".gitignore").read_text(encoding="utf-8")
    assert "assets/" in gi_text
    tracked_in_git = wm._run_git(ws_path, ["ls-files", "assets"])
    assert not tracked_in_git, f"assets не должен отслеживаться в Git: {tracked_in_git}"
