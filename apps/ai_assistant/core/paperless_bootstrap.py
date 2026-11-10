# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Core - Paperless Bootstrap
# =============================================================================
# Description:
#   Гарантирует доступность Paperless-ngx при старте AI-Assistant (assist.ps1):
#   если API не отвечает — открывает новое окно терминала с Docker Compose.
#   Сбой не блокирует запуск ассистента (Paperless — внешний сервис).
#
# Usage Examples:
#   from apps.ai_assistant.core.paperless_bootstrap import ensure_paperless_running
#
#   ensure_paperless_running()
#
# File: paperless_bootstrap.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 16:55:00
# =============================================================================

from __future__ import annotations
"""Автозапуск и проверка доступности Paperless-ngx."""

import json
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv

from logger import logger

DOCKER_FALLBACK_DIR = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Docker" / "Docker" / "resources" / "bin"


def load_paperless_config() -> Dict:
    """Читает секцию `paperless` из корневого config.json.

    Raises:
        KeyError: Если секция отсутствует.
    """
    from header import __root__

    return json.loads((Path(__root__) / "config.json").read_text(encoding="utf-8"))["paperless"]


def find_docker() -> Optional[str]:
    """Ищет docker в PATH, затем в стандартном каталоге Docker Desktop.

    Returns:
        Optional[str]: Путь к docker или None, если Docker не установлен.
    """
    return shutil.which("docker") or shutil.which("docker", path=str(DOCKER_FALLBACK_DIR))


def compose(args: List[str], build: bool = False) -> int:
    """Запускает `docker compose` в runtime-каталоге Paperless.

    Args:
        args: Аргументы compose (например, ['up', '-d']).
        build: Подключить docker-compose.build.yml (сборка из локальных исходников).

    Returns:
        int: Код возврата; 1, если Docker не найден.
    """
    from header import __root__

    docker = find_docker()
    if not docker:
        logger.error("Docker не найден: установите Docker Desktop с WSL2 backend")
        return 1
    files = ["-f", "docker-compose.yml"] + (["-f", "docker-compose.build.yml"] if build else [])
    runtime = Path(__root__) / load_paperless_config()["runtime_dir"]
    return subprocess.run([docker, "compose", *files, *args], cwd=runtime, check=False).returncode


def _sync_active_workspace() -> None:
    """Индексирует документы Paperless активной рабочей области (выполняется в фоновом потоке)."""
    from apps.ai_assistant.core.paperless_connector import PaperlessConnector, PaperlessError
    from apps.ai_assistant.core.paperless_sync import sync_workspace_from_paperless
    from apps.ai_assistant.core.workspace_manager import WorkspaceManager

    try:
        wm = WorkspaceManager()
        workspace_id = wm.get_active_workspace_id()
        if not workspace_id:
            return
        report = sync_workspace_from_paperless(wm, PaperlessConnector.from_config(), workspace_id)
        logger.info(f"[PaperlessBootstrap] Синхронизация области: {report}")
    except (PaperlessError, OSError, ValueError) as exc:
        logger.warning(f"[PaperlessBootstrap] Синхронизация пропущена: {exc}")


def launch_in_new_terminal() -> bool:
    """Открывает новое окно терминала: `docker compose up -d`, затем поток логов Paperless.

    Закрытие окна не останавливает контейнеры (логи читает отдельный `logs -f`).

    Returns:
        bool: True, если окно открыто; False, если Docker не найден.
    """
    from header import __root__

    docker = find_docker()
    if not docker:
        logger.error("Docker не найден: установите Docker Desktop с WSL2 backend")
        return False
    cfg = load_paperless_config()
    runtime = Path(__root__) / cfg["runtime_dir"]
    title = cfg["terminal_title"]
    script = f"& '{docker}' compose up -d; & '{docker}' compose logs -f --tail 20"
    shell = ["powershell.exe", "-NoExit", "-NoProfile", "-Command", script]
    wt = shutil.which("wt.exe")
    if wt:
        cmd = [wt, "-w", "new", "--title", title, "-d", str(runtime), *shell]
        subprocess.Popen(cmd)
    else:
        subprocess.Popen(shell, cwd=runtime, creationflags=subprocess.CREATE_NEW_CONSOLE)
    return True


def ensure_paperless_running() -> bool:
    """Проверяет API Paperless и при необходимости запускает контейнеры.

    Returns:
        bool: True, если API доступен; False при отключённом автозапуске или сбое
        (в этом случае ассистент продолжает работу без Paperless).
    """
    from header import __root__
    from apps.ai_assistant.core.paperless_connector import PaperlessConnector, PaperlessError

    load_dotenv(Path(__root__) / ".env")
    cfg = load_paperless_config()
    if not cfg.get("autostart"):
        return False
    try:
        connector = PaperlessConnector.from_config()
    except PaperlessError as exc:
        logger.warning(f"[PaperlessBootstrap] Интеграция отключена: {exc}")
        return False
    if _is_ready(connector, cfg):
        return True
    logger.info("[PaperlessBootstrap] Paperless недоступен, запускаю Docker Compose в новом окне терминала")
    if not launch_in_new_terminal():
        return False
    deadline = time.monotonic() + float(cfg["startup_timeout_sec"])
    while time.monotonic() < deadline:
        if connector.ping():
            logger.info("[PaperlessBootstrap] Paperless готов")
            return _is_ready(connector, cfg)
        time.sleep(float(cfg["startup_poll_sec"]))
    logger.warning("[PaperlessBootstrap] Paperless не ответил за отведённое время")
    return False


def _is_ready(connector, cfg: Dict) -> bool:
    """Проверяет API и, если включено, запускает фоновую синхронизацию активной области."""
    if not connector.ping():
        return False
    if cfg.get("sync_on_start"):
        threading.Thread(target=_sync_active_workspace, name="paperless-sync", daemon=True).start()
    return True
