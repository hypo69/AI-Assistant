"""
=============================================================================
Process Name: Test WebGUI Tab Menu Config REST API Router
=============================================================================
Description:
  Набор юнит-тестов для проверки REST API эндпоинтов управления конфигурацией
  меню вкладок (menu_config.json) и порядка перетаскиваемых кнопок (Drag & Drop).

File: test_router_menu_config.py
Project: ai-assistant
Package: tests
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-10-31 20:10:00
=============================================================================
"""

import pytest
from fastapi.testclient import TestClient

from apps.ai_assistant.main import app


@pytest.fixture
def client():
    """Тестовый клиент FastAPI приложения."""
    return TestClient(app)


def test_get_menu_config_existing_tab(client):
    """Проверяет получение конфигурации menu_config.json существующей вкладки."""
    response = client.get("/api/v1/tabs/tab_workspace/menu-config")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["tab_id"] == "tab_workspace"
    config = data["config"]
    assert config.get("draggable") is True
    assert "subtabs" in config
    assert len(config["subtabs"]["items"]) >= 5


def test_get_menu_config_non_existing_tab(client):
    """Проверяет возврат ошибки 404 для несуществующей вкладки."""
    response = client.get("/api/v1/tabs/tab_non_existing_xyz/menu-config")
    assert response.status_code == 404


def test_update_menu_order(client, tmp_path, monkeypatch):
    """Проверяет частичное обновление порядка кнопок через PUT."""
    # Создаем временную вкладку с menu_config.json
    tab_dir = tmp_path / "tab_test_order"
    tab_dir.mkdir()
    cfg_file = tab_dir / "menu_config.json"
    initial_data = {
        "tab_id": "tab-test",
        "draggable": True,
        "subtabs": {
            "nav_id": "test-subtabs-nav",
            "items": [
                {"id": "a", "order": 0},
                {"id": "b", "order": 1},
                {"id": "c", "order": 2}
            ]
        }
    }
    import json
    cfg_file.write_text(json.dumps(initial_data, ensure_ascii=False), encoding="utf-8")

    from apps.ai_assistant.api.routers import router_menu_config
    monkeypatch.setattr(router_menu_config, "WEBGUI_DIR", tmp_path)

    # Меняем порядок: c, a, b
    response = client.put(
        "/api/v1/tabs/tab_test_order/menu-config",
        json={"menu_type": "subtabs", "order": ["c", "a", "b"]}
    )
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "ok"
    items = res_data["config"]["subtabs"]["items"]
    assert items[0]["id"] == "c"
    assert items[0]["order"] == 0
    assert items[1]["id"] == "a"
    assert items[1]["order"] == 1
    assert items[2]["id"] == "b"
    assert items[2]["order"] == 2
