# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant Tests - Service File Authenticator
# =============================================================================
# Description:
#   Модульные тесты аутентификатора служебных файлов (ServiceFileAuthenticator)
#   и механизма скрытия/маркировки сопутствующих конспектов Obsidian с точкой:
#   1. Проверка первичного файлового аутентификатора имени (точка и подчёркивание).
#   2. Проверка зарезервированных системных имён и директорий.
#   3. Проверка аутентификации по содержимому (YAML frontmatter generator signature).
#   4. Проверка генерации dotfile-имени для сопутствующих заметок не-md файлов.
#   5. Проверка сохранения исходного имени для пользовательских .md файлов.
#   6. Проверка миграции устаревших файлов без точки в теневые dot-файлы.
#   7. Проверка фильтрации служебных файлов в get_directory_contents и манифесте.
#
# File: test_service_file_authenticator.py
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-03 17:30:00
# =============================================================================

from __future__ import annotations
"""Тесты аутентификатора служебных файлов и сопутствующих заметок с точкой."""

from pathlib import Path
import tempfile
import pytest

from apps.ai_assistant.core.service_file_authenticator import ServiceFileAuthenticator
from apps.ai_assistant.core.workspace_manager import WorkspaceManager
from apps.ai_assistant.core.workspace_items_tracker import WorkspaceItemsTracker


def test_service_file_authenticator_name_and_dot_rules() -> None:
    """Проверяет распознавание служебных файлов по префиксу точки, подчёркивания и зарезервированным именам."""
    # 1. Первичный аутентификатор: точка (dotfile convention)
    assert ServiceFileAuthenticator.is_service_name(".gitignore") is True
    assert ServiceFileAuthenticator.is_service_name(".obsidian") is True
    assert ServiceFileAuthenticator.is_service_name(".workspace") is True
    assert ServiceFileAuthenticator.is_service_name(".tracked_sources.json") is True
    assert ServiceFileAuthenticator.is_service_name(".דוד משה.md") is True
    assert ServiceFileAuthenticator.is_service_name(".doc_summary.md") is True

    # 2. Инфраструктурный префикс: подчеркивание
    assert ServiceFileAuthenticator.is_service_name("_Knowledge_Base.md") is True
    assert ServiceFileAuthenticator.is_service_name("_Topics") is True
    assert ServiceFileAuthenticator.is_service_name("_notes") is True
    assert ServiceFileAuthenticator.is_service_name("_Index.md") is True

    # 3. Зарезервированные системные файлы и папки
    assert ServiceFileAuthenticator.is_service_name("README.md") is True
    assert ServiceFileAuthenticator.is_service_name("readme.md") is True
    assert ServiceFileAuthenticator.is_service_name("assets") is True
    assert ServiceFileAuthenticator.is_service_name(".gitkeep") is True

    # 4. Пользовательские файлы не должны распознаваться как служебные
    assert ServiceFileAuthenticator.is_service_name("my_document.txt") is False
    assert ServiceFileAuthenticator.is_service_name("notes.md") is False
    assert ServiceFileAuthenticator.is_service_name("report_2026.docx") is False
    assert ServiceFileAuthenticator.is_service_name("דוד מושה.txt") is False


def test_service_file_authenticator_content_signatures() -> None:
    """Проверяет распознавание служебных файлов по цифровой подписи генератора в содержимом."""
    obsidian_yaml = (
        "---\n"
        "generator: ai_assistant_obsidian\n"
        "title: \"דוד משה\"\n"
        "document_id: דוד משה.txt\n"
        "---\n"
        "Текст конспекта Obsidian"
    )
    assert ServiceFileAuthenticator.is_service_content(obsidian_yaml) is True

    html_comment_sig = "<!-- AI-OBSIDIAN-KNOWLEDGE:START -->\nКонспект"
    assert ServiceFileAuthenticator.is_service_content(html_comment_sig) is True

    user_text = "Обычный пользовательский конспект без служебных маркеров."
    assert ServiceFileAuthenticator.is_service_content(user_text) is False


def test_resolve_obsidian_companion_filename_dot_prefix() -> None:
    """Проверяет генерацию имени сопутствующего конспекта с точкой для не-md документов."""
    # Для текстового, офисного или PDF документа — имя сопутствующего конспекта начинается с точки
    assert ServiceFileAuthenticator.resolve_obsidian_companion_filename("דוד משה.txt") == ".דוד משה.md"
    assert ServiceFileAuthenticator.resolve_obsidian_companion_filename("manual.pdf") == ".manual.md"
    assert ServiceFileAuthenticator.resolve_obsidian_companion_filename("table.xlsx") == ".table.md"
    assert ServiceFileAuthenticator.resolve_obsidian_companion_filename("path/to/nested_file.txt") == ".nested_file.md"

    # Если имя уже начинается с точки, точка не дублируется
    assert ServiceFileAuthenticator.resolve_obsidian_companion_filename(".hidden_src.txt") == ".hidden_src.md"

    # Для пользовательского .md документа имя сохраняется без искажений
    assert ServiceFileAuthenticator.resolve_obsidian_companion_filename("my_personal_notes.md") == "my_personal_notes.md"


@pytest.mark.asyncio
async def test_obsidian_vault_auto_migration_to_dotfile() -> None:
    """Проверяет создание сопутствующего файла с точкой и автоматическую миграцию старого файла без точки."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        wm = WorkspaceManager(base_dir=tmp_dir, workspaces_dir=Path(tmp_dir) / "workspaces")
        ws_id = "test_dot_ws"
        wm.create_or_select_workspace(workspace_id=ws_id, name="Test Dot WS")
        ws_path = wm.registry.workspace_path(ws_id)

        # Создаём устаревший файл без точки (как в ранних версиях)
        legacy_file = ws_path / "דוד מושה.md"
        legacy_file.write_text(
            "---\ngenerator: ai_assistant_obsidian\ntitle: \"דוד מושה\"\n---\nУстаревший файл конспекта",
            encoding="utf-8",
        )
        assert legacy_file.exists()

        # Разрешаем путь через ObsidianVaultBuilder
        resolved_path = wm.obsidian._resolve_doc_md_path(ws_path, "דוד מושה.txt")

        # Целевой путь должен начинаться с точки
        assert resolved_path.name == ".דוד מושה.md"
        assert resolved_path.exists()
        # Устаревший файл без точки должен быть удален / смигрирован
        assert not legacy_file.exists()

        # Проверяем, что в содержимом рабочей области файл распознан как системный (is_system=True)
        contents = wm.get_directory_contents(ws_id)
        dot_item = next((i for i in contents["items"] if i["name"] == ".דוד מושה.md"), None)
        assert dot_item is not None
        assert dot_item["is_system"] is True
        assert dot_item["role"] == "system"
        assert dot_item["generator"] == "ai_assistant_obsidian"
