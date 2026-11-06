# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant Tests - Workspace System Files & Content Manifest
# =============================================================================
# Description:
#   Тесты разделения системных и пользовательских файлов в рабочей области:
#   1. Проверка того, что внешняя папка на диске остаётся нетронутой (система
#      не создаёт во внешних папках никаких файлов).
#   2. Проверка маркировки автоматически сгенерированных файлов Obsidian
#      (с маркером generator: ai_assistant_obsidian) как системных (is_system=True).
#   3. Проверка генерации и сохранения единого манифеста содержимого
#      .workspace/manifest.json с ролями 'user' и 'system'.
#   4. Проверка отображения внешних ссылок (linked) как пользовательских файлов
#      с полными квалифицированными путями.
#
# File: test_workspace_system_files_manifest.py
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-03 17:00:00
# =============================================================================

from __future__ import annotations
"""Тесты разделения системных/пользовательских файлов и манифеста содержимого workspace."""

import json
from pathlib import Path
import tempfile
import pytest

from apps.ai_assistant.core.workspace_manager import WorkspaceManager
from apps.ai_assistant.core.workspace_items_tracker import WorkspaceItemsTracker


@pytest.fixture
def temp_workspace_manager():
    """Создает изолированный менеджер рабочих областей во временном каталоге."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        wm = WorkspaceManager(base_dir=tmp_dir, workspaces_dir=Path(tmp_dir) / "workspaces")
        yield wm


@pytest.mark.asyncio
async def test_external_folder_untouched_and_system_obsidian_file(temp_workspace_manager: WorkspaceManager):
    """Проверяет неприкосновенность внешних папок и классификацию авто-конспекта Obsidian как системного."""
    wm = temp_workspace_manager
    ws_id = "test_manifest_ws"
    wm.create_or_select_workspace(workspace_id=ws_id, name="Test Manifest WS")
    ws_path = wm.registry.workspace_path(ws_id)
    tracker = WorkspaceItemsTracker(wm)

    # 1. Создаём внешний каталог пользователя с исходным файлом (например, דוד מושה.txt)
    with tempfile.TemporaryDirectory() as ext_dir:
        ext_folder = Path(ext_dir)
        user_source_file = ext_folder / "דוד מושה.txt"
        user_source_file.write_text("לדוד מושה היתה חווה.", encoding="utf-8")

        # Добавляем внешний файл без копирования (как linked-источник)
        add_res = await tracker.add_disk_items(
            workspace_id=ws_id,
            paths=[str(user_source_file)],
            copy_to_workspace=False,
        )
        assert add_res["status"] == "ok"

        # Синхронизируем источники (при этом внутри workspace генерируется авто-конспект Obsidian)
        await wm.sync_linked_sources(workspace_id=ws_id)

        # 2. ПРОВЕРКА НЕПРИКОСНОВЕННОСТИ ВНЕШНЕЙ ПАПКИ:
        # Во внешней папке ext_dir должен остаться ТОЛЬКО исходный файл пользователя.
        # Система ничего не должна создавать во внешней папке!
        external_files = list(ext_folder.rglob("*"))
        assert len(external_files) == 1, f"Во внешней папке должны оставаться только файлы пользователя: {external_files}"
        assert external_files[0].name == "דוד מושה.txt"
        assert not (ext_folder / "דוד מושה.md").exists()
        assert not (ext_folder / ".git").exists()

        # 3. ПРОВЕРКА РАЗДЕЛЕНИЯ ФАЙЛОВ В РАБОЧЕЙ ОБЛАСТИ:
        contents = tracker.get_directory_contents(ws_id)
        items = contents["items"]

        # Внешний файл пользователя должен присутствовать и иметь is_system=False, source_mode='linked'
        user_item = next((i for i in items if i["rel_path"] == "דוד מושה.txt"), None)
        assert user_item is not None, "Исходный внешний файл должен быть в списке элементов"
        assert user_item["is_system"] is False, "Пользовательский файл не должен быть помечен системным"
        assert user_item["source_mode"] == "linked"
        assert user_item["is_external"] is True

        # Автоматически сгенерированный файл Obsidian должен иметь is_system=True
        obsidian_item = next((i for i in items if i["rel_path"] == "דוד מושה.md"), None)
        if obsidian_item:
            assert obsidian_item["is_system"] is True, "Сгенерированный файл Obsidian должен быть системным"
            assert obsidian_item.get("generator") == "ai_assistant_obsidian"
            assert obsidian_item.get("role") == "system"

        # 4. ПРОВЕРКА ЕДИНОГО МАНИФЕСТА СОДЕРЖИМОГО (.workspace/manifest.json)
        manifest_file = ws_path / ".workspace" / "manifest.json"
        assert manifest_file.exists(), "Манифест .workspace/manifest.json должен быть сохранён"
        manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
        assert manifest_data["workspace_id"] == ws_id
        assert "items" in manifest_data
        m_items = manifest_data["items"]
        assert "דוד מושה.txt" in m_items
        assert m_items["דוד מושה.txt"]["role"] == "user"
        assert m_items["דוד מושה.txt"]["source_mode"] == "linked"
        assert m_items["דוד מושה.txt"]["is_system"] is False

        if "דוד מושה.md" in m_items:
            assert m_items["דוד מושה.md"]["role"] == "system"
            assert m_items["דוד מושה.md"]["is_system"] is True
            assert m_items["דוד מושה.md"]["generator"] == "ai_assistant_obsidian"
