# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Tests - Panel Router Tests
# =============================================================================
# Description:
#   Тестирование универсального роутера панелей /v1/panel/{panel_id} и отдачи
#   статических файлов WebGUI.
#
# File: test_panel_router.py
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-17 00:51:00
# =============================================================================

from __future__ import annotations
"""Тесты для роутера панелей /v1/panel/{panel_id} и статики WebGUI."""

import pytest
from httpx import ASGITransport, AsyncClient

from apps.ai_assistant.main import app


@pytest.mark.asyncio
async def test_panel_endpoints() -> None:
    """Проверяет эндпоинты панелей /v1/panel/{panel_id}."""
    panels = [
        "panel-timeline",
        "panel-commits",
        "panel-diff-stats",
        "panel-wikillm-entities",
        "panel-knowledge-links",
        "panel-rag-chunks",
        "panel-verification-pipeline",
        "panel-system-status",
    ]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for p in panels:
            # Проверка маршрута /v1/panel/{panel_id}
            res = await client.get(f"/v1/panel/{p}?limit=10")
            assert res.status_code == 200, f"Ошибка для {p}: {res.text}"
            data = res.json()
            assert data["status"] == "ok"
            assert data["panel_id"] == p
            assert "data" in data
            assert isinstance(data["data"], list)

            # Проверка схемы /api/v1/panel/{panel_id}
            res_alt = await client.get(f"/api/v1/panel/{p}?limit=5")
            assert res_alt.status_code == 200
            assert res_alt.json()["status"] == "ok"

            # Проверка метаданных SQL /v1/panel/{panel_id}/sql
            res_sql = await client.get(f"/v1/panel/{p}/sql")
            assert res_sql.status_code == 200
            sql_data = res_sql.json()
            assert "sql" in sql_data
            assert sql_data["panel_id"] == p


@pytest.mark.asyncio
async def test_webgui_static_serving() -> None:
    """Проверяет раздачу статических файлов и точек входа WebGUI."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Корневой маршрут
        res_root = await client.get("/")
        assert res_root.status_code == 200
        assert "AI Assistant" in res_root.text

        # Маршрут /html/index.html
        res_html = await client.get("/html/index.html")
        assert res_html.status_code == 200
        assert "panel-loader.js" in res_html.text

        # Разметка всех вкладок (tab_<tab_id>)
        all_tabs = [
            "tab_workspace",
            "tab_timeline",
            "tab_commits",
            "tab_diff",
            "tab_wikillm",
            "tab_graph",
            "tab_rag",
            "tab_verification",
            "tab_status",
        ]
        for t in all_tabs:
            res_tab = await client.get(f"/html/{t}/index.html")
            assert res_tab.status_code == 200, f"Ошибка загрузки вкладки {t}"
            assert len(res_tab.text) > 50

        # Локали i18n
        res_loc = await client.get("/html/locales/ru.json")
        assert res_loc.status_code == 200
        loc_data = res_loc.json()
        assert "tabs" in loc_data
        assert "userSettings" in loc_data
