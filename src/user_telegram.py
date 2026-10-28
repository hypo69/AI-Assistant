# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin User Telegram Link Service
# =============================================================================
# Description:
#   Сервис привязки Telegram-аккаунтов к локальным пользователям платформы.
#   Генерирует одноразовые токены верификации, выполняет валидацию и связывание
#   Telegram ID с учетными записями в SQLite.
#
# File: user_telegram.py
# Project: ai-windows-admin
# Package: src
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 19:15:00
# =============================================================================

from __future__ import annotations

import datetime
from pathlib import Path
import secrets
import sqlite3
from typing import Any, Dict, Optional

from logger import logger


class UserTelegramService:
    """Сервис генерации кодов и привязки Telegram-аккаунтов к пользователям."""

    def __init__(self, db_path: Path) -> None:
        """Инициализация сервиса с указанием пути к базе данных пользователей."""
        self.db_path = db_path
        self._init_tables()

    def _get_connection(self) -> sqlite3.Connection:
        """Создает и возвращает соединение с SQLite."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self) -> None:
        """Создает таблицу токенов привязки, если она еще не создана."""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS telegram_link_tokens (
                        token TEXT PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        expires_at TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                    )
                    """
                )
                conn.commit()
        except Exception as exc:
            logger.error(f"[UserTelegramService] Ошибка инициализации таблицы токенов: {exc}")

    def get_user_by_telegram_id(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Ищет активного пользователя по его Telegram ID.

        Args:
            telegram_id: Числовой идентификатор пользователя в Telegram.

        Returns:
            Optional[Dict[str, Any]]: Запись пользователя или None.
        """
        try:
            with self._get_connection() as conn:
                row = conn.execute(
                    "SELECT * FROM users WHERE telegram_id = ? AND is_active = 1",
                    (int(telegram_id),),
                ).fetchone()
                return dict(row) if row else None
        except Exception as exc:
            logger.error(f"[UserTelegramService] Ошибка поиска по Telegram ID {telegram_id}: {exc}")
            return None

    def generate_link_token(self, user_id: int, ttl_seconds: int = 900) -> str:
        """Генерирует уникальный 8-значный код привязки для пользователя.

        Args:
            user_id: Числовой идентификатор пользователя.
            ttl_seconds: Время жизни токена в секундах (по умолчанию 15 минут).

        Returns:
            str: 8-значный токен (например, 'A1B2C3D4').
        """
        token = secrets.token_hex(4).upper()
        now = datetime.datetime.now()
        expires = now + datetime.timedelta(seconds=ttl_seconds)
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        exp_str = expires.strftime("%Y-%m-%d %H:%M:%S")

        with self._get_connection() as conn:
            conn.execute("DELETE FROM telegram_link_tokens WHERE user_id = ?", (user_id,))
            conn.execute(
                "INSERT INTO telegram_link_tokens (token, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
                (token, user_id, exp_str, now_str),
            )
            conn.commit()

        logger.info(f"[UserTelegramService] Сгенерирован код привязки Telegram для пользователя #{user_id}: {token}")
        return token

    def link_account(self, token: str, telegram_id: int, telegram_username: str = "") -> bool:
        """Привязывает Telegram ID к пользователю по действительному токену.

        Args:
            token: Одноразовый код привязки.
            telegram_id: Числовой ID в Telegram.
            telegram_username: Имя пользователя Telegram.

        Returns:
            bool: True при успехе, False при недействительном или просроченном коде.
        """
        clean_token = token.strip().upper()
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT user_id, expires_at FROM telegram_link_tokens WHERE token = ?",
                (clean_token,),
            ).fetchone()
            if not row:
                logger.warning(f"[UserTelegramService] Код привязки {clean_token} не найден")
                return False

            user_id = row["user_id"]
            expires_at = row["expires_at"]
            if expires_at < now_str:
                conn.execute("DELETE FROM telegram_link_tokens WHERE token = ?", (clean_token,))
                conn.commit()
                logger.warning(f"[UserTelegramService] Код привязки {clean_token} просрочен")
                return False

            # Очищаем telegram_id у других пользователей при необходимости
            conn.execute(
                "UPDATE users SET telegram_id = NULL, telegram_username = NULL WHERE telegram_id = ?",
                (int(telegram_id),),
            )

            # Привязываем к текущему пользователю
            conn.execute(
                "UPDATE users SET telegram_id = ?, telegram_username = ?, updated_at = ? WHERE id = ?",
                (int(telegram_id), str(telegram_username or ""), now_str, user_id),
            )
            conn.execute("DELETE FROM telegram_link_tokens WHERE token = ?", (clean_token,))
            conn.commit()

        logger.info(f"[UserTelegramService] Telegram ID {telegram_id} успешно привязан к пользователю #{user_id}")
        return True

    def unlink_account(self, user_id: int) -> bool:
        """Отвязывает Telegram от профиля пользователя.

        Args:
            user_id: Идентификатор пользователя.

        Returns:
            bool: True при успехе.
        """
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE users SET telegram_id = NULL, telegram_username = NULL, updated_at = ? WHERE id = ?",
                (now_str, user_id),
            )
            conn.execute("DELETE FROM telegram_link_tokens WHERE user_id = ?", (user_id,))
            conn.commit()

        logger.info(f"[UserTelegramService] Telegram отвязан от пользователя #{user_id}")
        return True
