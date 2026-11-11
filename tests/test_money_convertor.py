# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Money Convertor Utilities
# =============================================================================
# Description:
#   Модульные тесты для модуля конвертации денег (src/utils/convertors/money.py):
#   - Точные денежные расчеты (Decimal, неделимые единицы int).
#   - Парсинг различных форматов валют ($1,250.50, 1.250,50 руб и т.д.).
#   - Обработка исключений, валидация типов и алиасы функций.
#
# File: test_money_convertor.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 17:30:00
# =============================================================================

from __future__ import annotations
"""Тесты функций точных денежных расчетов модуля convertors.money."""

from decimal import Decimal
import pytest

from src.utils.convertors.money import (
    minor2decimal,
    minor_units_to_decimal,
    money2decimal,
    money2minor,
    money_to_minor_units,
    to_decimal_money,
)


def test_money2decimal_standard() -> None:
    """Проверяет преобразование стандартных строковых и числовых значений."""
    assert money2decimal("100.50") == Decimal("100.50")
    assert money2decimal(100) == Decimal("100.00")
    assert money2decimal(Decimal("55.456")) == Decimal("55.46")
    # Проверка алиаса
    assert to_decimal_money("100.50") == Decimal("100.50")


def test_money2decimal_currency_symbols_and_formats() -> None:
    """Проверяет очистку валютных знаков, пробелов и европейского формата разделителей."""
    assert money2decimal("$1,250.50") == Decimal("1250.50")
    assert money2decimal("1.250,50 €") == Decimal("1250.50")
    assert money2decimal(" 1500,75 ₽ ") == Decimal("1500.75")
    assert money2decimal("₪ 99.90") == Decimal("99.90")


def test_money2decimal_invalid_inputs() -> None:
    """Проверяет генерацию исключений на некорректных входных данных."""
    with pytest.raises(ValueError):
        money2decimal("")
    with pytest.raises(ValueError):
        money2decimal(None)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        money2decimal(True)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        money2decimal("не_число")


def test_money2minor() -> None:
    """Проверяет конвертацию сумм в минимальные неделимые единицы (копейки/центы)."""
    assert money2minor("12.50") == 1250
    assert money2minor(Decimal("100.05")) == 10005
    assert money2minor("0.01") == 1
    assert money2minor("0.00") == 0
    # Проверка алиаса
    assert money_to_minor_units("12.50") == 1250


def test_minor2decimal() -> None:
    """Проверяет обратную конвертацию неделимых единиц в Decimal."""
    assert minor2decimal(1250) == Decimal("12.50")
    assert minor2decimal(1) == Decimal("0.01")
    assert minor2decimal(0) == Decimal("0.00")
    # Проверка алиаса
    assert minor_units_to_decimal(1250) == Decimal("12.50")


def test_minor2decimal_invalid_type() -> None:
    """Проверяет отказ при передаче некорректного типа в minor2decimal."""
    with pytest.raises(TypeError):
        minor2decimal("100")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        minor2decimal(True)  # type: ignore[arg-type]
