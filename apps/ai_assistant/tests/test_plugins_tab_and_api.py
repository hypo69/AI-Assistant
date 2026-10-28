# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant Tests - Plugins Tab and API Suite
# =============================================================================
# Description:
#   Модульные и интеграционные тесты для REST API управления плагинами (/api/v1/plugins)
#   и проверки статических ассетов вкладки tab_plugins в WebGUI.
#
# File: test_plugins_tab_and_api.py
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-25 22:30:00
# =============================================================================

from __future__ import annotations

"""Тестирование REST API плагинов и интеграции вкладки tab_plugins."""

from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from header import __root__
from apps.ai_assistant.main import app


@pytest.mark.asyncio
async def test_plugins_tab_static_assets_exist() -> None:
    """Проверяет существование файлов вкладки tab_plugins на диске."""
    tab_dir = __root__ / "apps" / "ai_assistant" / "api" / "webgui" / "tab_plugins"
    assert tab_dir.exists(), f"Каталог {tab_dir} должен существовать"
    assert (tab_dir / "index.html").is_file(), "index.html вкладки tab_plugins должен существовать"
    assert (tab_dir / "main.js").is_file(), "main.js вкладки tab_plugins должен существовать"

    index_html = (__root__ / "apps" / "ai_assistant" / "api" / "webgui" / "index.html").read_text(encoding="utf-8")
    assert 'data-tab="tab-plugins"' in index_html, "Кнопка навигации на tab-plugins должна присутствовать в index.html"
    assert 'id="tab-plugins"' in index_html, "Контейнер tab-plugins должен присутствовать в index.html"


@pytest.mark.asyncio
async def test_api_list_plugins() -> None:
    """Проверяет эндпоинт GET /api/v1/plugins."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/plugins?lang=ru")
        assert res.status_code == 200
        plugins = res.json()
        assert isinstance(plugins, list)
        assert len(plugins) > 0

        plugin_names = [p.get("name") for p in plugins]
        assert "telegram_bot" in plugin_names
        assert "gdrive_sync" in plugin_names


@pytest.mark.asyncio
async def test_api_plugin_details_and_toggle() -> None:
    """Проверяет эндпоинты получения манифеста и переключения активности плагина."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Получение деталей плагина
        res = await client.get("/api/v1/plugins/telegram_bot?lang=ru")
        assert res.status_code == 200
        details = res.json()
        assert details["name"] == "telegram_bot"
        assert "actions" in details
        assert "tools" in details

        # 2. Переключение активности (toggle)
        res_toggle = await client.post(
            "/api/v1/plugins/telegram_bot/toggle",
            json={"enabled": True},
        )
        assert res_toggle.status_code == 200
        toggle_data = res_toggle.json()
        assert toggle_data["status"] == "success"
        assert toggle_data["enabled"] is True


@pytest.mark.asyncio
async def test_api_plugin_config_lifecycle() -> None:
    """Проверяет чтение и обновление параметров конфигурации плагина."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Чтение конфигурации
        res_cfg = await client.get("/api/v1/plugins/telegram_bot/config")
        assert res_cfg.status_code == 200
        data = res_cfg.json()
        assert "config" in data

        # Обновление конфигурации
        res_upd = await client.post(
            "/api/v1/plugins/telegram_bot/config",
            json={"config": {"test_param": "test_val"}},
        )
        assert res_upd.status_code == 200
        upd_data = res_upd.json()
        assert upd_data["status"] == "success"
        assert upd_data["config"].get("test_param") == "test_val"


@pytest.mark.asyncio
async def test_api_plugins_reload() -> None:
    """Проверяет вызов POST /api/v1/plugins/reload."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/v1/plugins/reload")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["count"] > 0


@pytest.mark.asyncio
async def test_api_plugins_marketplace_catalog() -> None:
    """Проверяет каталог стандартных плагинов в маркетплейсе."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/plugins/marketplace")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        assert len(data) >= 5

        # Проверяем структуру элементов маркетплейса
        ids = [item["id"] for item in data]
        assert "sqlite_db_viewer" in ids
        assert "python_ide_tools" in ids
        assert "markdown_notes" in ids
        assert "gitlens_inspector" in ids

        first = data[0]
        assert "id" in first
        assert "title" in first
        assert "description" in first
        assert "category" in first
        assert "installed" in first


@pytest.mark.asyncio
async def test_api_install_and_uninstall_marketplace_plugin() -> None:
    """Проверяет полный цикл установки и удаления стандартного плагина из маркетплейса."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        plugin_id = "sqlite_db_viewer"

        # 1. Установка плагина
        install_res = await client.post("/api/v1/plugins/install", json={"plugin_id": plugin_id})
        assert install_res.status_code == 200
        inst_data = install_res.json()
        assert inst_data["status"] in ("success", "already_installed")

        # 2. Проверка появления в списке установленных
        list_res = await client.get("/api/v1/plugins")
        assert list_res.status_code == 200
        plugin_names = [p.get("name") for p in list_res.json()]
        assert plugin_id in plugin_names

        # 3. Удаление плагина
        uninstall_res = await client.post(f"/api/v1/plugins/{plugin_id}/uninstall")
        assert uninstall_res.status_code == 200
        uninst_data = uninstall_res.json()
        assert uninst_data["status"] == "success"

        # 4. Проверка отсутствия после удаления
        list_after = await client.get("/api/v1/plugins")
        after_names = [p.get("name") for p in list_after.json()]
        assert plugin_id not in after_names
