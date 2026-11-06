# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-assistant Apps AI_Assistant Tests - Telegram Workspace Media
# =============================================================================
# Description:
#   Тесты переключения рабочих областей через Telegram (/workspace «דוד משה»),
#   сохранения оригиналов аудиофайлов (*.mp3) в папку assets/ рабочей области
#   и транскрибации контента с добавлением в базу знаний без затирания бинарных данных.
#
# File: test_telegram_workspace_media.py
# Project: ai-assistant
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-06 20:15:00
# =============================================================================

from __future__ import annotations
"""Тестирование переключения рабочих областей и конвейера обработки аудиофайлов."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from apps.ai_assistant.core.workspace_manager import WorkspaceManager
from plugins.telegram_bot import user_auth as user_manager
from plugins.telegram_bot.workspace_handler import (
    get_effective_user_workspace,
    handle_incoming_media,
    handle_workspace_callback,
    handle_workspace_command,
    resolve_workspace,
)


def test_user_auth_workspace_storage(tmp_path: Path) -> None:
    """Проверяет сохранение и получение выбранной рабочей области пользователя Telegram."""
    fake_auth = tmp_path / "telegram_auth.json"
    with patch("plugins.telegram_bot.user_auth._AUTH_FILE", fake_auth):
        assert user_manager.get_user_workspace(12345) is None

        user_manager.set_user_workspace(12345, "דוד_משה")
        assert user_manager.get_user_workspace(12345) == "דוד_משה"

        # Проверка для другого пользователя
        user_manager.set_user_workspace(67890, "workspace_b")
        assert user_manager.get_user_workspace(67890) == "workspace_b"
        assert user_manager.get_user_workspace(12345) == "דוד_משה"


def test_resolve_david_moshe_workspace(tmp_path: Path) -> None:
    """Проверяет корректное распознавание и переключение на рабочую область דוד משה."""
    wm = WorkspaceManager(
        base_dir=tmp_path / "data_ai",
        workspaces_dir=tmp_path / "workspaces",
    )
    wm.create_or_select_workspace("דוד_משה", name="דוד משה")

    # Вариант с пробелом
    ws_id, ws_name = resolve_workspace(wm, "דוד משה")
    assert ws_id == "דוד_משה"
    assert "דוד" in ws_name

    # Вариант с подчеркиванием
    ws_id_2, _ = resolve_workspace(wm, "דוד_משה")
    assert ws_id_2 == "דוד_משה"

    # Вариант написания דוד מושה
    ws_id_3, _ = resolve_workspace(wm, "דוד מושה")
    assert ws_id_3 == "דוד_משה"


@pytest.mark.asyncio
async def test_audio_saved_to_assets_with_transcription(tmp_path: Path) -> None:
    """Проверяет сохранение оригинала *.mp3 в assets/ и транскрипцию в рабочей области без затирания файла."""
    wm = WorkspaceManager(
        base_dir=tmp_path / "data_ai",
        workspaces_dir=tmp_path / "workspaces",
    )
    ws_id = "test_audio_ws"
    wm.create_or_select_workspace(ws_id, name="Тестовая область")

    mp3_filename = "interview_david_moshe.mp3"
    fake_mp3_content = b"\xFF\xFB\x90\x44" + b"\x00" * 256  # Симуляция MP3 заголовка и фреймов

    # Мокируем аудио конвертер, чтобы не отправлять реальные сетевые запросы к Gemini в тесте
    with patch("apps.ai_assistant.core.content_extractor.audio2text", new_callable=AsyncMock) as mock_audio2text:
        mock_audio2text.return_value = "Привет, это расшифровка интервью דוד משה."

        upload_res = await wm.add_uploaded_files(
            workspace_id=ws_id,
            files_data=[(mp3_filename, fake_mp3_content)],
            commit_message="Тест добавления аудио",
            audio_mode="model",
        )

    assert upload_res["status"] == "ok"
    assert upload_res["files_added"] == 1

    ws_path = wm.registry.workspace_path(ws_id)
    dest_asset = ws_path / "assets" / mp3_filename
    companion_md = ws_path / "assets" / f"{mp3_filename}.md"

    # 1. Оригинальный бинарный файл сохранен в assets/ и НЕ затерт текстом
    assert dest_asset.exists()
    assert dest_asset.read_bytes() == fake_mp3_content

    # 2. Текст транскрипции записан в companion .md
    assert companion_md.exists()
    companion_text = companion_md.read_text(encoding="utf-8")
    assert "Привет, это расшифровка интервью דוד משה." in companion_text

    # 3. Документ зарегистрирован в базе знаний
    docs = wm.store.list_documents(ws_id)
    doc_ids = [d.get("document_id") for d in docs]
    assert f"assets/{mp3_filename}" in doc_ids


@pytest.mark.asyncio
async def test_handle_workspace_command_switch(tmp_path: Path) -> None:
    """Проверяет выполнение команды /workspace דוד משה в боте."""
    fake_auth = tmp_path / "telegram_auth.json"
    wm = WorkspaceManager(
        base_dir=tmp_path / "data_ai",
        workspaces_dir=tmp_path / "workspaces",
    )
    wm.create_or_select_workspace("דוד_משה", name="דוד משה")

    update = MagicMock()
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    update.effective_user.id = 99999

    context = MagicMock()
    context.args = ["דוד", "משה"]

    with patch("plugins.telegram_bot.user_auth._AUTH_FILE", fake_auth):
        await handle_workspace_command(update, context, wm)

        assert user_manager.get_user_workspace(99999) == "דוד_משה"
        assert update.message.reply_text.called
        reply_call = update.message.reply_text.call_args[0][0]
        assert "דוד משה" in reply_call


@pytest.mark.asyncio
async def test_incoming_audio_pipeline(tmp_path: Path) -> None:
    """Проверяет сквозную обработку входящего аудиофайла от пользователя в рабочую область."""
    fake_auth = tmp_path / "telegram_auth.json"
    wm = WorkspaceManager(
        base_dir=tmp_path / "data_ai",
        workspaces_dir=tmp_path / "workspaces",
    )
    wm.create_or_select_workspace("דוד_משה", name="דוד משה")

    update = MagicMock()
    status_msg = MagicMock()
    status_msg.edit_text = AsyncMock()
    update.message = MagicMock()
    update.message.reply_text = AsyncMock(return_value=status_msg)
    update.message.chat.send_action = AsyncMock()
    update.effective_user.id = 77777
    update.effective_user.first_name = "Давид"

    fake_file = MagicMock()
    fake_file.download_as_bytearray = AsyncMock(return_value=bytearray(b"MP3_DATA_CONTENT"))
    context = MagicMock()
    context.bot.get_file = AsyncMock(return_value=fake_file)

    attachment = MagicMock()
    attachment.file_id = "test_audio_file_123"

    with patch("plugins.telegram_bot.user_auth._AUTH_FILE", fake_auth):
        user_manager.set_user_workspace(77777, "דוד_משה")

        with patch("apps.ai_assistant.core.content_extractor.audio2text", new_callable=AsyncMock) as mock_a2t:
            mock_a2t.return_value = "Текст записи שיחה"

            await handle_incoming_media(
                update=update,
                context=context,
                wm=wm,
                attachment=attachment,
                default_filename="voice_recording.mp3",
                admin_ids=[77777],
                is_audio=True,
            )

        # Проверяем, что оригинал файла лежит в assets/ области דוד_משה
        ws_path = wm.registry.workspace_path("דוד_משה")
        saved_mp3 = ws_path / "assets" / "voice_recording.mp3"
        assert saved_mp3.exists()
        assert saved_mp3.read_bytes() == b"MP3_DATA_CONTENT"

        # Проверяем статусное сообщение пользователю
        assert status_msg.edit_text.called
        last_call_text = status_msg.edit_text.call_args[0][0]
        assert "דוד משה" in last_call_text
        assert "assets/voice_recording.mp3" in last_call_text


@pytest.mark.asyncio
async def test_bot_engine_workspace_command_registration() -> None:
    """Проверяет регистрацию команды /workspace и алиасов /w, /ws в TelegramBotEngine."""
    from plugins.telegram_bot.bot import TelegramBotEngine
    engine = TelegramBotEngine(token="123456789:ABCdefGHIjklMNOpqrSTUvwxYZ_1234567")
    with patch("telegram.ext.Application.initialize", new_callable=AsyncMock):
        ok = await engine.initialize()
        assert ok is True
        assert engine.app is not None

        cmd_handlers = [
            h for h in engine.app.handlers.get(0, [])
            if hasattr(h, "commands")
        ]
        all_cmds = set()
        for h in cmd_handlers:
            all_cmds.update(h.commands)

        assert "workspace" in all_cmds
        assert "ws" in all_cmds
        assert "w" in all_cmds
