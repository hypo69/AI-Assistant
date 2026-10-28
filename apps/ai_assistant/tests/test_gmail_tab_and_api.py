# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant - Gmail Tab and API Tests
# =============================================================================
# Description:
#   Модульные тесты для вкладки управления почтой Gmail (tab_gmail),
#   маршрутизатора router_gmail и ядра GmailManager.
#   Проверяет эндпоинты профиля, меток, выборки писем, валидацию отправки,
#   а также корректность регистрации вкладки в WebGUI и отдачу статических ассетов.
#
# File: test_gmail_tab_and_api.py
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-23 19:23:00
# =============================================================================

from __future__ import annotations
"""Тесты функциональности вкладки Gmail и REST API."""

import pytest
from fastapi.testclient import TestClient

from apps.ai_assistant.core.gmail_manager import GmailManager, gmail_manager
from apps.ai_assistant.main import app


@pytest.fixture
def client() -> TestClient:
    """Фикстура тестового клиента FastAPI."""
    return TestClient(app)


def test_gmail_manager_profile():
    """Проверяет получение сводного профиля пользователя."""
    profile = gmail_manager.get_profile()
    assert isinstance(profile, dict)
    assert profile.get("status") in ("success", "error")
    if profile.get("status") == "success":
        assert "email" in profile
        assert "@" in profile["email"]
        assert "messages_total" in profile
        assert profile["messages_total"] >= 0


def test_gmail_manager_labels():
    """Проверяет получение меток Gmail."""
    res = gmail_manager.list_labels()
    assert isinstance(res, dict)
    assert res.get("status") in ("success", "error")
    if res.get("status") == "success":
        assert isinstance(res.get("labels"), list)
        label_ids = [l.get("id") for l in res["labels"]]
        assert "INBOX" in label_ids


def test_gmail_manager_extract_payload():
    """Проверяет безопасное декодирование plain и HTML частей письма."""
    import base64
    gm = GmailManager()
    plain_text = "Тестовое сообщение"
    html_text = "<p>Тестовое сообщение HTML</p>"
    
    b64_plain = base64.urlsafe_b64encode(plain_text.encode("utf-8")).decode()
    b64_html = base64.urlsafe_b64encode(html_text.encode("utf-8")).decode()
    
    payload = {
        "mimeType": "multipart/alternative",
        "parts": [
            {
                "mimeType": "text/plain",
                "body": {"data": b64_plain},
            },
            {
                "mimeType": "text/html",
                "body": {"data": b64_html},
            },
            {
                "mimeType": "application/pdf",
                "filename": "invoice.pdf",
                "body": {"size": 1024, "attachmentId": "att_123"},
            },
        ],
    }

    plain, html, attachments = gm._extract_payload_content(payload)
    assert plain == plain_text
    assert html == html_text
    assert len(attachments) == 1
    assert attachments[0]["filename"] == "invoice.pdf"
    assert attachments[0]["size"] == 1024


def test_api_gmail_profile_endpoint(client: TestClient):
    """Проверяет REST эндпоинт GET /api/v1/gmail/profile."""
    resp = client.get("/api/v1/gmail/profile")
    assert resp.status_code in (200, 502)
    data = resp.json()
    if resp.status_code == 200:
        assert data["status"] == "success"
        assert "@" in data["email"]


def test_api_gmail_labels_endpoint(client: TestClient):
    """Проверяет REST эндпоинт GET /api/v1/gmail/labels."""
    resp = client.get("/api/v1/gmail/labels")
    assert resp.status_code in (200, 502)
    data = resp.json()
    if resp.status_code == 200:
        assert "labels" in data
        assert isinstance(data["labels"], list)


def test_api_gmail_messages_endpoint(client: TestClient):
    """Проверяет REST эндпоинт выборки сообщений GET /api/v1/gmail/messages."""
    resp = client.get("/api/v1/gmail/messages?limit=2")
    assert resp.status_code in (200, 502)
    data = resp.json()
    if resp.status_code == 200:
        assert data["status"] == "success"
        assert "messages" in data
        assert isinstance(data["messages"], list)


def test_api_gmail_send_validation(client: TestClient):
    """Проверяет валидацию обязательных полей при отправке письма."""
    # Пустой получатель
    resp = client.post("/api/v1/gmail/messages/send", json={"to": "", "subject": "Test", "body": "Body"})
    assert resp.status_code == 400

    # Пустая тема
    resp2 = client.post("/api/v1/gmail/messages/send", json={"to": "recipient@example.com", "subject": "", "body": "Body"})
    assert resp2.status_code == 400


def test_gmail_webgui_assets_served(client: TestClient):
    """Проверяет доступность HTML и JS ассетов вкладки tab_gmail."""
    r_html = client.get("/html/tab_gmail/index.html")
    assert r_html.status_code == 200
    assert "tab-gmail-container" in r_html.text
    assert "btn-gmail-compose" in r_html.text
    assert "gmail-search-input" in r_html.text

    r_js = client.get("/html/tab_gmail/main.js")
    assert r_js.status_code == 200
    assert "loadProfile" in r_js.text
    assert "loadMessages" in r_js.text
    assert "sendEmailSubmit" in r_js.text


def test_gmail_tab_registered_in_index_and_main_js(client: TestClient):
    """Проверяет регистрацию вкладки в главном index.html и скрипте main.js."""
    r_index = client.get("/")
    assert r_index.status_code == 200
    assert 'data-tab="tab-gmail"' in r_index.text
    assert 'id="tab-gmail"' in r_index.text
    assert 'id="top-nav-gmail-btn"' in r_index.text
    assert 'id="top-nav-gmail-badge"' in r_index.text

    r_main_js = client.get("/html/js/main.js")
    assert r_main_js.status_code == 200
    assert "'gmail':" in r_main_js.text or '"gmail":' in r_main_js.text
