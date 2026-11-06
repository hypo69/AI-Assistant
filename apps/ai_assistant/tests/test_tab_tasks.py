# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant - Smart Tasks & Workflows Tests
# =============================================================================
# Description:
#   Комплексные тесты сервиса TaskOrchestratorService, REST API маршрутизатора
#   /api/v1/tasks и компонентов интерфейса вкладки tab_tasks.
#
# File: test_tab_tasks.py
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-03 16:46:00
# =============================================================================

from __future__ import annotations

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from apps.ai_assistant.core.task_orchestrator import TaskOrchestratorService
from apps.ai_assistant.main import app
from header import __root__


@pytest.fixture
def temp_orchestrator(tmp_path: Path) -> TaskOrchestratorService:
    """Создает изолированный экземпляр TaskOrchestratorService во временной директории."""
    db_file = tmp_path / "test_tasks.db"
    return TaskOrchestratorService(db_path=db_file)


@pytest.fixture
def api_client() -> TestClient:
    """Возвращает тестовый клиент FastAPI."""
    return TestClient(app)


def test_task_orchestrator_initial_state(temp_orchestrator: TaskOrchestratorService) -> None:
    """Проверяет начальное пустое состояние базы данных задач."""
    cases = temp_orchestrator.list_cases()
    assert isinstance(cases, list)
    assert len(cases) == 0


def test_decompose_cow_scenario(temp_orchestrator: TaskOrchestratorService) -> None:
    """Проверяет декомпозицию телефонного разговора дяди Моше о покупке коровы у Шмулика."""
    transcript = "Дядя Моше попросил начать подготавливать документы на покупку коровы у Шмулика с осмотром ветеринара."
    plan = temp_orchestrator.decompose_text(transcript, source_label="Телефонный разговор")

    assert "Шмулик" in plan["title"]
    assert "Моше" in plan["title"]
    assert plan["category"] == "deal"
    assert len(plan["actors"]) >= 4

    actor_roles = [a["role"] for a in plan["actors"]]
    assert "client" in actor_roles
    assert "seller" in actor_roles
    assert "veterinarian" in actor_roles
    assert "insurer" in actor_roles

    stages = [it["stage"] for it in plan["items"]]
    assert "documents" in stages
    assert "vet_inspection" in stages
    assert "insurance" in stages


def test_create_and_manage_case_lifecycle(temp_orchestrator: TaskOrchestratorService) -> None:
    """Проверяет полный жизненный цикл дела: создание, чтение, переключение статусов и удаление."""
    transcript = "Дядя Моше и корова Шмулика"
    plan = temp_orchestrator.decompose_text(transcript)

    # 1. Создание дела
    case = temp_orchestrator.create_case(
        title=plan["title"],
        description=plan["description"],
        category=plan["category"],
        raw_transcript=transcript,
        actors=plan["actors"],
        items=plan["items"]
    )
    assert case["id"].startswith("case_")
    assert len(case["items"]) == len(plan["items"])

    # 2. Получение деталей
    fetched = temp_orchestrator.get_case(case["id"])
    assert fetched is not None
    assert fetched["title"] == plan["title"]
    assert len(fetched["actors"]) == len(plan["actors"])

    # 3. Обновление статуса этапа
    first_item_id = fetched["items"][0]["id"]
    ok_item = temp_orchestrator.update_item_status(first_item_id, "done")
    assert ok_item is True

    # Проверка прогресса
    cases = temp_orchestrator.list_cases()
    assert len(cases) == 1
    assert cases[0]["completed_items"] == 1
    assert cases[0]["progress_percent"] > 0

    # 4. Обновление статуса всего дела
    ok_case = temp_orchestrator.update_case_status(case["id"], "completed")
    assert ok_case is True
    completed_cases = temp_orchestrator.list_cases(status="completed")
    assert len(completed_cases) == 1

    # 5. Удаление дела
    del_ok = temp_orchestrator.delete_case(case["id"])
    assert del_ok is True
    assert temp_orchestrator.get_case(case["id"]) is None


