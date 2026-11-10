# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant - FastAPI Middleware for Console Logging
# =============================================================================
# Description:
#   Промежуточное программное обеспечение (Middleware) для FastAPI.
#   Логирует состояния 200 и 304 исключительно в консоль без записи в файлы логов
#   с помощью `logger.console()`, а ошибки (4xx, 5xx) и прочие статусы направляет
#   в стандартный журнал логов.
#
# Usage Examples:
#   from fastapi import FastAPI
#   from apps.ai_assistant.api.middleware import ConsoleStatusLogMiddleware
#
#   app = FastAPI()
#   app.add_middleware(ConsoleStatusLogMiddleware)
#
# File: middleware.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.api
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-07 00:37:00
# =============================================================================

from __future__ import annotations
"""Модуль middleware для раздельного логирования HTTP-запросов в консоль и файлы логов."""

import time
from typing import Any, Callable, Optional, Set

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from logger import logger


class ConsoleStatusLogMiddleware(BaseHTTPMiddleware):
    """Middleware для выборочного логирования HTTP-запросов FastAPI.

    Состояния 200 (OK) и 304 (Not Modified) выводятся исключительно в консоль
    через `logger.console()`, предотвращая засорение постоянных дисковых логов.
    Все остальные статусы (редиректы, клиентские и серверные ошибки) направляются
    в штатный логгер подсистемы.

    Attributes:
        console_only_statuses (Set[int]): Набор статус-кодов для вывода только в консоль.
        console_color (str): Название цвета текста для вывода в консоль (по умолчанию logger.gray).
        console_bg_color (str): Название цвета фона для вывода в консоль (по умолчанию пустая строка).
    """

    def __init__(
        self,
        app: Any,
        console_only_statuses: Optional[Set[int]] = None,
        console_color: str = logger.gray,
        console_bg_color: str = "",
    ) -> None:
        """Инициализирует middleware избирательного логирования.

        Args:
            app (Any): ASGI-приложение.
            console_only_statuses (Optional[Set[int]]): Набор статус-кодов,
                выводимых только в консоль (по умолчанию {200, 304}).
            console_color (str): Цвет консольного текста для статус-кодов (по умолчанию logger.gray).
            console_bg_color (str): Цвет консольного фона для статус-кодов (по умолчанию без фона).
        """
        super().__init__(app)
        self.console_only_statuses: Set[int] = console_only_statuses or {200, 304}
        self.console_color: str = console_color
        self.console_bg_color: str = console_bg_color

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        """Перехватывает запрос, замеряет длительность и логирует результат.

        Args:
            request (Request): Объект входящего HTTP-запроса.
            call_next (Callable[[Request], Any]): Следующий обработчик в цепочке ASGI.

        Returns:
            Response: HTTP-ответ сервера.
        """
        start_time = time.perf_counter()
        try:
            response: Response = await call_next(request)
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            client_ip = request.client.host if request.client else "unknown"
            logger.error(
                f"[HTTP 500-EXC] {client_ip} - \"{request.method} {request.url.path}\" ({duration_ms:.1f}ms): {exc}",
                ex=exc,
            )
            raise

        duration_ms = (time.perf_counter() - start_time) * 1000
        client_ip = request.client.host if request.client else "unknown"
        status_code = response.status_code
        log_line = f'{client_ip} - "{request.method} {request.url.path}" {status_code} ({duration_ms:.1f}ms)'

        if status_code in self.console_only_statuses:
            logger.console(
                f"[ACCESS] {log_line}",
                text_color=self.console_color,
                bg_color=self.console_bg_color,
            )
        else:
            if status_code >= 500:
                logger.error(f"[HTTP {status_code}] {log_line}")
            elif status_code >= 400:
                logger.warning(f"[HTTP {status_code}] {log_line}")
            else:
                logger.info(f"[HTTP {status_code}] {log_line}")

        return response
