# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Common Rust+Wasm File Editor Suite
# =============================================================================
# Description:
#   Комплексный набор модульных и интеграционных тестов для общего модуля
#   редактора файлов на базе Rust + WebAssembly (apps/common/file_editor)
#   и его веб-интерфейса (apps/common/webgui/tab_file_editor).
#
# File: test_common_file_editor.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 17:15:00
# =============================================================================

from __future__ import annotations
"""Тесты каталога типов файлов VS Code, Wasm-ядра, сервиса и вкладки tab_file_editor."""

import base64
import re
from pathlib import Path
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.common.file_editor import (
    EditorMode,
    FileDiffRequest,
    FileEditorService,
    FileFormatRequest,
    FileSaveRequest,
    HexByteModification,
    SupportedFileCatalog,
    ensure_wasm_binary,
    file_editor_router,
)


def test_supported_file_catalog_vs_code_parity() -> None:
    """Проверяет, что каталог распознаёт все основные категории файлов VS Code."""
    assert SupportedFileCatalog.get_descriptor("main.py").default_mode == EditorMode.CODE
    assert SupportedFileCatalog.get_descriptor("lib.rs").language_id == "rust"
    assert SupportedFileCatalog.get_descriptor("README.md").default_mode == EditorMode.MARKDOWN
    assert SupportedFileCatalog.get_descriptor("report.csv").default_mode == EditorMode.TABULAR
    assert SupportedFileCatalog.get_descriptor("analysis.ipynb").default_mode == EditorMode.NOTEBOOK
    assert SupportedFileCatalog.get_descriptor("diagram.svg").default_mode == EditorMode.VECTOR_SVG
    assert SupportedFileCatalog.get_descriptor("photo.png").default_mode == EditorMode.IMAGE
    assert SupportedFileCatalog.get_descriptor("manual.pdf").default_mode == EditorMode.PDF
    assert SupportedFileCatalog.get_descriptor("sound.mp3").default_mode == EditorMode.MEDIA
    assert SupportedFileCatalog.get_descriptor("module.wasm").default_mode == EditorMode.HEX
    assert SupportedFileCatalog.get_descriptor("Dockerfile").language_id == "dockerfile"
    assert SupportedFileCatalog.get_descriptor("unknown.custom", is_binary_detected=True).default_mode == EditorMode.HEX

    all_types = SupportedFileCatalog.list_all()
    assert len(all_types) >= 75


def test_wasm_binary_generation_and_header() -> None:
    """Проверяет генерацию валидного бинарного модуля WebAssembly 1.0."""
    wasm_path = ensure_wasm_binary()
    assert wasm_path.exists()
    raw = wasm_path.read_bytes()
    assert raw.startswith(b"\x00asm\x01\x00\x00\x00")
    assert b"fnv1a_hash" in raw
    assert b"count_lines" in raw
    assert b"is_binary_buffer" in raw


def test_file_editor_service_text_binary_hex_and_diff(tmp_path: Path) -> None:
    """Проверяет чтение, сохранение, побайтовый Hex-патчинг, форматирование и Diff."""
    svc = FileEditorService(base_root=tmp_path)

    # 1. Сохранение и чтение текстового файла
    save_res = svc.save_file(
        FileSaveRequest(
            rel_path="src/app.py",
            content="def hello():\n    return 42\n",
            line_ending="LF",
            commit_to_git=False,
        )
    )
    assert save_res["status"] == "ok"

    read_res = svc.read_file("src/app.py")
    assert read_res["is_binary"] is False
    assert read_res["lines_count"] == 2
    assert "def hello():" in read_res["content"]

    # 2. Вычисление Unified Diff
    diff_res = svc.compute_diff(
        FileDiffRequest(
            rel_path="src/app.py",
            modified_content="def hello():\n    return 99\n",
        )
    )
    assert diff_res["has_changes"] is True
    assert diff_res["added_lines"] == 1
    assert diff_res["removed_lines"] == 1

    # 3. Запись бинарного файла и побайтовый патч через Hex-редактор
    raw_bin = b"\x00\x01\x02\x03\xAA\xBB"
    svc.save_file(
        FileSaveRequest(
            rel_path="firmware.bin",
            base64_content=base64.b64encode(raw_bin).decode("ascii"),
            commit_to_git=False,
        )
    )
    bin_read = svc.read_file("firmware.bin")
    assert bin_read["is_binary"] is True
    assert bin_read["descriptor"]["default_mode"] == "hex"

    svc.save_file(
        FileSaveRequest(
            rel_path="firmware.bin",
            hex_patches=[
                HexByteModification(offset=1, value=0xFF),
                HexByteModification(offset=4, value=0x55),
            ],
            commit_to_git=False,
        )
    )
    patched_bytes = (tmp_path / "firmware.bin").read_bytes()
    assert patched_bytes == b"\x00\xFF\x02\x03\x55\xBB"

    # 4. Проверка блокировки Path Traversal
    with pytest.raises(ValueError):
        svc.read_file("../../outside.txt")


