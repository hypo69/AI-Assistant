# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Google Contacts Skill - Core Client Module
# =============================================================================
# Description:
#   Базовый клиент для взаимодействия с Google People API v1 (Контакты и
#   телефонная книга) через OAuth 2.0. Предоставляет методы для получения списка
#   контактов, поиска по имени/номеру, добавления и удаления контактов.
#
# File: contacts_client.py
# Package: .agents.skills.google-contacts.scripts
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-27 16:15:00
# =============================================================================

from __future__ import annotations

"""Модуль клиента Google Contacts (People API) для навыка google-contacts."""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import header  # noqa: F401
from googleapiclient.discovery import build
from logger import logger
from src.ai.google_accounts_state import get_account_info, load_account_credentials

_PERSON_FIELDS = "names,emailAddresses,phoneNumbers,organizations,biographies,photos"


class GoogleContactsClient:
    """Клиент для выполнения операций с Google Contacts через People API v1."""

    def __init__(self, account_name: Optional[str] = None) -> None:
        """Инициализирует клиент Контактов.

        Args:
            account_name: Имя аккаунта Google из настроенного пула.
        """
        self._account_name = account_name or self._resolve_default_account()
        self._service: Optional[Any] = None

    def _resolve_default_account(self) -> str:
        """Определяет активный аккаунт по умолчанию."""
        info = get_account_info()
        return info.get("name", "davidka") if info else "davidka"

    def get_service(self) -> Any:
        """Возвращает экземпляр сервиса Google People API.

        Raises:
            RuntimeError: При отсутствии авторизационных данных.
        """
        if self._service is not None:
            return self._service

        creds = load_account_credentials(self._account_name)
        if not creds:
            raise RuntimeError(
                f"Не удалось получить авторизационные данные для аккаунта '{self._account_name}'. "
                "Проверьте наличие токена или выполните авторизацию через /auth/google."
            )

        self._service = build("people", "v1", credentials=creds, cache_discovery=False)
        return self._service

    def _normalize_person(self, person: Dict[str, Any]) -> Dict[str, Any]:
        """Преобразует структуру Google Person в удобный плоский словарь."""
        res_name = person.get("resourceName", "")
        names = person.get("names", [])
        display_name = names[0].get("displayName", "") if names else ""
        given_name = names[0].get("givenName", "") if names else ""
        family_name = names[0].get("familyName", "") if names else ""

        phones = [
            {"value": p.get("value", ""), "type": p.get("type", "mobile")}
            for p in person.get("phoneNumbers", [])
        ]
        emails = [
            {"value": e.get("value", ""), "type": e.get("type", "home")}
            for e in person.get("emailAddresses", [])
        ]
        orgs = [
            {"name": o.get("name", ""), "title": o.get("title", "")}
            for o in person.get("organizations", [])
        ]
        bios = [b.get("value", "") for b in person.get("biographies", [])]

        return {
            "resource_name": res_name,
            "display_name": display_name or "(Без имени)",
            "given_name": given_name,
            "family_name": family_name,
            "phones": phones,
            "emails": emails,
            "organizations": orgs,
            "notes": "\n".join(bios),
        }

    def list_contacts(
        self,
        query: Optional[str] = None,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """Возвращает список контактов из телефонной книги.

        Args:
            query: Текстовый поисковый запрос по имени, email или номеру телефона.
            max_results: Максимальное количество контактов (по умолчанию 50).

        Returns:
            Список нормализованных контактов.
        """
        service = self.get_service()

        if query and query.strip():
            # Поиск через searchContacts
            try:
                res = (
                    service.people()
                    .searchContacts(
                        query=query.strip(),
                        readMask=_PERSON_FIELDS,
                        pageSize=min(max(1, max_results), 30),
                    )
                    .execute()
                )
                results = res.get("results", [])
                return [self._normalize_person(r.get("person", {})) for r in results if r.get("person")]
            except Exception as ex:
                logger.warning(f"[GoogleContactsClient] Поиск через searchContacts не удался ({ex}), fallback на connections.list")

        # Листинг контактов пользователя
        res = (
            service.people()
            .connections()
            .list(
                resourceName="people/me",
                pageSize=min(max(1, max_results), 100),
                personFields=_PERSON_FIELDS,
                sortOrder="FIRST_NAME_ASCENDING",
            )
            .execute()
        )
        connections = res.get("connections", [])
        contacts = [self._normalize_person(p) for p in connections]

        if query:
            q_lower = query.lower()
            contacts = [
                c for c in contacts
                if q_lower in c["display_name"].lower()
                or any(q_lower in p["value"] for p in c["phones"])
                or any(q_lower in e["value"].lower() for e in c["emails"])
            ]

        return contacts

    def get_contact(self, resource_name: str) -> Dict[str, Any]:
        """Возвращает подробные данные контакта по его resourceName.

        Args:
            resource_name: Идентификатор контакта вида 'people/c1234567890'.

        Returns:
            Нормализованный словарь контакта.
        """
        service = self.get_service()
        person = service.people().get(resourceName=resource_name, personFields=_PERSON_FIELDS).execute()
        return self._normalize_person(person)

    def create_contact(
        self,
        given_name: str,
        family_name: str = "",
        phone: Optional[str] = None,
        email: Optional[str] = None,
        organization: Optional[str] = None,
        title: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Создает новый контакт в Google Contacts.

        Args:
            given_name: Имя контакта.
            family_name: Фамилия контакта.
            phone: Номер телефона.
            email: Электронная почта.
            organization: Организация / компания.
            title: Должность.
            notes: Заметки о контакте.

        Returns:
            Словарь созданного контакта.
        """
        service = self.get_service()
        body: Dict[str, Any] = {
            "names": [{"givenName": given_name, "familyName": family_name}],
        }
        if phone:
            body["phoneNumbers"] = [{"value": phone, "type": "mobile"}]
        if email:
            body["emailAddresses"] = [{"value": email, "type": "home"}]
        if organization or title:
            org_item: Dict[str, str] = {}
            if organization:
                org_item["name"] = organization
            if title:
                org_item["title"] = title
            body["organizations"] = [org_item]
        if notes:
            body["biographies"] = [{"value": notes}]

        created = service.people().createContact(body=body).execute()
        return {"status": "success", "contact": self._normalize_person(created)}

    def delete_contact(self, resource_name: str) -> Dict[str, Any]:
        """Удаляет контакт по resourceName.

        Args:
            resource_name: Идентификатор контакта вида 'people/c...'.

        Returns:
            Словарь со статусом операции.
        """
        service = self.get_service()
        service.people().deleteContact(resourceName=resource_name).execute()
        return {"status": "success", "resource_name": resource_name, "deleted": True}
