# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Core - Git Maintenance Service
# =============================================================================
# Description:
#   Сервис периодического обслуживания Git-репозитория и выполнения git gc:
#   сборка мусора, переупаковка объектов, удаление недостижимых ссылок (prune),
#   мониторинг размера каталога .git и планирование периодических запусков.
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.core.git_maintenance import GitMaintenanceService
#
#     service = GitMaintenanceService()
#     status = service.get_repo_info()
#     res = service.run_gc(aggressive=False, prune=True)
#
# File: git_maintenance.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-22 14:38:00
# =============================================================================

from __future__ import annotations
"""Сервис обслуживания репозитория и фонового выполнения git gc."""

import datetime
import json
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from logger import logger
from header import __root__

DEFAULT_CONFIG_PATH = __root__ / "apps" / "ai_assistant" / "config.json"


class GitMaintenanceService:
    """Сервис обслуживания Git репозитория и планирования очистки git gc."""

    def __init__(self, repo_path: Path | str = ".", config_path: Optional[Path | str] = None) -> None:
        """Инициализирует сервис обслуживания Git.

        Args:
            repo_path: Корневой путь Git-репозитория.
            config_path: Путь к файлу конфигурации config.json.
        """
        self.repo_path = Path(repo_path).resolve()
        self.config_path = Path(config_path).resolve() if config_path else DEFAULT_CONFIG_PATH
        self._is_running = False
        self._lock = threading.Lock()

    def _run_git(self, args: List[str], timeout_sec: int = 180) -> str:
        """Синхронно выполняет команду git в каталоге репозитория.

        Args:
            args: Список аргументов git.
            timeout_sec: Максимальный таймаут ожидания завершения.

        Returns:
            str: Вывод команды (stdout/stderr) или пустая строка.
        """
        cmd = ["git"] + args
        git_env = os.environ.copy()
        git_env["GIT_PAGER"] = "cat"
        git_env["PAGER"] = "cat"
        try:
            res = subprocess.run(
                cmd,
                cwd=str(self.repo_path),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=git_env,
                timeout=timeout_sec,
            )
            output = (res.stdout or "") + (("\n" + res.stderr) if res.stderr else "")
            if res.returncode != 0:
                logger.warning(f"[GitMaintenance] Команда {' '.join(cmd)} завершилась с кодом {res.returncode}: {res.stderr.strip()}")
            return output.strip()
        except subprocess.TimeoutExpired:
            logger.warning(f"[GitMaintenance] Таймаут выполнения git ({timeout_sec}s): {' '.join(cmd)}")
            return ""
        except Exception as exc:
            logger.error(f"[GitMaintenance] Ошибка запуска git: {exc}")
            return ""

    def get_repo_info(self) -> Dict[str, Any]:
        """Возвращает информацию о текущем состоянии объектов репозитория (git count-objects -vH).

        Returns:
            Dict[str, Any]: Метрики loose объектов, упакованных паков и размера.
        """
        raw = self._run_git(["count-objects", "-vH"], timeout_sec=15)
        info: Dict[str, Any] = {
            "loose_objects": 0,
            "loose_size": "0 KiB",
            "in_pack_objects": 0,
            "packs_count": 0,
            "pack_size": "0 KiB",
            "garbage_count": 0,
            "garbage_size": "0 KiB",
            "raw_output": raw,
        }
        for line in raw.splitlines():
            parts = line.split(":", 1)
            if len(parts) == 2:
                k = parts[0].strip().lower()
                v = parts[1].strip()
                if k == "count":
                    try:
                        info["loose_objects"] = int(v)
                    except ValueError:
                        pass
                elif k == "size":
                    info["loose_size"] = v
                elif k == "in-pack":
                    try:
                        info["in_pack_objects"] = int(v)
                    except ValueError:
                        pass
                elif k == "packs":
                    try:
                        info["packs_count"] = int(v)
                    except ValueError:
                        pass
                elif k == "size-pack":
                    info["pack_size"] = v
                elif k == "garbage":
                    try:
                        info["garbage_count"] = int(v)
                    except ValueError:
                        pass
                elif k == "size-garbage":
                    info["garbage_size"] = v

        return info

    def load_config(self) -> Dict[str, Any]:
        """Загружает секцию git_maintenance из файла config.json.

        Returns:
            Dict[str, Any]: Словарь параметров конфигурации обслуживания.
        """
        default_cfg: Dict[str, Any] = {
            "auto_gc_enabled": True,
            "gc_interval_hours": 24,
            "aggressive": False,
            "auto_prune": True,
            "last_gc_run": None,
            "last_gc_status": "not_run_yet",
        }
        if not self.config_path.exists():
            return default_cfg

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                root_cfg = json.load(f)
            return root_cfg.get("git_maintenance", default_cfg)
        except Exception as exc:
            logger.warning(f"[GitMaintenance] Ошибка чтения {self.config_path}: {exc}")
            return default_cfg

    def update_config(
        self,
        auto_gc_enabled: Optional[bool] = None,
        gc_interval_hours: Optional[int] = None,
        aggressive: Optional[bool] = None,
        auto_prune: Optional[bool] = None,
        last_gc_run: Optional[str] = None,
        last_gc_status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Обновляет параметры секции git_maintenance в config.json.

        Returns:
            Dict[str, Any]: Обновлённая конфигурация обслуживания.
        """
        root_cfg: Dict[str, Any] = {}
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    root_cfg = json.load(f)
            except Exception as exc:
                logger.warning(f"[GitMaintenance] Ошибка загрузки {self.config_path}: {exc}")

        current = root_cfg.get("git_maintenance", {
            "auto_gc_enabled": True,
            "gc_interval_hours": 24,
            "aggressive": False,
            "auto_prune": True,
            "last_gc_run": None,
            "last_gc_status": "not_run_yet",
        })

        if auto_gc_enabled is not None:
            current["auto_gc_enabled"] = bool(auto_gc_enabled)
        if gc_interval_hours is not None:
            current["gc_interval_hours"] = max(1, int(gc_interval_hours))
        if aggressive is not None:
            current["aggressive"] = bool(aggressive)
        if auto_prune is not None:
            current["auto_prune"] = bool(auto_prune)
        if last_gc_run is not None:
            current["last_gc_run"] = last_gc_run
        if last_gc_status is not None:
            current["last_gc_status"] = last_gc_status

        root_cfg["git_maintenance"] = current
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(root_cfg, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.error(f"[GitMaintenance] Ошибка сохранения {self.config_path}: {exc}")

        return current

    def get_status(self) -> Dict[str, Any]:
        """Возвращает агрегированный статус обслуживания Git.

        Returns:
            Dict[str, Any]: Полный статус обслуживания, параметров и репозитория.
        """
        cfg = self.load_config()
        repo_info = self.get_repo_info()
        return {
            "is_running": self._is_running,
            "auto_gc_enabled": cfg.get("auto_gc_enabled", True),
            "gc_interval_hours": cfg.get("gc_interval_hours", 24),
            "aggressive": cfg.get("aggressive", False),
            "auto_prune": cfg.get("auto_prune", True),
            "last_gc_run": cfg.get("last_gc_run"),
            "last_gc_status": cfg.get("last_gc_status", "not_run_yet"),
            "repo_info": repo_info,
        }

    def run_gc(self, aggressive: bool = False, prune: bool = True) -> Dict[str, Any]:
        """Выполняет оптимизацию репозитория git gc.

        Args:
            aggressive: Выполнять агрессивную перепаковку объектов.
            prune: Удалять недостижимые объекты немедленно (--prune=now).

        Returns:
            Dict[str, Any]: Результат выполнения git gc.
        """
        with self._lock:
            if self._is_running:
                return {
                    "success": False,
                    "message": "Процесс git gc уже выполняется",
                    "output": "",
                }
            self._is_running = True

        try:
            start_time = time.time()
            args = ["gc"]
            if aggressive:
                args.append("--aggressive")
            if prune:
                args.append("--prune=now")
            else:
                args.append("--auto")

            logger.console(f"[GitMaintenance] Запуск git gc: {' '.join(args)}...")
            output = self._run_git(args, timeout_sec=240)
            elapsed = round(time.time() - start_time, 2)
            timestamp = datetime.datetime.now().isoformat()

            status_str = f"Успешно завершено за {elapsed} сек ({timestamp})"
            logger.console(f"[GitMaintenance] {status_str}")

            self.update_config(last_gc_run=timestamp, last_gc_status=status_str)
            updated_info = self.get_repo_info()

            return {
                "success": True,
                "elapsed_sec": elapsed,
                "timestamp": timestamp,
                "output": output,
                "status": status_str,
                "repo_info": updated_info,
            }
        except Exception as exc:
            error_msg = f"Ошибка при выполнении git gc: {exc}"
            logger.error(f"[GitMaintenance] {error_msg}")
            self.update_config(last_gc_status=error_msg)
            return {
                "success": False,
                "error": error_msg,
            }
        finally:
            with self._lock:
                self._is_running = False

    def check_and_run_scheduled(self) -> Optional[Dict[str, Any]]:
        """Проверяет интервал, проводит диагностику показателей и запускает gc только при необходимости.

        Returns:
            Optional[Dict[str, Any]]: Результат диагностики/выполнения или None.
        """
        cfg = self.load_config()
        if not cfg.get("auto_gc_enabled", False):
            return None

        interval_hours = cfg.get("gc_interval_hours", 24)
        last_run_str = cfg.get("last_gc_run")

        should_check = False
        if not last_run_str:
            should_check = True
        else:
            try:
                last_dt = datetime.datetime.fromisoformat(last_run_str)
                delta = datetime.datetime.now() - last_dt
                if delta.total_seconds() >= interval_hours * 3600:
                    should_check = True
            except Exception:
                should_check = True

        if should_check:
            logger.info("[GitMaintenance] Плановая диагностика показателей репозитория...")
            from apps.ai_assistant.core.git_maintenance_analyzer import git_maintenance_analyzer, MaintenanceVerdict

            diagnosis = git_maintenance_analyzer.diagnose()
            now_iso = datetime.datetime.now().isoformat()

            # Если показатели требуют обслуживания - запускаем штатный git gc --auto
            if diagnosis.verdict == MaintenanceVerdict.MAINTENANCE_REQUIRED:
                logger.info(f"[GitMaintenance] Зафиксировано превышение порогов: {diagnosis.explanation}. Запуск git gc --auto...")
                res = self.run_gc(aggressive=False, prune=False)
                res["diagnosis"] = diagnosis.model_dump()
                return res

            # Иначе фиксируем статус Норма / Наблюдение без запуска тяжелых процессов
            status_text = f"Диагностика: {diagnosis.verdict_title}. {diagnosis.recommendation} ({now_iso})"
            self.update_config(last_gc_run=now_iso, last_gc_status=status_text)
            return {
                "success": True,
                "status": status_text,
                "diagnosis": diagnosis.model_dump(),
            }
        return None


# Глобальный синглтон сервиса обслуживания
git_maintenance_service = GitMaintenanceService()
