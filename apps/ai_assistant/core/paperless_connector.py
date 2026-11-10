# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Core - Paperless-ngx Connector
# =============================================================================
# Description:
#   Единый REST-клиент Paperless-ngx (DMS). Paperless — источник первичных
#   документов и OCR-текста; AI-Assistant хранит только факты, связи и ссылки
#   paperless_id, не дублируя текст в собственной БД.
#
# Usage Examples:
#   from apps.ai_assistant.core.paperless_connector import PaperlessConnector
#
#   connector = PaperlessConnector.from_config()
#   for doc in connector.iter_documents(tag_name="ws-default"):
#       text = connector.get_document_content(doc["id"])
#
# File: paperless_connector.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 16:05:00
# =============================================================================

from __future__ import annotations
"""REST-клиент Paperless-ngx: аутентификация по токену, документы, теги, задачи."""

import json
import os
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from logger import logger

TOKEN_ENV_VAR = "PAPERLESS_API_TOKEN"


class PaperlessError(RuntimeError):
    """Ошибка взаимодействия с Paperless-ngx API."""


class PaperlessConnector:
    """Клиент Paperless-ngx REST API с таймаутами и Exponential Backoff."""

    def __init__(
        self,
        base_url: str,
        token: str,
        api_version: int,
        connect_timeout: float,
        read_timeout: float,
        upload_timeout: float,
        retries: int,
        workspace_tag_prefix: str,
    ) -> None:
        """Создаёт клиент; все параметры передаются явно (DI), без значений по умолчанию.

        Args:
            base_url: Адрес Paperless (например, http://127.0.0.1:8000).
            token: API-токен Paperless (хранится в .env).
            api_version: Версия API Paperless.
            connect_timeout: Таймаут соединения, сек.
            read_timeout: Таймаут чтения, сек.
            upload_timeout: Таймаут чтения при загрузке файла, сек.
            retries: Число повторов при сетевых/5xx ошибках.
            workspace_tag_prefix: Префикс тега, отображающего рабочую область.

        Raises:
            PaperlessError: Если не задан адрес или токен.
        """
        if not base_url or not token:
            raise PaperlessError(f"Не заданы адрес Paperless или токен ({TOKEN_ENV_VAR})")
        self.base_url = base_url.rstrip("/")
        self.workspace_tag_prefix = workspace_tag_prefix
        self._timeout = (connect_timeout, read_timeout)
        self._upload_timeout = (connect_timeout, upload_timeout)
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Token {token}",
                "Accept": f"application/json; version={api_version}",
            }
        )
        retry = Retry(
            total=retries,
            backoff_factor=0.5,
            status_forcelist=(502, 503, 504),
            allowed_methods=frozenset({"GET", "HEAD"}),
        )
        self._session.mount("http://", HTTPAdapter(max_retries=retry))
        self._session.mount("https://", HTTPAdapter(max_retries=retry))

    @classmethod
    def from_config(cls, config_path: Optional[Path | str] = None) -> "PaperlessConnector":
        """Создаёт клиент из секции `paperless` файла config.json и токена из окружения.

        Args:
            config_path: Путь к config.json (по умолчанию — корень проекта).

        Returns:
            PaperlessConnector: Готовый клиент.

        Raises:
            PaperlessError: Если секция или токен отсутствуют.
        """
        from header import __root__

        path = Path(config_path) if config_path else Path(__root__) / "config.json"
        section = json.loads(path.read_text(encoding="utf-8")).get("paperless")
        if not section:
            raise PaperlessError(f"В {path} отсутствует секция 'paperless'")
        return cls(
            base_url=section["base_url"],
            token=os.environ.get(TOKEN_ENV_VAR, ""),
            api_version=int(section["api_version"]),
            connect_timeout=float(section["connect_timeout_sec"]),
            read_timeout=float(section["read_timeout_sec"]),
            upload_timeout=float(section["upload_timeout_sec"]),
            retries=int(section["retries"]),
            workspace_tag_prefix=section["workspace_tag_prefix"],
        )

    def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        """Выполняет HTTP-запрос и приводит сетевые/HTTP-ошибки к PaperlessError."""
        kwargs.setdefault("timeout", self._timeout)
        url = f"{self.base_url}{path}"
        try:
            response = self._session.request(method, url, **kwargs)
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.error(f"[PaperlessConnector] {method} {path}: {exc}")
            raise PaperlessError(f"{method} {path}: {exc}") from exc
        return response

    @staticmethod
    def obtain_token(base_url: str, username: str, password: str, timeout: float) -> str:
        """Получает API-токен по логину и паролю (однократная настройка).

        Args:
            base_url: Адрес Paperless.
            username: Имя пользователя.
            password: Пароль.
            timeout: Таймаут запроса, сек.

        Returns:
            str: API-токен.

        Raises:
            PaperlessError: При ошибке аутентификации.
        """
        try:
            resp = requests.post(
                f"{base_url.rstrip('/')}/api/token/",
                json={"username": username, "password": password},
                timeout=timeout,
            )
            resp.raise_for_status()
            return str(resp.json()["token"])
        except (requests.RequestException, KeyError, ValueError) as exc:
            raise PaperlessError(f"Не удалось получить токен: {exc}") from exc

    def ping(self) -> bool:
        """Проверяет доступность API и валидность токена.

        Returns:
            bool: True, если API отвечает и токен принят; иначе False.
        """
        try:
            self._request("GET", "/api/documents/", params={"page_size": 1})
        except PaperlessError:
            return False
        return True

    def iter_documents(self, tag_name: Optional[str] = None, query: Optional[str] = None, page_size: int = 100) -> Iterator[Dict[str, Any]]:
        """Итерирует документы постранично (без загрузки всего списка в память).

        Args:
            tag_name: Точное имя тега для фильтрации (рабочая область).
            query: Полнотекстовый запрос Paperless.
            page_size: Размер страницы.

        Yields:
            Dict[str, Any]: Метаданные документа (без поля content при truncate).
        """
        params: Dict[str, Any] = {"page_size": page_size, "fields": "id,title,modified,checksum,tags,archive_serial_number"}
        if tag_name:
            params["tags__name__iexact"] = tag_name
        if query:
            params["query"] = query
        path: Optional[str] = "/api/documents/"
        while path:
            data = self._request("GET", path, params=params).json()
            yield from data.get("results", [])
            nxt = data.get("next")
            path = nxt.replace(self.base_url, "", 1) if nxt else None
            params = {}

    def search_documents(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Полнотекстовый поиск по содержимому документов.

        Args:
            query: Поисковый запрос.
            limit: Максимум результатов.

        Returns:
            List[Dict[str, Any]]: Найденные документы.
        """
        resp = self._request("GET", "/api/documents/", params={"query": query, "page_size": limit})
        return list(resp.json().get("results", []))

    def get_document_metadata(self, document_id: int) -> Dict[str, Any]:
        """Возвращает метаданные документа (без OCR-текста через отдельный endpoint)."""
        return dict(self._request("GET", f"/api/documents/{int(document_id)}/").json())

    def get_document_content(self, document_id: int) -> str:
        """Возвращает OCR-текст документа — единственный источник текста для AI-Assistant."""
        return str(self._request("GET", f"/api/documents/{int(document_id)}/", params={"fields": "content"}).json().get("content", ""))

    def download_document(self, document_id: int, original: bool) -> bytes:
        """Скачивает файл документа.

        Args:
            document_id: Идентификатор документа Paperless.
            original: True — оригинал, False — архивная (OCR) версия.

        Returns:
            bytes: Содержимое файла.
        """
        resp = self._request(
            "GET",
            f"/api/documents/{int(document_id)}/download/",
            params={"original": "true" if original else "false"},
            timeout=self._upload_timeout,
        )
        return resp.content

    def upload_document(self, file_path: Path, title: str, tag_ids: List[int]) -> str:
        """Загружает документ в Paperless (асинхронная обработка).

        Args:
            file_path: Путь к файлу.
            title: Заголовок документа.
            tag_ids: Идентификаторы тегов.

        Returns:
            str: UUID задачи для отслеживания через get_task_status().
        """
        data: List[tuple] = [("title", title)] + [("tags", str(t)) for t in tag_ids]
        with open(file_path, "rb") as fh:
            resp = self._request(
                "POST",
                "/api/documents/post_document/",
                files={"document": (Path(file_path).name, fh)},
                data=data,
                timeout=self._upload_timeout,
            )
        return str(resp.json())

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Возвращает состояние фоновой задачи обработки документа.

        Raises:
            PaperlessError: Если задача не найдена.
        """
        results = self._request("GET", "/api/tasks/", params={"task_id": task_id}).json()
        items = results if isinstance(results, list) else results.get("results", [])
        if not items:
            raise PaperlessError(f"Задача {task_id} не найдена")
        return dict(items[0])

    def workspace_tag_name(self, workspace_id: str) -> str:
        """Имя тега Paperless, соответствующего рабочей области."""
        return f"{self.workspace_tag_prefix}{workspace_id}"

    def ensure_tag(self, name: str) -> int:
        """Возвращает id тега, создавая его при отсутствии.

        Args:
            name: Имя тега.

        Returns:
            int: Идентификатор тега.
        """
        found = self._request("GET", "/api/tags/", params={"name__iexact": name}).json().get("results", [])
        if found:
            return int(found[0]["id"])
        return int(self._request("POST", "/api/tags/", json={"name": name}).json()["id"])

    def ensure_workspace_tag(self, workspace_id: str) -> int:
        """Возвращает id тега рабочей области, создавая его при необходимости."""
        return self.ensure_tag(self.workspace_tag_name(workspace_id))

    def close(self) -> None:
        """Закрывает HTTP-сессию."""
        self._session.close()
