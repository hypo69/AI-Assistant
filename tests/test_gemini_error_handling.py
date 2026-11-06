# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-assistant Tests - Gemini Error Handling and Rotation
# =============================================================================
# Description:
#   Тесты обработки ошибок Google Gemini: проверка устойчивости к перегрузке
#   модели (503 / Overloaded), мягкой ротации при минутном rate limit (RPM),
#   корректной блокировки только при реальном суточном 429 Quota Exceeded
#   и формирования понятных сообщений об ошибках.
#
# Usage Examples:
#   pytest tests/test_gemini_error_handling.py
#
# File: test_gemini_error_handling.py
# Project: ai-assistant
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-03 16:27:00
# =============================================================================

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from src.ai.gemini.errors import GoogleGenerativeAIErrorMixin
from src.ai.gemini.core import GoogleGenerativeAICore


class DummyGeminiAI(GoogleGenerativeAICore, GoogleGenerativeAIErrorMixin):
    """Тестовый класс-заглушка с поведением GoogleGenerativeAI."""

    def __init__(self) -> None:
        self.api_keys = ["AIzaSyTestKey1", "AIzaSyTestKey2"]
        self._key_names_active = ["key_1", "key_2"]
        self.api_key_owners = ["owner_1", "owner_2"]
        self.api_key = self.api_keys[0]
        self.model_name = "gemini-3.5-flash-lite"
        self._last_exception = ""
        self._key_errors = {}
        self._unavailable_attempts = 0
        self._all_keys_exhausted = False
        self.sleep_on_exhausted = False
        self._client = MagicMock()


@pytest.mark.asyncio
async def test_handle_overloaded_error_does_not_exhaust_key() -> None:
    """Проверяет, что при ошибке 'The model is overloaded' ключ НЕ помечается как exhausted."""
    ai = DummyGeminiAI()
    ai._mark_key_exhausted = MagicMock()
    ai._switch_model = MagicMock(return_value=True)

    err = Exception("503 The model is overloaded. Please try again later.")

    # Первая попытка перегрузки: должен быть retry с ожиданием, ключ не исчерпан
    retry = await ai._handle_api_error(err, ai.model_name, attempt=0, max_attempts=5)
    assert retry is True
    assert ai._unavailable_attempts == 1
    ai._mark_key_exhausted.assert_not_called()
    assert "AIzaSyTestKey1" in ai.api_keys


@pytest.mark.asyncio
async def test_persistent_overload_switches_model() -> None:
    """Проверяет, что при устойчивой перегрузке происходит переключение модели, а не блокировка ключа."""
    ai = DummyGeminiAI()
    ai._mark_key_exhausted = MagicMock()
    ai._switch_model = MagicMock(return_value=True)

    err = Exception("Model is overloaded. High demand.")

    # Симулируем 3 последовательные ошибки перегрузки
    await ai._handle_api_error(err, ai.model_name, attempt=0, max_attempts=5)
    await ai._handle_api_error(err, ai.model_name, attempt=1, max_attempts=5)
    retry = await ai._handle_api_error(err, ai.model_name, attempt=2, max_attempts=5)

    assert retry is True
    # На 3-й попытке вызвана смена модели
    ai._switch_model.assert_called_once()
    # Ключ по-прежнему не блокируется как exhausted!
    ai._mark_key_exhausted.assert_not_called()


@pytest.mark.asyncio
async def test_rpm_rate_limit_soft_rotation() -> None:
    """Проверяет мягкую ротацию ключа при минутном лимите (RPM) без блокировки на 24 часа."""
    ai = DummyGeminiAI()
    ai._mark_key_exhausted = MagicMock()

    err = Exception("ResourceExhausted: 429 Quota exceeded for quota metric 'Queries' and limit 'Queries per minute'")

    retry = await ai._handle_api_error(err, ai.model_name, attempt=0, max_attempts=5)

    assert retry is True
    # Ключ переключился на второй
    assert ai.api_key == "AIzaSyTestKey2"
    # Суточная блокировка НЕ вызвана!
    ai._mark_key_exhausted.assert_not_called()


@pytest.mark.asyncio
async def test_daily_quota_exhaustion_marks_key() -> None:
    """Проверяет маркировку ключа как exhausted только при реальном суточном лимите."""
    ai = DummyGeminiAI()
    ai._mark_key_exhausted = MagicMock()
    ai._switch_api_key = MagicMock(return_value=True)

    err = Exception("ResourceExhausted: 429 Daily request quota exceeded for project")

    retry = await ai._handle_api_error(err, ai.model_name, attempt=0, max_attempts=5)

    assert retry is True
    ai._mark_key_exhausted.assert_called_once_with("AIzaSyTestKey1")


def test_retry_exhausted_error_msg_shows_model_overload() -> None:
    """Проверяет, что сообщение об ошибке четко говорит о перегрузке модели Google."""
    ai = DummyGeminiAI()
    ai._last_exception = "503 The model is overloaded. Please try again later."

    msg = ai._get_retry_exhausted_error_msg(ai.model_name)
    assert "перегружена на стороне Google" in msg
    assert "Все API ключи исчерпаны" not in msg
