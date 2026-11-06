# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Telegram Bot Single-User Auth Adapter
# =============================================================================
# Description:
#   Легковесный адаптер привязки Telegram-аккаунта и хранения выбранной рабочей
#   области пользователя для однопользовательского режима без устаревшей БД.
#
# File: user_auth.py
# Package: plugins.telegram_bot
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-06 20:38:00
# =============================================================================

from __future__ import annotations

import json
from pathlib import Path
import time
from typing import Any, Dict, List, Optional

from header import __root__

_AUTH_FILE = __root__ / "data" / "telegram_auth.json"


def _load_state() -> Dict[str, Any]:
    """Загружает локальное состояние привязки Telegram."""
    if _AUTH_FILE.exists():
        try:
            with open(_AUTH_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_state(state: Dict[str, Any]) -> None:
    """Сохраняет локальное состояние привязки Telegram."""
    try:
        _AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_AUTH_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def link_telegram_account(token: str, tg_id: int, tg_username: str) -> bool:
    """Проверяет одноразовый код и привязывает аккаунт Telegram."""
    state = _load_state()
    saved_token = state.get("pending_token")
    expires = state.get("token_expires_at", 0)
    if saved_token and str(saved_token).strip() == str(token).strip() and time.time() < expires:
        state["telegram_id"] = tg_id
        state["telegram_username"] = tg_username
        state.pop("pending_token", None)
        _save_state(state)
        return True
    return False


def get_user_by_telegram_id(tg_id: int, admin_ids: Optional[List[int]] = None) -> Optional[Dict[str, Any]]:
    """Возвращает профиль пользователя, если Telegram ID привязан или находится в списке администраторов."""
    state = _load_state()
    admins = list(state.get("admin_telegram_ids") or [])
    if admin_ids:
        admins.extend(admin_ids)
    if state.get("telegram_id") == tg_id or tg_id in admins:
        return {"id": 1, "name": state.get("user_name", "Администратор"), "email": "admin@localhost"}
    return None


def get_user_workspace(tg_id: int) -> Optional[str]:
    """Возвращает идентификатор активной рабочей области для пользователя Telegram."""
    state = _load_state()
    user_ws_map = state.get("user_workspaces")
    if isinstance(user_ws_map, dict) and str(tg_id) in user_ws_map:
        return str(user_ws_map[str(tg_id)])
    selected = state.get("selected_workspace")
    return str(selected) if selected else None


def set_user_workspace(tg_id: int, workspace_id: str) -> None:
    """Сохраняет выбранную рабочую область для пользователя Telegram."""
    state = _load_state()
    if "user_workspaces" not in state or not isinstance(state["user_workspaces"], dict):
        state["user_workspaces"] = {}
    clean_id = str(workspace_id).strip()
    state["user_workspaces"][str(tg_id)] = clean_id
    state["selected_workspace"] = clean_id
    _save_state(state)


def get_user_directory(user_id: int = 1, subfolder: str = "", create: bool = True) -> Path:
    """Возвращает локальный каталог для хранения файлов Telegram (audio, dialogs)."""
    base = __root__ / "data" / "telegram"
    if subfolder:
        base = base / subfolder
    if create:
        base.mkdir(parents=True, exist_ok=True)
    return base
