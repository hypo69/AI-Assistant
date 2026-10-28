# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant - Models & Providers Management Router
# =============================================================================
# Description:
#   FastAPI маршрутизатор управления моделями ИИ, провайдерами (Gemini, Foundry,
#   Ollama, AGY, ONNX), системной инструкцией, избранными моделями и тестированием.
#   Обслуживает вкладку tab_models WebGUI AI Assistant.
#
# File: router_models.py
# Package: apps.ai_assistant.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 16:47:30
# =============================================================================

from __future__ import annotations

"""Маршрутизатор моделей, провайдеров, ключей и настроек ИИ."""

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from header import __root__
from logger import logger

router = APIRouter(tags=["AI Models & Providers"])


# -----------------------------------------------------------------------------
# Вспомогательные функции конфигурации
# -----------------------------------------------------------------------------

def resolve_active_config_path() -> Path:
    """Возвращает путь к активному файлу конфигурации."""
    root_cfg = __root__ / "config.json"
    if root_cfg.exists():
        return root_cfg
    app_cfg = __root__ / "apps" / "ai_assistant" / "config.json"
    if app_cfg.exists():
        return app_cfg
    return root_cfg


def save_ai_config(provider: Optional[str] = None, model_name: str = "") -> None:
    """Сохраняет выбранную модель и провайдера в конфигурационных файлах."""
    cfg = _load_root_config()
    ai_sec = cfg.setdefault("ai_providers_and_models_configuration", {})
    if model_name:
        ai_sec["default_model"] = model_name
    if provider:
        ai_sec["default_provider"] = provider
        prov_key = provider.lower().strip()
        providers = ai_sec.setdefault("providers", {})
        prov_obj = providers.setdefault(prov_key, {})
        prov_obj["enabled"] = True
        if model_name:
            prov_obj["model"] = model_name
            prov_obj["default_model"] = model_name

    cfg.pop("ai", None)

    if "llm" in cfg:
        if model_name:
            cfg["llm"]["default_model"] = model_name
        if provider:
            cfg["llm"]["default_provider"] = provider
    _save_root_config(cfg)

    # Синхронизация локальной конфигурации модуля ai_assistant при наличии
    app_cfg_path = __root__ / "apps" / "ai_assistant" / "config.json"
    if app_cfg_path.exists():
        try:
            with open(app_cfg_path, "r", encoding="utf-8") as f:
                app_cfg = json.load(f)
            if "llm" not in app_cfg:
                app_cfg["llm"] = {}
            if model_name:
                app_cfg["llm"]["default_model"] = model_name
            if provider:
                app_cfg["llm"]["default_provider"] = provider
            with open(app_cfg_path, "w", encoding="utf-8") as f:
                json.dump(app_cfg, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            logger.warning(f"[router_models] Ошибка синхронизации apps/ai_assistant/config.json: {exc}")

def _load_root_config() -> Dict[str, Any]:
    """Загружает главный конфигурационный файл config.json."""
    cfg_path = resolve_active_config_path()
    if cfg_path.exists():
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.warning(f"[router_models] Ошибка чтения {cfg_path}: {exc}")
    return {}


def _save_root_config(cfg: Dict[str, Any]) -> None:
    """Сохраняет главный конфигурационный файл config.json."""
    cfg_path = resolve_active_config_path()
    try:
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)
    except Exception as exc:
        logger.error(f"[router_models] Ошибка записи {cfg_path}: {exc}")


def _get_provider_config(provider_key: str) -> Dict[str, Any]:
    """Возвращает секцию настроек указанного провайдера."""
    cfg = _load_root_config()
    ai_sec = cfg.get("ai_providers_and_models_configuration", {})
    providers = ai_sec.get("providers", {})
    return providers.get(provider_key, {})


