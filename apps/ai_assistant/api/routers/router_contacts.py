# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant - Google Contacts REST Router
# =============================================================================
# Description:
#   FastAPI маршрутизатор управления Google Контактами (People API) через навык
#   google-contacts: поиск, список телефонной книги, добавление и удаление.
#
# File: router_contacts.py
# Package: apps.ai_assistant.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-27 16:30:00
# =============================================================================

from __future__ import annotations

"""REST API маршрутизатор Google Contacts."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from apps.ai_assistant.core.skills_bridge import get_contacts_client
from logger import logger

router = APIRouter(prefix="/api/v1/contacts", tags=["Google Contacts"])


class CreateContactPayload(BaseModel):
    """Полезная нагрузка для создания контакта."""

    given_name: str = Field(..., description="Имя")
    family_name: str = Field("", description="Фамилия")
    phone: Optional[str] = Field(None, description="Номер телефона")
    email: Optional[str] = Field(None, description="Email адрес")
    organization: Optional[str] = Field(None, description="Компания / организация")
    title: Optional[str] = Field(None, description="Должность")
    notes: Optional[str] = Field(None, description="Заметки")
    account_name: Optional[str] = Field(None, description="Имя аккаунта")


@router.get("", summary="Список контактов телефонной книги")
async def list_contacts(
    query: Optional[str] = Query(None, description="Поисковый запрос (имя, телефон, email)"),
    limit: int = Query(50, ge=1, le=100, description="Максимальное количество контактов"),
    account_name: Optional[str] = Query(None, description="Имя аккаунта"),
) -> Dict[str, Any]:
    """Возвращает список контактов из телефонной книги."""
    try:
        clean_q = query if isinstance(query, str) and query.strip() else None
        clean_limit = limit if isinstance(limit, int) else 50
        clean_acc = account_name if isinstance(account_name, str) and account_name.strip() else None

        client = get_contacts_client(account_name=clean_acc)
        contacts = client.list_contacts(query=clean_q, max_results=clean_limit)
        return {"status": "success", "count": len(contacts), "contacts": contacts}
    except Exception as exc:
        logger.error(f"[RouterContacts] Ошибка получения контактов: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("", summary="Создание нового контакта")
async def create_contact(payload: CreateContactPayload) -> Dict[str, Any]:
    """Создает новый контакт в Google Contacts."""
    try:
        client = get_contacts_client(account_name=payload.account_name)
        res = client.create_contact(
            given_name=payload.given_name,
            family_name=payload.family_name,
            phone=payload.phone,
            email=payload.email,
            organization=payload.organization,
            title=payload.title,
            notes=payload.notes,
        )
        return res
    except Exception as exc:
        logger.error(f"[RouterContacts] Ошибка создания контакта: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/{resource_name:path}", summary="Удаление контакта")
async def delete_contact(
    resource_name: str,
    account_name: Optional[str] = Query(None, description="Имя аккаунта"),
) -> Dict[str, Any]:
    """Удаляет контакт по resourceName."""
    try:
        client = get_contacts_client(account_name=account_name)
        res = client.delete_contact(resource_name=resource_name)
        return res
    except Exception as exc:
        logger.error(f"[RouterContacts] Ошибка удаления контакта: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
