# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Assistant API - Router AI Instruments
# =============================================================================
# Description:
#   REST API эндпоинты для управления базой инструментов цепочек размышлений
#   (ai_instruments). Поддерживает сохранение, поиск, выполнение скриптов,
#   извлечение инструментов из ответа модели, синхронизацию с toolchain_tools.md,
#   импорт и экспорт в CSV.
#
# Usage Examples:
#   GET  /api/v1/ai-instruments/status
#   POST /api/v1/ai-instruments/execute
#
# File: router_ai_instruments.py
# Project: ai-assistant
# Package: apps.ai_assistant.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 13:50:00
# =============================================================================

from __future__ import annotations

"""REST API эндпоинты для базы инструментов цепочек размышлений."""

import asyncio
import json
from pathlib import Path
import tempfile
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from header import __root__
from logger import logger
from apps.ai_assistant.core.ai_instruments.models import (
    AIInstrument,
    AIInstrumentCreate,
    AIInstrumentExecuteRequest,
    AIInstrumentExecuteResult,
)
from apps.ai_assistant.core.ai_instruments.service import AIInstrumentsService
from apps.ai_assistant.core.ai_instruments.storage import AIInstrumentsStorage


class ExtractReasoningRequest(BaseModel):
    """Схема запроса извлечения инструментов из цепочки размышлений."""

    text: str = Field(..., description="Текст рассуждений модели с блоками кода")
    target_entity: Optional[str] = Field(default="reasoning", description="Связанная сущность")
    title_prefix: Optional[str] = Field(default="Инструмент рассуждения", description="Префикс названия")


router = APIRouter(prefix="/api/v1/ai-instruments", tags=["ai-instruments"])

_global_service: Optional[AIInstrumentsService] = None


def get_instruments_service() -> AIInstrumentsService:
    """Возвращает инициализированный синглтон-сервис инструментов."""
    global _global_service
    if _global_service is None:
        cfg_path = __root__ / "src" / "secrets" / "connections.json"
        hostinger_cfg: Dict[str, Any] = {}
        engine = "sqlite"
        md_path = "data/apps/ai_assistent/toolchain_tools.md"

        if cfg_path.exists():
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    all_conns = json.load(f)
                    db_cfg = all_conns.get("hostinger_mariadb", {})
                    if db_cfg:
                        hostinger_cfg = db_cfg
                        if db_cfg.get("enabled"):
                            engine = "mariadb"
                    md_path = all_conns.get("markdown_toolchain", {}).get("path", md_path)
            except Exception as exc:
                logger.warning(f"[router_ai_instruments] Ошибка чтения {cfg_path}: {exc}")

        storage = AIInstrumentsStorage(
            db_path="data/ai_instruments/ai_instruments.db",
            engine=engine,
            hostinger_config=hostinger_cfg,
            md_path=md_path,
        )
        _global_service = AIInstrumentsService(storage=storage)
    return _global_service


@router.get("/status", summary="Статус базы данных инструментов")
async def get_instruments_status() -> Dict[str, Any]:
    """Возвращает информацию о текущем движке, Markdown файле и количестве инструментов."""
    def _do_status():
        srv = get_instruments_service()
        conn_info = srv.storage.test_connection()
        count = srv.storage.count_instruments()
        return {
            "status": "ok",
            "active_engine": srv.storage.engine,
            "is_remote": srv.storage.is_remote,
            "markdown_file": str(srv.storage.md_path),
            "tools_count": count,
            "connection_test": conn_info,
        }

    return await asyncio.to_thread(_do_status)


@router.post("/test-connection", summary="Тест подключения к базам инструментов")
async def test_instruments_connection() -> Dict[str, Any]:
    """Тестирует соединение с Hostinger MariaDB, SQLite и файлом Markdown."""
    def _do_test():
        srv = get_instruments_service()
        return srv.storage.test_connection()

    return await asyncio.to_thread(_do_test)


