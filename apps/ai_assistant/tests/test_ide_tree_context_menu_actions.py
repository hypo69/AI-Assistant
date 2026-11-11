# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant Tests - IDE Tree View Context Menu Actions
# =============================================================================
# Description:
#   TDD-тесты для операций контекстного меню (ПКМ) дерева файлов и папок:
#   - copy file: REST API POST /api/v1/workspaces/{id}/items/copy (дублирование файла с коммитом Git)
#   - copy filename: клиентский обработчик копирования имени файла в буфер обмена
#   - rename: переименование файла и папки через /items/move и модальное окно
#   - SSR-рендеринг {{key}} плейсхолдеров в #ide-tree-context-menu, #modal-ide-rename-item
#     и #modal-ide-copy-item на 4 языках (ru, en, he, uk) без хардкода текста.
#
# File: test_ide_tree_context_menu_actions.py
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-11 23:50:00
# =============================================================================

from __future__ import annotations
"""Тесты действий ПКМ контекстного меню дерева файлов (copy file, copy filename, rename) и их SSR i18n."""

import json
from pathlib import Path
import re

from bs4 import BeautifulSoup
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
import pytest

from apps.ai_assistant.api.routers import router_knowledge
from apps.ai_assistant.core.workspace_manager import WorkspaceManager
from apps.ai_assistant.main import app


_WEBGUI_DIR = Path(__file__).resolve().parent.parent / "api" / "webgui"
_LOCALES_DIR = _WEBGUI_DIR / "locales"
_INDEX_HTML = _WEBGUI_DIR / "index.html"


def _create_isolated_wm(tmp_path: Path) -> WorkspaceManager:
    """Создаёт изолированный экземпляр WorkspaceManager во временной директории."""
    return WorkspaceManager(
        base_dir=tmp_path / "ai_data",
        workspaces_dir=tmp_path / "workspaces",
    )


def test_copy_workspace_item_api_creates_copy_and_commits_git(tmp_path: Path, monkeypatch) -> None:
    """Эндпоинт POST /items/copy дублирует файл в рабочей области, сохраняет содержимое и фиксирует в Git."""
    wm = _create_isolated_wm(tmp_path)
    monkeypatch.setattr(router_knowledge, "_workspace_manager", wm)

    test_app = FastAPI()
    test_app.include_router(router_knowledge.router)
    client = TestClient(test_app)

    ws_id = "copy_ws"
    wm.create_or_select_workspace(ws_id, "Тест копирования")
    wm.create_workspace_item(
        workspace_id=ws_id,
        rel_path="docs/note.md",
        is_dir=False,
        content="# Заметка\n\nСодержимое для копирования.",
    )

    res = client.post(
        f"/api/v1/workspaces/{ws_id}/items/copy",
        json={
            "source_rel_path": "docs/note.md",
            "target_rel_path": "docs/note_copy.md",
            "commit_message": "Копия заметки",
        },
    )
    assert res.status_code == 200
    payload = res.json()
    assert payload["status"] == "ok"
    assert payload["source_rel_path"] == "docs/note.md"
    assert payload["target_rel_path"] == "docs/note_copy.md"
    assert payload["commit_hash"]

    # Проверяем физическое наличие копии и совпадение содержимого
    _, ws_path = wm._get_or_create_workspace(ws_id)
    copied_file = ws_path / "docs" / "note_copy.md"
    assert copied_file.exists()
    assert "Содержимое для копирования." in copied_file.read_text(encoding="utf-8")

    # Повторное копирование в существующий путь возвращает 400
    dup_res = client.post(
        f"/api/v1/workspaces/{ws_id}/items/copy",
        json={
            "source_rel_path": "docs/note.md",
            "target_rel_path": "docs/note_copy.md",
        },
    )
    assert dup_res.status_code == 400

    # Копирование несуществующего файла возвращает 404
    missing_res = client.post(
        f"/api/v1/workspaces/{ws_id}/items/copy",
        json={
            "source_rel_path": "docs/unknown.md",
            "target_rel_path": "docs/unknown_copy.md",
        },
    )
    assert missing_res.status_code == 404

    # Копирование директории отклоняется с кодом 400
    wm.create_workspace_item(workspace_id=ws_id, rel_path="docs/sub", is_dir=True)
    dir_res = client.post(
        f"/api/v1/workspaces/{ws_id}/items/copy",
        json={
            "source_rel_path": "docs/sub",
            "target_rel_path": "docs/sub_copy",
        },
    )
    assert dir_res.status_code == 400


