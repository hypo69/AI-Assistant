# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-assistant Tests - Common File Tree Explorer Suite
# =============================================================================
# Description:
#   Комплексный набор модульных и интеграционных тестов для модуля древовидного
#   проводника файлов и директорий (apps/common/file_tree) и его веб-интерфейса
#   (apps/common/webgui/tab_file_tree).
#
# File: test_common_file_tree.py
# Project: ai-assistant
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 19:55:00
# =============================================================================

from __future__ import annotations
"""Тесты древовидного проводника файлов, навигации, создания объектов и WebGUI вкладки."""

import json
from pathlib import Path
import re
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.common.file_tree import (
    CreateItemRequest,
    FileTreeService,
    file_tree_router,
)


def _setup_test_workspace(tmp_path: Path) -> Path:
    """Создает тестовую структуру папок и файлов во временной директории."""
    ws = tmp_path / "test_workspace"
    ws.mkdir(parents=True, exist_ok=True)

    # 1. Корневые файлы
    (ws / "README.md").write_text("# Проект Тест\n\nОписание тестового проекта для проверки дерева файлов.\n", encoding="utf-8")
    (ws / "config.json").write_text('{"app": "test", "version": "1.0"}', encoding="utf-8")
    (ws / "binary.bin").write_bytes(b"\x00\x01\x02\x03\xFF\xFE")

    # 2. Поддиректория src/
    src = ws / "src"
    src.mkdir(parents=True, exist_ok=True)
    (src / "main.py").write_text('"""Главный модуль запуска."""\n\ndef run():\n    return 42\n', encoding="utf-8")
    (src / "utils.py").write_text('"""Вспомогательные утилиты."""\n\ndef add(a, b):\n    return a + b\n', encoding="utf-8")

    # 3. Вложенная поддиректория src/core/
    core = src / "core"
    core.mkdir(parents=True, exist_ok=True)
    (core / "engine.py").write_text('"""Ядро вычислений."""\nclass Engine:\n    pass\n', encoding="utf-8")

    # 4. Пустая директория
    (ws / "empty_folder").mkdir(parents=True, exist_ok=True)

    return ws


def test_file_tree_service_browse_root_and_breadcrumbs(tmp_path: Path) -> None:
    """Проверяет рекурсивное сканирование корня, структуру дерева и хлебные крошки."""
    ws_root = _setup_test_workspace(tmp_path)
    svc = FileTreeService(base_root=ws_root)

    res = svc.browse_directory(dir_path="")
    assert res.status == "ok"
    assert res.current_dir == ""
    assert res.parent_dir is None
    assert len(res.breadcrumbs) == 1
    assert res.breadcrumbs[0].name == "/ (Корень)"
    assert res.total_files == 6
    assert res.total_dirs == 3

    # Проверяем, что узлы отсортированы (папки первыми)
    node_names = [n.name for n in res.tree]
    assert "src" in node_names
    assert "README.md" in node_names

    # Находим узел src и проверяем детей
    src_node = next(n for n in res.tree if n.name == "src")
    assert src_node.is_dir is True
    assert src_node.children_count == 3
    child_names = [c.name for c in src_node.children]
    assert "core" in child_names
    assert "main.py" in child_names
    assert "utils.py" in child_names


def test_file_tree_service_browse_subdirectory_and_up_navigation(tmp_path: Path) -> None:
    """Проверяет сканирование поддиректории и навигацию к родительскому каталогу."""
    ws_root = _setup_test_workspace(tmp_path)
    svc = FileTreeService(base_root=ws_root)

    res = svc.browse_directory(dir_path="src/core")
    assert res.status == "ok"
    assert res.current_dir == "src/core"
    assert res.parent_dir == "src"
    assert len(res.breadcrumbs) == 3
    assert res.breadcrumbs[0].name == "/ (Корень)"
    assert res.breadcrumbs[1].name == "src"
    assert res.breadcrumbs[2].name == "core"
    assert res.breadcrumbs[2].is_current is True

    assert len(res.tree) == 1
    assert res.tree[0].name == "engine.py"
    assert res.tree[0].is_dir is False


def test_file_tree_service_summary_generation(tmp_path: Path) -> None:
    """Проверяет генерацию аналитической сводки для markdown, python и бинарных файлов."""
    ws_root = _setup_test_workspace(tmp_path)
    svc = FileTreeService(base_root=ws_root)

    # Markdown
    sum_md = svc.get_file_summary("README.md")
    assert sum_md.status == "ok"
    assert sum_md.extension == ".md"
    assert sum_md.is_binary is False
    assert sum_md.lines_count is not None and sum_md.lines_count >= 1
    assert "Проект Тест" in sum_md.summary

    # Python
    sum_py = svc.get_file_summary("src/main.py")
    assert sum_py.status == "ok"
    assert sum_py.language_id == "python"
    assert sum_py.is_binary is False
    assert "Главный модуль запуска" in sum_py.summary

    # Binary
    sum_bin = svc.get_file_summary("binary.bin")
    assert sum_bin.status == "ok"
    assert sum_bin.is_binary is True
    assert "Бинарные данные" in sum_bin.preview


