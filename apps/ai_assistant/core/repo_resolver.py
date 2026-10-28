# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Core - Repo Resolver
# =============================================================================
# Description:
#   Модуль динамического разрешения путей Git-репозиториев для рабочих пространств
#   и основного проекта. Позволяет бесшовно переключать контекст адаптеров Git,
#   движка истории, diff и панелей интерфейса на каталог выбранного пространства.
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.core.repo_resolver import resolve_repo_path
#
#     repo_path = resolve_repo_path(workspace_id="my_ws")
#
# File: repo_resolver.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 17:28:00
# =============================================================================

from __future__ import annotations
"""Разрешение целевого пути к Git-репозиторию на основе идентификатора рабочей области или прямого пути."""

from pathlib import Path
from typing import Optional

from logger import logger
from apps.ai_assistant.core.workspace_registry import WorkspaceRegistry, resolve_workspaces_dir


def resolve_repo_path(
    workspace_id: Optional[str] = None,
    repo_path: Optional[str] = None,
) -> Path:
    """Определяет действительный путь к Git-репозиторию для рабочего пространства или проекта.

    Args:
        workspace_id: Необязательный идентификатор рабочего пространства.
        repo_path: Необязательный прямой путь к целевой директории репозитория.

    Returns:
        Path: Абсолютный путь к найденному и проверенному Git-репозиторию.
    """
    # 1. Прямой путь передан явно
    if repo_path and str(repo_path).strip():
        p = Path(repo_path).resolve()
        if p.exists() and p.is_dir():
            return p

    # 2. Передан идентификатор рабочего пространства
    clean_ws = (workspace_id or "").strip()
    if clean_ws and clean_ws.lower() not in ("main", "root", "project", "none", "null"):
        try:
            ws = WorkspaceRegistry(resolve_workspaces_dir()).get_workspace(clean_ws)
            if ws:
                return Path(ws["path"]).resolve()
            logger.warning(f"[RepoResolver] Рабочее пространство {clean_ws} не найдено в каталоге workspaces")
        except Exception as exc:
            logger.warning(f"[RepoResolver] Ошибка поиска пути для workspace_id={clean_ws}: {exc}")

    # 3. Если ни repo_path, ни workspace_id не переданы явно, проверяем глобально сохранённый активный репозиторий
    if not clean_ws and not repo_path:
        try:
            from apps.ai_assistant.core.workspace_manager import WorkspaceManager

            saved = WorkspaceManager().store.get_active_repo()
            saved_repo = saved.get("repo_path")
            if saved_repo:
                target_p = Path(saved_repo).resolve()
                if target_p.exists() and target_p.is_dir():
                    return target_p

            active_id = saved.get("workspace_id")
            if active_id and active_id.lower() not in ("main", "root", "project", "none", "null"):
                ws = WorkspaceRegistry(resolve_workspaces_dir()).get_workspace(active_id)
                if ws:
                    return Path(ws["path"]).resolve()
        except Exception as exc:
            logger.debug(f"[RepoResolver] Активный репозиторий по умолчанию не разрешен: {exc}")

    # 4. Fallback: первое доступное рабочее пространство в data или корень
    workspaces = WorkspaceRegistry(resolve_workspaces_dir()).list_workspaces()
    if workspaces and clean_ws.lower() not in ("main", "root"):
        return Path(workspaces[0]["path"]).resolve()
    return Path(".").resolve()
