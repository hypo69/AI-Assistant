# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Tests - Telegram Workspace Scenario
# =============================================================================
# Description:
#   Набор юнит- и интеграционных тестов для специального сценария обработки
#   рабочего пространства «דוד משה» при добавлении файла «שיחה בין דוד משה לשמוליק»
#   через Telegram-бота или REST API (10-секундный спиннер и добавление файла
#   "C:\Users\onela\Desktop\דוד מושה — רשימת מסמכים\שיחה בין דוד משה לשמוליק.md").
#
# File: test_telegram_workspace_scenario.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 00:20:00
# =============================================================================

from __future__ import annotations
"""Тестирование сценария Telegram-бота для рабочего пространства דוד משה."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest

from apps.ai_assistant.core.telegram_workspace_scenario import TelegramWorkspaceScenarioService
from apps.ai_assistant.core.workspace_manager import WorkspaceManager


def test_david_moshe_workspace_and_trigger_matching() -> None:
    """Проверяет распознавание пространства «דוד משה» и входного файла «שיחה בין דוד משה לשמוליק»."""
    service = TelegramWorkspaceScenarioService()

    assert service.is_david_moshe_workspace("דוד משה") is True
    assert service.is_david_moshe_workspace("דוד_משה") is True
    assert service.is_david_moshe_workspace("דוד מושה") is True
    assert service.is_david_moshe_workspace("other_workspace") is False

    assert service.is_trigger_file("שיחה בין דוד משה לשמוליק") is True
    assert service.is_trigger_file("שיחה בין דוד משה לשמוליק.md") is True
    assert service.is_trigger_file("שיחה_בין_דוד_משה_לשמוליק.ogg") is True
    assert service.is_trigger_file("random_audio.mp3") is False


@pytest.mark.asyncio
async def test_telegram_scenario_spinner_and_file_addition(tmp_path: Path) -> None:
    """Проверяет запуск спиннера, отсчёт времени и добавление целевого файла в рабочую область דוד משה."""
    target_desktop_file = Path(r"C:\Users\onela\Desktop\דוד מושה — רשימת מסמכים\שיחה בין דוד משה לשמוליק.md")
    if not target_desktop_file.exists():
        target_desktop_file = tmp_path / "שיחה בין דוד משה לשמוליק.md"
        target_desktop_file.write_text("דוד משה: בוקר טוב שמוליק.\nשמוליק: בוקר אור דוד משה.", encoding="utf-8")

    state_file = tmp_path / "telegram_scenario_state.json"
    service = TelegramWorkspaceScenarioService(state_file=state_file)
    wm = WorkspaceManager(
        base_dir=tmp_path / "data_ai",
        workspaces_dir=tmp_path / "workspaces",
    )
    wm.create_or_select_workspace("דוד_משה", name="דוד משה")

    # 1. Запускаем сценарий (спиннер) с короткой задержкой для теста
    initial_state = await service.trigger_scenario(
        wm=wm,
        workspace_id="דוד_משה",
        trigger_source="telegram_bot",
        trigger_file_name="שיחה בין דוד משה לשמוליק",
        delay_seconds=0.2,
        wait_for_completion=False,
    )
    assert initial_state["status"] == "processing"
    assert initial_state["workspace_id"] == "דוד_משה"

    # 2. Ждём завершения таймера спиннера
    await asyncio.sleep(0.35)
    final_state = await service.get_status(wm)
    assert final_state["status"] == "completed"

    # 3. Проверяем, что файл добавлен в рабочую область דוד_משה и отслеживается Git
    dir_contents = wm.get_directory_contents("דוד_משה")
    file_names = [item["name"] for item in dir_contents["items"]]
    added_filename = Path(final_state.get("target_file_name") or final_state.get("target_file_path") or "02_transcript_david_moshe_shmulik_v3.md").name
    assert added_filename in file_names

    added_item = next(i for i in dir_contents["items"] if i["name"] == added_filename)
    assert added_item["tracked_by_git"] is True
    assert added_filename in str(added_item.get("local_path") or added_item.get("rel_path"))


def test_david_moshe_audio_trigger_matching() -> None:
    """Проверяет распознавание триггерного аудиофайла דוד משה - שמוליק שיחת טלפון.mp3."""
    service = TelegramWorkspaceScenarioService()
    assert service.is_trigger_file("דוד משה - שמוליק שיחת טלפון.mp3") is True
    assert service.is_trigger_file("דוד משה - שמוליק שיחת טלפון") is True
    assert service.is_trigger_file("דוד משה שמוליק שיחת טלפון") is True
    assert service.is_trigger_file("02_transcript_david_moshe_shmulik_v3.md") is True


@pytest.mark.asyncio
async def test_david_moshe_audio_upload_copies_transcript(tmp_path: Path) -> None:
    """Проверяет, что при загрузке аудиофайла דוד משה файл транскрипта размещается в transcripts/ с Obsidian-разметкой и заметками сущностей."""
    # Создаем фиктивный файл транскрипта
    fake_transcript_src = tmp_path / "02_transcript_david_moshe_shmulik_v3.md"
    fake_transcript_text = "# Стенограмма беседы דוד משה и שמוליק\n\nדוד משה: שלום שמוליק.\nשמוליק: שלום דוד משה."
    fake_transcript_src.write_text(fake_transcript_text, encoding="utf-8")

    wm = WorkspaceManager(
        base_dir=tmp_path / "data_ai",
        workspaces_dir=tmp_path / "workspaces",
    )
    ws_id = "דוד_משה"
    wm.create_or_select_workspace(ws_id, name="דוד משה")

    audio_filename = "דוד משה - שמוליק שיחת טלפון.mp3"
    fake_audio_bytes = b"ID3\x03\x00\x00\x00" + b"\x00" * 200

    # Переопределяем путь к транскрипту для теста через patch конфигурации сценария
    orig_load_cfg = wm.scenario_service.load_scenario_config
    def mock_load_cfg():
        cfg = orig_load_cfg()
        cfg["target_file_path"] = str(fake_transcript_src)
        return cfg

    with patch.object(wm.scenario_service, "load_scenario_config", side_effect=mock_load_cfg):
        with patch("apps.ai_assistant.core.content_extractor.audio2text", new_callable=AsyncMock) as mock_a2t:
            mock_a2t.return_value = "Текст распознавания аудио"
            upload_res = await wm.add_uploaded_files(
                workspace_id=ws_id,
                files_data=[(audio_filename, fake_audio_bytes)],
                commit_message="Тест загрузки аудио דוד משה",
            )

    assert upload_res["status"] == "ok"
    assert upload_res["files_added"] >= 1

    ws_path = wm.registry.workspace_path(ws_id)
    dest_audio = ws_path / "assets" / audio_filename
    dest_transcript = ws_path / "transcripts" / "02_transcript_david_moshe_shmulik_v3.md"
    companion_md = ws_path / "assets" / f"{audio_filename}.md"

    # 1. Проверяем, что аудиофайл сохранен в assets/
    assert dest_audio.exists()
    assert dest_audio.read_bytes() == fake_audio_bytes

    # 2. Транскрипт размещён в transcripts/ в Obsidian-формате (frontmatter + вложение аудио + wikilinks)
    assert dest_transcript.exists()
    transcript_md = dest_transcript.read_text(encoding="utf-8")
    assert transcript_md.startswith("---")
    assert f"![[assets/{audio_filename}]]" in transcript_md
    assert "[[שמוליק]]" in transcript_md

    # 3. Проверяем, что companion markdown для аудиофайла содержит стенограмму
    assert companion_md.exists()
    assert "דוד משה" in companion_md.read_text(encoding="utf-8")

    # 4. Транскрипт и заметки сущностей зарегистрированы в KnowledgeStore
    doc_ids = [d.get("document_id") for d in wm.store.list_documents(ws_id)]
    assert "transcripts/02_transcript_david_moshe_shmulik_v3.md" in doc_ids
    assert "entities/זינה.md" in doc_ids
    assert "deals/עסקת רכישת זינה.md" in doc_ids