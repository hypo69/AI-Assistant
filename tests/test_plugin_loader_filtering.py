# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Plugin Loader Filtering Unit Tests
# =============================================================================
# Description:
#   Модульные тесты фильтрации плагинов при загрузке. Проверяют, что при наличии
#   списка разрешенных плагинов (enabled) неотмеченные плагины не импортируются
#   и не инициализируются.
#
# File: test_plugin_loader_filtering.py
# Project: ai-breadboard
# Package: tests
# Author: hypo69
# Updated: 2026-10-28 17:31:00
# Copyright: © 2026 hypo69
# =============================================================================

"""Модульные тесты ранней фильтрации загрузчика плагинов.

Проверяет корректность работы механизма `load_plugins` при ограничении
списка активных плагинов через конфигурацию `enabled`.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

from plugins import load_plugins
from plugins import _parse_plugins_config


class TestPluginLoaderFiltering(unittest.TestCase):
    """Набор тестов для проверки фильтрации плагинов в загрузчике."""

    def test_parse_plugins_config_enabled_list(self) -> None:
        """Проверка парсинга конфигурации со списком enabled."""
        cfg = {"enabled": ["telegram_bot"]}
        enabled, disabled, specific = _parse_plugins_config(cfg)
        self.assertEqual(enabled, {"telegram_bot"})
        self.assertEqual(disabled, set())
        self.assertEqual(specific, {})

    def test_parse_plugins_config_disabled_list(self) -> None:
        """Проверка парсинга конфигурации со списком disabled."""
        cfg = {"disabled": ["facebook", "whatsapp"]}
        enabled, disabled, specific = _parse_plugins_config(cfg)
        self.assertIsNone(enabled)
        self.assertEqual(disabled, {"facebook", "whatsapp"})

    def test_load_plugins_only_enabled_plugin(self) -> None:
        """Проверка, что загружаются только разрешенные плагины из списка enabled."""
        loaded = load_plugins()
        self.assertIn("telegram_bot", loaded)
        self.assertNotIn("facebook", loaded)
        self.assertNotIn("whatsapp", loaded)
        self.assertNotIn("invoice_processor", loaded)
        self.assertNotIn("user_storage", loaded)


if __name__ == "__main__":
    unittest.main()
