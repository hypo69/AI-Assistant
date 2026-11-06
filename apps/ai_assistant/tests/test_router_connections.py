# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Assistant Tests - Connections & Instruments Routers Test Suite
# =============================================================================
# Description:
#   Интеграционные тесты FastAPI эндпоинтов для базы инструментов и
#   управления сетевыми подключениями (/api/v1/ai-instruments/* и /api/v1/connections/*).
#
# File: test_router_connections.py
# Project: ai-assistant
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-03 16:45:00
# =============================================================================

from __future__ import annotations

"""Интеграционные тесты REST API эндпоинтов инструментов и соединений."""

import pytest
from fastapi.testclient import TestClient
from apps.ai_assistant.main import app

client = TestClient(app)


def test_ai_instruments_status_endpoint():
    """Проверка эндпоинта /api/v1/ai-instruments/status."""
    res = client.get("/api/v1/ai-instruments/status")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "active_engine" in data
    assert "tools_count" in data


def test_ai_instruments_crud_and_execute_endpoint():
    """Проверка создания, чтения, выполнения и удаления инструмента через API."""
    payload = {
        "tool_id": "inst_api_test_tool",
        "name": "Инструмент проверки API",
        "tool_type": "python",
        "command": "print('hello_api_instruments')",
        "description": "Тестирование через REST API",
        "target_entity": "test:api",
    }
    save_res = client.post("/api/v1/ai-instruments/save", json=payload)
    assert save_res.status_code == 200
    assert save_res.json()["status"] == "ok"

    # Чтение
    get_res = client.get("/api/v1/ai-instruments/item/inst_api_test_tool")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Инструмент проверки API"

    # Выполнение
    exec_res = client.post(
        "/api/v1/ai-instruments/execute",
        json={"tool_id": "inst_api_test_tool", "parameters": {}},
    )
    assert exec_res.status_code == 200
    assert exec_res.json()["success"] is True
    assert "hello_api_instruments" in exec_res.json()["stdout"]

    # Удаление
    del_res = client.delete("/api/v1/ai-instruments/item/inst_api_test_tool")
    assert del_res.status_code == 200
    assert del_res.json()["deleted"] is True


def test_ai_instruments_extract_from_reasoning_endpoint():
    """Проверка извлечения инструментов из текста рассуждений через API."""
    text = """
    В ходе рассуждения выделим вспомогательный расчет:
    ```python
    x = 100
    print(x * 2)
    ```
    """
    res = client.post(
        "/api/v1/ai-instruments/extract-from-reasoning",
        json={"text": text, "target_entity": "reasoning:calc"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["extracted_count"] == 1


def test_connections_get_and_save_config():
    """Проверка получения и сохранения конфигурации сетевых соединений."""
    res_get = client.get("/api/v1/connections/config")
    assert res_get.status_code == 200
    assert isinstance(res_get.json(), dict)

    # Сохранение обновленной секции
    update_payload = {
        "ftp": {
            "host": "ftp.test.local",
            "port": 21,
            "username": "tester",
        }
    }
    res_save = client.post("/api/v1/connections/save", json=update_payload)
    assert res_save.status_code == 200
    assert res_save.json()["status"] == "ok"
    assert res_save.json()["config"]["ftp"]["host"] == "ftp.test.local"


def test_connections_test_sqlite_endpoint():
    """Проверка тестирования подключения к SQLite через API."""
    test_req = {
        "service_type": "sqlite",
        "config": {"path": "data/ai_instruments/ai_instruments.db"},
    }
    res = client.post("/api/v1/connections/test", json=test_req)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "latency_ms" in data
