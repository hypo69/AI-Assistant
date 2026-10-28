# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Tests - Port Switch Lifecycle
# =============================================================================
# Description:
#   Модульные тесты переключателя подключения к существующему процессу / перезапуска
#   сервера при занятом сетевом порте 8002 (устранение WinError 10048).
#
# File: test_server_port_switch.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-25 19:40:00
# =============================================================================

from __future__ import annotations
"""Тестирование механизма разрешения конфликта сетевого порта и выбора режима работы."""

import socket
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from apps.ai_assistant.main import (
    is_port_in_use,
    kill_process_on_port,
    resolve_occupied_port_action,
    run,
)


def test_is_port_in_use_free_and_occupied() -> None:
    """Проверяет корректность определения свободного и занятого порта сокетом."""
    # Создаём реальный слушающий сокет на временном свободном порту
    test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    test_sock.bind(("127.0.0.1", 0))
    test_sock.listen(1)
    allocated_port = test_sock.getsockname()[1]

    try:
        # Порт сейчас занят
        assert is_port_in_use(allocated_port, "127.0.0.1") is True
    finally:
        test_sock.close()

    # После закрытия сокета порт должен стать свободным
    assert is_port_in_use(allocated_port, "127.0.0.1") is False


def test_resolve_occupied_port_action_explicit_user_choice() -> None:
    """Проверяет приоритет явного выбора пользователя через CLI-аргументы."""
    assert resolve_occupied_port_action(8002, user_choice="connect") == "connect"
    assert resolve_occupied_port_action(8002, user_choice="restart") == "restart"


def test_resolve_occupied_port_action_from_config() -> None:
    """Проверяет выбор стратегии из конфигурационного файла, если CLI-флаг не передан."""
    assert resolve_occupied_port_action(8002, on_occupied_config="connect") == "connect"
    assert resolve_occupied_port_action(8002, on_occupied_config="restart") == "restart"


def test_resolve_occupied_port_action_interactive_connect(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет интерактивный выбор подключения (ввод '1' или нажатие Enter)."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    assert resolve_occupied_port_action(8002) == "connect"

    monkeypatch.setattr("builtins.input", lambda prompt="": "1")
    assert resolve_occupied_port_action(8002) == "connect"


def test_resolve_occupied_port_action_interactive_restart(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет интерактивный выбор перезапуска (ввод '2' или 'restart')."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt="": "2")
    assert resolve_occupied_port_action(8002) == "restart"

    monkeypatch.setattr("builtins.input", lambda prompt="": "r")
    assert resolve_occupied_port_action(8002) == "restart"


def test_resolve_occupied_port_action_non_interactive_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет безопасный fallback на 'connect' при неинтерактивном запуске (CI, background)."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert resolve_occupied_port_action(8002) == "connect"


@patch("apps.ai_assistant.main.launch_gui")
@patch("apps.ai_assistant.main.is_port_in_use", return_value=True)
def test_run_when_occupied_connect_mode(mock_in_use: MagicMock, mock_launch_gui: MagicMock) -> None:
    """Проверяет, что при режиме 'connect' сервер uvicorn не запускается, а сразу открывается GUI."""
    with patch("apps.ai_assistant.main.resolve_occupied_port_action", return_value="connect"):
        with patch("uvicorn.Server.run") as mock_server_run:
            run(port=8002, action="connect", engine="electron")
            # Сервер не должен запускаться повторно
            mock_server_run.assert_not_called()
            # Оболочка GUI должна быть открыта
            mock_launch_gui.assert_called_once()
            call_url = mock_launch_gui.call_args[0][0]
            assert "8002" in call_url


@patch("apps.ai_assistant.main.launch_gui")
@patch("apps.ai_assistant.main.kill_process_on_port", return_value=True)
def test_run_when_occupied_restart_mode(mock_kill: MagicMock, mock_launch_gui: MagicMock) -> None:
    """Проверяет, что при режиме 'restart' старый процесс завершается и запускается новый сервер."""
    # Сначала порт занят, после kill освобождается
    port_states = [True, False, False]

    def mock_is_occupied(*args: any, **kwargs: any) -> bool:
        if port_states:
            return port_states.pop(0)
        return False

    with patch("apps.ai_assistant.main.is_port_in_use", side_effect=mock_is_occupied):
        with patch("apps.ai_assistant.main.resolve_occupied_port_action", return_value="restart"):
            with patch("threading.Thread") as mock_thread:
                run(port=8002, action="restart", engine="electron")
                mock_kill.assert_called_once_with(8002)
                mock_thread.assert_called_once()
                mock_launch_gui.assert_called_once()
