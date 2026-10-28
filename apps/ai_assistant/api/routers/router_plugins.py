# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant - Plugins Management Router
# =============================================================================
# Description:
#   FastAPI маршрутизатор управления модульными плагинами (Plugins Hub).
#   Обеспечивает получение манифестов, переключение активности, вызов действий
#   плагинов (Actions) и динамическое обновление параметров конфигурации.
#
# Usage Examples:
#   GET  /api/v1/plugins
#   POST /api/v1/plugins/{name}/toggle
#   POST /api/v1/plugins/{name}/action/{action_id}
#   POST /api/v1/plugins/{name}/config
#
# File: router_plugins.py
# Package: apps.ai_assistant.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 18:29:00
# =============================================================================

from __future__ import annotations

"""REST API маршрутизатор управления модульными плагинами системы."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from header import __root__
from logger import logger
from plugins import BasePlugin, load_plugins
from apps.ai_assistant.api.routers.plugins_marketplace import (
    get_marketplace_catalog,
    install_marketplace_plugin,
    uninstall_user_plugin,
)

router = APIRouter(prefix="/api/v1/plugins", tags=["Plugins"])

_PLUGINS_CACHE: Dict[str, BasePlugin] = {}


def get_plugins_registry() -> Dict[str, BasePlugin]:
    """Возвращает или инициализирует кэшированный реестр плагинов (включая отключенные для управления в UI)."""
    global _PLUGINS_CACHE
    if not _PLUGINS_CACHE:
        try:
            _PLUGINS_CACHE = load_plugins(include_disabled=True)
        except Exception as exc:
            logger.error(f"[router_plugins] Ошибка начальной загрузки плагинов: {exc}")
            _PLUGINS_CACHE = {}
    return _PLUGINS_CACHE


def reload_plugins_registry() -> Dict[str, BasePlugin]:
    """Принудительно перезагружает все плагины (включая отключенные для управления в UI)."""
    global _PLUGINS_CACHE
    try:
        _PLUGINS_CACHE = load_plugins(include_disabled=True)
    except Exception as exc:
        logger.error(f"[router_plugins] Ошибка перезагрузки плагинов: {exc}")
    return _PLUGINS_CACHE


class PluginToggleRequest(BaseModel):
    """Схема запроса переключения статуса плагина."""
    enabled: bool = Field(..., description="Флаг активности плагина")


class PluginActionRequest(BaseModel):
    """Схема запроса выполнения действия плагина."""
    params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Параметры действия")


class PluginConfigRequest(BaseModel):
    """Схема запроса сохранения конфигурации плагина."""
    config: Dict[str, Any] = Field(..., description="Словарь параметров конфигурации")


class PluginInstallRequest(BaseModel):
    """Схема запроса установки плагина из маркетплейса."""
    plugin_id: str = Field(..., description="Идентификатор стандартного плагина")


from apps.ai_assistant.api.routers.router_models import resolve_active_config_path


def _get_active_config_path() -> Path:
    """Определяет активный файл config.json через единый резолвер конфигурации."""
    return resolve_active_config_path()


def _save_plugin_state_to_config(plugin_name: str, enabled: bool) -> None:
    """Сохраняет состояние активности плагина в конфигурационный файл."""
    cfg_path = _get_active_config_path()
    try:
        cfg: Dict[str, Any] = {}
        if cfg_path.exists():
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)

        if "plugins" not in cfg or not isinstance(cfg["plugins"], dict):
            cfg["plugins"] = {"disabled": []}

        plugins_sec = cfg["plugins"]
        if "disabled" not in plugins_sec or not isinstance(plugins_sec["disabled"], list):
            plugins_sec["disabled"] = []

        norm_name = plugin_name.strip().lower()
        if enabled:
            if norm_name in plugins_sec["disabled"]:
                plugins_sec["disabled"].remove(norm_name)
            if "enabled" in plugins_sec and isinstance(plugins_sec["enabled"], list):
                if norm_name not in plugins_sec["enabled"]:
                    plugins_sec["enabled"].append(norm_name)
        else:
            if norm_name not in plugins_sec["disabled"]:
                plugins_sec["disabled"].append(norm_name)
            if "enabled" in plugins_sec and isinstance(plugins_sec["enabled"], list):
                if norm_name in plugins_sec["enabled"]:
                    plugins_sec["enabled"].remove(norm_name)

        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)
    except Exception as exc:
        logger.warning(f"[router_plugins] Ошибка сохранения состояния плагина в config: {exc}")


@router.get("", summary="Список всех доступных плагинов")
@router.get("/", include_in_schema=False)
async def list_plugins(lang: str = Query("ru", description="Язык интерфейса")) -> List[Dict[str, Any]]:
    """Возвращает список всех зарегистрированных плагинов с их метаданными и манифестами."""
    registry = get_plugins_registry()
    manifests = []
    for name, plugin in sorted(registry.items(), key=lambda item: item[0]):
        try:
            m = plugin.get_manifest(lang=lang)
            manifests.append(m)
        except Exception as exc:
            logger.warning(f"[router_plugins] Ошибка формирования манифеста плагина {name}: {exc}")
            manifests.append({
                "name": name,
                "title": getattr(plugin, "title", name),
                "version": getattr(plugin, "version", "1.0.0"),
                "description": getattr(plugin, "description", ""),
                "icon": getattr(plugin, "icon", "🧩"),
                "category": getattr(plugin, "category", "general"),
                "enabled": getattr(plugin, "enabled", True),
                "scope": getattr(plugin, "scope", "user"),
                "is_running": getattr(plugin, "is_running", False),
                "actions": [],
                "tools": [],
                "fields": [],
                "config": getattr(plugin, "config", {}),
            })
    return manifests


@router.post("/reload", summary="Перезагрузка реестра плагинов")
async def reload_plugins() -> Dict[str, Any]:
    """Пересканирует каталог plugins/ и повторно инициализирует плагины."""
    registry = reload_plugins_registry()
    return {"status": "success", "count": len(registry), "plugins": list(registry.keys())}


@router.get("/marketplace", summary="Каталог стандартных плагинов в стиле VS Code")
async def list_marketplace() -> List[Dict[str, Any]]:
    """Возвращает список доступных стандартных плагинов с информацией об их установке."""
    registry = get_plugins_registry()
    installed_names = list(registry.keys())
    return get_marketplace_catalog(installed_names)


@router.post("/install", summary="Установка стандартного плагина из маркетплейса")
async def install_plugin(payload: PluginInstallRequest) -> Dict[str, Any]:
    """Устанавливает стандартный плагин по его идентификатору и перезагружает реестр."""
    try:
        res = install_marketplace_plugin(payload.plugin_id)
        # Активируем плагин в конфигурации при установке
        _save_plugin_state_to_config(payload.plugin_id, True)
        reload_plugins_registry()
        return res
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error(f"[router_plugins] Ошибка установки плагина {payload.plugin_id}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка установки плагина: {exc}")


@router.get("/{name}", summary="Манифест конкретного плагина")
async def get_plugin_details(name: str, lang: str = Query("ru")) -> Dict[str, Any]:
    """Возвращает подробный манифест выбранного плагина."""
    registry = get_plugins_registry()
    plugin = registry.get(name) or registry.get(name.lower())
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Плагин '{name}' не найден")
    return plugin.get_manifest(lang=lang)


@router.post("/{name}/toggle", summary="Включение или отключение плагина")
async def toggle_plugin(name: str, payload: PluginToggleRequest) -> Dict[str, Any]:
    """Переключает флаг активности плагина и сохраняет состояние в config.json."""
    registry = get_plugins_registry()
    plugin = registry.get(name) or registry.get(name.lower())
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Плагин '{name}' не найден")

    plugin.enabled = payload.enabled
    _save_plugin_state_to_config(plugin.name, payload.enabled)

    # Запуск или остановка фоновых служб плагина
    try:
        if payload.enabled and not plugin.is_running:
            await plugin.start()
        elif not payload.enabled and plugin.is_running:
            await plugin.stop()
    except Exception as exc:
        logger.warning(f"[router_plugins] Ошибка при смене статуса фонового сервиса {name}: {exc}")

    return {
        "status": "success",
        "name": plugin.name,
        "enabled": plugin.enabled,
        "is_running": plugin.is_running,
    }


@router.post("/{name}/action/{action_id}", summary="Выполнение действия плагина")
async def execute_plugin_action(name: str, action_id: str, payload: PluginActionRequest) -> Dict[str, Any]:
    """Выполняет объявленное действие плагина по его идентификатору."""
    registry = get_plugins_registry()
    plugin = registry.get(name) or registry.get(name.lower())
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Плагин '{name}' не найден")

    try:
        res = await plugin.execute_action(action_id, params=payload.params)
        return {"status": "success", "plugin": plugin.name, "action_id": action_id, "result": res}
    except Exception as exc:
        logger.error(f"[router_plugins] Ошибка выполнения действия {action_id} плагина {name}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка выполнения действия: {exc}")


@router.get("/{name}/config", summary="Получение конфигурации плагина")
async def get_plugin_config(name: str) -> Dict[str, Any]:
    """Возвращает текущую конфигурацию и форму полей настроек плагина."""
    registry = get_plugins_registry()
    plugin = registry.get(name) or registry.get(name.lower())
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Плагин '{name}' не найден")

    fields = plugin.get_config_fields() if hasattr(plugin, "get_config_fields") else []
    return {
        "name": plugin.name,
        "config": plugin.config,
        "fields": fields,
    }


@router.post("/{name}/config", summary="Обновление конфигурации плагина")
async def update_plugin_config(name: str, payload: PluginConfigRequest) -> Dict[str, Any]:
    """Обновляет и сохраняет параметры конфигурации плагина."""
    registry = get_plugins_registry()
    plugin = registry.get(name) or registry.get(name.lower())
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Плагин '{name}' не найден")

    try:
        plugin.update_config(payload.config)
        return {"status": "success", "name": plugin.name, "config": plugin.config}
    except Exception as exc:
        logger.error(f"[router_plugins] Ошибка обновления конфигурации плагина {name}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/{name}/uninstall", summary="Удаление установленного пользовательского плагина")
async def uninstall_plugin(name: str) -> Dict[str, Any]:
    """Удаляет директорию пользовательского плагина и перезагружает реестр."""
    try:
        res = uninstall_user_plugin(name)
        _save_plugin_state_to_config(name, False)
        reload_plugins_registry()
        return res
    except PermissionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error(f"[router_plugins] Ошибка удаления плагина {name}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка удаления плагина: {exc}")
