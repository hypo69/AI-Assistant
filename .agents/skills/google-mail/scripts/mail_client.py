# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Google Mail Skill - Core Client Module
# =============================================================================
# Description:
#   Базовый клиент для взаимодействия с Gmail API через сохраненные токены OAuth 2.0.
#   Предоставляет методы для чтения профиля, выборки писем, просмотра содержимого,
#   отправки новых сообщений с вложениями и управления метками.
#
# File: mail_client.py
# Package: .agents.skills.google-mail.scripts
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-27 16:15:00
# =============================================================================

from __future__ import annotations

"""Модуль клиента Gmail API для навыка google-mail."""

import base64
import os
import sys
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, List, Optional

# Добавление корня проекта в sys.path
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import header  # noqa: F401
from googleapiclient.discovery import build
from logger import logger
from src.ai.google_accounts_state import get_account_info, load_account_credentials


class GoogleMailClient:
    """Клиент для выполнения операций с Gmail через официальный API."""

    def __init__(self, account_name: Optional[str] = None) -> None:
        """Инициализирует клиент почты Google.

        Args:
            account_name: Имя аккаунта Google из настроенного пула (по умолчанию активный).
        """
        self._account_name = account_name or self._resolve_default_account()
        self._service: Optional[Any] = None

    def _resolve_default_account(self) -> str:
        """Определяет активный аккаунт по умолчанию."""
        info = get_account_info()
        return info.get("name", "davidka") if info else "davidka"

    def get_service(self) -> Any:
        """Возвращает инициализированный сервис Gmail API.

        Raises:
            RuntimeError: Если не удалось загрузить учетные данные OAuth.
        """
        if self._service is not None:
            return self._service

        creds = load_account_credentials(self._account_name)
        if not creds:
            raise RuntimeError(
                f"Не удалось получить авторизационные данные для аккаунта '{self._account_name}'. "
                "Проверьте наличие токена или выполните авторизацию через /auth/google."
            )

        self._service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        return self._service

    def get_profile(self) -> Dict[str, Any]:
        """Возвращает данные профиля почтового ящика.

        Returns:
            Словарь с полями emailAddress, messagesTotal, threadsTotal, historyId.
        """
        service = self.get_service()
        return service.users().getProfile(userId="me").execute()

    def list_messages(
        self,
        query: str = "",
        label_ids: Optional[List[str]] = None,
        max_results: int = 10,
    ) -> List[Dict[str, Any]]:
        """Ищет сообщения в почтовом ящике по запросу и меткам.

        Args:
            query: Строка поискового запроса Gmail (например: 'is:unread', 'from:boss').
            label_ids: Список идентификаторов меток (например: ['INBOX', 'UNREAD']).
            max_results: Максимальное количество сообщений для возврата.

        Returns:
            Список словарей с краткой информацией о сообщениях.
        """
        service = self.get_service()
        request_params: Dict[str, Any] = {
            "userId": "me",
            "maxResults": min(max(1, max_results), 100),
        }
        if query:
            request_params["q"] = query
        if label_ids:
            request_params["labelIds"] = label_ids

        response = service.users().messages().list(**request_params).execute()
        raw_messages = response.get("messages", [])

        results: List[Dict[str, Any]] = []
        for item in raw_messages:
            msg_id = item.get("id")
            if not msg_id:
                continue
            try:
                msg_data = (
                    service.users()
                    .messages()
                    .get(userId="me", id=msg_id, format="metadata", metadataHeaders=["Subject", "From", "Date"])
                    .execute()
                )
                headers = {h.get("name", ""): h.get("value", "") for h in msg_data.get("payload", {}).get("headers", [])}
                results.append({
                    "id": msg_id,
                    "thread_id": msg_data.get("threadId", ""),
                    "snippet": msg_data.get("snippet", ""),
                    "subject": headers.get("Subject", "(Без темы)"),
                    "from": headers.get("From", ""),
                    "date": headers.get("Date", ""),
                    "labels": msg_data.get("labelIds", []),
                })
            except Exception as exc:
                logger.warning(f"[GoogleMailClient] Ошибка получения метаданных письма {msg_id}: {exc}")
                results.append({"id": msg_id, "error": str(exc)})

        return results

    def get_message(self, message_id: str) -> Dict[str, Any]:
        """Возвращает детальную информацию о сообщении, включая тело письма.

        Args:
            message_id: Уникальный ID сообщения в Gmail.

        Returns:
            Словарь с темой, отправителем, получателем, датой, телом письма и списком вложений.
        """
        service = self.get_service()
        msg = service.users().messages().get(userId="me", id=message_id, format="full").execute()

        payload = msg.get("payload", {})
        headers = {h.get("name", ""): h.get("value", "") for h in payload.get("headers", [])}

        body_text = ""
        body_html = ""
        attachments = []

        def _extract_parts(part: Dict[str, Any]) -> None:
            nonlocal body_text, body_html
            mime_type = part.get("mimeType", "")
            filename = part.get("filename", "")
            body = part.get("body", {})

            if filename:
                attachments.append({
                    "filename": filename,
                    "mime_type": mime_type,
                    "size": body.get("size", 0),
                    "attachment_id": body.get("attachmentId", ""),
                })
                return

            data = body.get("data")
            if data:
                try:
                    decoded = base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", errors="replace")
                    if mime_type == "text/plain" and not body_text:
                        body_text = decoded
                    elif mime_type == "text/html" and not body_html:
                        body_html = decoded
                except Exception as ex:
                    logger.warning(f"[GoogleMailClient] Ошибка декодирования тела письма: {ex}")

            for sub_part in part.get("parts", []):
                _extract_parts(sub_part)

        _extract_parts(payload)

        return {
            "id": message_id,
            "thread_id": msg.get("threadId", ""),
            "snippet": msg.get("snippet", ""),
            "subject": headers.get("Subject", "(Без темы)"),
            "from": headers.get("From", ""),
            "to": headers.get("To", ""),
            "date": headers.get("Date", ""),
            "labels": msg.get("labelIds", []),
            "body_plain": body_text or msg.get("snippet", ""),
            "body_html": body_html,
            "attachments": attachments,
        }

    def send_message(
        self,
        to: str,
        subject: str,
        body_plain: str,
        body_html: Optional[str] = None,
        attachments: Optional[List[str]] = None,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Отправляет электронное письмо через Gmail API.

        Args:
            to: Email получателя (или через запятую).
            subject: Тема письма.
            body_plain: Текст письма в обычном формате.
            body_html: Опциональный HTML вариант текста.
            attachments: Список путей к файлам для прикрепления.
            cc: Опциональные адресаты копии.
            bcc: Опциональные адресаты скрытой копии.

        Returns:
            Словарь с результатом отправки: id, threadId, status.
        """
        service = self.get_service()
        msg = EmailMessage()
        msg["To"] = to
        msg["Subject"] = subject
        if cc:
            msg["Cc"] = cc
        if bcc:
            msg["Bcc"] = bcc

        msg.set_content(body_plain)
        if body_html:
            msg.add_alternative(body_html, subtype="html")

        if attachments:
            for attach_path in attachments:
                p = Path(attach_path)
                if not p.is_file():
                    logger.warning(f"[GoogleMailClient] Вложение не найдено: {attach_path}")
                    continue
                file_bytes = p.read_bytes()
                msg.add_attachment(
                    file_bytes,
                    maintype="application",
                    subtype="octet-stream",
                    filename=p.name,
                )

        raw_bytes = msg.as_bytes()
        encoded_message = base64.urlsafe_b64encode(raw_bytes).decode("utf-8")
        body_payload = {"raw": encoded_message}

        sent = service.users().messages().send(userId="me", body=body_payload).execute()
        return {
            "status": "success",
            "id": sent.get("id", ""),
            "thread_id": sent.get("threadId", ""),
            "labels": sent.get("labelIds", []),
        }

    def modify_labels(
        self,
        message_id: str,
        add_labels: Optional[List[str]] = None,
        remove_labels: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Добавляет или удаляет метки у сообщения.

        Args:
            message_id: ID сообщения.
            add_labels: Список меток для добавления.
            remove_labels: Список меток для снятия.

        Returns:
            Словарь с обновленными метками.
        """
        service = self.get_service()
        payload: Dict[str, Any] = {
            "addLabelIds": add_labels or [],
            "removeLabelIds": remove_labels or [],
        }
        res = service.users().messages().modify(userId="me", id=message_id, body=payload).execute()
        return {"status": "success", "id": message_id, "labels": res.get("labelIds", [])}

    def trash_message(self, message_id: str) -> Dict[str, Any]:
        """Перемещает сообщение в корзину.

        Args:
            message_id: ID сообщения.

        Returns:
            Словарь с результатом операции.
        """
        service = self.get_service()
        res = service.users().messages().trash(userId="me", id=message_id).execute()
        return {"status": "success", "id": message_id, "trashed": True}
