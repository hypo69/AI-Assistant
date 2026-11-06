# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Assistant API - Router Connections
# =============================================================================
# Description:
#   REST API маршрутизатор для управления и тестирования сетевых подключений
#   (Hostinger MariaDB / MySQL, SQLite, FTP, SSH, SMTP, IMAP). Позволяет сохранять
#   учетные записи в `src/secrets/connections.json` и выполнять проверку задержки.
#
# Usage Examples:
#   GET  /api/v1/connections/config
#   POST /api/v1/connections/save
#   POST /api/v1/connections/test
#
# File: router_connections.py
# Project: ai-assistant
# Package: apps.ai_assistant.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-03 16:32:00
# =============================================================================

from __future__ import annotations

"""REST API эндпоинты настройки и тестирования сетевых соединений."""

import ftplib
import imaplib
import json
import smtplib
import socket
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from logger import logger

try:
    import pymysql

    HAS_PYMYSQL = True
except ImportError:
    HAS_PYMYSQL = False

router = APIRouter(prefix="/api/v1/connections", tags=["connections"])
CONNECTIONS_FILE = Path("src/secrets/connections.json")


class TestConnectionRequest(BaseModel):
    """Схема запроса на проверку соединения."""

    service_type: str = Field(..., description="Тип сервиса: hostinger_mariadb, sqlite, ftp, ssh, smtp, imap")
    config: Dict[str, Any] = Field(default_factory=dict, description="Параметры соединения")


def _load_connections_data() -> Dict[str, Any]:
    """Загружает параметры подключений из JSON файла."""
    if CONNECTIONS_FILE.exists():
        try:
            with open(CONNECTIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.warning(f"[router_connections] Сбой чтения {CONNECTIONS_FILE}: {exc}")
    return {}


def _save_connections_data(data: Dict[str, Any]) -> bool:
    """Сохраняет параметры подключений в JSON файл."""
    try:
        CONNECTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONNECTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as exc:
        logger.error(f"[router_connections] Сбой сохранения {CONNECTIONS_FILE}: {exc}")
        return False


@router.get("/config", summary="Получение конфигурации соединений")
async def get_connections_config() -> Dict[str, Any]:
    """Возвращает текущие настройки всех подключений."""
    return _load_connections_data()


@router.post("/save", summary="Сохранение настроек подключений")
async def save_connections_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Сохраняет обновленные параметры соединений."""
    current = _load_connections_data()
    # Обновляем переданные секции
    for section_name, section_val in payload.items():
        if isinstance(section_val, dict) and isinstance(current.get(section_name), dict):
            current[section_name].update(section_val)
        else:
            current[section_name] = section_val

    ok = _save_connections_data(current)
    if not ok:
        raise HTTPException(status_code=500, detail="Не удалось сохранить конфигурацию")
    return {"status": "ok", "config": current}


@router.post("/test", summary="Проверка сетевого соединения")
async def test_connection(req: TestConnectionRequest) -> Dict[str, Any]:
    """Тестирует соединение с указанным сервисом и возвращает время отклика."""
    st = req.service_type.lower()
    cfg = req.config
    t0 = time.time()

    try:
        if st in ("hostinger_mariadb", "mariadb", "mysql"):
            host = cfg.get("host", "srv1502.hstgr.io")
            port = int(cfg.get("port", 3306))
            user = cfg.get("user", "u177424397_davidka")
            password = cfg.get("password", "")
            db = cfg.get("database", "u177424397_comp_knowledge")
            ip_fallback = cfg.get("ip_fallback", "77.37.35.16")

            if HAS_PYMYSQL and password:
                try:
                    conn = pymysql.connect(
                        host=host,
                        port=port,
                        user=user,
                        password=password,
                        database=db,
                        connect_timeout=5,
                        charset="utf8mb4",
                    )
                    conn.close()
                except Exception as ex1:
                    if ip_fallback and ip_fallback != host:
                        conn = pymysql.connect(
                            host=ip_fallback,
                            port=port,
                            user=user,
                            password=password,
                            database=db,
                            connect_timeout=5,
                            charset="utf8mb4",
                        )
                        conn.close()
                    else:
                        raise ex1
            else:
                # Быстрая проверка сокета
                with socket.create_connection((host, port), timeout=5):
                    pass

            lat = round((time.time() - t0) * 1000, 2)
            return {"success": True, "latency_ms": lat, "message": f"Соединение с MariaDB ({host}:{port}) успешно"}

        elif st == "sqlite":
            db_path = Path(cfg.get("path", "data/ai_instruments/ai_instruments.db"))
            db_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(str(db_path)) as conn:
                conn.execute("SELECT 1").fetchone()
            lat = round((time.time() - t0) * 1000, 2)
            return {"success": True, "latency_ms": lat, "message": f"База данных SQLite доступна ({db_path})"}

        elif st == "ftp":
            host = cfg.get("host", "")
            port = int(cfg.get("port", 21))
            if not host:
                raise ValueError("Не указан хост FTP")
            with socket.create_connection((host, port), timeout=5):
                pass
            lat = round((time.time() - t0) * 1000, 2)
            return {"success": True, "latency_ms": lat, "message": f"Порт FTP ({host}:{port}) доступен"}

        elif st == "ssh":
            host = cfg.get("host", "")
            port = int(cfg.get("port", 22))
            if not host:
                raise ValueError("Не указан хост SSH")
            with socket.create_connection((host, port), timeout=5):
                pass
            lat = round((time.time() - t0) * 1000, 2)
            return {"success": True, "latency_ms": lat, "message": f"Порт SSH ({host}:{port}) доступен"}

        elif st == "smtp":
            host = cfg.get("host", "smtp.gmail.com")
            port = int(cfg.get("port", 587))
            with smtplib.SMTP(host, port, timeout=5) as s:
                s.ehlo()
            lat = round((time.time() - t0) * 1000, 2)
            return {"success": True, "latency_ms": lat, "message": f"SMTP сервер ({host}:{port}) ответил успешно"}

        elif st == "imap":
            host = cfg.get("host", "imap.gmail.com")
            port = int(cfg.get("port", 993))
            with imaplib.IMAP4_SSL(host, port) as m:
                m.noop()
            lat = round((time.time() - t0) * 1000, 2)
            return {"success": True, "latency_ms": lat, "message": f"IMAP сервер ({host}:{port}) доступен"}

        else:
            raise ValueError(f"Неизвестный тип сервиса: {st}")

    except Exception as exc:
        lat = round((time.time() - t0) * 1000, 2)
        logger.warning(f"[router_connections] Ошибка проверки {st}: {exc}")
        return {"success": False, "latency_ms": lat, "error": str(exc), "message": f"Сбой проверки соединения: {exc}"}
