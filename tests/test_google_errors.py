# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Google API Errors Parser
# =============================================================================
# Description:
#   Тесты для модуля парсинга, диагностики и обработки ошибок Google API
#   (src/utils/google_errors.py): проверка распознавания причин ошибок,
#   извлечения ID проекта, формирования прямых ссылок в Google Cloud Console
#   и генерации пошаговых рекомендаций.
#
# Usage Examples:
#   pytest tests/test_google_errors.py
#
# File: test_google_errors.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 18:45:00
# =============================================================================

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import pytest

from src.utils.google_errors import (
    ParsedGoogleError,
    parse_google_error,
    log_google_error,
    handle_google_errors,
)


USER_ERROR_SAMPLE = (
    '<HttpError 403 when requesting '
    'https://www.googleapis.com/calendar/v3/calendars/primary/events?'
    'timeMin=2026-10-28T16%3A03%3A04.595821%2B00%3A00&maxResults=50&singleEvents=true&'
    'orderBy=startTime&timeMax=2026-11-04T16%3A03%3A04.595821%2B00%3A00&alt=json '
    'returned "Google Calendar API has not been used in project 256600533244 before or it is disabled. '
    'Enable it by visiting https://console.developers.google.com/apis/api/calendar-json.googleapis.com/overview?project=256600533244 then retry. '
    'If you enabled this API recently, wait a few minutes for the action to propagate to our systems and retry.". '
    'Details: "[{\'message\': \'Google Calendar API has not been used in project 256600533244 before or it is disabled. '
    'Enable it by visiting https://console.developers.google.com/apis/api/calendar-json.googleapis.com/overview?project=256600533244 then retry. '
    'If you enabled this API recently, wait a few minutes for the action to propagate to our systems and retry.\', '
    '\'domain\': \'usageLimits\', \'reason\': \'accessNotConfigured\', \'extendedHelp\': \'https://console.developers.google.com\'}]">'
)


class DummyHttpResp:
    """Имитация HTTP ответа httplib2/googleapiclient."""

    def __init__(self, status: int, reason: str = "Forbidden") -> None:
        self.status = status
        self.reason = reason


class DummyHttpError(Exception):
    """Имитация googleapiclient.errors.HttpError."""

    def __init__(self, resp: DummyHttpResp, content: bytes, uri: str = "") -> None:
        super().__init__(f"<HttpError {resp.status} when requesting {uri} returned {content.decode('utf-8', errors='ignore')}>")
        self.resp = resp
        self.content = content
        self.uri = uri


def test_parse_user_error_string_access_not_configured() -> None:
    """Проверяет распознавание ошибки отключенного API из примера пользователя."""
    parsed = parse_google_error(USER_ERROR_SAMPLE)

    assert isinstance(parsed, ParsedGoogleError)
    assert parsed.status_code == 403
    assert parsed.reason == "accessNotConfigured"
    assert parsed.project_id == "256600533244"
    assert "Calendar" in parsed.service_name
    assert "calendar-json.googleapis.com" in (parsed.console_url or "")
    assert len(parsed.remediation_steps) >= 3
    assert any("Включите" in step or "Enable" in step for step in parsed.remediation_steps)

    err_dict = parsed.to_dict()
    assert err_dict["status"] == "error"
    assert err_dict["error_code"] == 403
    assert err_dict["reason"] == "accessNotConfigured"
    assert err_dict["project_id"] == "256600533244"
    assert "console_url" in err_dict


def test_parse_httperror_object_access_not_configured() -> None:
    """Проверяет разбор объекта HttpError с JSON телом."""
    json_payload = {
        "error": {
            "code": 403,
            "message": "Gmail API has not been used in project 123456789 before or it is disabled.",
            "errors": [
                {
                    "message": "Gmail API has not been used in project 123456789 before or it is disabled.",
                    "domain": "usageLimits",
                    "reason": "accessNotConfigured",
                    "extendedHelp": "https://console.developers.google.com/apis/api/gmail.googleapis.com/overview?project=123456789",
                }
            ],
            "status": "PERMISSION_DENIED",
        }
    }
    dummy_resp = DummyHttpResp(status=403, reason="Forbidden")
    dummy_exc = DummyHttpError(
        resp=dummy_resp,
        content=json.dumps(json_payload).encode("utf-8"),
        uri="https://gmail.googleapis.com/gmail/v1/users/me/messages",
    )

    parsed = parse_google_error(dummy_exc)

    assert parsed.status_code == 403
    assert parsed.reason == "accessNotConfigured"
    assert parsed.project_id == "123456789"
    assert "Gmail" in parsed.service_name
    assert "123456789" in (parsed.console_url or "")


