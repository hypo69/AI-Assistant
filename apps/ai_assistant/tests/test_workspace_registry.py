# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Test AI Assistant Workspace Registry
# =============================================================================
# Description:
#   Модульные тесты файлового реестра рабочих пространств (WorkspaceRegistry):
#   - Обнаружение пространств сканированием каталога (только папки с .git).
#   - Автосоздание .workspace/config.json и исключение его из Git.
#   - Сохранение имени/описания и CRUD привязанных источников в config.json.
#
# File: test_workspace_registry.py
# Package: apps/ai_assistant/tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 20:07:00
# =============================================================================

from __future__ import annotations
"""Модульные тесты WorkspaceRegistry."""

import json
from pathlib import Path

from apps.ai_assistant.core.workspace_registry import WorkspaceRegistry
from apps.ai_assistant.core.workspace_manager import WorkspaceManager


def _make_ws(root: Path, name: str) -> Path:
    """Создаёт папку пространства с минимальным каталогом .git."""
    ws = root / name
    (ws / ".git" / "refs" / "heads").mkdir(parents=True)
    (ws / ".git" / "HEAD").write_text("ref: refs/heads/master\n", encoding="utf-8")
    (ws / ".git" / "refs" / "heads" / "master").write_text("abc123\n", encoding="utf-8")
    return ws


def test_scan_detects_only_git_folders_and_creates_config(tmp_path: Path) -> None:
    """Пространствами считаются только подпапки с .git; config.json создаётся автоматически."""
    ws = _make_ws(tmp_path, "alpha")
    (tmp_path / "plain_dir").mkdir()
    _make_ws(tmp_path, ".hidden")

    registry = WorkspaceRegistry(tmp_path)
    items = registry.list_workspaces()

    assert [w["workspace_id"] for w in items] == ["alpha"]
    assert items[0]["name"] == "alpha"
    assert items[0]["git_head"] == "abc123"
    cfg_file = ws / ".workspace" / "config.json"
    assert cfg_file.exists()
    assert ".workspace/" in (ws / ".git" / "info" / "exclude").read_text(encoding="utf-8")


def test_user_config_json_in_root_is_not_touched(tmp_path: Path) -> None:
    """Пользовательский config.json в корне пространства не используется как настройки."""
    ws = _make_ws(tmp_path, "beta")
    (ws / "config.json").write_text('{"env": "production"}', encoding="utf-8")

    registry = WorkspaceRegistry(tmp_path)
    registry.save_workspace("beta", name="Бета", description="Описание")

    assert json.loads((ws / "config.json").read_text(encoding="utf-8")) == {"env": "production"}
    ws_info = registry.get_workspace("beta")
    assert ws_info["name"] == "Бета"
    assert ws_info["description"] == "Описание"


def test_get_workspace_missing_returns_none(tmp_path: Path) -> None:
    """Отсутствующее пространство или папка без .git возвращают None."""
    (tmp_path / "no_git").mkdir()
    registry = WorkspaceRegistry(tmp_path)
    assert registry.get_workspace("absent") is None
    assert registry.get_workspace("no_git") is None


def test_sources_crud_in_config(tmp_path: Path) -> None:
    """Источники добавляются, обновляются и удаляются в .workspace/config.json."""
    _make_ws(tmp_path, "gamma")
    registry = WorkspaceRegistry(tmp_path)

    src = registry.add_source("gamma", "file", "C:/data/doc.txt", "doc.txt")
    assert registry.list_sources("gamma")[0]["source_id"] == src["source_id"]

    assert registry.update_source_status("gamma", src["source_id"], status="active", item_count=3)
    updated = registry.list_sources("gamma")[0]
    assert updated["status"] == "active"
    assert updated["item_count"] == 3
    assert updated["last_scanned_at"]

    assert registry.delete_source("gamma", src["source_id"]) is True
    assert registry.delete_source("gamma", src["source_id"]) is False
    assert registry.list_sources("gamma") == []


def test_multilingual_workspace_creation(tmp_path: Path) -> None:
    """Проверяет создание рабочих областей с именами на иврите и русском языке без искажения в знаки подчеркивания."""
    wm = WorkspaceManager(base_dir=tmp_path / "base", workspaces_dir=tmp_path / "workspaces")

    # 1. Создание рабочей области с именем на иврите
    he_ws = wm.create_or_select_workspace(workspace_id="דוד מושה", name="דוד מושה")
    assert he_ws["workspace_id"] == "דוד_מושה"
    assert he_ws["name"] == "דוד מושה"
    assert (tmp_path / "workspaces" / "דוד_מושה").is_dir()
    assert (tmp_path / "workspaces" / "דוד_מושה" / ".git").exists()

    # 2. Создание рабочей области с русским именем
    ru_ws = wm.create_or_select_workspace(workspace_id="Моя Новая Область", name="Моя Новая Область")
    assert ru_ws["workspace_id"] == "Моя_Новая_Область"
    assert (tmp_path / "workspaces" / "Моя_Новая_Область").is_dir()