def _update_provider_config(provider_key: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Обновляет и сохраняет параметры конкретного провайдера."""
    cfg = _load_root_config()
    if "ai_providers_and_models_configuration" not in cfg:
        cfg["ai_providers_and_models_configuration"] = {}
    if "providers" not in cfg["ai_providers_and_models_configuration"]:
        cfg["ai_providers_and_models_configuration"]["providers"] = {}

    cur = cfg["ai_providers_and_models_configuration"]["providers"].get(provider_key, {})
    cur.update(data)
    cfg["ai_providers_and_models_configuration"]["providers"][provider_key] = cur
    _save_root_config(cfg)
    return cur


# -----------------------------------------------------------------------------
# Pydantic Модели
# -----------------------------------------------------------------------------

class SetModelRequest(BaseModel):
    """Полезная нагрузка установки активной модели."""
    model: str = Field(..., description="Название модели")
    provider: Optional[str] = Field(None, description="Провайдер модели")
    save_to_config: Optional[bool] = Field(True, description="Сохранить в config.json")


class TestModelPayload(BaseModel):
    """Полезная нагрузка тестового запроса к модели."""
    model: str = Field("", description="Название модели")
    provider: str = Field("", description="Провайдер")
    message: str = Field("", description="Текст тестового сообщения")
    system_instruction: Optional[str] = Field(None, description="Системная инструкция")


# -----------------------------------------------------------------------------
# Эндпоинты каталога и выбора моделей
# -----------------------------------------------------------------------------

@router.get("/api/v1/chat/models", summary="Каталог доступных моделей по провайдерам")
async def get_available_chat_models(refresh: bool = False, include_unsupported: bool = False) -> Dict[str, Any]:
    """Возвращает сгруппированный список моделей для всех поддерживаемых провайдеров."""
    try:
        from src.ai.model_manager import get_available_models, load_unsupported_models

        gemini_models = get_available_models("gemini", force_refresh=refresh, include_unsupported=include_unsupported)
        foundry_raw = get_available_models("foundry", force_refresh=refresh, include_unsupported=include_unsupported)
        foundry_models = [f"foundry:{m}" if not m.startswith("foundry:") else m for m in foundry_raw]

        ollama_raw = get_available_models("ollama", force_refresh=refresh, include_unsupported=include_unsupported)
        ollama_models = [f"ollama:{m}" if not m.startswith("ollama:") else m for m in ollama_raw]

        agy_models = get_available_models("agy", force_refresh=refresh, include_unsupported=include_unsupported)

        gemini_cli_raw = get_available_models("gemini_cli", force_refresh=refresh, include_unsupported=include_unsupported)
        gemini_cli_models = [f"gemini_cli:{m}" if not m.startswith("gemini_cli:") else m for m in gemini_cli_raw]

        openai_raw = get_available_models("openai", force_refresh=refresh, include_unsupported=include_unsupported)
        openai_models = [
            f"openai:{m}" if not any(m.startswith(f"{p}:") for p in ("openai", "deepseek", "groq", "openrouter", "lmstudio")) else m
            for m in openai_raw
        ]

        return {
            "models": {
                "gemini": gemini_models or ["gemini-3.1-flash-lite", "gemini-2.5-flash"],
                "foundry": foundry_models or ["foundry:qwen2.5-1.5b-instruct-generic-cpu:4"],
                "ollama": ollama_models or ["ollama:llama3.1", "ollama:qwen2.5:3b"],
                "agy": agy_models or ["agy-gemini-3.6-flash"],
                "gemini_cli": gemini_cli_models or ["gemini_cli:gemini-3.1-flash-lite"],
                "openai": openai_models or ["openai:gpt-4o-mini", "deepseek:deepseek-chat"],
                "onnx": ["onnx:directml-default"],
            },
            "unsupported_models": {
                "gemini": list(load_unsupported_models("gemini")),
                "foundry": list(load_unsupported_models("foundry")),
                "ollama": list(load_unsupported_models("ollama")),
                "agy": list(load_unsupported_models("agy")),
            }
        }
    except Exception as exc:
        logger.warning(f"[router_models] Ошибка загрузки списка моделей: {exc}")
        return {
            "models": {
                "gemini": ["gemini-3.1-flash-lite", "gemini-2.5-flash"],
                "agy": ["agy-gemini-3.6-flash"],
                "ollama": ["ollama:llama3.1"],
                "foundry": ["foundry:qwen2.5-1.5b"],
            }
        }


@router.get("/api/v1/chat/active-model", summary="Текущая активная модель")
@router.get("/api/v1/tc/model", summary="Текущая модель TC")
async def get_active_model() -> Dict[str, Any]:
    """Возвращает текущую выбранную модель и провайдер."""
    try:
        from src.user_manager import user_manager
        settings = user_manager.get_user_settings(1) or {}
        if settings.get("model"):
            user_model = settings.get("model")
            prov = "gemini"
            mod = user_model
            if ":" in user_model:
                prov, mod = user_model.split(":", 1)
            elif user_model.startswith("agy-"):
                prov, mod = "agy", user_model
            return {"status": "ok", "provider": prov, "model": mod, "config_file": "user_settings"}
    except Exception:
        pass

    cfg = _load_root_config()
    ai_sec = cfg.get("ai_providers_and_models_configuration", {})
    prov = ai_sec.get("default_provider", "gemini")
    model = ai_sec.get("default_model", "gemini-3.1-flash-lite")
    return {"status": "ok", "provider": prov, "model": model, "config_file": "config.json"}


@router.post("/api/v1/tc/model", summary="Сохранить активную модель")
@router.post("/api/v1/chat/model", summary="Установить модель чата")
async def set_active_model(req: SetModelRequest) -> Dict[str, Any]:
    """Сохраняет выбранную модель и провайдер в конфигурации и настройках пользователя."""
    target_model = req.model.strip()
    provider = (req.provider or "").strip().lower()
    if not provider:
        if ":" in target_model:
            provider, target_model = target_model.split(":", 1)
        elif target_model.startswith("agy-"):
            provider = "agy"
        else:
            provider = "gemini"

    try:
        from src.user_manager import user_manager
        user_manager.update_user_settings(1, model=target_model)
    except Exception as exc:
        logger.debug(f"[router_models] Ошибка обновления user_settings: {exc}")

    if req.save_to_config:
        save_ai_config(provider=provider, model_name=target_model)

    return {
        "status": "success",
        "message": f"Модель {target_model} успешно сохранена",
        "model": target_model,
        "provider": provider
    }


# -----------------------------------------------------------------------------
# Эндпоинты настроек пользователя и избранных моделей (/auth/settings, /auth/favorites)
# -----------------------------------------------------------------------------

@router.get("/auth/settings", summary="Чтение настроек профиля пользователя")
@router.get("/api/v1/auth/settings", summary="Чтение настроек профиля пользователя (v1)")
async def get_user_auth_settings() -> Dict[str, Any]:
    """Возвращает сохраненные настройки пользователя, включая избранные модели."""
    try:
        from src.user_manager import user_manager
        settings = user_manager.get_user_settings(1) or {}
    except Exception:
        settings = {}

    if not settings.get("model"):
        cfg = _load_root_config()
        ai_sec = cfg.get("ai_providers_and_models_configuration", {})
        prov = ai_sec.get("default_provider", "gemini")
        model = ai_sec.get("default_model", "gemini-3.1-flash-lite")
        settings["model"] = model
        settings["provider"] = prov

    settings.setdefault("status", "ok")
    settings.setdefault("favorite_models", {})
    return settings


@router.post("/auth/settings", summary="Сохранение настроек пользователя")
@router.post("/api/v1/auth/settings", summary="Сохранение настроек пользователя (v1)")
async def update_user_auth_settings(request: Request) -> Dict[str, Any]:
    """Обновляет пользовательские настройки и активную модель."""
    try:
        body = await request.json()
        model_name = body.get("model")
        provider = body.get("provider", "")

        try:
            from src.user_manager import user_manager
            user_manager.update_user_settings(1, model=model_name)
        except Exception:
            pass

        if model_name:
            save_ai_config(provider=provider, model_name=model_name)

        return {"status": "ok", "saved": body}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@router.get("/auth/favorites", summary="Список избранных моделей")
async def get_favorite_models() -> Dict[str, Any]:
    """Возвращает словарь избранных моделей и заметок к ним."""
    try:
        from src.user_manager import user_manager
        settings = user_manager.get_user_settings(1) or {}
        favs = settings.get("favorite_models", {})
        return {"status": "ok", "favorites": favs}
    except Exception:
        return {"status": "ok", "favorites": {}}


@router.post("/auth/favorites/{model_name:path}", summary="Добавить модель в избранное")
async def add_favorite_model(model_name: str, request: Request) -> Dict[str, Any]:
    """Добавляет модель в избранное с опциональной заметкой."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    note = body.get("note", "")

    try:
        from src.user_manager import user_manager
        settings = user_manager.get_user_settings(1) or {}
        favs = dict(settings.get("favorite_models", {}))
        favs[model_name] = {"note": note, "added_at": time.time()}
        user_manager.update_user_settings(1, favorite_models=favs)
        return {"status": "ok", "model": model_name, "favorites": favs}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@router.delete("/auth/favorites/{model_name:path}", summary="Удалить модель из избранного")
async def delete_favorite_model(model_name: str) -> Dict[str, Any]:
    """Удаляет модель из списка избранного."""
    try:
        from src.user_manager import user_manager
        settings = user_manager.get_user_settings(1) or {}
        favs = dict(settings.get("favorite_models", {}))
        favs.pop(model_name, None)
        user_manager.update_user_settings(1, favorite_models=favs)
        return {"status": "ok", "model": model_name, "favorites": favs}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


# -----------------------------------------------------------------------------
# Тестирование модели в реальном времени (/api/v1/chat/test-model)
# -----------------------------------------------------------------------------

@router.post("/api/v1/chat/test-model", summary="Интерактивное тестирование генерации модели")
async def test_model_endpoint(req: TestModelPayload) -> Dict[str, Any]:
    """Отправляет тестовый запрос к указанной модели и возвращает сгенерированный ответ и задержку."""
    start_time = time.perf_counter()
    target_model = req.model.strip()
    provider = req.provider.strip().lower()

    if not target_model:
        target_model = "gemini-3.1-flash-lite"
    if not provider:
        provider = "gemini"

    test_msg = req.message.strip() or "Привет! Назови свою модель и провайдера, и подтверди готовность к работе."

    try:
        from src.ai.orchestration.unified_chat import UnifiedChatModel
        model_instance = UnifiedChatModel(
            provider=provider,
            model=target_model,
            system_instruction=req.system_instruction or "",
        )
        response_text = ""

        if hasattr(model_instance, "ask"):
            response_text = await model_instance.ask(test_msg)
        elif hasattr(model_instance, "chat"):
            response_text = await model_instance.chat(test_msg)
        elif hasattr(model_instance, "chat_stream"):
            chunks = []
            async for chunk in model_instance.chat_stream(test_msg):
                if chunk:
                    clean_chunk = chunk.replace("[CHAT]", "").replace("[VOICE]", "")
                    if clean_chunk:
                        chunks.append(clean_chunk)
            response_text = "".join(chunks)
        else:
            response_text = f"Модель {target_model} готова к генерации (режим ответа подтвержден)."

        duration_ms = round((time.perf_counter() - start_time) * 1000, 1)
        return {
            "status": "success",
            "response": response_text,
            "model": target_model,
            "provider": provider,
            "duration_ms": duration_ms
        }
    except Exception as exc:
        logger.error(f"[router_models] Ошибка проверочного запроса к {target_model}: {exc}", exc_info=True)
        duration_ms = round((time.perf_counter() - start_time) * 1000, 1)
        return {
            "status": "error",
            "message": str(exc),
            "model": target_model,
            "provider": provider,
            "duration_ms": duration_ms
        }


# -----------------------------------------------------------------------------
# Эндпоинты системной инструкции (System Instruction)
# -----------------------------------------------------------------------------

@router.get("/api/v1/tc/model-instruction", summary="Получить системную инструкцию TC")
@router.get("/api/v1/chat/model-instruction", summary="Получить системную инструкцию Chat")
@router.get("/api/admin/system_instruction", summary="Получить системную инструкцию Admin")
async def get_system_instruction() -> Dict[str, Any]:
    """Возвращает текущую системную инструкцию ИИ."""
    try:
        from src.user_manager import user_manager
        settings = user_manager.get_user_settings(1) or {}
        if settings.get("system_instruction"):
            return {"status": "success", "content": settings["system_instruction"]}
    except Exception:
        pass

    prompt_file = __root__ / "apps" / "windows" / "prompts" / "tc" / "system_instruction.md"
    if not prompt_file.exists():
        prompt_file = __root__ / "apps" / "windows" / "prompts" / "chat" / "system_instruction.md"

    if prompt_file.exists():
        try:
            return {"status": "success", "content": prompt_file.read_text(encoding="utf-8", errors="replace")}
        except Exception:
            pass

    return {"status": "success", "content": "Вы — интеллектуальный ассистент платформы AI Windows Admin."}


@router.post("/api/v1/tc/model-instruction", summary="Сохранить системную инструкцию TC")
@router.post("/api/v1/chat/model-instruction", summary="Сохранить системную инструкцию Chat")
@router.post("/api/admin/system_instruction", summary="Сохранить системную инструкцию Admin")
async def save_system_instruction(request: Request) -> Dict[str, Any]:
    """Сохраняет системную инструкцию ИИ на диск и в профиль пользователя."""
    try:
        body = await request.json()
        content = body.get("content") or body.get("instruction") or body.get("system_instruction") or ""
        if content:
            try:
                from src.user_manager import user_manager
                user_manager.update_user_settings(1, system_instruction=content)
            except Exception:
                pass

            prompt_file = __root__ / "apps" / "windows" / "prompts" / "tc" / "system_instruction.md"
            prompt_file.parent.mkdir(parents=True, exist_ok=True)
            prompt_file.write_text(content, encoding="utf-8")

        return {"status": "success", "content": content}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


# -----------------------------------------------------------------------------
# Эндпоинты конфигурации провайдеров (Foundry, Ollama, AGY, ONNX)
# -----------------------------------------------------------------------------

@router.get("/api/foundry/config", summary="Настройки Foundry")
async def get_foundry_config() -> Dict[str, Any]:
    """Получить параметры подключения к Microsoft Foundry Local."""
    return _get_provider_config("foundry")


@router.post("/api/foundry/config", summary="Сохранить настройки Foundry")
async def save_foundry_config(request: Request) -> Dict[str, Any]:
    """Сохранить параметры подключения к Microsoft Foundry Local."""
    body = await request.json()
    return _update_provider_config("foundry", body)


@router.get("/api/ollama/config", summary="Настройки Ollama")
async def get_ollama_config() -> Dict[str, Any]:
    """Получить параметры подключения к локальному серверу Ollama."""
    return _get_provider_config("ollama")


@router.post("/api/ollama/config", summary="Сохранить настройки Ollama")
async def save_ollama_config(request: Request) -> Dict[str, Any]:
    """Сохранить параметры подключения к серверу Ollama."""
    body = await request.json()
    return _update_provider_config("ollama", body)


@router.get("/api/agy/config", summary="Настройки Antigravity (AGY)")
async def get_agy_config() -> Dict[str, Any]:
    """Получить параметры конфигурации Google Antigravity (AGY)."""
    return _get_provider_config("agy")


@router.post("/api/agy/config", summary="Сохранить настройки Antigravity (AGY)")
async def save_agy_config(request: Request) -> Dict[str, Any]:
    """Сохранить параметры конфигурации Google Antigravity (AGY)."""
    body = await request.json()
    return _update_provider_config("agy", body)


@router.get("/api/onnx/config", summary="Настройки ONNX")
async def get_onnx_config() -> Dict[str, Any]:
    """Получить параметры конфигурации ONNX / DirectML."""
    return _get_provider_config("onnx")


@router.post("/api/onnx/config", summary="Сохранить настройки ONNX")
async def save_onnx_config(request: Request) -> Dict[str, Any]:
    """Сохранить параметры конфигурации ONNX / DirectML."""
    body = await request.json()
    return _update_provider_config("onnx", body)


@router.get("/api/v1/models/summary", summary="Сводка состояния моделей")
async def get_models_summary() -> Dict[str, Any]:
    """Возвращает общую сводку доступности провайдеров и моделей."""
    cfg = _load_root_config()
    ai_sec = cfg.get("ai_providers_and_models_configuration", {})
    return {
        "status": "active",
        "default_provider": ai_sec.get("default_provider", "gemini"),
        "default_model": ai_sec.get("default_model", "gemini-3.1-flash-lite"),
        "providers": list(ai_sec.get("providers", {}).keys()),
    }
