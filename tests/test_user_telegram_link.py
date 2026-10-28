# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - User Telegram Linking Service
# =============================================================================
# Description:
#   Тестирование генерации одноразовых кодов привязки к Telegram, связывания
#   Telegram ID с пользователем, поиска по Telegram ID и отвязки аккаунта.
#
# File: test_user_telegram_link.py
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 19:20:00
# =============================================================================

from __future__ import annotations

import time
from pathlib import Path
import pytest

from src.user_manager import UserManager


def test_telegram_link_lifecycle(tmp_path: Path) -> None:
    """Проверяет полный жизненный цикл привязки Telegram-аккаунта к пользователю."""
    um = UserManager(root_dir=tmp_path)

    # 1. Создаем тестового пользователя
    user_id = um.create_user_admin(
        email="telegram_user@test.local",
        name="Telegram Test User",
    )
    assert user_id is not None

    # До привязки пользователь не должен находиться по telegram_id
    assert um.get_user_by_telegram_id(99887766) is None

    # 2. Генерируем 8-значный токен
    token = um.generate_telegram_link_token(user_id, ttl_seconds=300)
    assert isinstance(token, str)
    assert len(token) == 8

    # 3. Привязываем Telegram-аккаунт по токену
    success = um.link_telegram_account(token, telegram_id=99887766, telegram_username="tg_tester")
    assert success is True

    # 4. Проверяем поиск пользователя по Telegram ID
    found_user = um.get_user_by_telegram_id(99887766)
    assert found_user is not None
    assert found_user["id"] == user_id
    assert found_user["telegram_id"] == 99887766
    assert found_user["telegram_username"] == "tg_tester"

    # Повторная попытка использовать тот же токен должна вернуть False (одноразовый)
    assert um.link_telegram_account(token, telegram_id=99887766) is False

    # 5. Проверяем получение персональной директории
    audio_dir = um.get_user_directory(user_id, subfolder="audio")
    assert audio_dir.exists()
    assert audio_dir.name == "audio"

    # 6. Отвязываем аккаунт
    unlinked = um.unlink_telegram_account(user_id)
    assert unlinked is True
    assert um.get_user_by_telegram_id(99887766) is None


def test_telegram_link_token_expired(tmp_path: Path) -> None:
    """Проверяет отклонение просроченного кода привязки."""
    um = UserManager(root_dir=tmp_path)
    user_id = um.create_user_admin(
        email="expired_user@test.local",
        name="Expired User",
    )
    assert user_id is not None

    # Генерируем токен с временем жизни 0 секунд
    token = um.generate_telegram_link_token(user_id, ttl_seconds=-1)
    assert um.link_telegram_account(token, telegram_id=112233) is False
    assert um.get_user_by_telegram_id(112233) is None
