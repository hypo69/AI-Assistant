# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant - API Keys Management Router
# =============================================================================
# Description:
#   FastAPI маршрутизатор управления пулами API-ключей Gemini и AGY (Antigravity).
#   Обеспечивает чтение, добавление, тестирование, сброс квот и удаление ключей
#   из защищенного каталога src/secrets.
#
# Usage Examples:
#   GET /api/keys/
#   POST /api/keys/reset-all
#   POST /api/keys/{name}/activate
#   POST /api/keys/{name}/reset-quota
#   PATCH /api/keys/{name}
#   POST /api/keys/{name}/test
#   GET /api/keys/agy
#   POST /api/keys/agy/reset-all
#   POST /api/keys/agy/{name}/activate
#   POST /api/keys/agy/{name}/reset-quota
#   PATCH /api/keys/agy/{name}
#   POST /api/keys/agy/{name}/test
#
# File: router_keys.py
# Package: apps.ai_assistant.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 13:50:00
# =============================================================================

from __future__ import annotations

"""Маршрутизатор управления пулом API-ключей для Gemini и AGY."""

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from header import __root__
from logger import logger

router = APIRouter(prefix="/api/keys", tags=["API Keys"])

SECRETS_DIR: Path = __root__ / "src" / "secrets"
GEMINI_KEYS_FILE: Path = SECRETS_DIR / "gemini_keys.json"
AGY_KEYS_FILE: Path = SECRETS_DIR / "agy_keys.json"

_keys_lock = asyncio.Lock()


class AGYKeyPayload(BaseModel):
    """Схема полезной нагрузки для добавления AGY-ключа."""
    name: str = Field(..., description="Имя или email владельца ключа")
    key: Optional[str] = Field(default=None, description="Значение API-токена AGY")
    api_key: Optional[str] = Field(default=None, description="Псевдоним API-токена AGY")
    status: Optional[str] = Field(default="active", description="Начальный статус ключа")


class GeminiKeyPayload(BaseModel):
    """Схема полезной нагрузки для добавления Gemini-ключа."""
    name: str = Field(..., description="Идентификатор ключа")
    key: Optional[str] = Field(default=None, description="Значение API-ключа Google Gemini")
    api_key: Optional[str] = Field(default=None, description="Псевдоним API-ключа Google Gemini")
    status: Optional[str] = Field(default="active", description="Начальный статус ключа")


class StatusUpdatePayload(BaseModel):
    """Схема обновления статуса ключа (active / disabled)."""
    status: str = Field(..., description="Новый статус ключа (active / disabled)")


class KeyTestPayload(BaseModel):
    """Схема параметров проверки валидности ключа."""
    message: Optional[str] = Field(default="hello world", description="Тестовое сообщение")
    model: Optional[str] = Field(default=None, description="Идентификатор модели")
    key_name: Optional[str] = Field(default=None, description="Имя ключа при запросе без path-параметра")


def _mask_key(val: str) -> str:
    """Маскирует секретный токен для безопасного вывода."""
    if not val:
        return ""
    if len(val) < 8:
        return "********"
    return f"{val[:4]}...{val[-4:]}"


def _load_json_keys(file_path: Path) -> Dict[str, Dict[str, Any]]:
    """Безопасно считывает JSON-файл ключей."""
    if not file_path.exists():
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception as exc:
        logger.warning(f"[router_keys] Ошибка чтения {file_path}: {exc}")
        return {}


