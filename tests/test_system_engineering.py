# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - System Engineering Utilities
# =============================================================================
# Description:
#   Модульные тесты для утилит системной инженерии (src/utils/system_engineering.py):
#   - Финансовые расчеты высокой точности (Decimal, неделимые единицы).
#   - Парсинг различных форматов валют ($1,250.50, 1.250,50 руб и т.д.).
#   - Обработка исключений и защита от float-погрешностей.
#
# File: test_system_engineering.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 16:55:00
# =============================================================================

from __future__ import annotations
"""Тесты функций точных денежных расчетов стандарта SYSTEM_ENGINEERING.md."""

from decimal import Decimal
import pytest

from src.utils.system_engineering import (
    minor_units_to_decimal,
    money_to_minor_units,
    to_decimal_money,
)


def test_to_decimal_money_standard() -> None:
    """Проверяет преобразование стандартных строковых и числовых значений."""
    assert to_decimal_money("100.50") == Decimal("100.50")
    assert to_decimal_money(100) == Decimal("100.00")
    assert to_decimal_money(Decimal("55.456")) == Decimal("55.46")


def test_to_decimal_money_currency_symbols_and_formats() -> None:
    """Проверяет очистку валютных знаков, пробелов и европейского формата разделителей."""
    assert to_decimal_money("$1,250.50") == Decimal("1250.50")
    assert to_decimal_money("1.250,50 €") == Decimal("1250.50")
    assert to_decimal_money(" 1500,75 ₽ ") == Decimal("1500.75")
    assert to_decimal_money("₪ 99.90") == Decimal("99.90")


def test_to_decimal_money_invalid_inputs() -> None:
    """Проверяет генерацию исключений на некорректных входных данных."""
    with pytest.raises(ValueError):
        to_decimal_money("")
    with pytest.raises(ValueError):
        to_decimal_money(None)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        to_decimal_money(True)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        to_decimal_money("не_число")


def test_money_to_minor_units() -> None:
    """Проверяет конвертацию сумм в минимальные неделимые единицы (копейки/центы)."""
    assert money_to_minor_units("12.50") == 1250
    assert money_to_minor_units(Decimal("100.05")) == 10005
    assert money_to_minor_units("0.01") == 1
    assert money_to_minor_units("0.00") == 0


def test_minor_units_to_decimal() -> None:
    """Проверяет обратную конвертацию неделимых единиц в Decimal."""
    assert minor_units_to_decimal(1250) == Decimal("12.50")
    assert minor_units_to_decimal(1) == Decimal("0.01")
    assert minor_units_to_decimal(0) == Decimal("0.00")


def test_minor_units_invalid_type() -> None:
    """Проверяет отказ при передаче некорректного типа в minor_units_to_decimal."""
    with pytest.raises(TypeError):
        minor_units_to_decimal("100")  # type: ignore[arg-type]
