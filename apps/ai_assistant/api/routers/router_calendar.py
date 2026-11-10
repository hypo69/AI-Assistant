# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant - Google Calendar REST Router
# =============================================================================
# Description:
#   FastAPI маршрутизатор управления Google Календарем через навык google-calendar.
#   Предоставляет endpoints для просмотра событий, создания встреч и удаления.
#
# File: router_calendar.py
# Package: apps.ai_assistant.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 13:50:00
# =============================================================================

from __future__ import annotations

"""REST API маршрутизатор Google Календаря."""

import asyncio
from datetime import datetime, timedelta, timezone
import time
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from apps.ai_assistant.core.skills_bridge import get_calendar_client
from logger import logger

router = APIRouter(prefix="/api/v1/calendar", tags=["Google Calendar"])

_IDEMPOTENCY_TTL_SEC: float = 300.0
_idempotency_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_idempotency_lock = asyncio.Lock()


class CreateEventPayload(BaseModel):
    """Полезная нагрузка для создания события в календаре."""

    summary: str = Field(..., description="Название события")
    start_time: str = Field(..., description="Время начала в ISO формате")
    end_time: str = Field(..., description="Время окончания в ISO формате")
    description: str = Field(default="", description="Описание события")
    location: str = Field(default="", description="Место проведения или ссылка")
    attendees: Optional[List[str]] = Field(default_factory=list, description="Email участников")
    calendar_id: str = Field(default="primary", description="ID календаря")
    account_name: Optional[str] = Field(default=None, description="Имя аккаунта")


@router.get("/events", summary="Список предстоящих событий")
async def list_events(
    days: int = Query(7, ge=1, le=90, description="Количество дней вперед"),
    query: Optional[str] = Query(None, description="Текстовый фильтр"),
    limit: int = Query(25, ge=1, le=100, description="Лимит событий"),
    calendar_id: str = Query("primary", description="ID календаря"),
    account_name: Optional[str] = Query(None, description="Имя аккаунта"),
) -> Dict[str, Any]:
    """Возвращает список событий календаря на ближайшие дни."""
    try:
        clean_days = days if isinstance(days, int) else 7
        clean_q = query if isinstance(query, str) and query.strip() else None
        clean_limit = limit if isinstance(limit, int) else 25
        clean_cal_id = calendar_id if isinstance(calendar_id, str) and calendar_id.strip() else "primary"
        clean_acc = account_name if isinstance(account_name, str) and account_name.strip() else None

        now = datetime.now(timezone.utc)
        time_max = (now + timedelta(days=clean_days)).isoformat()

        def _fetch_events():
            client = get_calendar_client(account_name=clean_acc)
            return client.list_events(
                calendar_id=clean_cal_id,
                time_min=now.isoformat(),
                time_max=time_max,
                query=clean_q,
                max_results=clean_limit,
            )

        events = await asyncio.to_thread(_fetch_events)
        return {"status": "success", "count": len(events), "events": events}
    except Exception as exc:
        parsed = logger.google_error(exc, context="RouterCalendar.list_events")
        if parsed and parsed.reason != "unknown":
            raise HTTPException(status_code=parsed.status_code, detail=parsed.to_dict())
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/events", summary="Создание нового события")
async def create_event(
    payload: CreateEventPayload,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
) -> Dict[str, Any]:
    """Создает событие в календаре пользователя с защитой от дублей по Idempotency-Key."""
    clean_idem = (idempotency_key or "").strip()
    if clean_idem:
        async with _idempotency_lock:
            now_ts = time.monotonic()
            expired = [k for k, (ts, _) in _idempotency_cache.items() if now_ts - ts > _IDEMPOTENCY_TTL_SEC]
            for k in expired:
                _idempotency_cache.pop(k, None)
            if clean_idem in _idempotency_cache:
                return _idempotency_cache[clean_idem][1]

    try:
        def _do_create():
            client = get_calendar_client(account_name=payload.account_name)
            return client.create_event(
                summary=payload.summary,
                start_time=payload.start_time,
                end_time=payload.end_time,
                description=payload.description,
                location=payload.location,
                attendees=payload.attendees,
                calendar_id=payload.calendar_id,
            )

        res = await asyncio.to_thread(_do_create)
        if clean_idem and isinstance(res, dict):
            async with _idempotency_lock:
                _idempotency_cache[clean_idem] = (time.monotonic(), res)
        return res
    except Exception as exc:
        parsed = logger.google_error(exc, context="RouterCalendar.create_event")
        if parsed and parsed.reason != "unknown":
            raise HTTPException(status_code=parsed.status_code, detail=parsed.to_dict())
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/events/{event_id}", summary="Удаление события")
async def delete_event(
    event_id: str,
    calendar_id: str = Query("primary", description="ID календаря"),
    account_name: Optional[str] = Query(None, description="Имя аккаунта"),
) -> Dict[str, Any]:
    """Удаляет событие из календаря."""
    try:
        def _do_delete():
            client = get_calendar_client(account_name=account_name)
            return client.delete_event(event_id=event_id, calendar_id=calendar_id)

        res = await asyncio.to_thread(_do_delete)
        return res
    except Exception as exc:
        parsed = logger.google_error(exc, context="RouterCalendar.delete_event")
        if parsed and parsed.reason != "unknown":
            raise HTTPException(status_code=parsed.status_code, detail=parsed.to_dict())
        raise HTTPException(status_code=500, detail=str(exc))
