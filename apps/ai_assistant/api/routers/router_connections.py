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
# Updated: 2026-11-10 13:50:00
# =============================================================================

from __future__ import annotations

"""REST API эндпоинты настройки и тестирования сетевых соединений."""

import asyncio
import ftplib
import imaplib
import json
import os
import smtplib
import socket
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from header import __root__
from logger import logger

try:
    import pymysql

    HAS_PYMYSQL = True
except ImportError:
    HAS_PYMYSQL = False

router = APIRouter(prefix="/api/v1/connections", tags=["connections"])
CONNECTIONS_FILE = __root__ / "src" / "secrets" / "connections.json"

_SENSITIVE_FIELDS = ("password", "pass", "secret", "api_key", "token")


class TestConnectionRequest(BaseModel):
    """Схема запроса на проверку соединения."""

    service_type: str = Field(..., description="Тип сервиса: hostinger_mariadb, sqlite, ftp, ssh, smtp, imap")
    config: Dict[str, Any] = Field(default_factory=dict, description="Параметры соединения")


def _load_connections_data() -> Dict[str, Any]:
    """Загружает параметры подключений из JSON файла."""
    if CONNECTIONS_FILE.exists():
        try:
            with open(CONNECTIONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception as exc:
            logger.warning(f"[router_connections] Сбой чтения {CONNECTIONS_FILE}: {exc}")
    return {}


def _save_connections_data(data: Dict[str, Any]) -> bool:
    """Атомарно сохраняет параметры подключений в JSON файл через временный файл .tmp."""
    try:
        CONNECTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = CONNECTIONS_FILE.with_suffix(".json.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, CONNECTIONS_FILE)
        return True
    except Exception as exc:
        logger.error(f"[router_connections] Сбой сохранения {CONNECTIONS_FILE}: {exc}")
        return False


def _mask_config_passwords(data: Dict[str, Any]) -> Dict[str, Any]:
    """Маскирует непустые пароли и секреты ('***') перед отдачей в UI."""
    masked: Dict[str, Any] = {}
    for k, v in data.items():
        if isinstance(v, dict):
            sec_copy = dict(v)
            for sk, sv in sec_copy.items():
                if sk.lower() in _SENSITIVE_FIELDS and isinstance(sv, str) and sv:
                    sec_copy[sk] = "***"
            masked[k] = sec_copy
        else:
            masked[k] = v
    return masked


@router.get("/config", summary="Получение конфигурации соединений")
async def get_connections_config() -> Dict[str, Any]:
    """Возвращает текущие настройки всех подключений с замаскированными паролями."""
    raw = await asyncio.to_thread(_load_connections_data)
    return _mask_config_passwords(raw)


@router.post("/save", summary="Сохранение настроек подключений")
async def save_connections_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Сохраняет обновленные параметры соединений с сохранением старого пароля, если передано '***'."""
    current = await asyncio.to_thread(_load_connections_data)
    for section_name, section_val in payload.items():
        if isinstance(section_val, dict):
            existing_sec = current.get(section_name) if isinstance(current.get(section_name), dict) else {}
            merged_sec = dict(existing_sec)
            for fk, fv in section_val.items():
                if fk.lower() in _SENSITIVE_FIELDS and fv == "***":
                    # Сохраняем прежний пароль из файла
                    if fk in existing_sec:
                        merged_sec[fk] = existing_sec[fk]
                else:
                    merged_sec[fk] = fv
            current[section_name] = merged_sec
        else:
            current[section_name] = section_val

    ok = await asyncio.to_thread(_save_connections_data, current)
    if not ok:
        raise HTTPException(status_code=500, detail="Не удалось сохранить конфигурацию")
    return {"status": "ok", "config": _mask_config_passwords(current)}


def _sync_test_connection(st: str, cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Синхронно проверяет соединение с внешним сервисом или локальной БД SQLite."""
    t0 = time.perf_counter()

    try:
        if st in ("hostinger_mariadb", "mariadb", "mysql"):
            saved_all = _load_connections_data()
            saved_db = saved_all.get("hostinger_mariadb", {}) if isinstance(saved_all.get("hostinger_mariadb"), dict) else {}

            host = (cfg.get("host") or saved_db.get("host") or os.environ.get("MARIADB_HOST", "")).strip()
            port = int(cfg.get("port") or saved_db.get("port") or os.environ.get("MARIADB_PORT", 3306))
            user = (cfg.get("user") or saved_db.get("user") or os.environ.get("MARIADB_USER", "")).strip()
            raw_pwd = cfg.get("password", "")
            password = saved_db.get("password", "") if raw_pwd == "***" else (raw_pwd or saved_db.get("password") or os.environ.get("MARIADB_PASSWORD", ""))
            db = (cfg.get("database") or saved_db.get("database") or os.environ.get("MARIADB_DATABASE", "")).strip()
            ip_fallback = (cfg.get("ip_fallback") or saved_db.get("ip_fallback") or os.environ.get("MARIADB_IP_FALLBACK", "")).strip()

            if not host:
                raise ValueError("Не указан хост MariaDB / MySQL в конфигурации или переменных окружения")

            if HAS_PYMYSQL and password and user:
                try:
                    conn = pymysql.connect(
                        host=host,
                        port=port,
                        user=user,
                        password=password,
                        database=db,
                        connect_timeout=5,
                        read_timeout=5,
                        write_timeout=5,
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
                            read_timeout=5,
                            write_timeout=5,
                            charset="utf8mb4",
                        )
                        conn.close()
                    else:
                        raise ex1
            else:
                with socket.create_connection((host, port), timeout=5):
                    pass

            lat = round((time.perf_counter() - t0) * 1000, 2)
            return {"success": True, "latency_ms": lat, "message": f"Соединение с MariaDB ({host}:{port}) успешно"}

        elif st == "sqlite":
            raw_rel = str(cfg.get("path", "data/ai_instruments/ai_instruments.db")).strip()
            p = Path(raw_rel)
            resolved_db = (p if p.is_absolute() else (__root__ / p)).resolve()
            root_resolved = __root__.resolve()
            try:
                resolved_db.relative_to(root_resolved)
            except ValueError:
                raise ValueError("Путь к базе данных SQLite выходит за пределы корневой директории проекта")

            resolved_db.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(str(resolved_db), timeout=5.0) as conn:
                conn.execute("SELECT 1").fetchone()
            lat = round((time.perf_counter() - t0) * 1000, 2)
            return {"success": True, "latency_ms": lat, "message": f"База данных SQLite доступна ({raw_rel})"}

        elif st == "ftp":
            host = str(cfg.get("host", "")).strip()
            port = int(cfg.get("port", 21))
            if not host:
                raise ValueError("Не указан хост FTP")
            with socket.create_connection((host, port), timeout=5):
                pass
            lat = round((time.perf_counter() - t0) * 1000, 2)
            return {"success": True, "latency_ms": lat, "message": f"Порт FTP ({host}:{port}) доступен"}

        elif st == "ssh":
            host = str(cfg.get("host", "")).strip()
            port = int(cfg.get("port", 22))
            if not host:
                raise ValueError("Не указан хост SSH")
            with socket.create_connection((host, port), timeout=5):
                pass
            lat = round((time.perf_counter() - t0) * 1000, 2)
            return {"success": True, "latency_ms": lat, "message": f"Порт SSH ({host}:{port}) доступен"}

        elif st == "smtp":
            host = str(cfg.get("host") or os.environ.get("SMTP_HOST", "smtp.gmail.com")).strip()
            port = int(cfg.get("port", 587))
            with smtplib.SMTP(host, port, timeout=5) as s:
                s.ehlo()
            lat = round((time.perf_counter() - t0) * 1000, 2)
            return {"success": True, "latency_ms": lat, "message": f"SMTP сервер ({host}:{port}) ответил успешно"}

        elif st == "imap":
            host = str(cfg.get("host") or os.environ.get("IMAP_HOST", "imap.gmail.com")).strip()
            port = int(cfg.get("port", 993))
            with imaplib.IMAP4_SSL(host, port, timeout=5) as m:
                m.noop()
            lat = round((time.perf_counter() - t0) * 1000, 2)
            return {"success": True, "latency_ms": lat, "message": f"IMAP сервер ({host}:{port}) доступен"}

        else:
            raise ValueError(f"Неизвестный тип сервиса: {st}")

    except Exception as exc:
        lat = round((time.perf_counter() - t0) * 1000, 2)
        logger.warning(f"[router_connections] Ошибка проверки {st}: {exc}")
        return {"success": False, "latency_ms": lat, "error": str(exc), "message": f"Сбой проверки соединения: {exc}"}


@router.post("/test", summary="Проверка сетевого соединения")
async def test_connection(req: TestConnectionRequest) -> Dict[str, Any]:
    """Тестирует соединение с указанным сервисом в отдельном потоке и возвращает время отклика."""
    st = req.service_type.lower().strip()
    return await asyncio.to_thread(_sync_test_connection, st, req.config)
