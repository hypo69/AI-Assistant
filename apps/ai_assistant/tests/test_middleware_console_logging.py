# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant - Tests for Console Status Log Middleware
# =============================================================================
# Description:
#   Модульные тесты для промежуточного программного обеспечения
#   `ConsoleStatusLogMiddleware`. Проверяют раздельное логирование HTTP-запросов:
#   статусы 200 и 304 логируются только в консоль через `logger.console()`,
#   а остальные коды ответов (4xx, 5xx и др.) направляются в соответствующие уровни логгера.
#
# Usage Examples:
#   pytest apps/ai_assistant/tests/test_middleware_console_logging.py
#
# File: test_middleware_console_logging.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-07 00:38:00
# =============================================================================

from __future__ import annotations
"""Модульные тесты middleware избирательного консольного логирования."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, Response
from fastapi.testclient import TestClient

from apps.ai_assistant.api.middleware import ConsoleStatusLogMiddleware
from apps.ai_assistant.main import app as main_app


@pytest.fixture
def mock_app() -> FastAPI:
    """Создает изолированное FastAPI-приложение для тестирования middleware."""
    test_app = FastAPI()
    test_app.add_middleware(ConsoleStatusLogMiddleware)

    @test_app.get("/test/status-200")
    def get_200() -> dict[str, str]:
        return {"status": "ok"}

    @test_app.get("/test/status-304")
    def get_304() -> Response:
        return Response(status_code=304)

    @test_app.get("/test/status-404")
    def get_404() -> Response:
        return Response(status_code=404, content="Not found")

    @test_app.get("/test/status-500")
    def get_500() -> Response:
        return Response(status_code=500, content="Internal error")

    return test_app


def test_status_200_logged_only_to_console(mock_app: FastAPI) -> None:
    """Проверяет, что статус 200 логируется через logger.console со светло-серым цветом и не пишет в стандартный лог."""
    client = TestClient(mock_app)
    with patch("apps.ai_assistant.api.middleware.logger") as mock_logger:
        resp = client.get("/test/status-200")
        assert resp.status_code == 200
        mock_logger.console.assert_called_once()
        assert mock_logger.console.call_args.kwargs.get("text_color") in ("gray", "light_gray")
        mock_logger.info.assert_not_called()
        mock_logger.warning.assert_not_called()
        mock_logger.error.assert_not_called()


def test_status_304_logged_only_to_console(mock_app: FastAPI) -> None:
    """Проверяет, что статус 304 логируется только в консоль со светло-серым цветом."""
    client = TestClient(mock_app)
    with patch("apps.ai_assistant.api.middleware.logger") as mock_logger:
        resp = client.get("/test/status-304")
        assert resp.status_code == 304
        mock_logger.console.assert_called_once()
        assert mock_logger.console.call_args.kwargs.get("text_color") in ("gray", "light_gray")
        mock_logger.info.assert_not_called()
        mock_logger.warning.assert_not_called()
        mock_logger.error.assert_not_called()


def test_status_404_logged_as_warning(mock_app: FastAPI) -> None:
    """Проверяет, что статус 404 передается в logger.warning и не попадает в logger.console."""
    client = TestClient(mock_app)
    with patch("apps.ai_assistant.api.middleware.logger") as mock_logger:
        resp = client.get("/test/status-404")
        assert resp.status_code == 404
        mock_logger.console.assert_not_called()
        mock_logger.warning.assert_called_once()
        assert "404" in mock_logger.warning.call_args[0][0]


def test_status_500_logged_as_error(mock_app: FastAPI) -> None:
    """Проверяет, что статус 500 передается в logger.error."""
    client = TestClient(mock_app)
    with patch("apps.ai_assistant.api.middleware.logger") as mock_logger:
        resp = client.get("/test/status-500")
        assert resp.status_code == 500
        mock_logger.console.assert_not_called()
        mock_logger.error.assert_called_once()
        assert "500" in mock_logger.error.call_args[0][0]


def test_main_app_has_console_status_middleware() -> None:
    """Проверяет, что основное приложение AI Assistant содержит зарегистрированный ConsoleStatusLogMiddleware."""
    client = TestClient(main_app)
    with patch("apps.ai_assistant.api.middleware.logger.console") as mock_console:
        resp = client.get("/api/v1/health")
        if resp.status_code == 200:
            mock_console.assert_called()


def test_logger_color_attributes() -> None:
    """Проверяет наличие встроенных цветовых констант в объекте logger."""
    from logger import logger as real_logger

    assert hasattr(real_logger, "gray")
    assert real_logger.gray in ("gray", "light_gray")
    assert hasattr(real_logger, "white")
    assert real_logger.white == "white"
    assert hasattr(real_logger, "black")
    assert real_logger.black == "black"
    assert hasattr(real_logger, "green")
    assert real_logger.green == "green"
    assert hasattr(real_logger, "red")
    assert real_logger.red == "red"


def test_status_with_custom_colors() -> None:
    """Проверяет логирование с явным указанием цвета текста и фона через logger.gray и logger.white."""
    from logger import logger as real_logger

    custom_app = FastAPI()
    custom_app.add_middleware(
        ConsoleStatusLogMiddleware,
        console_color=real_logger.gray,
        console_bg_color=real_logger.white,
    )

    @custom_app.get("/custom-test")
    def get_custom() -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(custom_app)
    with patch("apps.ai_assistant.api.middleware.logger.console") as mock_console:
        resp = client.get("/custom-test")
        assert resp.status_code == 200
        mock_console.assert_called_once()
        assert mock_console.call_args.kwargs.get("text_color") in ("gray", "light_gray")
        assert mock_console.call_args.kwargs.get("bg_color") == "white"