def test_rename_file_and_folder_via_move_api(tmp_path: Path, monkeypatch) -> None:
    """Эндпоинт POST /items/move корректно переименовывает как файл, так и папку."""
    wm = _create_isolated_wm(tmp_path)
    monkeypatch.setattr(router_knowledge, "_workspace_manager", wm)

    test_app = FastAPI()
    test_app.include_router(router_knowledge.router)
    client = TestClient(test_app)

    ws_id = "rename_ws"
    wm.create_or_select_workspace(ws_id, "Тест переименования")
    wm.create_workspace_item(workspace_id=ws_id, rel_path="folder_a/alpha.txt", is_dir=False, content="hello")

    # Переименование файла
    res_file = client.post(
        f"/api/v1/workspaces/{ws_id}/items/move",
        json={
            "old_rel_path": "folder_a/alpha.txt",
            "new_rel_path": "folder_a/beta.txt",
        },
    )
    assert res_file.status_code == 200
    _, ws_path = wm._get_or_create_workspace(ws_id)
    assert (ws_path / "folder_a" / "beta.txt").exists()
    assert not (ws_path / "folder_a" / "alpha.txt").exists()

    # Переименование папки
    res_dir = client.post(
        f"/api/v1/workspaces/{ws_id}/items/move",
        json={
            "old_rel_path": "folder_a",
            "new_rel_path": "folder_b",
        },
    )
    assert res_dir.status_code == 200
    assert (ws_path / "folder_b" / "beta.txt").exists()
    assert not (ws_path / "folder_a").exists()


def test_tree_context_menu_and_modals_use_i18n_placeholders_without_hardcode() -> None:
    """Проверяет, что меню #ide-tree-context-menu и модалки rename/copy в index.html используют {{key}} и имеют уникальные id."""
    raw_html = _INDEX_HTML.read_text(encoding="utf-8")
    soup = BeautifulSoup(raw_html, "html.parser")

    for block_id in ("ide-tree-context-menu", "modal-ide-rename-item", "modal-ide-copy-item"):
        block = soup.find(id=block_id)
        assert block is not None, f"Блок #{block_id} должен присутствовать в index.html"

        # Каждый элемент с data-i18n* обязан иметь уникальный id
        i18n_els = block.find_all(lambda el: any(a.startswith("data-i18n") for a in el.attrs))
        assert i18n_els, f"В #{block_id} должны быть элементы с data-i18n*"
        for el in i18n_els:
            assert el.get("id"), f"Элемент {el.name} в #{block_id} с {el.attrs} должен иметь id"

        # В исходном шаблоне не должно быть захардкоженной кириллицы (всё через {{key}})
        block_html_no_comments = re.sub(r"<!--.*?-->", "", str(block), flags=re.DOTALL)
        without_tokens = re.sub(r"\{\{[a-zA-Z0-9_.-]+\}\}", "", block_html_no_comments)
        cyrillic = re.findall(r"[А-Яа-яЁё]+", without_tokens)
        assert not cyrillic, f"В #{block_id} обнаружен захардкоженный текст вместо {{{{key}}}}: {cyrillic}"

    # Проверка обязательных пунктов меню ПКМ
    for item_id, action in (
        ("cm-tree-item-copy-file", "copy-file"),
        ("cm-tree-item-copy-filename", "copy-filename"),
        ("cm-tree-item-rename", "rename"),
        ("cm-tree-item-reveal", "reveal"),
    ):
        el = soup.find(id=item_id)
        assert el is not None, f"Пункт меню #{item_id} отсутствует в index.html"
        assert el.get("data-tree-action") == action
        assert el.get("data-i18n-title")
        assert "{{" in (el.get("title") or ""), f"У #{item_id} title должен задаваться через {{{{key}}}}"


def test_tree_context_menu_i18n_keys_exist_in_all_four_locales() -> None:
    """Проверяет наличие всех ключей локализации для меню дерева и модалок rename/copy во всех 4 языках."""
    raw_html = _INDEX_HTML.read_text(encoding="utf-8")
    soup = BeautifulSoup(raw_html, "html.parser")

    keys_to_check = set()
    for block_id in ("ide-tree-context-menu", "modal-ide-rename-item", "modal-ide-copy-item"):
        block = soup.find(id=block_id)
        assert block is not None
        for el in block.find_all():
            for attr_name, attr_val in el.attrs.items():
                if attr_name.startswith("data-i18n") and isinstance(attr_val, str):
                    keys_to_check.add(attr_val)

    assert keys_to_check

    def _resolve(d: dict, dot_key: str):
        cur = d
        for part in dot_key.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return None
        return cur

    cyrillic_re = re.compile(r"[А-Яа-яЁё]")
    for lang in ("ru", "en", "he", "uk"):
        locale_data = json.loads((_LOCALES_DIR / f"{lang}.json").read_text(encoding="utf-8"))
        for key in sorted(keys_to_check):
            val = _resolve(locale_data, key)
            assert isinstance(val, str) and val.strip(), f"Ключ {key} отсутствует или пуст в {lang}.json"
            if lang == "he":
                assert not cyrillic_re.search(val), f"Кириллица в ивритском ключе {key}: {val}"