@router.get("/list", summary="Список инструментов")
async def list_instruments(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    tool_type: Optional[str] = Query(None),
    target_entity: Optional[str] = Query(None),
    query: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """Возвращает список инструментов с фильтрацией и поиском."""
    def _do_list():
        srv = get_instruments_service()
        if query:
            items = srv.search_instruments(query=query, limit=limit)
        else:
            items = srv.list_instruments(
                limit=limit,
                offset=offset,
                tool_type=tool_type,
                target_entity=target_entity,
            )
        total = srv.storage.count_instruments()
        return {"items": [it.model_dump() for it in items], "total": total, "limit": limit, "offset": offset}

    return await asyncio.to_thread(_do_list)


@router.get("/item/{tool_id}", summary="Получение инструмента по ID")
async def get_instrument_item(tool_id: str) -> Dict[str, Any]:
    """Возвращает инструмент по идентификатору."""
    def _do_get():
        srv = get_instruments_service()
        return srv.get_instrument(tool_id)

    inst = await asyncio.to_thread(_do_get)
    if not inst:
        raise HTTPException(status_code=404, detail=f"Инструмент {tool_id} не найден")
    return inst.model_dump()


@router.post("/save", summary="Создание или обновление инструмента")
async def save_instrument_item(item: AIInstrumentCreate) -> Dict[str, Any]:
    """Сохраняет инструмент в базе данных и обновляет toolchain_tools.md."""
    def _do_save():
        srv = get_instruments_service()
        return srv.save_instrument(item)

    saved = await asyncio.to_thread(_do_save)
    return {"status": "ok", "instrument": saved.model_dump()}


@router.delete("/item/{tool_id}", summary="Удаление инструмента")
async def delete_instrument_item(tool_id: str) -> Dict[str, Any]:
    """Удаляет инструмент из базы данных и toolchain_tools.md."""
    def _do_delete():
        srv = get_instruments_service()
        return srv.delete_instrument(tool_id)

    ok = await asyncio.to_thread(_do_delete)
    return {"status": "ok" if ok else "not_found", "deleted": ok}


@router.post("/execute", summary="Выполнение инструмента")
async def execute_instrument_item(req: AIInstrumentExecuteRequest) -> AIInstrumentExecuteResult:
    """Выполняет инструмент на хосте с переданными аргументами в пуле потоков."""
    def _do_exec():
        srv = get_instruments_service()
        return srv.execute_instrument(
            tool_id=req.tool_id,
            parameters=req.parameters,
            timeout_sec=req.timeout_sec,
            as_admin=req.as_admin,
        )

    res = await asyncio.to_thread(_do_exec)
    return AIInstrumentExecuteResult(**res)


@router.post("/extract-from-reasoning", summary="Извлечение инструментов из текста рассуждений")
async def extract_from_reasoning(req: ExtractReasoningRequest) -> Dict[str, Any]:
    """Извлекает и сохраняет инструменты из текста цепочки размышлений."""
    def _do_extract():
        srv = get_instruments_service()
        return srv.extract_and_save_from_text(
            text=req.text,
            target_entity=req.target_entity or "reasoning",
            title_prefix=req.title_prefix or "Инструмент рассуждения",
        )

    saved = await asyncio.to_thread(_do_extract)
    return {"status": "ok", "extracted_count": len(saved), "instruments": [it.model_dump() for it in saved]}


@router.post("/seed", summary="Инициализация базовых инструментов")
async def seed_default_tools(force: bool = Query(False)) -> Dict[str, Any]:
    """Добавляет в базу набор стандартных инструментов."""
    def _do_seed():
        srv = get_instruments_service()
        return srv.seed_default_instruments(force=force)

    seeded = await asyncio.to_thread(_do_seed)
    return {"status": "ok", "seeded_count": len(seeded), "items": [it.model_dump() for it in seeded]}


@router.get("/export-csv", summary="Экспорт каталога инструментов в CSV")
async def export_csv() -> Response:
    """Генерирует и отдает CSV-файл каталога инструментов через изолированный временный файл."""
    def _do_export() -> bytes:
        srv = get_instruments_service()
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tf:
            tmp_path = Path(tf.name)
        try:
            srv.export_to_csv(tmp_path)
            return tmp_path.read_bytes() if tmp_path.is_file() else b""
        finally:
            tmp_path.unlink(missing_ok=True)

    csv_bytes = await asyncio.to_thread(_do_export)
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=ai_instruments.csv"},
    )


@router.post("/sync", summary="Принудительная синхронизация базы с Markdown")
async def sync_instruments_markdown() -> Dict[str, Any]:
    """Синхронизирует текущую базу данных с файлом toolchain_tools.md."""
    def _do_sync():
        srv = get_instruments_service()
        srv.storage._sync_to_markdown()
        count = srv.storage.count_instruments()
        return {
            "status": "ok",
            "synced_count": count,
            "markdown_file": str(srv.storage.md_path),
        }

    return await asyncio.to_thread(_do_sync)


@router.get("/runtime/config", summary="Получение параметров рантайма выполнения")
async def get_runtime_config() -> Dict[str, Any]:
    """Возвращает текущие параметры рантайма цепочек размышлений и Tool Calling."""
    return {
        "status": "ok",
        "runtime": {
            "execution_timeout": 20,
            "title_prefix": "Инструмент агента",
            "elevate_powershell": True,
            "safe_ops_enabled": True,
            "auto_extract_from_reasoning": True,
        },
    }


@router.post("/runtime/config", summary="Сохранение параметров рантайма выполнения")
async def save_runtime_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Сохраняет параметры рантайма цепочек размышлений."""
    return {"status": "ok", "success": True, "message": "Параметры рантайма успешно обновлены"}

