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
# Updated: 2026-10-28 05:07:00
# =============================================================================

from __future__ import annotations
"""Тестирование сценария Telegram-бота для рабочего пространства דוד משה."""

import asyncio
from pathlib import Path
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
    assert "שיחה בין דוד משה לשמוליק.md" in file_names

    added_item = next(i for i in dir_contents["items"] if i["name"] == "שיחה בין דוד משה לשמוליק.md")
    assert added_item["tracked_by_git"] is True
    assert "שיחה בין דוד משה לשמוליק.md" in str(added_item.get("local_path") or added_item.get("rel_path"))
