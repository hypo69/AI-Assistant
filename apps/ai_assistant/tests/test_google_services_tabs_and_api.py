# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant Tests - Google Workspace Tabs & API
# =============================================================================
# Description:
#   Тестирование REST API маршрутизаторов Google Календаря, Google Диска,
#   Google Контактов, семантического поиска Gmail и раздачи статических ассетов вкладок.
#
# File: test_google_services_tabs_and_api.py
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 19:00:00
# =============================================================================

from __future__ import annotations

"""Модульные тесты для Google Workspace вкладок и маршрутизаторов API."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from apps.ai_assistant.main import app

client = TestClient(app)


def test_drive_files_api() -> None:
    """Проверяет endpoint листинга файлов Google Drive."""
    mock_files = [{"id": "f1", "name": "Document.pdf", "mimeType": "application/pdf"}]
    with patch("apps.ai_assistant.api.routers.router_drive.get_drive_client") as mock_get_client:
        mock_instance = MagicMock()
        mock_instance.list_files.return_value = mock_files
        mock_get_client.return_value = mock_instance

        resp = client.get("/api/v1/drive/files?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "success"
        assert len(data.get("files", [])) == 1
        assert data["files"][0]["name"] == "Document.pdf"


def test_drive_file_content_get_and_save_api() -> None:
    """Проверяет чтение и сохранение содержимого файла Google Drive для модального редактора."""
    mock_content = {
        "status": "success",
        "file_id": "file_123",
        "name": "Notes.md",
        "mime_type": "text/markdown",
        "content": "# Заметки Google Drive\nТестовый контент",
        "is_binary": False,
        "size": 42,
    }
    with patch("apps.ai_assistant.api.routers.router_drive.get_drive_client") as mock_get_client:
        mock_instance = MagicMock()
        mock_instance.get_file_content.return_value = mock_content
        mock_instance.update_file_content.return_value = {"status": "success", "file": {"id": "file_123", "name": "Notes.md"}}
        mock_get_client.return_value = mock_instance

        # 1. Чтение содержимого
        resp = client.get("/api/v1/drive/files/file_123/content")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "success"
        assert data.get("content") == "# Заметки Google Drive\nТестовый контент"
        assert data.get("is_binary") is False

        # 2. Сохранение нового содержимого
        save_resp = client.post(
            "/api/v1/drive/files/file_123/content",
            json={"content": "# Новые заметки\nОбновлено через веб-редактор", "mime_type": "text/markdown"},
        )
        assert save_resp.status_code == 200
        save_data = save_resp.json()
        assert save_data.get("status") == "success"
        mock_instance.update_file_content.assert_called_once_with(
            file_id="file_123",
            content="# Новые заметки\nОбновлено через веб-редактор",
            mime_type="text/markdown",
        )


def test_calendar_events_api() -> None:
    """Проверяет endpoint получения событий Google Календаря."""
    mock_events = [{"id": "ev1", "summary": "Архитектурная сессия", "start": "2026-10-28T10:00:00Z"}]
    with patch("apps.ai_assistant.api.routers.router_calendar.get_calendar_client") as mock_get_client:
        mock_instance = MagicMock()
        mock_instance.list_events.return_value = mock_events
        mock_get_client.return_value = mock_instance

        resp = client.get("/api/v1/calendar/events?days=7")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "success"
        assert len(data.get("events", [])) == 1
        assert data["events"][0]["summary"] == "Архитектурная сессия"


def test_contacts_api() -> None:
    """Проверяет endpoint телефонной книги Google Contacts."""
    mock_contacts = [{"resource_name": "people/c1", "display_name": "Алексей Иванов", "phones": [{"value": "+79991112233"}]}]
    with patch("apps.ai_assistant.api.routers.router_contacts.get_contacts_client") as mock_get_client:
        mock_instance = MagicMock()
        mock_instance.list_contacts.return_value = mock_contacts
        mock_get_client.return_value = mock_instance

        resp = client.get("/api/v1/contacts?limit=20")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "success"
        assert len(data.get("contacts", [])) == 1
        assert data["contacts"][0]["display_name"] == "Алексей Иванов"


def test_gmail_semantic_search_api() -> None:
    """Проверяет endpoint семантического ИИ-поиска писем Gmail."""
    mock_messages = [
        {"id": "m1", "subject": "Безопасность учетной записи GitHub", "snippet": "Обнаружена уязвимость", "from": "alerts@github.com"},
        {"id": "m2", "subject": "Планы на обед", "snippet": "Пойдем в кафе", "from": "friend@example.com"},
    ]
    with patch("apps.ai_assistant.api.routers.router_gmail.gmail_rag_service.semantic_search") as mock_search:
        mock_search.return_value = {
            "status": "success",
            "count": 1,
            "messages": [
                {
                    "id": "m1",
                    "subject": "Безопасность учетной записи GitHub",
                    "snippet": "Обнаружена уязвимость",
                    "from": "alerts@github.com",
                    "semantic_score": 0.95,
                }
            ],
        }

        resp = client.get("/api/v1/gmail/semantic_search?q=github+безопасность")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "success"
        assert data.get("count") >= 1
        first_msg = data["messages"][0]
        assert first_msg["id"] == "m1"
        assert "semantic_score" in first_msg
        assert first_msg["semantic_score"] > 0


def test_google_tabs_static_assets_served() -> None:
    """Проверяет доступность HTML и JS файлов для всех созданных вкладок."""
    endpoints = [
        "/html/tab_calendar/index.html",
        "/html/tab_calendar/main.js",
        "/html/tab_drive/index.html",
        "/html/tab_drive/main.js",
        "/html/tab_contacts/index.html",
        "/html/tab_contacts/main.js",
    ]
    for url in endpoints:
        resp = client.get(url)
        assert resp.status_code == 200, f"Не удалось загрузить статический файл {url}"