def test_faiss_index_stored_inside_workspace(tmp_path: Path) -> None:
    """Проверяет хранение FAISS индекса внутри рабочего пространства (.workspace/faiss_indices)."""
    wm = WorkspaceManager(base_dir=tmp_path / "base", workspaces_dir=tmp_path / "workspaces")
    ws_id = "test_faiss_ws"
    wm.create_or_select_workspace(workspace_id=ws_id, name="Test FAISS WS")

    # 1. Получение TextRAG и добавление документа
    rag = wm.get_faiss_rag(ws_id)
    rag.add_documents([
        {"id": f"{ws_id}:doc1:s0", "text": "Тестовый документ векторного поиска", "meta": {"workspace_id": ws_id}}
    ])

    expected_faiss_dir = tmp_path / "workspaces" / ws_id / ".workspace" / "faiss_indices"
    assert expected_faiss_dir.is_dir()

    # Проверяем, что файлы индекса лежат именно внутри рабочего пространства
    assert rag.index_file == expected_faiss_dir / f"ws_{ws_id}.faiss"
    assert rag.meta_file == expected_faiss_dir / f"ws_{ws_id}.json"
    assert (expected_faiss_dir / f"ws_{ws_id}.json").exists()

    # Проверяем, что в старой центральной папке индекс не создавался
    assert not (tmp_path / "base" / "faiss_indices" / f"ws_{ws_id}.json").exists()

    # 2. Проверка автоматической миграции устаревшего индекса
    legacy_ws = "legacy_ws"
    wm.create_or_select_workspace(workspace_id=legacy_ws, name="Legacy WS")
    legacy_dir = tmp_path / "base" / "faiss_indices"
    legacy_dir.mkdir(parents=True, exist_ok=True)
    legacy_json = legacy_dir / f"ws_{legacy_ws}.json"
    legacy_json.write_text(json.dumps([{"id": "old", "text": "старый вектор"}]), encoding="utf-8")
    legacy_faiss = legacy_dir / f"ws_{legacy_ws}.faiss"
    legacy_faiss.write_text("dummy faiss binary data", encoding="utf-8")

    migrated_rag = wm.get_faiss_rag(legacy_ws)
    target_legacy_dir = tmp_path / "workspaces" / legacy_ws / ".workspace" / "faiss_indices"
    assert (target_legacy_dir / f"ws_{legacy_ws}.json").exists()
    assert (target_legacy_dir / f"ws_{legacy_ws}.faiss").exists()


def test_sqlite_databases_stored_inside_workspace(tmp_path: Path) -> None:
    """Проверяет хранение SQLite баз данных внутри рабочего пространства (.workspace/)."""
    wm = WorkspaceManager(base_dir=tmp_path / "base", workspaces_dir=tmp_path / "workspaces")
    ws_id = "test_sqlite_ws"
    wm.create_or_select_workspace(workspace_id=ws_id, name="Test SQLite WS")

    # 1. Проверяем пути к базам данных
    db_path = wm.get_workspace_db_path(ws_id)
    graph_path = wm.get_workspace_graph_path(ws_id)
    expected_meta = tmp_path / "workspaces" / ws_id / ".workspace"

    assert db_path == expected_meta / "knowledge_store.db"
    assert graph_path == expected_meta / "temporal_graph.db"

    # 2. Сохраняем документ через KnowledgeStore для данного пространства
    store = wm.get_workspace_store(ws_id)
    store.store_document_and_facts(
        workspace_id=ws_id,
        document_id="doc_sqlite_test",
        file_path="doc.txt",
        raw_content="Текст документа для SQLite",
        commit_hash="c112233",
        analysis_result={"language": "ru", "sentences": [], "facts": []},
    )

    # Проверяем, что файл knowledge_store.db физически создан внутри .workspace
    assert (expected_meta / "knowledge_store.db").exists()

    # 3. Добавляем связь в темпоральный граф
    graph = wm.get_workspace_graph(ws_id)
    graph.add_link(
        source_id="c112233",
        target_id="doc_sqlite_test",
        relation_type="modifies",
        valid_from="c112233",
    )

    # Проверяем, что temporal_graph.db физически создан внутри .workspace
    assert (expected_meta / "temporal_graph.db").exists()


