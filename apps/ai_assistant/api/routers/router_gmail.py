# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant - Gmail REST Router
# =============================================================================
# Description:
#   FastAPI маршрутизатор управления почтой Gmail пользователя:
#   просмотр профиля, списка папок и меток, выборка писем с поисковыми запросами,
#   детальное чтение, отправка новых сообщений, отметка прочитанными/помеченными
#   и перемещение в корзину.
#
# File: router_gmail.py
# Package: apps.ai_assistant.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 13:50:00
# =============================================================================

from __future__ import annotations
"""Маршрутизатор REST API для работы с почтой Gmail через OAuth 2.0."""

import asyncio
import time
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from logger import logger
from apps.ai_assistant.core.gmail_manager import gmail_manager
from apps.ai_assistant.core.gmail_rag_service import gmail_rag_service

router = APIRouter(prefix="/api/v1/gmail", tags=["Gmail Management"])

_IDEMPOTENCY_TTL_SEC: float = 300.0
_send_idempotency_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_send_idempotency_lock = asyncio.Lock()


class SendEmailPayload(BaseModel):
    """Полезная нагрузка отправки письма."""

    to: str = Field(..., description="Адрес получателя")
    subject: str = Field(..., description="Тема письма")
    body: str = Field(..., description="Текст сообщения")
    cc: Optional[str] = Field(default=None, description="Копия (CC)")
    bcc: Optional[str] = Field(default=None, description="Скрытая копия (BCC)")
    is_html: bool = Field(default=False, description="Признак HTML формата")
    account_name: Optional[str] = Field(default=None, description="Имя аккаунта из пула")


class ModifyLabelsPayload(BaseModel):
    """Полезная нагрузка изменения меток письма."""

    add_labels: Optional[List[str]] = Field(default_factory=list, description="Метки для добавления")
    remove_labels: Optional[List[str]] = Field(default_factory=list, description="Метки для удаления")
    account_name: Optional[str] = Field(default=None, description="Имя аккаунта")


@router.get("/profile", summary="Сводный профиль Gmail пользователя")
async def get_profile(account_name: Optional[str] = Query(None, description="Имя аккаунта")) -> Dict[str, Any]:
    """Возвращает информацию о текущем почтовом ящике Gmail и счетчиках сообщений."""
    res = await asyncio.to_thread(gmail_manager.get_profile, account_name=account_name)
    if res.get("status") == "error":
        raise HTTPException(status_code=502, detail=res.get("message", "Ошибка обращения к Gmail API"))
    return res


@router.get("/labels", summary="Список меток и папок почтового ящика")
async def get_labels(account_name: Optional[str] = Query(None, description="Имя аккаунта")) -> Dict[str, Any]:
    """Возвращает список меток и системных папок Gmail."""
    res = await asyncio.to_thread(gmail_manager.list_labels, account_name=account_name)
    if res.get("status") == "error":
        raise HTTPException(status_code=502, detail=res.get("message", "Ошибка получения меток"))
    return res


@router.get("/messages", summary="Список сообщений с фильтрацией и поиском")
async def get_messages(
    q: str = Query("", description="Поисковый запрос Gmail (например: 'is:unread', 'from:google.com')"),
    label: Optional[str] = Query(None, description="ID метки (INBOX, SENT, TRASH, SPAM, STARRED и т.д.)"),
    limit: int = Query(20, ge=1, le=50, description="Лимит сообщений на странице"),
    page_token: Optional[str] = Query(None, description="Токен следующей страницы"),
    account_name: Optional[str] = Query(None, description="Имя аккаунта"),
) -> Dict[str, Any]:
    """Выполняет поиск и постраничную выборку писем с метаданными заголовков."""
    label_ids = [label.strip()] if label and label.strip() else None
    res = await asyncio.to_thread(
        gmail_manager.list_messages,
        query=q,
        label_ids=label_ids,
        max_results=limit,
        page_token=page_token,
        account_name=account_name,
    )
    if res.get("status") == "error":
        raise HTTPException(status_code=502, detail=res.get("message", "Ошибка выборки сообщений"))
    return res


@router.get("/messages/{message_id}", summary="Полный просмотр письма")
async def get_message_detail(
    message_id: str,
    account_name: Optional[str] = Query(None, description="Имя аккаунта"),
) -> Dict[str, Any]:
    """Возвращает полное тело письма, список заголовков и вложений."""
    res = await asyncio.to_thread(gmail_manager.get_message, message_id=message_id, account_name=account_name)
    if res.get("status") == "error":
        raise HTTPException(status_code=404, detail=res.get("message", "Письмо не найдено"))
    return res