def test_api_tasks_endpoints(api_client: TestClient) -> None:
    """Проверяет REST API маршруты /api/v1/tasks (decompose, cases, sync_calendar)."""
    # 1. Декомпозиция
    decomp_resp = api_client.post(
        "/api/v1/tasks/decompose",
        json={"text": "Купить корову у Шмулика для дяди Моше", "source_label": "Звонок"}
    )
    assert decomp_resp.status_code == 200
    plan = decomp_resp.json()["plan"]
    assert "Шмулик" in plan["title"]

    # 2. Создание дела
    create_resp = api_client.post(
        "/api/v1/tasks/cases",
        json={
            "title": plan["title"],
            "description": plan["description"],
            "category": plan["category"],
            "raw_transcript": "Тестовый транскрипт",
            "actors": plan["actors"],
            "items": plan["items"]
        }
    )
    assert create_resp.status_code == 200
    case_data = create_resp.json()["case"]
    case_id = case_data["id"]

    # 3. Список дел
    list_resp = api_client.get("/api/v1/tasks/cases")
    assert list_resp.status_code == 200
    assert any(c["id"] == case_id for c in list_resp.json()["cases"])

    # 4. Детали дела
    detail_resp = api_client.get(f"/api/v1/tasks/cases/{case_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["case"]["id"] == case_id

    # 5. Синхронизация календаря
    first_item = case_data["items"][0]
    cal_resp = api_client.post(
        "/api/v1/tasks/actions/sync_calendar",
        json={
            "case_id": case_id,
            "item_id": first_item["id"],
            "summary": "Осмотр коровы ветеринаром",
            "start_time": "2026-11-05T10:00:00",
            "end_time": "2026-11-05T11:00:00",
            "location": "Хозяйство Шмулика"
        }
    )
    assert cal_resp.status_code == 200
    assert cal_resp.json()["success"] is True

    # 6. Удаление дела
    del_resp = api_client.delete(f"/api/v1/tasks/cases/{case_id}")
    assert del_resp.status_code == 200


def test_tab_tasks_files_and_locales_integrity() -> None:
    """Проверяет физическое наличие всех файлов вкладки tab_tasks и наличие переводов во всех словарях."""
    webgui_dir = __root__ / "apps" / "ai_assistant" / "api" / "webgui"
    tab_dir = webgui_dir / "tab_tasks"

    assert (tab_dir / "index.html").exists(), "index.html вкладки отсутствует"
    assert (tab_dir / "main.js").exists(), "main.js вкладки отсутствует"
    assert (tab_dir / "menu_config.json").exists(), "menu_config.json отсутствует"
    assert (tab_dir / "README.md").exists(), "README.md вкладки отсутствует"

    # Проверка чистоты разметки index.html (запрет тегов <script>)
    index_html_text = (tab_dir / "index.html").read_text(encoding="utf-8")
    assert "<script" not in index_html_text, "В index.html вкладки обнаружен запрещенный тег <script>"

    # Проверка наличия i18n ключей во всех 4 словарях
    locales = ["ru", "en", "he", "uk"]
    for loc in locales:
        loc_file = webgui_dir / "locales" / f"{loc}.json"
        assert loc_file.exists(), f"Словарь {loc}.json не найден"
        data = json.loads(loc_file.read_text(encoding="utf-8"))

        assert "tasks" in data["tabs"], f"tabs.tasks отсутствует в {loc}.json"
        assert "tasks" in data["titles"]["ide"], f"titles.ide.tasks отсутствует в {loc}.json"
        assert "tasks" in data["ui"], f"ui.tasks отсутствует в {loc}.json"
        assert "subtabCases" in data["ui"]["tasks"], f"ui.tasks.subtabCases отсутствует в {loc}.json"
        assert "subtabIntake" in data["ui"]["tasks"], f"ui.tasks.subtabIntake отсутствует в {loc}.json"
        assert "subtabCoordination" in data["ui"]["tasks"], f"ui.tasks.subtabCoordination отсутствует в {loc}.json"
        assert "subtabDocs" in data["ui"]["tasks"], f"ui.tasks.subtabDocs отсутствует в {loc}.json"
