# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Utils - System Engineering Helpers
# =============================================================================
# Description:
#   Инженерные утилиты стандарта SYSTEM_ENGINEERING.md:
#   - Финансовые расчеты высокой точности (Decimal, целочисленные неделимые единицы)
#     с защитой от ошибок округления IEEE 754 (float).
#   - Очистка и нормализация денежных строк (валютные знаки, пробелы, разделители).
#
# Usage Examples:
#   Python API:
#     from src.utils.system_engineering import (
#         minor_units_to_decimal,
#         money_to_minor_units,
#         to_decimal_money,
#     )
#
#     d = to_decimal_money("$1,250.50")      # Decimal('1250.50')
#     minor = money_to_minor_units(d)       # 125050 (копейки / центы)
#     d2 = minor_units_to_decimal(minor)    # Decimal('1250.50')
#
# File: system_engineering.py
# Project: ai-windows-admin
# Package: src.utils
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 16:55:00
# =============================================================================

from __future__ import annotations
"""Инженерные утилиты стандарта системной инженерии: точные денежные расчеты без float."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
from typing import Union


def to_decimal_money(val: Union[str, int, float, Decimal], precision: int = 2) -> Decimal:
    """Преобразует строковое или числовое значение в тип Decimal с заданной точностью.

    Выполняет нормализацию: удаляет знаки валют, пробелы, обрабатывает запятые и точки
    в качестве десятичных разделителей, защищая финансовые расчеты от ошибок IEEE 754.

    Args:
        val: Исходное денежное значение (строка, целое число, Decimal или float).
        precision: Количество знаков после запятой (по умолчанию 2).

    Returns:
        Decimal: Нормализованное значение Decimal с квантованием ROUND_HALF_UP.

    Raises:
        ValueError: Если строку невозможно распознать как корректную денежную сумму.
        TypeError: При неподдерживаемом типе входного значения.
    """
    if val is None:
        raise ValueError("Денежное значение не может быть None")

    if isinstance(val, bool):
        raise TypeError("Логический тип (bool) недопустим для денежных величин")

    if isinstance(val, (int, Decimal)):
        clean_str = str(val)
    elif isinstance(val, float):
        clean_str = str(val)
    elif isinstance(val, str):
        s = val.strip()
        if not s:
            raise ValueError("Пустая строка не является денежным значением")
        # Удаляем валютные символы, кавычки и пробелы
        s = re.sub(r"[\s\$\€\₽\£\₪\¥\元\₹]", "", s)
        # Обработка разделителей тысяч и десятичных долей:
        # 1. Формат "1,250.50" -> "1250.50"
        # 2. Формат "1.250,50" -> "1250.50"
        # 3. Формат "1250,50" -> "1250.50"
        if "," in s and "." in s:
            if s.rfind(",") > s.rfind("."):
                # Европейский формат: 1.250,50
                s = s.replace(".", "").replace(",", ".")
            else:
                # Американский формат: 1,250.50
                s = s.replace(",", "")
        elif "," in s:
            s = s.replace(",", ".")
        clean_str = s
    else:
        raise TypeError(f"Неподдерживаемый тип денежной величины: {type(val)}")

    try:
        dec = Decimal(clean_str)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Невозможно преобразовать '{val}' в Decimal: {exc}") from exc

    quantum = Decimal("10") ** -precision
    return dec.quantize(quantum, rounding=ROUND_HALF_UP)


def money_to_minor_units(
    val: Union[str, int, float, Decimal],
    minor_units_per_major: int = 100,
) -> int:
    """Конвертирует денежную сумму в минимальные неделимые единицы (копейки, центы, сатоши).

    Args:
        val: Денежное значение (строка, Decimal, число).
        minor_units_per_major: Количество неделимых единиц в одной базовой (100 для копеек/центов).

    Returns:
        int: Сумма в неделимых единицах (целое число int).
    """
    dec = val if isinstance(val, Decimal) else to_decimal_money(val)
    scaled = dec * Decimal(minor_units_per_major)
    return int(scaled.to_integral_value(rounding=ROUND_HALF_UP))


def minor_units_to_decimal(
    minor_val: int,
    minor_units_per_major: int = 100,
) -> Decimal:
    """Конвертирует неделимые единицы (копейки, центы) обратно в Decimal.

    Args:
        minor_val: Целочисленное значение в неделимых единицах.
        minor_units_per_major: Количество неделимых единиц в одной базовой (100).

    Returns:
        Decimal: Десятичная сумма Decimal с точностью до 2 знаков.
    """
    if not isinstance(minor_val, (int, Decimal)):
        raise TypeError(f"minor_val должен быть int, получено: {type(minor_val)}")
    dec = Decimal(int(minor_val)) / Decimal(minor_units_per_major)
    return dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


__all__ = [
    "minor_units_to_decimal",
    "money_to_minor_units",
    "to_decimal_money",
]
