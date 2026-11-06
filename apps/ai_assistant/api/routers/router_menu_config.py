# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant WebGUI - Tab Menu Config Router
# =============================================================================
# Description:
#   REST API роутер для управления файлами конфигурации меню (menu_config.json)
#   в директориях вкладок WebGUI. Обеспечивает чтение и сохранение пользовательского
#   порядка перетаскиваемых кнопок (Drag & Drop) панелей и блоков.
#
# Usage Examples:
#   GET /api/v1/tabs/tab_workspace/menu-config
#   PUT /api/v1/tabs/tab_workspace/menu-config
#
# File: router_menu_config.py
# Package: apps.ai_assistant.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 19:57:00
# =============================================================================

from __future__ import annotations
"""REST API роутер для чтения и сохранения конфигураций меню вкладок."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Path as FPath
from pydantic import BaseModel, Field

from logger import logger

router = APIRouter(prefix="/api/v1/tabs", tags=["WebGUI Menu Configuration"])

WEBGUI_DIR = Path(__file__).resolve().parent.parent / "webgui"


class UpdateMenuOrderRequest(BaseModel):
    """Модель запроса обновления порядка кнопок меню."""
    menu_type: str = Field(default="subtabs", description="Тип меню: subtabs или blocks")
    block_key: Optional[str] = Field(default=None, description="Ключ родительской панели для блоков (например: files)")
    order: List[str] = Field(..., description="Упорядоченный список идентификаторов кнопок или panel/block ID")


def _resolve_tab_dir(tab_id: str) -> Optional[Path]:
    """Находит директорию вкладки по её идентификатору."""
    normalized = tab_id if tab_id.startswith("tab_") else f"tab_{tab_id.replace('tab-', '')}"
    candidate = WEBGUI_DIR / normalized
    if candidate.is_dir():
        return candidate
    alt = WEBGUI_DIR / tab_id
    if alt.is_dir():
        return alt
    return None


@router.get("/{tab_id}/menu-config", summary="Получить конфигурацию меню вкладки")
async def get_tab_menu_config(
    tab_id: str = FPath(..., description="Идентификатор вкладки, например tab_workspace")
) -> Dict[str, Any]:
    """Возвращает содержимое файла menu_config.json из каталога указанной вкладки."""
    tab_dir = _resolve_tab_dir(tab_id)
    if not tab_dir:
        raise HTTPException(status_code=404, detail=f"Директория вкладки '{tab_id}' не найдена")

    config_path = tab_dir / "menu_config.json"
    if not config_path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"Конфигурационный файл menu_config.json не найден во вкладке '{tab_id}'"
        )

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        return {"status": "ok", "tab_id": tab_id, "config": data}
    except Exception as e:
        logger.error(f"Ошибка чтения menu_config.json для вкладки '{tab_id}': {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка разбора конфигурации: {e}")


@router.put("/{tab_id}/menu-config", summary="Сохранить полную конфигурацию или порядок кнопок меню")
async def save_tab_menu_config(
    tab_id: str = FPath(..., description="Идентификатор вкладки"),
    payload: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Сохраняет конфигурацию меню вкладки на диск.
    Поддерживает как полную перезапись конфигурации, так и обновление порядка кнопок.
    """
    if payload is None:
        raise HTTPException(status_code=400, detail="Тело запроса не может быть пустым")

    tab_dir = _resolve_tab_dir(tab_id)
    if not tab_dir:
        raise HTTPException(status_code=404, detail=f"Директория вкладки '{tab_id}' не найдена")

    config_path = tab_dir / "menu_config.json"

    try:
        # Если передан частичный запрос с order
        if "order" in payload and isinstance(payload["order"], list):
            if not config_path.is_file():
                raise HTTPException(status_code=404, detail="Базовый файл menu_config.json не существует")

            current_data = json.loads(config_path.read_text(encoding="utf-8"))
            order_list = payload["order"]
            menu_type = payload.get("menu_type", "subtabs")
            block_key = payload.get("block_key")

            if menu_type == "subtabs" and "subtabs" in current_data:
                items = current_data["subtabs"].get("items", [])
                items_map = {
                    (item.get("panel_id") or item.get("id") or item.get("button_id")): item
                    for item in items
                }
                reordered = []
                for idx, k in enumerate(order_list):
                    if k in items_map:
                        item = items_map[k]
                        item["order"] = idx
                        reordered.append(item)
                for k, item in items_map.items():
                    if item not in reordered:
                        item["order"] = len(reordered)
                        reordered.append(item)
                current_data["subtabs"]["items"] = reordered

            elif menu_type == "blocks" and block_key and "blocks" in current_data:
                block_group = current_data["blocks"].get(block_key, {})
                items = block_group.get("items", [])
                items_map = {
                    (item.get("block_id") or item.get("id") or item.get("button_id")): item
                    for item in items
                }
                reordered = []
                for idx, k in enumerate(order_list):
                    if k in items_map:
                        item = items_map[k]
                        item["order"] = idx
                        reordered.append(item)
                for k, item in items_map.items():
                    if item not in reordered:
                        item["order"] = len(reordered)
                        reordered.append(item)
                block_group["items"] = reordered

            config_path.write_text(json.dumps(current_data, indent=2, ensure_ascii=False), encoding="utf-8")
            logger.info(f"Порядок кнопок меню вкладки '{tab_id}' успешно обновлен")
            return {"status": "ok", "message": "Порядок кнопок сохранен", "config": current_data}

        # Полная запись конфигурации
        config_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info(f"Конфигурация menu_config.json для вкладки '{tab_id}' сохранена")
        return {"status": "ok", "message": "Конфигурация меню успешно сохранена", "config": payload}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка сохранения menu_config.json для вкладки '{tab_id}': {e}")
        raise HTTPException(status_code=500, detail=f"Не удалось сохранить конфигурацию: {e}")
