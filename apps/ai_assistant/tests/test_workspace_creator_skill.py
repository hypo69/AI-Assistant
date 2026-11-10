# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant Tests - Workspace Creator Skill & Engine
# =============================================================================
# Description:
#   Модульные и интеграционные тесты навыка создания рабочего пространства
#   на основе локальной директории (WorkspaceCreatorEngine & CLI):
#   1. Аудит и профилирование локальной папки (файлы, язык, метаданные).
#   2. Создание полноценного рабочего пространства с привязкой на месте.
#   3. Инициализация Git, .gitignore, Obsidian Vault и контекстного README.md.
#   4. Тестирование CLI-утилиты навыка (audit, create).
#   5. Тестирование REST API эндпоинтов (/audit-directory, /create-from-directory).
#
# File: test_workspace_creator_skill.py
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 16:53:00
# =============================================================================

from __future__ import annotations
"""Тесты навыка и движка создания рабочего пространства на базе локальной папки."""

import asyncio
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import pytest
from httpx import ASGITransport, AsyncClient

from apps.ai_assistant.core.workspace_manager import WorkspaceManager
from apps.ai_assistant.core.workspace_creator_engine import WorkspaceCreatorEngine
from apps.ai_assistant.main import app


@pytest.fixture
def temp_workspace_manager():
    """Создаёт изолированный менеджер рабочих областей во временном каталоге."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        base_p = Path(tmp_dir)
        wm = WorkspaceManager(base_dir=str(base_p), workspaces_dir=base_p / "workspaces")
        yield wm


def test_workspace_creator_audit_directory(temp_workspace_manager: WorkspaceManager) -> None:
    """Проверяет аудит локальной директории, подсчёт файлов и детекцию языка."""
    with tempfile.TemporaryDirectory() as src_dir:
        src_path = Path(src_dir)
        # Создаем файлы на русском языке
        (src_path / "документ1.txt").write_text("Это важный отчет о проделанной работе за квартал.", encoding="utf-8")
        (src_path / "данные.csv").write_text("id,имя,значение\n1,альфа,100", encoding="utf-8")
        sub_dir = src_path / "вложенная_папка"
        sub_dir.mkdir()
        (sub_dir / "заметки.md").write_text("# Заметки проекта\nПлан развития инфраструктуры.", encoding="utf-8")

        engine = WorkspaceCreatorEngine(temp_workspace_manager)

        profile = engine.audit_directory(src_path)

        assert profile["total_files"] == 3
        assert ".txt" in profile["extensions"]
        assert ".csv" in profile["extensions"]
        assert ".md" in profile["extensions"]
        assert profile["detected_language"] == "ru"
        assert profile["suggested_id"] != ""
        assert profile["folder_name"] == src_path.name
        assert len(profile["sample_files"]) == 3


@pytest.mark.asyncio
async def test_workspace_creator_create_workspace_from_directory(temp_workspace_manager: WorkspaceManager) -> None:
    """Проверяет полное создание рабочего пространства на основе локальной папки."""
    wm = temp_workspace_manager
    engine = WorkspaceCreatorEngine(wm)

    with tempfile.TemporaryDirectory() as local_dir:
        local_p = Path(local_dir)
        (local_p / "договор.txt").write_text("Текст договора об оказании услуг и поставке оборудования.", encoding="utf-8")
        (local_p / "спецификация.md").write_text("# Спецификация оборудования\nСписок позиций.", encoding="utf-8")

        res = await engine.create_workspace_from_directory(
            directory_path=local_p,
            workspace_id="test_local_space",
            name="Тестовое Локальное Пространство",
            language="ru",
            in_place=True,
        )

        assert res["status"] == "ok"
        assert res["workspace_id"] == "test_local_space"
        assert res["name"] == "Тестовое Локальное Пространство"
        assert res["language"] == "ru"

        # Проверяем, что рабочая область зарегистрирована
        ws_info = wm.get_workspace("test_local_space")
        assert ws_info is not None
        assert ws_info["name"] == "Тестовое Локальное Пространство"

        ws_path = wm.registry.workspace_path("test_local_space")
        assert ws_path.exists()

        # Проверяем наличие .gitignore, Obsidian Vault и README.md
        assert (ws_path / ".gitignore").exists()
        assert (ws_path / ".obsidian").exists()
        assert (ws_path / "_Knowledge_Base.md").exists()
        readme = (ws_path / "README.md").read_text(encoding="utf-8")
        assert "Тестовое Локальное Пространство" in readme
        assert "Локальный источник на диске" in readme


def test_workspace_creator_cli_audit() -> None:
    """Проверяет вызов CLI-скрипта навыка workspace_creator_cli.py audit."""
    cli_script = Path(__file__).parents[3] / ".agents" / "skills" / "workspace-creator" / "scripts" / "workspace_creator_cli.py"
    assert cli_script.exists(), "Скрипт workspace_creator_cli.py должен существовать"

    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "test.txt").write_text("Тестовый файл", encoding="utf-8")

        cmd = [sys.executable, str(cli_script), "audit", tmp_dir, "--json"]
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        assert proc.returncode == 0, f"CLI вернул ошибку: {proc.stderr} | stdout: {proc.stdout}"

        # Извлекаем JSON блок из вывода (отсекая возможные строки логов)
        out = proc.stdout.strip()
        json_start = out.find("{")
        json_end = out.rfind("}") + 1
        data = json.loads(out[json_start:json_end])
        assert data["total_files"] == 1
        assert ".txt" in data["extensions"]


@pytest.mark.asyncio
async def test_router_knowledge_audit_and_create_endpoints() -> None:
    """Проверяет REST API эндпоинты /audit-directory и /create-from-directory."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with tempfile.TemporaryDirectory() as tmp_dir:
            (Path(tmp_dir) / "sample.txt").write_text("Текст документа для тестирования API.", encoding="utf-8")

            # 1. Тест аудита через API
            audit_res = await client.post("/api/v1/workspaces/audit-directory", json={"directory_path": tmp_dir})
            assert audit_res.status_code == 200
            audit_data = audit_res.json()
            assert audit_data["total_files"] == 1
            assert audit_data["detected_language"] == "ru"

            # 2. Тест создания пространства через API
            create_res = await client.post(
                "/api/v1/workspaces/create-from-directory",
                json={
                    "directory_path": tmp_dir,
                    "workspace_id": "api_created_ws",
                    "name": "API Created WS",
                    "language": "ru",
                },
            )
            assert create_res.status_code == 200
            create_data = create_res.json()
            assert create_data["status"] == "ok"
            assert create_data["workspace_id"] == "api_created_ws"