def test_delete_workspace_success_and_protection(tmp_path: Path) -> None:
    """Проверяет удаление рабочего пространства и защиту от недопустимых путей."""
    import pytest
    root = tmp_path / "workspaces"
    root.mkdir()
    _make_ws(root, "ws_to_delete")
    _make_ws(root, "ws_keep")

    reg = WorkspaceRegistry(root)
    assert len(reg.list_workspaces()) == 2

    # 1. Успешное удаление
    res = reg.delete_workspace("ws_to_delete")
    assert res is True
    assert not (root / "ws_to_delete").exists()
    assert len(reg.list_workspaces()) == 1
    assert reg.list_workspaces()[0]["workspace_id"] == "ws_keep"

    # 2. Повторное удаление вызывает FileNotFoundError
    with pytest.raises(FileNotFoundError):
        reg.delete_workspace("ws_to_delete")

    # 3. Защита от path traversal и недопустимых имён
    with pytest.raises(ValueError):
        reg.delete_workspace("../other")

    with pytest.raises(ValueError):
        reg.delete_workspace(".git")

    with pytest.raises(ValueError):
        reg.delete_workspace("")


def test_manager_delete_workspace_switches_active(tmp_path: Path) -> None:
    """Проверяет удаление рабочей области через WorkspaceManager со сменой активной области."""
    wm = WorkspaceManager(base_dir=tmp_path / "base", workspaces_dir=tmp_path / "workspaces")
    wm.create_or_select_workspace("ws1", name="Workspace 1")
    wm.create_or_select_workspace("ws2", name="Workspace 2")

    wm.store.set_active_workspace("ws1")
    assert wm.store.get_active_workspace_id() == "ws1"

    result = wm.delete_workspace("ws1")
    assert result["status"] == "ok"
    assert result["deleted_workspace_id"] == "ws1"
    assert result["active_workspace_id"] == "ws2"
    assert wm.store.get_active_workspace_id() == "ws2"


def test_readme_creation_and_multilingual_structure(tmp_path: Path) -> None:
    """Проверяет обязательную структуру README.md с первой строкой lang=... и главами."""
    from apps.ai_assistant.core.workspace_registry import (
        generate_workspace_readme,
        parse_workspace_readme,
    )

    # 1. Русский
    content_ru = generate_workspace_readme("Мой Проект", "Тестовое описание проекта", "ru")
    lines_ru = content_ru.splitlines()
    assert lines_ru[0] == "lang=ru"
    assert "# Мой Проект" in content_ru
    assert "## Описание" in content_ru
    assert "Тестовое описание проекта" in content_ru

    # 2. English
    content_en = generate_workspace_readme("Demo Project", "Test project description", "en")
    assert content_en.splitlines()[0] == "lang=en"
    assert "# Demo Project" in content_en
    assert "## Description" in content_en

    # 3. Иврит
    content_he = generate_workspace_readme("פרויקט דוגמה", "תיאור מרחב עבודה", "he")
    assert content_he.splitlines()[0] == "lang=he"
    assert "# פרויקט דוגמה" in content_he
    assert "## תיאור" in content_he

    # 4. Украинский
    content_ua = generate_workspace_readme("Мій Проєкт", "Опис робочого простору", "ua")
    assert content_ua.splitlines()[0] == "lang=ua"
    assert "# Мій Проєкт" in content_ua
    assert "## Опис" in content_ua

    # 5. Парсер
    readme_file = tmp_path / "README.md"
    readme_file.write_text(content_ru, encoding="utf-8")
    parsed = parse_workspace_readme(readme_file)
    assert parsed["language"] == "ru"
    assert parsed["name"] == "Мой Проект"
    assert parsed["description"] == "Тестовое описание проекта"


def test_workspace_creation_initializes_readme(tmp_path: Path) -> None:
    """Проверяет, что create_or_select_workspace автоматически создаёт README.md с lang=..."""
    wm = WorkspaceManager(base_dir=tmp_path / "base", workspaces_dir=tmp_path / "workspaces")
    ws_meta = wm.create_or_select_workspace("test_readme_ws", name="README Тест", description="Описание для теста", language="ru")
    assert ws_meta["workspace_id"] == "test_readme_ws"

    ws_dir = tmp_path / "workspaces" / "test_readme_ws"
    readme_path = ws_dir / "README.md"
    assert readme_path.exists()
    content = readme_path.read_text(encoding="utf-8")
    assert content.startswith("lang=ru")
    assert "# README Тест" in content
    assert "## Описание" in content
    assert "Описание для теста" in content