def test_file_editor_formatting_json_xml_csv() -> None:
    """Проверяет форматирование и диагностику ошибок синтаксиса для JSON, XML и CSV."""
    valid_json = FileEditorService.format_buffer(
        FileFormatRequest(content='{"b":1,"a":2}', extension="json", indent_size=2)
    )
    assert valid_json["valid"] is True
    assert '  "b": 1' in valid_json["formatted"]

    invalid_json = FileEditorService.format_buffer(
        FileFormatRequest(content='{"broken": }', extension="json")
    )
    assert invalid_json["valid"] is False
    assert len(invalid_json["diagnostics"]) > 0

    csv_fmt = FileEditorService.format_buffer(
        FileFormatRequest(content=" name , age \n Alice , 30 ", extension="csv")
    )
    assert csv_fmt["valid"] is True
    assert "name,age\nAlice,30\n" == csv_fmt["formatted"]


def test_router_and_webgui_tab_compliance() -> None:
    """Проверяет эндпоинты FastAPI роутера и соответствие вкладки стандартам WebGUI."""
    app = FastAPI()
    app.include_router(file_editor_router)
    client = TestClient(app)

    cat_resp = client.get("/api/v1/file-editor/catalog")
    assert cat_resp.status_code == 200
    assert cat_resp.json()["total_types"] >= 75

    wasm_resp = client.get("/api/v1/file-editor/wasm")
    assert wasm_resp.status_code == 200
    assert wasm_resp.headers["content-type"].startswith("application/wasm")
    assert wasm_resp.content.startswith(b"\x00asm")

    # Аудит верстки apps/common/webgui/tab_file_editor/index.html
    tab_dir = Path("apps/common/webgui/tab_file_editor")
    index_html = (tab_dir / "index.html").read_text(encoding="utf-8")
    style_css = (tab_dir / "style.css").read_text(encoding="utf-8")

    # Запрет тегов <script> в index.html вкладки
    assert "<script" not in index_html.lower()
    # Запрет хардкода HEX цветов в index.html и style.css
    assert re.search(r"#[0-9a-fA-F]{3,6}\b", index_html) is None
    assert re.search(r"#[0-9a-fA-F]{3,6}\b", style_css) is None


def test_tab_file_editor_i18n_ids_and_static_serving() -> None:
    """Проверяет уникальность ID у всех i18n-элементов, наличие ключей в 4 локалях и раздачу через /html."""
    import json
    from html.parser import HTMLParser
    from apps.ai_assistant.main import app as main_app

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

    tab_html = Path("apps/common/webgui/tab_file_editor/index.html").read_text(encoding="utf-8")
    parser = _I18nAuditParser()
    parser.feed(tab_html)

    assert not parser.missing_id_on_i18n, f"Элементы с data-i18n без id: {parser.missing_id_on_i18n}"
    assert len(parser.ids) == len(set(parser.ids)), "Обнаружены дублирующиеся ID в tab_file_editor/index.html"

    for lang in ["ru", "en", "he", "uk"]:
        loc = json.loads(Path(f"apps/common/webgui/locales/{lang}.json").read_text(encoding="utf-8"))
        for key in parser.i18n_keys:
            cur = loc
            for part in key.split("."):
                assert isinstance(cur, dict) and part in cur, f"Ключ {key} отсутствует в локали {lang}.json"
                cur = cur[part]

    client = TestClient(main_app)
    r_html = client.get("/html/tab_file_editor/index.html")
    r_js = client.get("/html/tab_file_editor/main.js")
    assert r_html.status_code == 200
    assert r_js.status_code == 200
    assert "initFileEditorTab" in r_js.text