@router.post("/messages/send", summary="Отправка нового письма")
async def send_email(
    payload: SendEmailPayload,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
) -> Dict[str, Any]:
    """Отправляет электронное письмо получателю с защитой от дублирования по Idempotency-Key."""
    if not payload.to or not payload.to.strip():
        raise HTTPException(status_code=400, detail="Укажите адрес получателя (To)")
    if not payload.subject or not payload.subject.strip():
        raise HTTPException(status_code=400, detail="Укажите тему письма (Subject)")

    clean_idem = (idempotency_key or "").strip()
    if clean_idem:
        async with _send_idempotency_lock:
            now_ts = time.monotonic()
            expired = [k for k, (ts, _) in _send_idempotency_cache.items() if now_ts - ts > _IDEMPOTENCY_TTL_SEC]
            for k in expired:
                _send_idempotency_cache.pop(k, None)
            if clean_idem in _send_idempotency_cache:
                return _send_idempotency_cache[clean_idem][1]

    res = await asyncio.to_thread(
        gmail_manager.send_message,
        to=payload.to.strip(),
        subject=payload.subject.strip(),
        body=payload.body,
        cc=payload.cc,
        bcc=payload.bcc,
        is_html=payload.is_html,
        account_name=payload.account_name,
    )
    if res.get("status") == "error":
        raise HTTPException(status_code=500, detail=res.get("message", "Не удалось отправить письмо"))

    if clean_idem and isinstance(res, dict):
        async with _send_idempotency_lock:
            _send_idempotency_cache[clean_idem] = (time.monotonic(), res)
    return res


@router.post("/messages/{message_id}/modify", summary="Изменение меток (прочитано/помечено)")
async def modify_message_labels(message_id: str, payload: ModifyLabelsPayload) -> Dict[str, Any]:
    """Добавляет или снимает метки (например UNREAD, STARRED)."""
    res = await asyncio.to_thread(
        gmail_manager.modify_labels,
        message_id=message_id,
        add_labels=payload.add_labels,
        remove_labels=payload.remove_labels,
        account_name=payload.account_name,
    )
    if res.get("status") == "error":
        raise HTTPException(status_code=500, detail=res.get("message", "Ошибка изменения меток"))
    return res


@router.post("/messages/{message_id}/trash", summary="Перемещение письма в корзину")
async def trash_message_endpoint(
    message_id: str,
    account_name: Optional[str] = Query(None, description="Имя аккаунта"),
) -> Dict[str, Any]:
    """Перемещает письмо в корзину."""
    res = await asyncio.to_thread(gmail_manager.trash_message, message_id=message_id, account_name=account_name)
    if res.get("status") == "error":
        raise HTTPException(status_code=500, detail=res.get("message", "Ошибка перемещения в корзину"))
    return res


@router.post("/messages/{message_id}/untrash", summary="Восстановление письма из корзины")
async def untrash_message_endpoint(
    message_id: str,
    account_name: Optional[str] = Query(None, description="Имя аккаунта"),
) -> Dict[str, Any]:
    """Восстанавливает письмо из корзины."""
    res = await asyncio.to_thread(gmail_manager.untrash_message, message_id=message_id, account_name=account_name)
    if res.get("status") == "error":
        raise HTTPException(status_code=500, detail=res.get("message", "Ошибка восстановления"))
    return res


@router.delete("/messages/{message_id}", summary="Окончательное удаление письма")
async def delete_message_endpoint(
    message_id: str,
    account_name: Optional[str] = Query(None, description="Имя аккаунта"),
) -> Dict[str, Any]:
    """Безвозвратно удаляет письмо из ящика."""
    res = await asyncio.to_thread(gmail_manager.delete_message, message_id=message_id, account_name=account_name)
    if res.get("status") == "error":
        raise HTTPException(status_code=500, detail=res.get("message", "Ошибка удаления письма"))
    return res


@router.get("/semantic_search", summary="Семантический ИИ-поиск писем через RAG и векторный индекс")
async def semantic_search_messages(
    q: str = Query(..., min_length=1, description="Естественно-языковой запрос пользователя"),
    limit: int = Query(15, ge=1, le=50, description="Максимальное количество релевантных писем"),
    account_name: Optional[str] = Query(None, description="Имя аккаунта"),
) -> Dict[str, Any]:
    """Выполняет семантический RAG-поиск писем с ранжированием релевантности через TextRAG и FAISS."""
    try:
        return await asyncio.to_thread(
            gmail_rag_service.semantic_search,
            query=q,
            limit=limit,
            account_name=account_name,
        )
    except Exception as exc:
        logger.error(f"[RouterGmail] Ошибка семантического RAG-поиска: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
