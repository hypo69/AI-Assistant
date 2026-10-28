# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Tests - Tab Models & API Tests
# =============================================================================
# Description:
#   Комплексное тестирование вкладки tab_models, статических файлов WebGUI
#   и серверных API эндпоинтов управления моделями, провайдерами, API-ключами
#   (Gemini, AGY) и Google-аккаунтами.
#
# File: test_models_tab_and_api.py
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-22 16:25:00
# =============================================================================

from __future__ import annotations
"""Тесты для модуля tab_models и REST API моделей, провайдеров и ключей."""

import pytest
from httpx import ASGITransport, AsyncClient

from apps.ai_assistant.main import app


@pytest.mark.asyncio
async def test_tab_models_static_assets() -> None:
    """Проверяет доступность разметки и клиентских скриптов tab_models."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Проверка главной разметки index.html для вкладки tab_models
        res_html = await client.get("/html/tab_models/index.html")
        assert res_html.status_code == 200
        content = res_html.text
        assert "provider-tab-select" in content
        assert "models-tab-select" in content
        assert "pill-gemini" in content
        assert "pill-agy" in content
        assert "pill-google-accounts" in content
        assert "keys-table" in content

        # Проверка главного скрипта оркестратора main.js
        res_js = await client.get("/html/tab_models/main.js")
        assert res_js.status_code == 200
        assert "initModelsTab" in res_js.text

        # Проверка утилит
        res_utils = await client.get("/html/tab_models/common/ui_utils.js")
        assert res_utils.status_code == 200
        assert "apiFetch" in res_utils.text

        # Проверка панели каталога моделей
        res_cat = await client.get("/html/tab_models/panel_models_catalog/panel.js")
        assert res_cat.status_code == 200
        assert "loadTabModels" in res_cat.text

        res_cat_test = await client.get("/html/tab_models/panel_models_catalog/test.js")
        assert res_cat_test.status_code == 200
        assert "executeModelTest" in res_cat_test.text

        # Проверка панели ключей Gemini
        res_gemini = await client.get("/html/tab_models/panel_gemini_keys/panel.js")
        assert res_gemini.status_code == 200
        assert "refreshKeysList" in res_gemini.text

        # Проверка панели ключей AGY
        res_agy = await client.get("/html/tab_models/panel_agy_keys/panel.js")
        assert res_agy.status_code == 200
        assert "refreshAgyKeysList" in res_agy.text

        # Проверка панели Google-аккаунтов
        res_gacc = await client.get("/html/tab_models/panel_google_accounts/panel.js")
        assert res_gacc.status_code == 200
        assert "refreshGoogleAccountsList" in res_gacc.text

        # Проверка панели настроек провайдеров
        res_providers = await client.get("/html/tab_models/panel_providers_config/panel.js")
        assert res_providers.status_code == 200
        assert "loadFoundryConfig" in res_providers.text


@pytest.mark.asyncio
async def test_tab_models_navigation_in_index() -> None:
    """Проверяет интеграцию tab_models в главный index.html."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/")
        assert res.status_code == 200
        html = res.text
        assert 'data-tab="tab-models"' in html
        assert 'id="tab-models"' in html


@pytest.mark.asyncio
async def test_models_and_providers_api_endpoints() -> None:
    """Проверяет серверные эндпоинты каталога моделей и конфигурации провайдеров."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Проверка каталога моделей
        res_models = await client.get("/api/v1/chat/models")
        assert res_models.status_code == 200
        models_data = res_models.json()
        assert isinstance(models_data, dict)
        assert "models" in models_data or "gemini" in models_data

        # Проверка активной модели
        res_active = await client.get("/api/v1/chat/active-model")
        assert res_active.status_code == 200
        active_data = res_active.json()
        assert "model" in active_data

        # Проверка совместимого эндпоинта /api/v1/tc/model
        res_tc = await client.get("/api/v1/tc/model")
        assert res_tc.status_code == 200
        tc_data = res_tc.json()
        assert "model" in tc_data

        # Проверка сводки моделей
        res_summary = await client.get("/api/v1/models/summary")
        assert res_summary.status_code == 200
        summary_data = res_summary.json()
        assert summary_data["status"] == "active"
        assert "providers" in summary_data
        assert "default_model" in summary_data

        # Проверка настроек провайдеров (Foundry, Ollama, AGY, ONNX)
        res_foundry = await client.get("/api/foundry/config")
        assert res_foundry.status_code == 200

        res_ollama = await client.get("/api/ollama/config")
        assert res_ollama.status_code == 200

        res_agy = await client.get("/api/agy/config")
        assert res_agy.status_code == 200

        res_onnx = await client.get("/api/onnx/config")
        assert res_onnx.status_code == 200


@pytest.mark.asyncio
async def test_keys_and_accounts_api_endpoints() -> None:
    """Проверяет серверные эндпоинты ключей API (Gemini, AGY) и Google-аккаунтов."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Проверка списка ключей Gemini
        res_keys = await client.get("/api/keys/")
        assert res_keys.status_code == 200
        keys_data = res_keys.json()
        assert isinstance(keys_data, list)

        # Проверка списка ключей AGY
        res_agy_keys = await client.get("/api/keys/agy")
        assert res_agy_keys.status_code == 200
        agy_data = res_agy_keys.json()
        assert isinstance(agy_data, list)

        # Проверка списка Google-аккаунтов
        res_accs = await client.get("/api/v1/auth/google-accounts")
        assert res_accs.status_code == 200
        accs_data = res_accs.json()
        assert isinstance(accs_data, dict)
        assert "accounts" in accs_data
