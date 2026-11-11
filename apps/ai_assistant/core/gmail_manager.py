# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant - Gmail Manager Core
# =============================================================================
# Description:
#   Ядро интеграции с Gmail API на базе авторизованного профиля Google OAuth 2.0.
#   Реализует получение профиля пользователя, списков меток и папок, выборку
#   писем с фильтрацией и поиском, детальный просмотр сообщений, отправку писем,
#   изменение меток (прочитано/непрочитано/помечено) и перемещение в корзину.
#
# File: gmail_manager.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 20:00:00
# =============================================================================

from __future__ import annotations
"""Модуль взаимодействия с Gmail API через сохраненный OAuth 2.0 токен."""

import base64
from concurrent.futures import ThreadPoolExecutor
from email.message import EmailMessage
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from googleapiclient.discovery import build

from logger import logger
from src.ai.google_accounts_state import get_account_info, load_account_credentials


class GmailManager:
    """Менеджер операций с почтовым ящиком Gmail через официальный API."""

    def __init__(self, default_account: Optional[str] = None) -> None:
        """Инициализирует менеджер Gmail.

        Args:
            default_account: Имя аккаунта Google из пула (по умолчанию 'davidka' или дефолтный).
        """
        self._default_account = default_account
        self._services: Dict[str, Any] = {}
        self._lock = threading.RLock()
        self._account_locks: Dict[str, threading.RLock] = {}
        self._cache: Dict[str, Tuple[float, Any]] = {}

    def _get_account_lock(self, account_name: str) -> threading.RLock:
        """Возвращает или создает рекурсивный мьютекс для конкретного аккаунта."""
        with self._lock:
            if account_name not in self._account_locks:
                self._account_locks[account_name] = threading.RLock()
            return self._account_locks[account_name]

    def clear_cache(self, account_name: Optional[str] = None) -> None:
        """Сбрасывает кэш профиля и меток для указанного или всех аккаунтов."""
        with self._lock:
            if account_name:
                acc = self._resolve_account_name(account_name)
                keys_to_del = [k for k in self._cache if k.startswith(f"{acc}:")]
                for k in keys_to_del:
                    self._cache.pop(k, None)
            else:
                self._cache.clear()

    def _resolve_account_name(self, account_name: Optional[str] = None) -> str:
        """Определяет имя используемого аккаунта."""
        if account_name and account_name.strip():
            return account_name.strip()
        if self._default_account and self._default_account.strip():
            return self._default_account.strip()
        info = get_account_info()
        return info.get("name", "davidka") if info else "davidka"

    def get_service(self, account_name: Optional[str] = None) -> Optional[Any]:
        """Возвращает кэшированный или новый экземпляр клиента Gmail API.

        Args:
            account_name: Имя аккаунта Google.

        Returns:
            Экземпляр клиента Google API Client Discovery или None.
        """
        acc = self._resolve_account_name(account_name)
        with self._lock:
            if acc in self._services:
                return self._services[acc]

            try:
                creds = load_account_credentials(acc)
                if not creds:
                    logger.warning(f"[GmailManager] Не удалось загрузить credentials для аккаунта '{acc}'")
                    return None
                service = build("gmail", "v1", credentials=creds, cache_discovery=False)
                self._services[acc] = service
                return service
            except Exception as exc:
                logger.error(f"[GmailManager] Ошибка создания клиента Gmail для '{acc}': {exc}")
                return None

    def get_profile(self, account_name: Optional[str] = None, force: bool = False) -> Dict[str, Any]:
        """Получает сводный профиль почтового ящика пользователя с кэшированием.

        Args:
            account_name: Имя аккаунта.
            force: Принудительное обновление без использования кэша.

        Returns:
            Словарь с email, общим числом сообщений и тредов.
        """
        acc = self._resolve_account_name(account_name)
        cache_key = f"{acc}:profile"
        if not force:
            with self._lock:
                cached = self._cache.get(cache_key)
                if cached and (time.monotonic() - cached[0] < 15.0):
                    return dict(cached[1])

        lock = self._get_account_lock(acc)
        with lock:
            if not force:
                with self._lock:
                    cached = self._cache.get(cache_key)
                    if cached and (time.monotonic() - cached[0] < 15.0):
                        return dict(cached[1])

            service = self.get_service(acc)
            if not service:
                return {
                    "status": "error",
                    "account": acc,
                    "message": f"Не удалось подключиться к Gmail для аккаунта '{acc}'. Проверьте OAuth-авторизацию.",
                }

            try:
                profile = service.users().getProfile(userId="me").execute(num_retries=3)
                res = {
                    "status": "success",
                    "account": acc,
                    "email": profile.get("emailAddress", ""),
                    "messages_total": profile.get("messagesTotal", 0),
                    "threads_total": profile.get("threadsTotal", 0),
                    "history_id": profile.get("historyId", ""),
                }
                with self._lock:
                    self._cache[cache_key] = (time.monotonic(), res)
                return res
            except Exception as exc:
                logger.error(f"[GmailManager] Ошибка получения профиля Gmail: {exc}")
                return {"status": "error", "account": acc, "message": str(exc)}

    def list_labels(self, account_name: Optional[str] = None, force: bool = False) -> Dict[str, Any]:
        """Получает список меток (папок) пользователя с информацией о непрочитанных сообщениях.

        Args:
            account_name: Имя аккаунта.
            force: Принудительное обновление без использования кэша.

        Returns:
            Словарь со списком меток.
        """
        acc = self._resolve_account_name(account_name)
        cache_key = f"{acc}:labels"
        if not force:
            with self._lock:
                cached = self._cache.get(cache_key)
                if cached and (time.monotonic() - cached[0] < 10.0):
                    return dict(cached[1])

        lock = self._get_account_lock(acc)
        with lock:
            if not force:
                with self._lock:
                    cached = self._cache.get(cache_key)
                    if cached and (time.monotonic() - cached[0] < 10.0):
                        return dict(cached[1])

            service = self.get_service(acc)
            if not service:
                return {"status": "error", "labels": [], "message": "Сервис недоступен"}

            try:
                raw_labels = service.users().labels().list(userId="me").execute(num_retries=3)
                labels_list = []
                for lab in raw_labels.get("labels", []):
                    labels_list.append({
                        "id": lab.get("id"),
                        "name": lab.get("name"),
                        "type": lab.get("type"),
                        "messages_total": lab.get("messagesTotal", 0),
                        "messages_unread": lab.get("messagesUnread", 0),
                        "threads_total": lab.get("threadsTotal", 0),
                        "threads_unread": lab.get("threadsUnread", 0),
                    })
                res = {"status": "success", "account": acc, "labels": labels_list}
                with self._lock:
                    self._cache[cache_key] = (time.monotonic(), res)
                return res
            except Exception as exc:
                logger.error(f"[GmailManager] Ошибка получения меток: {exc}")
                return {"status": "error", "labels": [], "message": str(exc)}

    def list_messages(
        self,
        query: str = "",
        label_ids: Optional[List[str]] = None,
        max_results: int = 20,
        page_token: Optional[str] = None,
        account_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Запрашивает список писем с метаданными заголовков и фрагментом текста.

        Args:
            query: Поисковый запрос Gmail (например, "from:example.com" или "is:unread").
            label_ids: Фильтр по ID меток (например, ["INBOX"]).
            max_results: Максимальное количество сообщений (по умолчанию 20).
            page_token: Токен пагинации.
            account_name: Имя аккаунта.

        Returns:
            Словарь с массивом писем и пагинацией.
        """
        acc = self._resolve_account_name(account_name)
        lock = self._get_account_lock(acc)
        with lock:
            service = self.get_service(acc)
            if not service:
                return {"status": "error", "messages": [], "message": "Сервис недоступен"}

            try:
                req_params: Dict[str, Any] = {
                    "userId": "me",
                    "maxResults": min(max(max_results, 1), 50),
                }
                if query and query.strip():
                    req_params["q"] = query.strip()
                if label_ids:
                    req_params["labelIds"] = label_ids
                if page_token:
                    req_params["pageToken"] = page_token

                res = service.users().messages().list(**req_params).execute(num_retries=3)
                raw_items = res.get("messages", [])
                next_page_token = res.get("nextPageToken", "")
                result_estimate = res.get("resultSizeEstimate", 0)

                if not raw_items:
                    return {
                        "status": "success",
                        "account": acc,
                        "messages": [],
                        "next_page_token": next_page_token,
                        "total_estimate": result_estimate,
                    }

                # Пакетная выборка легковесных метаданных чанками по 10 для предотвращения HTTP 429
                message_order_map: Dict[str, int] = {item["id"]: idx for idx, item in enumerate(raw_items)}
                ordered_results: List[Optional[Dict[str, Any]]] = [None] * len(raw_items)
                batch_chunk_size = 10

                for i in range(0, len(raw_items), batch_chunk_size):
                    chunk = raw_items[i : i + batch_chunk_size]
                    chunk_failed_ids: List[str] = []

                    def _batch_callback(request_id: str, response: Any, exception: Any) -> None:
                        if exception:
                            logger.warning(f"[GmailManager] Ошибка пакетного запроса {request_id}: {exception}")
                            chunk_failed_ids.append(request_id)
                            return
                        m_id = response.get("id", request_id)
                        headers_map = {
                            h.get("name", "").lower(): h.get("value", "")
                            for h in response.get("payload", {}).get("headers", [])
                        }
                        labels = response.get("labelIds", [])
                        item_data = {
                            "id": m_id,
                            "thread_id": response.get("threadId", ""),
                            "subject": headers_map.get("subject", "(Без темы)"),
                            "from": headers_map.get("from", ""),
                            "to": headers_map.get("to", ""),
                            "date": headers_map.get("date", ""),
                            "snippet": response.get("snippet", ""),
                            "labels": labels,
                            "is_unread": "UNREAD" in labels,
                            "is_starred": "STARRED" in labels,
                        }
                        idx = message_order_map.get(m_id)
                        if idx is not None and 0 <= idx < len(ordered_results):
                            ordered_results[idx] = item_data

                    try:
                        batch = service.new_batch_http_request(callback=_batch_callback)
                        for item in chunk:
                            batch.add(
                                service.users().messages().get(
                                    userId="me",
                                    id=item["id"],
                                    format="metadata",
                                    metadataHeaders=["Subject", "From", "To", "Date"],
                                ),
                                request_id=item["id"],
                            )
                        batch.execute()
                    except Exception as batch_exc:
                        logger.warning(f"[GmailManager] Пакетный запрос чанка не удался: {batch_exc}")
                        chunk_failed_ids.extend([it["id"] for it in chunk])

                    # Повторная выборка с экспоненциальной задержкой для отклонённых из-за 429 писем
                    if chunk_failed_ids:
                        time.sleep(0.5)
                        for fid in chunk_failed_ids:
                            try:
                                meta = service.users().messages().get(
                                    userId="me",
                                    id=fid,
                                    format="metadata",
                                    metadataHeaders=["Subject", "From", "To", "Date"],
                                ).execute(num_retries=3)
                                headers_map = {
                                    h.get("name", "").lower(): h.get("value", "")
                                    for h in meta.get("payload", {}).get("headers", [])
                                }
                                labels = meta.get("labelIds", [])
                                idx = message_order_map.get(fid)
                                if idx is not None and 0 <= idx < len(ordered_results):
                                    ordered_results[idx] = {
                                        "id": fid,
                                        "thread_id": meta.get("threadId", ""),
                                        "subject": headers_map.get("subject", "(Без темы)"),
                                        "from": headers_map.get("from", ""),
                                        "to": headers_map.get("to", ""),
                                        "date": headers_map.get("date", ""),
                                        "snippet": meta.get("snippet", ""),
                                        "labels": labels,
                                        "is_unread": "UNREAD" in labels,
                                        "is_starred": "STARRED" in labels,
                                    }
                            except Exception as seq_exc:
                                logger.warning(f"[GmailManager] Ошибка повторного чтения сообщения {fid}: {seq_exc}")

                parsed_messages = [item for item in ordered_results if item is not None]
                return {
                    "status": "success",
                    "account": acc,
                    "messages": parsed_messages,
                    "next_page_token": next_page_token,
                    "total_estimate": result_estimate,
                }
            except Exception as exc:
                logger.error(f"[GmailManager] Ошибка получения сообщений: {exc}")
                return {"status": "error", "messages": [], "message": str(exc)}

    def get_message(self, message_id: str, account_name: Optional[str] = None) -> Dict[str, Any]:
        """Получает детальную информацию о письме, включая раскодированное тело и вложения.

        Args:
            message_id: Идентификатор письма в Gmail.
            account_name: Имя аккаунта.

        Returns:
            Словарь с полным содержимым письма.
        """
        acc = self._resolve_account_name(account_name)
        lock = self._get_account_lock(acc)
        with lock:
            service = self.get_service(acc)
            if not service:
                return {"status": "error", "message": "Сервис недоступен"}

            try:
                m = service.users().messages().get(userId="me", id=message_id, format="full").execute(num_retries=3)
                payload = m.get("payload", {})
                headers_map = {
                    h.get("name", "").lower(): h.get("value", "")
                    for h in payload.get("headers", [])
                }

                plain_body, html_body, attachments = self._extract_payload_content(payload)

                labels = m.get("labelIds", [])
                return {
                    "status": "success",
                    "account": acc,
                    "id": message_id,
                    "thread_id": m.get("threadId", ""),
                    "subject": headers_map.get("subject", "(Без темы)"),
                    "from": headers_map.get("from", ""),
                    "to": headers_map.get("to", ""),
                    "cc": headers_map.get("cc", ""),
                    "bcc": headers_map.get("bcc", ""),
                    "date": headers_map.get("date", ""),
                    "snippet": m.get("snippet", ""),
                    "labels": labels,
                    "is_unread": "UNREAD" in labels,
                    "is_starred": "STARRED" in labels,
                    "body_plain": plain_body,
                    "body_html": html_body,
                    "attachments": attachments,
                }
            except Exception as exc:
                logger.error(f"[GmailManager] Ошибка получения письма {message_id}: {exc}")
                return {"status": "error", "message": str(exc)}

    def _extract_payload_content(self, payload: Dict[str, Any]) -> Tuple[str, str, List[Dict[str, Any]]]:
        """Рекурсивно извлекает текстовые части (plain и html) и метаданные вложений."""
        plain = ""
        html = ""
        attachments: List[Dict[str, Any]] = []

        def _traverse(part: Dict[str, Any]) -> None:
            nonlocal plain, html, attachments
            mime_type = part.get("mimeType", "")
            filename = part.get("filename", "")
            body = part.get("body", {})

            if filename and body.get("attachmentId"):
                attachments.append({
                    "filename": filename,
                    "mime_type": mime_type,
                    "size": body.get("size", 0),
                    "attachment_id": body.get("attachmentId"),
                })

            data_str = body.get("data")
            if data_str:
                try:
                    decoded = base64.urlsafe_b64decode(data_str).decode("utf-8", errors="replace")
                    if mime_type == "text/plain":
                        plain += decoded
                    elif mime_type == "text/html":
                        html += decoded
                except Exception as d_exc:
                    logger.warning(f"[GmailManager] Ошибка декодирования тела части: {d_exc}")

            for subpart in part.get("parts", []):
                _traverse(subpart)

        _traverse(payload)
        return plain, html, attachments

    def send_message(
        self,
        to: str,
        subject: str,
        body: str,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        is_html: bool = False,
        account_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Формирует и отправляет электронное письмо через Gmail API.

        Args:
            to: Email получателя (или список через запятую).
            subject: Тема письма.
            body: Текст письма.
            cc: Копия.
            bcc: Скрытая копия.
            is_html: Признак HTML-разметки.
            account_name: Имя аккаунта.

        Returns:
            Результат выполнения отправки.
        """
        acc = self._resolve_account_name(account_name)
        lock = self._get_account_lock(acc)
        with lock:
            service = self.get_service(acc)
            if not service:
                return {"status": "error", "message": "Сервис недоступен"}

            try:
                # Получаем собственный email для поля From
                profile = service.users().getProfile(userId="me").execute(num_retries=3)
                user_email = profile.get("emailAddress", "me")

                msg = EmailMessage()
                msg["To"] = to
                msg["From"] = user_email
                msg["Subject"] = subject
                if cc and cc.strip():
                    msg["Cc"] = cc.strip()
                if bcc and bcc.strip():
                    msg["Bcc"] = bcc.strip()

                if is_html:
                    msg.set_content(body)
                    msg.add_alternative(body, subtype="html")
                else:
                    msg.set_content(body)

                raw_bytes = msg.as_bytes()
                raw_b64 = base64.urlsafe_b64encode(raw_bytes).decode("utf-8")

                sent_res = service.users().messages().send(
                    userId="me",
                    body={"raw": raw_b64},
                ).execute(num_retries=3)

                self.clear_cache(acc)
                return {
                    "status": "success",
                    "message": "Письмо успешно отправлено",
                    "id": sent_res.get("id"),
                    "thread_id": sent_res.get("threadId"),
                }
            except Exception as exc:
                logger.error(f"[GmailManager] Ошибка отправки письма: {exc}")
                return {"status": "error", "message": str(exc)}

    def modify_labels(
        self,
        message_id: str,
        add_labels: Optional[List[str]] = None,
        remove_labels: Optional[List[str]] = None,
        account_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Добавляет или удаляет метки у сообщения (например, UNREAD, STARRED).

        Args:
            message_id: ID сообщения.
            add_labels: Список меток для добавления.
            remove_labels: Список меток для удаления.
            account_name: Имя аккаунта.

        Returns:
            Статус выполнения.
        """
        acc = self._resolve_account_name(account_name)
        lock = self._get_account_lock(acc)
        with lock:
            service = self.get_service(acc)
            if not service:
                return {"status": "error", "message": "Сервис недоступен"}

            try:
                body: Dict[str, Any] = {
                    "addLabelIds": add_labels or [],
                    "removeLabelIds": remove_labels or [],
                }
                res = service.users().messages().modify(
                    userId="me",
                    id=message_id,
                    body=body,
                ).execute(num_retries=3)
                self.clear_cache(acc)
                return {"status": "success", "id": message_id, "labels": res.get("labelIds", [])}
            except Exception as exc:
                logger.error(f"[GmailManager] Ошибка изменения меток {message_id}: {exc}")
                return {"status": "error", "message": str(exc)}

    def trash_message(self, message_id: str, account_name: Optional[str] = None) -> Dict[str, Any]:
        """Перемещает письмо в корзину (TRASH)."""
        acc = self._resolve_account_name(account_name)
        lock = self._get_account_lock(acc)
        with lock:
            service = self.get_service(acc)
            if not service:
                return {"status": "error", "message": "Сервис недоступен"}

            try:
                res = service.users().messages().trash(userId="me", id=message_id).execute(num_retries=3)
                self.clear_cache(acc)
                return {"status": "success", "id": message_id, "message": "Письмо перемещено в корзину", "labels": res.get("labelIds", [])}
            except Exception as exc:
                logger.error(f"[GmailManager] Ошибка перемещения в корзину {message_id}: {exc}")
                return {"status": "error", "message": str(exc)}

    def untrash_message(self, message_id: str, account_name: Optional[str] = None) -> Dict[str, Any]:
        """Восстанавливает письмо из корзины."""
        acc = self._resolve_account_name(account_name)
        lock = self._get_account_lock(acc)
        with lock:
            service = self.get_service(acc)
            if not service:
                return {"status": "error", "message": "Сервис недоступен"}

            try:
                res = service.users().messages().untrash(userId="me", id=message_id).execute(num_retries=3)
                self.clear_cache(acc)
                return {"status": "success", "id": message_id, "message": "Письмо восстановлено из корзины", "labels": res.get("labelIds", [])}
            except Exception as exc:
                logger.error(f"[GmailManager] Ошибка восстановления из корзины {message_id}: {exc}")
                return {"status": "error", "message": str(exc)}

    def delete_message(self, message_id: str, account_name: Optional[str] = None) -> Dict[str, Any]:
        """Безвозвратно удаляет письмо."""
        acc = self._resolve_account_name(account_name)
        lock = self._get_account_lock(acc)
        with lock:
            service = self.get_service(acc)
            if not service:
                return {"status": "error", "message": "Сервис недоступен"}

            try:
                service.users().messages().delete(userId="me", id=message_id).execute(num_retries=3)
                self.clear_cache(acc)
                return {"status": "success", "id": message_id, "message": "Письмо безвозвратно удалено"}
            except Exception as exc:
                logger.error(f"[GmailManager] Ошибка окончательного удаления {message_id}: {exc}")
                return {"status": "error", "message": str(exc)}


gmail_manager = GmailManager()
