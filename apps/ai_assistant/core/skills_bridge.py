# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant Core - Skills Bridge
# =============================================================================
# Description:
#   Мост для прямого вызова клиентов навыков Google Workspace (Google Mail,
#   Google Calendar, Google Drive, Google Contacts) из серверной части WebGUI.
#
# File: skills_bridge.py
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 13:50:00
# =============================================================================

from __future__ import annotations

"""Модуль интеграции и прямого доступа к навыкам Google Workspace."""

import importlib.util
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from header import __root__
from logger import logger

_SKILLS_DIR = (__root__ / ".agents" / "skills").resolve()
_MODULE_CACHE: Dict[str, Any] = {}
_CACHE_LOCK = threading.RLock()


def _load_skill_module(skill_name: str, script_name: str) -> Any:
    """Динамически загружает модуль скрипта из указанного навыка с потокобезопасным кэшированием.

    Args:
        skill_name: Имя навыка (например, 'google-calendar').
        script_name: Имя скрипта без расширения (например, 'calendar_client').

    Returns:
        Загруженный модуль Python.
    """
    cache_key = f"{skill_name}.{script_name}"
    with _CACHE_LOCK:
        if cache_key in _MODULE_CACHE:
            return _MODULE_CACHE[cache_key]

        file_path = (_SKILLS_DIR / skill_name / "scripts" / f"{script_name}.py").resolve()
        try:
            file_path.relative_to(_SKILLS_DIR.resolve())
        except ValueError:
            raise ValueError(f"Попытка выхода за пределы директории навыков: {file_path}")

        if not file_path.is_file():
            raise FileNotFoundError(f"Модуль навыка не найден: {file_path}")

        spec = importlib.util.spec_from_file_location(f"skills.{skill_name}.{script_name}", str(file_path))
        if not spec or not spec.loader:
            raise ImportError(f"Не удалось инициализировать spec для {file_path}")

        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _MODULE_CACHE[cache_key] = mod
        return mod


def get_calendar_client(account_name: Optional[str] = None) -> Any:
    """Возвращает экземпляр GoogleCalendarClient из навыка google-calendar."""
    mod = _load_skill_module("google-calendar", "calendar_client")
    return mod.GoogleCalendarClient(account_name=account_name)


def get_drive_client(account_name: Optional[str] = None) -> Any:
    """Возвращает экземпляр GoogleDriveClient из навыка google-drive."""
    mod = _load_skill_module("google-drive", "drive_client")
    return mod.GoogleDriveClient(account_name=account_name)


def get_contacts_client(account_name: Optional[str] = None) -> Any:
    """Возвращает экземпляр GoogleContactsClient из навыка google-contacts."""
    mod = _load_skill_module("google-contacts", "contacts_client")
    return mod.GoogleContactsClient(account_name=account_name)


def get_mail_client(account_name: Optional[str] = None) -> Any:
    """Возвращает экземпляр GoogleMailClient из навыка google-mail."""
    mod = _load_skill_module("google-mail", "mail_client")
    return mod.GoogleMailClient(account_name=account_name)
