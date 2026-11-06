# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Tests - Workspace Isolated Temporal Graph
# =============================================================================
# Description:
#   Модульные тесты полной изоляции темпорального графа связей по рабочим пространствам
#   (Local-First / USB-Portable). Проверяют отсутствие глобальной смешанной базы,
#   независимость графов между пространствами и корректную фильтрацию через Panel API.
#
# File: test_workspace_isolated_graph.py
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-06 23:15:00
# =============================================================================

import pytest
from pathlib import Path
from httpx import AsyncClient, ASGITransport

from apps.ai_assistant.main import app
from apps.ai_assistant.core.workspace_manager import WorkspaceManager
from apps.ai_assistant.core.workspace_registry import WorkspaceRegistry


@pytest.mark.asyncio
async def test_workspace_isolated_graph_lifecycle(tmp_path: Path) -> None:
    """Проверяет изолированное хранение связей темпорального графа внутри .workspace/ каждого проекта."""
    ws_root = tmp_path / "workspaces"
    ws_root.mkdir(parents=True, exist_ok=True)

    wm = WorkspaceManager(base_dir=tmp_path / "app_data", workspaces_dir=ws_root)

    ws_a = wm.create_or_select_workspace("project_alpha", name="Project Alpha")
    ws_b = wm.create_or_select_workspace("project_beta", name="Project Beta")

    # 1. Получаем изолированные графы
    graph_a = wm.get_workspace_graph("project_alpha")
    graph_b = wm.get_workspace_graph("project_beta")

    # 2. Добавляем связи только в project_alpha
    graph_a.add_link(
        source_id="commit_alpha_01",
        target_id="src/alpha_core.py",
        relation_type="modifies",
        valid_from="commit_alpha_01",
    )
    graph_a.add_link(
        source_id="doc_alpha_spec.pdf",
        target_id="ArchitectureSpecAlpha",
        relation_type="documents",
        valid_from="commit_alpha_01",
    )

    # 3. Проверяем, что в project_alpha 2 связи, а в project_beta — 0
    links_a = graph_a.get_all_links()
    links_b = graph_b.get_all_links()

    assert len(links_a) == 2
    assert len(links_b) == 0

    # 4. Проверяем физическое размещение файлов БД в .workspace/
    db_file_a = Path(ws_a["path"]) / ".workspace" / "temporal_graph.db"
    db_file_b = Path(ws_b["path"]) / ".workspace" / "temporal_graph.db"
    assert db_file_a.exists()

    # 5. Инвалидация в графе project_alpha
    superseded = graph_a.supersede_link(
        source_id="commit_alpha_01",
        target_id="src/alpha_core.py",
        invalidating_commit="commit_alpha_02",
    )
    assert superseded is True
    active_a = graph_a.get_active_links()
    assert len(active_a) == 1
    assert active_a[0].target_id == "ArchitectureSpecAlpha"


@pytest.mark.asyncio
async def test_panel_router_knowledge_links_isolated() -> None:
    """Проверяет эндпоинт GET /api/v1/panel/panel-knowledge-links на изолированную выдачу по workspace_id."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Без активного воркспейса и без параметров возвращается пустой список связей
        res_default = await client.get("/api/v1/panel/panel-knowledge-links")
        assert res_default.status_code == 200
        data_default = res_default.json()
        assert "data" in data_default
        assert isinstance(data_default["data"], list)

        # Вызов с конкретным воркспейсом
        res_ws = await client.get("/api/v1/panel/panel-knowledge-links?workspace_id=non_existent_ws_123")
        assert res_ws.status_code == 200
        data_ws = res_ws.json()
        assert len(data_ws["data"]) == 0
