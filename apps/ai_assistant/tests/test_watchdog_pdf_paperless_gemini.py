# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant Tests - Watchdog PDF -> Paperless -> Gemini -> Git
# =============================================================================
# Description:
#   Тестирует конвейер автоматической обработки PDF-файлов наблюдателем watchdog:
#   1. Передача PDF в Paperless-ngx и получение структурированного .md.
#   2. Анализ смысла .md и структуры папок рабочей области моделью Gemini.
#   3. Размещение .md файла в подходящей папке и Git-коммит с осмысленным
#      названием, сформулированным моделью на основе изменений.
#   4. Обработка обновлений (diff), внешних привязанных источников, защита от
#      Path Traversal и резервный fallback при недоступности Paperless/Gemini.
#
# File: test_watchdog_pdf_paperless_gemini.py
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-11 23:44:30
# =============================================================================

from __future__ import annotations
"""Тесты конвейера Watchdog: PDF -> Paperless -> Gemini -> Git commit."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.ai_assistant.core.watchdog_pdf_pipeline import (
    WatchdogPdfPipeline,
    format_paperless_markdown,
    resolve_gemini_candidates,
    sanitize_target_dir,
)
from apps.ai_assistant.core.workspace_manager import WorkspaceManager
from apps.ai_assistant.core.workspace_watchdog import (
    WatchTarget,
    WorkspaceWatchdogService,
    save_watchdog_config,
)


@pytest.fixture()
def isolated_env(tmp_path: Path):
    """Создаёт изолированный WorkspaceManager и конфигурацию watchdog."""
    wm = WorkspaceManager(
        base_dir=tmp_path / "base_data",
        workspaces_dir=tmp_path / "workspaces",
    )
    wm.create_or_select_workspace("pdf_ws", name="Бухгалтерия", description="Финансовые и юридические документы", language="ru")
    cfg_path = tmp_path / "config.json"
    save_watchdog_config(
        {"enabled": True, "auto_transcribe_media": True, "auto_git_commit": True, "debounce_seconds": 0.2},
        cfg_path,
    )
    return wm, cfg_path


def _fake_paperless_connector(paperless_id: int, content: str, title: str):
    """Создаёт мок-коннектор PaperlessConnector."""
    conn = MagicMock()
    conn.ping.return_value = True
    conn.ingest_file.return_value = {
        "paperless_id": paperless_id,
        "content": content,
        "metadata": {"id": paperless_id, "title": title, "created_date": "2026-11-11"},
    }
    conn.close.return_value = None
    return conn


@pytest.mark.asyncio
async def test_watchdog_pdf_to_paperless_gemini_and_git_commit(isolated_env, tmp_path: Path) -> None:
    """PDF в рабочей области проходит через Paperless, размещается Gemini в подходящую папку и коммитится в Git."""
    wm, cfg_path = isolated_env
    ws_path = Path(wm.registry.get_workspace("pdf_ws")["path"])
    (ws_path / "Финансы" / "Счета").mkdir(parents=True, exist_ok=True)
    (ws_path / "Договоры").mkdir(parents=True, exist_ok=True)

    pdf_file = ws_path / "invoice_77.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 mock invoice")

    fake_conn = _fake_paperless_connector(
        paperless_id=105,
        content="Счёт на оплату №77 от ООО «Альфа».\nСумма к оплате: 15 000 руб.",
        title="Счёт №77 от ООО Альфа",
    )

    captured_prompts = []

    def _chat_factory(system_instruction: str, provider: str, model: str):
        mock_chat = MagicMock()

        async def _ask(q: str, **kwargs):
            captured_prompts.append({"provider": provider, "model": model, "q": q})
            return json.dumps({
                "target_dir": "Финансы/Счета",
                "commit_message": "Добавлен счёт №77 от ООО Альфа на 15 000 руб. в Финансы/Счета",
            }, ensure_ascii=False)

        mock_chat.ask = _ask
        return mock_chat

    pipeline = WatchdogPdfPipeline(
        workspace_manager=wm,
        paperless_factory=lambda: fake_conn,
        chat_model_factory=_chat_factory,
    )
    wd = WorkspaceWatchdogService(workspace_manager=wm, config_path=cfg_path, pdf_pipeline=pipeline)
    pipeline.suppress_callback = wd.suppress_workspace

    res = await wd.process_file_event(
        WatchTarget(kind="workspace", workspace_id="pdf_ws", root_path=ws_path),
        pdf_file,
        "created",
    )

    assert res["status"] == "ok"
    assert res["action"] == "pdf_paperless_gemini_committed"
    assert res["paperless_id"] == 105
    assert res["ocr_source"] == "paperless"
    assert res["document_id"] == "Финансы/Счета/invoice_77.md"

    # Проверяем вызовы Paperless и Gemini
    fake_conn.ingest_file.assert_called_once()
    fake_conn.close.assert_called_once()
    assert len(captured_prompts) == 1
    prompt_payload = json.loads(captured_prompts[0]["q"])
    folder_paths = [f["path"] for f in prompt_payload["existing_folders"]]
    assert "Финансы/Счета" in folder_paths
    assert "Счёт на оплату №77" in prompt_payload["markdown_content"]

    # Проверяем сохранённый .md файл, БД знаний и Git-коммит
    placed_md = ws_path / "Финансы" / "Счета" / "invoice_77.md"
    assert placed_md.exists()
    md_text = placed_md.read_text(encoding="utf-8")
    assert "Paperless ID: `#105`" in md_text
    assert "15 000 руб." in md_text

    docs = wm.store.list_documents("pdf_ws")
    matched = [d for d in docs if d["document_id"] == "Финансы/Счета/invoice_77.md"]
    assert len(matched) == 1
    assert matched[0]["paperless_id"] == 105

    git_log = wm._run_git(ws_path, ["log", "-n", "5", "--oneline"])
    assert "Добавлен счёт №77 от ООО Альфа на 15 000 руб. в Финансы/Счета" in git_log
    assert wd.get_status()["stats"]["pdf_processed"] == 1


@pytest.mark.asyncio
async def test_watchdog_pdf_update_passes_diff_to_gemini(isolated_env) -> None:
    """При обновлении PDF в Gemini передаётся diff прежнего .md, и коммит формулируется по изменениям."""
    wm, cfg_path = isolated_env
    ws_path = Path(wm.registry.get_workspace("pdf_ws")["path"])
    target_folder = ws_path / "Договоры"
    target_folder.mkdir(parents=True, exist_ok=True)
    (target_folder / "contract_12.md").write_text("# Договор №12\n\nСрок действия: до 31.12.2026.\n", encoding="utf-8")

    pdf_file = ws_path / "contract_12.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 updated contract")

    fake_conn = _fake_paperless_connector(
        paperless_id=208,
        content="Срок действия: до 31.12.2027.",
        title="Договор №12",
    )

    seen_payloads = []

    def _chat_factory(system_instruction: str, provider: str, model: str):
        mock_chat = MagicMock()

        async def _ask(q: str, **kwargs):
            seen_payloads.append(json.loads(q))
            return json.dumps({
                "target_dir": "Договоры",
                "commit_message": "Продлён срок действия договора №12 до 31.12.2027",
            }, ensure_ascii=False)

        mock_chat.ask = _ask
        return mock_chat

    pipeline = WatchdogPdfPipeline(
        workspace_manager=wm,
        paperless_factory=lambda: fake_conn,
        chat_model_factory=_chat_factory,
    )
    wd = WorkspaceWatchdogService(workspace_manager=wm, config_path=cfg_path, pdf_pipeline=pipeline)

    res = await wd.process_file_event(
        WatchTarget(kind="workspace", workspace_id="pdf_ws", root_path=ws_path),
        pdf_file,
        "modified",
    )

    assert res["status"] == "ok"
    assert res["document_id"] == "Договоры/contract_12.md"
    assert seen_payloads[0]["is_update"] is True
    assert seen_payloads[0]["previous_dir"] == "Договоры"
    assert "31.12.2027" in seen_payloads[0]["diff_snippet"]

    git_log = wm._run_git(ws_path, ["log", "-n", "5", "--oneline"])
    assert "Продлён срок действия договора №12 до 31.12.2027" in git_log


@pytest.mark.asyncio
async def test_watchdog_linked_source_pdf_and_offline_fallback(isolated_env, tmp_path: Path) -> None:
    """PDF из внешней папки также обрабатывается; при сбое Paperless/Gemini срабатывает безопасный fallback."""
    wm, cfg_path = isolated_env
    ws_path = Path(wm.registry.get_workspace("pdf_ws")["path"])
    ext_dir = tmp_path / "external_inbox"
    ext_dir.mkdir(parents=True, exist_ok=True)
    ext_pdf = ext_dir / "tax_invoice.pdf"
    ext_pdf.write_bytes(b"%PDF-1.4 offline")

    offline_conn = MagicMock()
    offline_conn.ping.return_value = False
    offline_conn.close.return_value = None

    def _broken_chat(system_instruction: str, provider: str, model: str):
        m = MagicMock()
        m.ask = AsyncMock(side_effect=RuntimeError("Gemini offline"))
        return m

    pipeline = WatchdogPdfPipeline(
        workspace_manager=wm,
        paperless_factory=lambda: offline_conn,
        chat_model_factory=_broken_chat,
    )
    wd = WorkspaceWatchdogService(workspace_manager=wm, config_path=cfg_path, pdf_pipeline=pipeline)

    with patch.object(
        wm.extractor,
        "extract",
        new=AsyncMock(return_value={"text": "Налоговый invoice и чек оплаты за ноябрь."}),
    ):
        res = await wd.process_file_event(
            WatchTarget(kind="linked_source", workspace_id="pdf_ws", root_path=ext_dir),
            ext_pdf,
            "created",
        )

    assert res["status"] == "ok"
    assert res["ocr_source"] == "extractor_fallback"
    assert res["evaluated_by"] == "local_fallback"
    assert res["target_dir"] == "Финансы и Бухгалтерия"
    assert (ws_path / "Финансы и Бухгалтерия" / "tax_invoice.md").exists()


def test_sanitization_and_gemini_candidate_resolution() -> None:
    """Проверяет защиту от Path Traversal и извлечение Gemini-моделей из конфигурации."""
    assert sanitize_target_dir("../../.git/hooks") == "hooks"
    assert sanitize_target_dir(".workspace/_Topics/assets") == "Документы"
    assert sanitize_target_dir("Финансы/Счета:2026") == "Финансы/Счета_2026"

    fake_cfg = SimpleNamespace(
        default_provider="agy",
        default_model="agy-gemini-3.1-flash-lite",
        providers=SimpleNamespace(
            gemini=SimpleNamespace(enabled=True, default_model="gemini-3.5-flash"),
            agy=SimpleNamespace(enabled=True, default_model="agy-gemini-3.1-flash-lite"),
            gemini_cli=SimpleNamespace(enabled=False, default_model="gemini-2.5-flash"),
        ),
    )
    cands = resolve_gemini_candidates(fake_cfg)
    assert cands == [("agy", "agy-gemini-3.1-flash-lite"), ("gemini", "gemini-3.5-flash")]

    formatted = format_paperless_markdown("doc.pdf", "Текст документа", paperless_id=7)
    assert formatted.startswith("# doc\n")
    assert "Paperless ID: `#7`" in formatted