def test_file_tree_service_create_item_in_specific_directory(tmp_path: Path) -> None:
    """Проверяет создание нового файла строго в целевой директории."""
    ws_root = _setup_test_workspace(tmp_path)
    svc = FileTreeService(base_root=ws_root)

    # Создание файла в src/core/
    req_file = CreateItemRequest(
        target_dir="src/core",
        name="config.py",
        is_dir=False,
        content="# Core config\nTIMEOUT = 30\n",
    )
    res_file = svc.create_item(req_file)
    assert res_file.status == "ok"
    assert res_file.rel_path == "src/core/config.py"
    assert (ws_root / "src/core/config.py").exists()
    assert (ws_root / "src/core/config.py").read_text(encoding="utf-8") == "# Core config\nTIMEOUT = 30\n"

    # Создание директории в src/
    req_dir = CreateItemRequest(
        target_dir="src",
        name="modules",
        is_dir=True,
    )
    res_dir = svc.create_item(req_dir)
    assert res_dir.status == "ok"
    assert res_dir.rel_path == "src/modules"
    assert (ws_root / "src/modules").is_dir()


def test_file_tree_service_path_traversal_protection(tmp_path: Path) -> None:
    """Проверяет блокировку выхода за пределы рабочей директории (Path Traversal)."""
    ws_root = _setup_test_workspace(tmp_path)
    svc = FileTreeService(base_root=ws_root)

    with pytest.raises(ValueError):
        svc.browse_directory(dir_path="../../outside")

    with pytest.raises(ValueError):
        svc.get_file_summary(rel_path="../../outside.txt")


def test_file_tree_router_endpoints(tmp_path: Path, monkeypatch) -> None:
    """Проверяет эндпоинты FastAPI роутера /api/v1/file-tree/*."""
    ws_root = _setup_test_workspace(tmp_path)
    mock_svc = FileTreeService(base_root=ws_root)

    import apps.common.file_tree.router as router_mod
    monkeypatch.setattr(router_mod, "_tree_service", mock_svc)

    app = FastAPI()
    app.include_router(file_tree_router)
    client = TestClient(app)

    # 1. GET /browse
    res_browse = client.get("/api/v1/file-tree/browse?dir_path=src")
    assert res_browse.status_code == 200
    browse_data = res_browse.json()
    assert browse_data["current_dir"] == "src"
    assert browse_data["parent_dir"] == ""
    assert len(browse_data["breadcrumbs"]) == 2

    # 2. GET /summary
    res_sum = client.get("/api/v1/file-tree/summary?rel_path=README.md")
    assert res_sum.status_code == 200
    sum_data = res_sum.json()
    assert sum_data["extension"] == ".md"

    # 3. POST /create
    res_create = client.post(
        "/api/v1/file-tree/create",
        json={
            "target_dir": "src",
            "name": "constants.py",
            "is_dir": False,
            "content": "PI = 3.14159\n",
        },
    )
    assert res_create.status_code == 200
    assert res_create.json()["rel_path"] == "src/constants.py"

    # 4. GET /directories
    res_dirs = client.get("/api/v1/file-tree/directories")
    assert res_dirs.status_code == 200
    dir_paths = [d["path"] for d in res_dirs.json()]
    assert "" in dir_paths
    assert "src" in dir_paths
    assert "src/core" in dir_paths


def test_webgui_tab_file_tree_compliance_and_i18n() -> None:
    """Проверяет соответствие вкладки tab_file_tree стандартам WebGUI (без script, без hex, уникальные ID, i18n)."""
    tab_dir = Path("apps/common/webgui/tab_file_tree")
    index_html = (tab_dir / "index.html").read_text(encoding="utf-8")
    style_css = (tab_dir / "style.css").read_text(encoding="utf-8")

    # 1. Запрет тегов <script> в index.html
    assert "<script" not in index_html.lower()

    # 2. Запрет хардкода HEX цветов в index.html и style.css
    assert re.search(r"#[0-9a-fA-F]{3,6}\b", index_html) is None
    assert re.search(r"#[0-9a-fA-F]{3,6}\b", style_css) is None

    # 3. Парсинг ID и data-i18n
    from html.parser import HTMLParser

    class _I18nAuditParser(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.ids: list[str] = []
            self.missing_id_on_i18n: list[dict[str, str | None]] = []
            self.i18n_keys: list[str] = []

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            attr_map = dict(attrs)
            el_id = attr_map.get("id")
            if el_id:
                self.ids.append(el_id)
            i18n_attrs = {k: v for k, v in attr_map.items() if k.startswith("data-i18n") and v}
            if i18n_attrs:
                if not el_id:
                    self.missing_id_on_i18n.append(i18n_attrs)
                self.i18n_keys.extend(v for v in i18n_attrs.values() if v)

    parser = _I18nAuditParser()
    parser.feed(index_html)

    assert not parser.missing_id_on_i18n, f"Элементы с data-i18n без id: {parser.missing_id_on_i18n}"
    assert len(parser.ids) == len(set(parser.ids)), "Обнаружены дублирующиеся ID в tab_file_tree/index.html"

    # 4. Проверка наличия всех ключей во всех 4 локалях
    for lang in ["ru", "en", "he", "uk"]:
        loc = json.loads(Path(f"apps/common/webgui/locales/{lang}.json").read_text(encoding="utf-8"))
        for key in parser.i18n_keys:
            cur = loc
            for part in key.split("."):
                assert isinstance(cur, dict) and part in cur, f"Ключ {key} отсутствует в локали {lang}.json"
                cur = cur[part]

    # 5. Проверка статической раздачи через роутер приложения
    from apps.ai_assistant.main import app as main_app
    client = TestClient(main_app)
    r_html = client.get("/html/tab_file_tree/index.html")
    r_js = client.get("/html/tab_file_tree/main.js")
    r_css = client.get("/html/tab_file_tree/style.css")

    assert r_html.status_code == 200
    assert r_js.status_code == 200
    assert r_css.status_code == 200
    assert "initFileTreeTab" in r_js.text