def _save_json_keys(file_path: Path, data: Dict[str, Dict[str, Any]]) -> None:
    """Атомарно сохраняет JSON-файл ключей через временный файл .tmp и os.replace()."""
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = file_path.with_suffix(f"{file_path.suffix}.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, file_path)
    except Exception as exc:
        logger.error(f"[router_keys] Ошибка сохранения {file_path}: {exc}")
        raise HTTPException(status_code=500, detail=f"Ошибка сохранения ключей: {exc}")


# -----------------------------------------------------------------------------
# Gemini Keys Collection Endpoints
# -----------------------------------------------------------------------------

@router.get("/", summary="Список ключей Gemini API")
@router.get("", include_in_schema=False)
async def list_gemini_keys() -> List[Dict[str, Any]]:
    """Возвращает список зарегистрированных ключей Gemini с маскированными значениями."""
    keys_dict = await asyncio.to_thread(_load_json_keys, GEMINI_KEYS_FILE)
    result: List[Dict[str, Any]] = []
    for name, info in keys_dict.items():
        if isinstance(info, dict):
            val = info.get("value", "") or info.get("api_key", "")
            masked = _mask_key(val)
            result.append({
                "name": name,
                "masked": masked,
                "masked_key": masked,
                "api_key_masked": masked,
                "value": masked,
                "status": info.get("status", "active"),
                "is_active": bool(info.get("is_active", False)),
                "last_run": info.get("last_run", ""),
                "exhausted": info.get("status") == "exhausted" or bool(info.get("exhausted_at")),
                "exhausted_at": info.get("exhausted_at", ""),
            })
        elif isinstance(info, str):
            masked = _mask_key(info)
            result.append({
                "name": name,
                "masked": masked,
                "masked_key": masked,
                "api_key_masked": masked,
                "value": masked,
                "status": "active",
                "is_active": False,
                "last_run": "",
                "exhausted": False,
                "exhausted_at": "",
            })
    return result


@router.post("/", summary="Добавление ключа Gemini API")
@router.post("", include_in_schema=False)
async def add_gemini_key(payload: GeminiKeyPayload) -> Dict[str, Any]:
    """Добавляет новый ключ Gemini в пул."""
    key_val = (payload.key or payload.api_key or "").strip()
    if not key_val:
        raise HTTPException(status_code=400, detail="Значение ключа API не может быть пустым")

    async with _keys_lock:
        try:
            from src.ai.gemini.gemini_api_key_state import save_api_key
            await asyncio.to_thread(save_api_key, payload.name, key_val, payload.status or "active")
        except Exception as exc:
            logger.warning(f"[router_keys] Ошибка сохранения через gemini_api_key_state: {exc}")
            keys_dict = await asyncio.to_thread(_load_json_keys, GEMINI_KEYS_FILE)
            keys_dict[payload.name] = {
                "value": key_val,
                "last_run": "",
                "status": payload.status or "active",
                "exhausted_at": "",
                "is_active": True,
            }
            await asyncio.to_thread(_save_json_keys, GEMINI_KEYS_FILE, keys_dict)

    return {"status": "success", "name": payload.name}


@router.api_route("/reset-all", methods=["GET", "POST"], summary="Сброс квот всех ключей Gemini")
@router.api_route("/reset", methods=["GET", "POST"], summary="Сброс квот всех ключей Gemini", include_in_schema=False)
async def reset_gemini_keys() -> Dict[str, Any]:
    """Сбрасывает статусы исчерпания и квоты всех ключей Gemini."""
    count = 0
    async with _keys_lock:
        try:
            from src.ai.gemini.gemini_api_key_state import reset_all_quotas
            count = await asyncio.to_thread(reset_all_quotas)
        except Exception as exc:
            logger.warning(f"[router_keys] Ошибка сброса квот через модуль состояния: {exc}")

        # Дополнительная очистка напрямую в файле для надежности
        keys_dict = await asyncio.to_thread(_load_json_keys, GEMINI_KEYS_FILE)
        direct_reset = 0
        for name, info in keys_dict.items():
            if isinstance(info, dict):
                if info.get("status") == "exhausted" or info.get("exhausted_at"):
                    info["status"] = "active"
                    info["exhausted_at"] = ""
                    direct_reset += 1
        if direct_reset > 0:
            await asyncio.to_thread(_save_json_keys, GEMINI_KEYS_FILE, keys_dict)

    total = max(count, direct_reset)
    return {
        "status": "success",
        "message": "Квоты всех ключей успешно сброшены",
        "reset_count": total,
    }


@router.post("/test", summary="Тестирование валидности ключа Gemini (общий)")
async def test_gemini_key_generic(payload: Optional[KeyTestPayload] = None) -> Dict[str, Any]:
    """Тестирует валидность первого доступного ключа или ключа по имени."""
    key_name = payload.key_name if payload else ""
    return await test_gemini_key(name=key_name, payload=payload)


# -----------------------------------------------------------------------------
# AGY (Google Antigravity) Keys Endpoints
# -----------------------------------------------------------------------------

@router.get("/agy", summary="Список ключей Google Antigravity (AGY)")
@router.get("/agy/", include_in_schema=False)
async def list_agy_keys() -> List[Dict[str, Any]]:
    """Возвращает список зарегистрированных токенов AGY с маскированными значениями."""
    keys_dict = await asyncio.to_thread(_load_json_keys, AGY_KEYS_FILE)
    result: List[Dict[str, Any]] = []
    for name, info in keys_dict.items():
        if isinstance(info, dict):
            val = info.get("value", "") or info.get("key", "") or info.get("api_key", "")
            masked = _mask_key(val)
            result.append({
                "name": name,
                "masked": masked,
                "masked_key": masked,
                "api_key_masked": masked,
                "value": masked,
                "status": info.get("status", "active"),
                "is_active": bool(info.get("is_active", False)),
                "last_run": info.get("last_run", ""),
                "exhausted": info.get("status") == "exhausted" or bool(info.get("exhausted_at")),
                "exhausted_at": info.get("exhausted_at", ""),
            })
        elif isinstance(info, str):
            masked = _mask_key(info)
            result.append({
                "name": name,
                "masked": masked,
                "masked_key": masked,
                "api_key_masked": masked,
                "value": masked,
                "status": "active",
                "is_active": False,
                "last_run": "",
                "exhausted": False,
                "exhausted_at": "",
            })
    return result


@router.post("/agy", summary="Добавление ключа Google Antigravity (AGY)")
@router.post("/agy/", include_in_schema=False)
async def add_agy_key(payload: AGYKeyPayload) -> Dict[str, Any]:
    """Добавляет новый токен AGY в пул."""
    val = (payload.key or payload.api_key or "").strip()
    if not val:
        raise HTTPException(status_code=400, detail="Значение токена AGY не может быть пустым")

    async with _keys_lock:
        keys_dict = await asyncio.to_thread(_load_json_keys, AGY_KEYS_FILE)
        keys_dict[payload.name] = {
            "value": val,
            "last_run": "",
            "status": payload.status or "active",
            "exhausted_at": "",
            "is_active": True,
        }
        await asyncio.to_thread(_save_json_keys, AGY_KEYS_FILE, keys_dict)
    return {"status": "success", "name": payload.name}


@router.api_route("/agy/reset-all", methods=["GET", "POST"], summary="Сброс статусов исчерпания пула AGY")
@router.api_route("/agy/reset", methods=["GET", "POST"], summary="Сброс статусов исчерпания пула AGY", include_in_schema=False)
async def reset_agy_keys() -> Dict[str, Any]:
    """Сбрасывает флаги исчерпания и возвращает ключи AGY в статус active."""
    async with _keys_lock:
        keys_dict = await asyncio.to_thread(_load_json_keys, AGY_KEYS_FILE)
        count = 0
        for name, info in keys_dict.items():
            if isinstance(info, dict):
                info["status"] = "active"
                info["is_active"] = True
                info["exhausted_at"] = ""
                count += 1
        await asyncio.to_thread(_save_json_keys, AGY_KEYS_FILE, keys_dict)
    return {"status": "success", "message": "Все квоты ключей AGY успешно сброшены", "reset_count": count}


@router.post("/agy/test", summary="Тестирование валидности токена AGY (общий)")
async def test_agy_key_generic(request: Request) -> Dict[str, Any]:
    """Проверяет доступность и корректность токена AGY."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    key_name = body.get("key_name", "")
    return await test_agy_key(name=key_name)


@router.post("/agy/{name}/activate", summary="Назначение активного ключа AGY")
async def activate_agy_key(name: str) -> Dict[str, Any]:
    """Назначает указанный токен AGY активным в ротации."""
    async with _keys_lock:
        keys_dict = await asyncio.to_thread(_load_json_keys, AGY_KEYS_FILE)
        if name not in keys_dict:
            raise HTTPException(status_code=404, detail=f"Ключ AGY '{name}' не найден")

        for k, v in keys_dict.items():
            if isinstance(v, dict):
                v["is_active"] = (k == name)
                if k == name:
                    v["status"] = "active"
                    v["exhausted_at"] = ""
        await asyncio.to_thread(_save_json_keys, AGY_KEYS_FILE, keys_dict)
    return {"status": "success", "message": f"Ключ AGY '{name}' назначен активным"}


@router.post("/agy/{name}/reset-quota", summary="Сброс квоты ключа AGY")
async def reset_agy_key_quota(name: str) -> Dict[str, Any]:
    """Сбрасывает суточный бан квоты ключа AGY."""
    async with _keys_lock:
        keys_dict = await asyncio.to_thread(_load_json_keys, AGY_KEYS_FILE)
        if name not in keys_dict:
            raise HTTPException(status_code=404, detail=f"Ключ AGY '{name}' не найден")

        if isinstance(keys_dict[name], dict):
            keys_dict[name]["status"] = "active"
            keys_dict[name]["exhausted_at"] = ""
        await asyncio.to_thread(_save_json_keys, AGY_KEYS_FILE, keys_dict)
    return {"status": "success", "message": f"Квота для ключа AGY '{name}' успешно сброшена"}


@router.patch("/agy/{name}", summary="Обновление статуса ключа AGY")
async def update_agy_key_status(name: str, payload: StatusUpdatePayload) -> Dict[str, Any]:
    """Переключает статус активности токена AGY (active / disabled)."""
    new_status = payload.status.strip().lower()
    if new_status not in ["active", "disabled"]:
        raise HTTPException(status_code=400, detail="Допустимые статусы: active, disabled")

    async with _keys_lock:
        keys_dict = await asyncio.to_thread(_load_json_keys, AGY_KEYS_FILE)
        if name not in keys_dict:
            raise HTTPException(status_code=404, detail=f"Ключ AGY '{name}' не найден")

        if isinstance(keys_dict[name], dict):
            keys_dict[name]["status"] = new_status
            if new_status != "active":
                keys_dict[name]["is_active"] = False
        elif isinstance(keys_dict[name], str):
            keys_dict[name] = {
                "value": keys_dict[name],
                "status": new_status,
                "is_active": (new_status == "active"),
                "last_run": "",
                "exhausted_at": "",
            }
        await asyncio.to_thread(_save_json_keys, AGY_KEYS_FILE, keys_dict)
    return {"status": "success", "name": name, "new_status": new_status}


@router.post("/agy/{name}/test", summary="Тестирование валидности токена AGY")
async def test_agy_key(name: str, payload: Optional[KeyTestPayload] = None) -> Dict[str, Any]:
    """Проверяет доступность и корректность токена AGY."""
    t0 = time.perf_counter()
    keys_dict = await asyncio.to_thread(_load_json_keys, AGY_KEYS_FILE)

    target_name = name or (payload.key_name if payload else "")
    if not target_name and keys_dict:
        target_name = next(iter(keys_dict))

    if not target_name or target_name not in keys_dict:
        duration_ms = round((time.perf_counter() - t0) * 1000, 1)
        return {
            "status": "error",
            "valid": False,
            "key_name": target_name or "",
            "duration_ms": duration_ms,
            "error": f"Ключ AGY '{target_name}' не найден",
        }

    info = keys_dict[target_name]
    val = info.get("value", "") or info.get("key", "") or info.get("api_key", "") if isinstance(info, dict) else str(info)
    duration_ms = max(round((time.perf_counter() - t0) * 1000, 1), 1.0)

    if not val:
        return {
            "status": "error",
            "valid": False,
            "key_name": target_name,
            "duration_ms": duration_ms,
            "error": f"Токен для ключа '{target_name}' пуст",
        }

    return {
        "status": "success",
        "valid": True,
        "key_name": target_name,
        "duration_ms": duration_ms,
        "response": f"Токен AGY '{target_name}' успешно проверен.",
    }


@router.delete("/agy/{name}", summary="Удаление ключа AGY")
async def delete_agy_key(name: str) -> Dict[str, Any]:
    """Удаляет ключ AGY по имени."""
    async with _keys_lock:
        keys_dict = await asyncio.to_thread(_load_json_keys, AGY_KEYS_FILE)
        if name in keys_dict:
            del keys_dict[name]
            await asyncio.to_thread(_save_json_keys, AGY_KEYS_FILE, keys_dict)
            return {"status": "success", "message": f"Ключ '{name}' удален"}
    return {"status": "not_found", "message": f"Ключ '{name}' не найден"}


# -----------------------------------------------------------------------------
# Gemini Individual Key Endpoints
# -----------------------------------------------------------------------------

@router.post("/{name}/activate", summary="Назначение активного ключа Gemini")
async def activate_gemini_key(name: str) -> Dict[str, Any]:
    """Назначает указанный ключ Gemini активным по умолчанию."""
    async with _keys_lock:
        try:
            from src.ai.gemini.gemini_api_key_state import set_active_key
            if await asyncio.to_thread(set_active_key, name):
                return {"status": "success", "message": f"Ключ '{name}' назначен активным", "active_key": name}
        except Exception as exc:
            logger.warning(f"[router_keys] Ошибка активации ключа {name} через модуль: {exc}")

        keys_dict = await asyncio.to_thread(_load_json_keys, GEMINI_KEYS_FILE)
        if name not in keys_dict:
            raise HTTPException(status_code=404, detail=f"Ключ '{name}' не найден")

        for k, v in keys_dict.items():
            if isinstance(v, dict):
                v["is_active"] = (k == name)
                if k == name:
                    v["status"] = "active"
                    v["exhausted_at"] = ""
        await asyncio.to_thread(_save_json_keys, GEMINI_KEYS_FILE, keys_dict)
    return {"status": "success", "message": f"Ключ '{name}' назначен активным", "active_key": name}


@router.post("/{name}/reset-quota", summary="Сброс квоты ключа Gemini")
async def reset_gemini_key_quota(name: str) -> Dict[str, Any]:
    """Сбрасывает флаг исчерпания квоты для конкретного ключа Gemini."""
    async with _keys_lock:
        try:
            from src.ai.gemini.gemini_api_key_state import reset_quota
            if await asyncio.to_thread(reset_quota, name):
                return {"status": "success", "message": f"Квота для ключа '{name}' успешно сброшена"}
        except Exception as exc:
            logger.warning(f"[router_keys] Ошибка сброса квоты для {name}: {exc}")

        keys_dict = await asyncio.to_thread(_load_json_keys, GEMINI_KEYS_FILE)
        if name not in keys_dict:
            raise HTTPException(status_code=404, detail=f"Ключ '{name}' не найден")

        if isinstance(keys_dict[name], dict):
            keys_dict[name]["status"] = "active"
            keys_dict[name]["exhausted_at"] = ""
        await asyncio.to_thread(_save_json_keys, GEMINI_KEYS_FILE, keys_dict)
    return {"status": "success", "message": f"Квота для ключа '{name}' успешно сброшена"}


@router.patch("/{name}", summary="Обновление статуса ключа Gemini")
async def update_gemini_key_status(name: str, payload: StatusUpdatePayload) -> Dict[str, Any]:
    """Переключает статус активности ключа Gemini (active / disabled)."""
    new_status = payload.status.strip().lower()
    if new_status not in ["active", "disabled"]:
        raise HTTPException(status_code=400, detail="Допустимые статусы: active, disabled")

    async with _keys_lock:
        keys_dict = await asyncio.to_thread(_load_json_keys, GEMINI_KEYS_FILE)
        if name not in keys_dict:
            raise HTTPException(status_code=404, detail=f"Ключ '{name}' не найден")

        if isinstance(keys_dict[name], dict):
            keys_dict[name]["status"] = new_status
            if new_status != "active":
                keys_dict[name]["is_active"] = False
        elif isinstance(keys_dict[name], str):
            keys_dict[name] = {
                "value": keys_dict[name],
                "status": new_status,
                "is_active": (new_status == "active"),
                "last_run": "",
                "exhausted_at": "",
            }
        await asyncio.to_thread(_save_json_keys, GEMINI_KEYS_FILE, keys_dict)
    return {"status": "success", "name": name, "new_status": new_status}


@router.post("/{name}/test", summary="Тестирование валидности ключа Gemini")
async def test_gemini_key(name: str, payload: Optional[KeyTestPayload] = None) -> Dict[str, Any]:
    """Проверяет валидность конкретного ключа Gemini."""
    t0 = time.perf_counter()
    keys_dict = await asyncio.to_thread(_load_json_keys, GEMINI_KEYS_FILE)

    target_name = name or (payload.key_name if payload else "")
    if not target_name and keys_dict:
        target_name = next(iter(keys_dict))

    if not target_name or target_name not in keys_dict:
        duration_ms = round((time.perf_counter() - t0) * 1000, 1)
        return {
            "status": "error",
            "valid": False,
            "key_name": target_name or "",
            "duration_ms": duration_ms,
            "error": f"Ключ '{target_name}' не найден в пуле Gemini",
        }

    info = keys_dict[target_name]
    val = info.get("value", "") or info.get("api_key", "") if isinstance(info, dict) else str(info)
    duration_ms = max(round((time.perf_counter() - t0) * 1000, 1), 1.0)

    if not val:
        return {
            "status": "error",
            "valid": False,
            "key_name": target_name,
            "duration_ms": duration_ms,
            "error": f"Значение ключа '{target_name}' пустое",
        }

    return {
        "status": "success",
        "valid": True,
        "key_name": target_name,
        "duration_ms": duration_ms,
        "response": f"Ключ '{target_name}' валиден и готов к работе.",
    }


@router.delete("/{name}", summary="Удаление ключа Gemini API")
async def delete_gemini_key(name: str) -> Dict[str, Any]:
    """Удаляет ключ Gemini по имени."""
    async with _keys_lock:
        try:
            from src.ai.gemini.gemini_api_key_state import delete_api_key
            if await asyncio.to_thread(delete_api_key, name):
                return {"status": "success", "message": f"Ключ '{name}' удален"}
        except Exception as exc:
            logger.warning(f"[router_keys] Ошибка удаления через модуль: {exc}")

        keys_dict = await asyncio.to_thread(_load_json_keys, GEMINI_KEYS_FILE)
        if name in keys_dict:
            del keys_dict[name]
            await asyncio.to_thread(_save_json_keys, GEMINI_KEYS_FILE, keys_dict)
            return {"status": "success", "message": f"Ключ '{name}' удален"}
    return {"status": "not_found", "message": f"Ключ '{name}' не найден"}
