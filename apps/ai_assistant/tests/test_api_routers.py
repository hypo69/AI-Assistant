# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Tests - API Routers
# =============================================================================
# Description:
#   Интеграционные тесты REST API роутеров микросервиса AI Assistant:
#   история Git, построение таймлайна, аннотации, инвалидация и поиск.
#
# File: test_api_routers.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 09:30:00
# =============================================================================

from __future__ import annotations
"""Интеграционное тестирование REST API маршрутизаторов."""

import pytest
from starlette.testclient import TestClient
from apps.ai_assistant.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    """Проверка доступности эндпоинта /health."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "apps.ai_assistant"


def test_api_history_endpoint() -> None:
    """Проверка получения списка коммитов через /api/v1/history."""
    response = client.get("/api/v1/history?limit=3")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if len(data) > 0:
        assert "commit_hash" in data[0]
        assert "author" in data[0]


def test_api_timeline_endpoint() -> None:
    """Проверка построения таймлайна через /api/v1/timeline."""
    response = client.get("/api/v1/timeline?file_path=config.json&limit=3")
    assert response.status_code == 200
    data = response.json()
    assert data["file_path"] == "config.json"
    assert "checkpoints" in data


def test_api_annotate_and_links_lifecycle() -> None:
    """Проверка двухшагового создания аннотации и чтения графа связей."""
    payload = {
        "source_id": "test_commit_hash",
        "target_id": "test_wiki_entity",
        "relation_type": "modifies",
        "valid_from": "test_commit_hash",
        "summary": "Тестовая аннотация модуля",
        "confidence": 0.9,
        "provenance": "test_suite",
    }
    # 1. Создание аннотации
    post_res = client.post("/api/v1/annotate", json=payload)
    assert post_res.status_code == 200
    res_data = post_res.json()
    assert res_data["status"] == "verified_and_saved"
    assert res_data["verification_passed"] is True

    # 2. Чтение активных связей
    get_res = client.get("/api/v1/knowledge-links?source_id=test_commit_hash")
    assert get_res.status_code == 200
    links = get_res.json()
    assert any(lnk["target_id"] == "test_wiki_entity" for lnk in links)


def test_api_query_search() -> None:
    """Проверка параллельного гибридного поиска /api/v1/query."""
    query_payload = {
        "query": "config",
        "limit": 5,
    }
    response = client.post("/api/v1/query", json=query_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "config"
    assert "commits" in data
    assert "rag_chunks" in data
    assert "wiki_entities" in data
