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
# Updated: 2026-11-10 13:50:00
# =============================================================================

from __future__ import annotations
"""Модуль middleware для раздельного логирования HTTP-запросов в консоль и файлы логов, трассировки и сбора метрик RED."""

from collections import deque
import threading
import time
from typing import Any, Callable, Deque, Dict, Optional, Set, Tuple
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from logger import logger


_TELEMETRY_LOCK = threading.Lock()
_REQUEST_TIMINGS_MS: Deque[Tuple[float, int]] = deque(maxlen=2000)
_TOTAL_REQUESTS: int = 0
_TOTAL_ERRORS: int = 0


def _record_request_metric(duration_ms: float, status_code: int) -> None:
    """Потокобезопасно записывает метрику выполнения HTTP-запроса (RED).

    Args:
        duration_ms (float): Длительность обработки запроса в миллисекундах.
        status_code (int): HTTP статус-код ответа.
    """
    global _TOTAL_REQUESTS, _TOTAL_ERRORS
    with _TELEMETRY_LOCK:
        _TOTAL_REQUESTS += 1
        if status_code >= 500:
            _TOTAL_ERRORS += 1
        _REQUEST_TIMINGS_MS.append((duration_ms, status_code))


def get_http_telemetry_snapshot() -> Dict[str, Any]:
    """Возвращает срез метрик RED (Rate, Errors, Duration) и перцентили задержек p50/p95/p99.

    Returns:
        Dict[str, Any]: Словарь с общим числом запросов, ошибками и перцентилями задержек.
    """
    with _TELEMETRY_LOCK:
        samples = [d for d, _ in _REQUEST_TIMINGS_MS]
        total = _TOTAL_REQUESTS
        errors = _TOTAL_ERRORS

    if not samples:
        return {
            "total_requests": total,
            "error_count": errors,
            "error_rate_pct": 0.0,
            "p50_ms": 0.0,
            "p95_ms": 0.0,
            "p99_ms": 0.0,
        }

    samples.sort()
    n = len(samples)

    def _percentile(p: float) -> float:
        idx = min(n - 1, max(0, int(round((p / 100.0) * (n - 1)))))
        return round(samples[idx], 2)

    return {
        "total_requests": total,
        "error_count": errors,
        "error_rate_pct": round((errors / max(total, 1)) * 100.0, 2),
        "p50_ms": _percentile(50.0),
        "p95_ms": _percentile(95.0),
        "p99_ms": _percentile(99.0),
    }


def _extract_or_generate_trace_id(request: Request) -> str:
    """Извлекает сквозной идентификатор трассировки из заголовков или генерирует новый.

    Args:
        request (Request): Входящий HTTP-запрос.

    Returns:
        str: Строка идентификатора трассировки.
    """
    incoming = request.headers.get("X-Trace-Id") or request.headers.get("traceparent")
    if incoming and incoming.strip():
        return incoming.strip()[:64]
    return uuid.uuid4().hex[:16]


class ConsoleStatusLogMiddleware(BaseHTTPMiddleware):
    """Middleware для выборочного логирования HTTP-запросов FastAPI, сквозного trace_id и метрик RED.

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
        """Перехватывает запрос, проставляет trace_id, замеряет длительность и логирует результат.

        Args:
            request (Request): Объект входящего HTTP-запроса.
            call_next (Callable[[Request], Any]): Следующий обработчик в цепочке ASGI.

        Returns:
            Response: HTTP-ответ сервера.
        """
        trace_id = _extract_or_generate_trace_id(request)
        request.state.trace_id = trace_id
        start_time = time.perf_counter()
        try:
            response: Response = await call_next(request)
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            _record_request_metric(duration_ms, 500)
            client_ip = request.client.host if request.client else "unknown"
            logger.error(
                f"[HTTP 500-EXC] [trace={trace_id}] {client_ip} - \"{request.method} {request.url.path}\" ({duration_ms:.1f}ms): {exc}",
                ex=exc,
            )
            raise

        duration_ms = (time.perf_counter() - start_time) * 1000
        status_code = response.status_code
        _record_request_metric(duration_ms, status_code)

        response.headers["X-Trace-Id"] = trace_id
        response.headers["X-Process-Time-Ms"] = f"{duration_ms:.2f}"

        client_ip = request.client.host if request.client else "unknown"
        log_line = f'{client_ip} - "{request.method} {request.url.path}" {status_code} ({duration_ms:.1f}ms) [trace={trace_id}]'

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