def test_parse_insufficient_permissions() -> None:
    """Проверяет диагностику ошибки недостаточных OAuth scopes."""
    json_payload = {
        "error": {
            "code": 403,
            "message": "Request had insufficient authentication scopes.",
            "status": "PERMISSION_DENIED",
            "details": [
                {
                    "@type": "type.googleapis.com/google.rpc.ErrorInfo",
                    "reason": "ACCESS_TOKEN_SCOPE_INSUFFICIENT",
                    "domain": "googleapis.com",
                }
            ],
        }
    }
    dummy_resp = DummyHttpResp(status=403, reason="Forbidden")
    dummy_exc = DummyHttpError(
        resp=dummy_resp,
        content=json.dumps(json_payload).encode("utf-8"),
        uri="https://www.googleapis.com/drive/v3/files",
    )

    parsed = parse_google_error(dummy_exc)

    assert parsed.status_code == 403
    assert parsed.reason in ("ACCESS_TOKEN_SCOPE_INSUFFICIENT", "insufficientPermissions")
    assert any("OAuth" in step or "авторизац" in step for step in parsed.remediation_steps)


def test_parse_invalid_grant_token_expired() -> None:
    """Проверяет распознавание истекшего или отозванного токена OAuth (401)."""
    raw_text = '{"error": "invalid_grant", "error_description": "Token has been expired or revoked."}'
    parsed = parse_google_error(raw_text)

    assert parsed.status_code == 401
    assert parsed.reason == "invalid_grant"
    assert any("токен" in step.lower() or "авторизац" in step.lower() for step in parsed.remediation_steps)


def test_parse_rate_limit_exceeded() -> None:
    """Проверяет диагностику превышения квот (429 / rateLimitExceeded)."""
    raw_text = (
        '<HttpError 429 when requesting https://www.googleapis.com/... '
        'returned "User Rate Limit Exceeded". Details: "[{\'reason\': \'rateLimitExceeded\'}]">'
    )
    parsed = parse_google_error(raw_text)

    assert parsed.status_code == 429
    assert parsed.reason == "rateLimitExceeded"
    assert any("квот" in step.lower() or "повтор" in step.lower() for step in parsed.remediation_steps)


def test_log_google_error_outputs_to_console() -> None:
    """Проверяет логирование ошибки через logger.console."""
    from logger import logger as global_logger
    with patch.object(global_logger, "console") as mock_console:
        parsed = log_google_error(USER_ERROR_SAMPLE, context="TestContext")
        assert isinstance(parsed, ParsedGoogleError)
        assert mock_console.called
        # Проверяем, что в вывод попадает ссылка и ID проекта
        console_calls = [str(call.args) for call in mock_console.call_args_list]
        combined = " ".join(console_calls)
        assert "256600533244" in combined


def test_handle_google_errors_decorator_sync() -> None:
    """Проверяет декоратор handle_google_errors для синхронных функций."""
    @handle_google_errors(context="SyncCalendarCall")
    def faulty_func() -> str:
        raise DummyHttpError(
            resp=DummyHttpResp(status=403),
            content=b'{"error":{"message":"API disabled","errors":[{"reason":"accessNotConfigured"}]}}',
            uri="https://www.googleapis.com/calendar/v3/calendars",
        )

    with pytest.raises(RuntimeError) as exc_info:
        faulty_func()

    assert "accessNotConfigured" in str(exc_info.value) or "Google Calendar API" in str(exc_info.value)


@pytest.mark.asyncio
async def test_handle_google_errors_decorator_async() -> None:
    """Проверяет декоратор handle_google_errors для асинхронных функций."""
    @handle_google_errors(context="AsyncCalendarCall")
    async def faulty_async_func() -> str:
        raise DummyHttpError(
            resp=DummyHttpResp(status=403),
            content=b'{"error":{"message":"API disabled","errors":[{"reason":"accessNotConfigured"}]}}',
            uri="https://www.googleapis.com/calendar/v3/calendars",
        )

    with pytest.raises(RuntimeError) as exc_info:
        await faulty_async_func()

    assert "accessNotConfigured" in str(exc_info.value) or "Google Calendar API" in str(exc_info.value)


def test_router_calendar_handles_google_403_and_returns_structured_remediation() -> None:
    """Проверяет, что router_calendar при HttpError 403 возвращает статус 403 со структурой решения."""
    from fastapi.testclient import TestClient
    from apps.ai_assistant.main import app

    client = TestClient(app)

    with patch("apps.ai_assistant.api.routers.router_calendar.get_calendar_client") as mock_get_client:
        mock_instance = MagicMock()
        mock_instance.list_events.side_effect = DummyHttpError(
            resp=DummyHttpResp(status=403),
            content=b'{"error":{"message":"Google Calendar API has not been used in project 256600533244 before or it is disabled.","errors":[{"reason":"accessNotConfigured"}]}}',
            uri="https://www.googleapis.com/calendar/v3/calendars/primary/events",
        )
        mock_get_client.return_value = mock_instance

        resp = client.get("/api/v1/calendar/events")
        assert resp.status_code == 403
        data = resp.json()
        assert "detail" in data
        detail = data["detail"]
        assert detail["status"] == "error"
        assert detail["error_code"] == 403
        assert detail["reason"] == "accessNotConfigured"
        assert detail["project_id"] == "256600533244"
        assert len(detail["remediation_steps"]) >= 3
        assert "console_url" in detail