@pytest.mark.asyncio
async def test_ssr_renders_tree_context_menu_and_modals_in_all_languages() -> None:
    """Проверяет SSR-подстановку {{key}} для меню дерева, модалок rename/copy и наличие JS-обработчиков."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res_ru = await client.get("/?lang=ru")
        assert res_ru.status_code == 200
        assert "Копировать файл..." in res_ru.text
        assert "Копировать имя файла" in res_ru.text
        assert "Переименовать..." in res_ru.text
        assert "Показать в проводнике" in res_ru.text
        assert "{{ide." not in res_ru.text
        assert "{{placeholders.ide." not in res_ru.text
        assert "{{titles.ide." not in res_ru.text

        res_en = await client.get("/?lang=en")
        assert res_en.status_code == 200
        assert "Copy file..." in res_en.text
        assert "Copy filename" in res_en.text
        assert "Rename..." in res_en.text
        assert "Reveal in File Explorer" in res_en.text
        assert "{{ide." not in res_en.text

        res_he = await client.get("/", cookies={"app_language": "he"})
        assert res_he.status_code == 200
        assert "העתק קובץ..." in res_he.text
        assert "העתק שם קובץ" in res_he.text
        assert "שנה שם..." in res_he.text
        assert "הצג בסייר הקבצים" in res_he.text
        assert "{{ide." not in res_he.text

        res_uk = await client.get("/?lang=uk")
        assert res_uk.status_code == 200
        assert "Копіювати файл..." in res_uk.text
        assert "Копіювати ім'я файлу" in res_uk.text
        assert "Перейменувати..." in res_uk.text
        assert "Показати у провіднику" in res_uk.text
        assert "{{ide." not in res_uk.text

        res_js = await client.get("/html/js/ide_tree_context_menu.js")
        assert res_js.status_code == 200
        js_text = res_js.text
        for token in (
            "copy-file",
            "copy-filename",
            "rename",
            "reveal",
            "/items/copy",
            "/items/move",
            "/reveal-item",
            "openCopyModal",
            "openRenameModal",
            "copyFilenameToClipboard",
            "revealInOsExplorer",
        ):
            assert token in js_text, f"В ide_tree_context_menu.js отсутствует '{token}'"
        assert "?.onclick =" not in js_text


def test_reveal_workspace_item_api_opens_os_explorer(tmp_path: Path, monkeypatch) -> None:
    """Эндпоинт POST /reveal-item запускает проводник ОС для файла (/select), папки и корня."""
    wm = _create_isolated_wm(tmp_path)
    monkeypatch.setattr(router_knowledge, "_workspace_manager", wm)

    launched_cmds: list[list[str]] = []

    def _fake_popen(cmd, **kwargs):
        launched_cmds.append(list(cmd))
        return None

    import apps.ai_assistant.core.workspace_items_tracker as tracker_mod
    monkeypatch.setattr(tracker_mod.subprocess, "Popen", _fake_popen)
    monkeypatch.setattr(tracker_mod.os, "name", "nt")

    test_app = FastAPI()
    test_app.include_router(router_knowledge.router)
    client = TestClient(test_app)

    ws_id = "reveal_ws"
    wm.create_or_select_workspace(ws_id, "Тест показа в проводнике")
    wm.create_workspace_item(workspace_id=ws_id, rel_path="sub/doc.txt", is_dir=False, content="hi")
    _, ws_path = wm._get_or_create_workspace(ws_id)

    # 1. Файл -> explorer.exe /select, <file_path>
    res_file = client.post(f"/api/v1/workspaces/{ws_id}/reveal-item", json={"rel_path": "sub/doc.txt"})
    assert res_file.status_code == 200
    assert res_file.json()["opened"] is True
    assert launched_cmds[-1][0] == "explorer.exe"
    assert "/select," in launched_cmds[-1]
    assert str((ws_path / "sub" / "doc.txt").resolve()) == launched_cmds[-1][-1]

    # 2. Подкаталог -> explorer.exe <dir_path>
    res_dir = client.post(f"/api/v1/workspaces/{ws_id}/reveal-item", json={"rel_path": "sub"})
    assert res_dir.status_code == 200
    assert launched_cmds[-1] == ["explorer.exe", str((ws_path / "sub").resolve())]

    # 3. Корень рабочей области -> explorer.exe <ws_path>
    res_root = client.post(f"/api/v1/workspaces/{ws_id}/reveal-item", json={"rel_path": ""})
    assert res_root.status_code == 200
    assert launched_cmds[-1] == ["explorer.exe", str(ws_path.resolve())]

    # 4. Несуществующий файл -> 404
    res_404 = client.post(f"/api/v1/workspaces/{ws_id}/reveal-item", json={"rel_path": "sub/missing.txt"})
    assert res_404.status_code == 404

    # 5. Path traversal -> 400/404
    res_bad = client.post(f"/api/v1/workspaces/{ws_id}/reveal-item", json={"rel_path": "../outside.txt"})
    assert res_bad.status_code in (400, 404)
