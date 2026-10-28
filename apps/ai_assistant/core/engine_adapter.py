# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Core - Dual Engine Adapter API
# =============================================================================
# Description:
#   Единый контракт команд и событий (Engine Adapter API) для поддержки двух
#   движков оболочки Obsidian и базы знаний:
#   1. Electron (приоритетный движок: Chromium + Node.js runtime, IPC, полная
#      совместимость с экосистемой Obsidian и десктопной оболочкой).
#   2. WebView2 (встроенный лёгкий Windows GUI хост через pywebview / Edge).
#
#   Разделяет общий веб-интерфейс, движок отображения и общий backend
#   (FastAPI · файловая система · Obsidian Vault · Git · WikiLLM · RAG).
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.core.engine_adapter import EngineRuntimeManager
#
#     mgr = EngineRuntimeManager(preferred_engine="electron")
#     status = mgr.get_status()
#
# File: engine_adapter.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 17:19:00
# =============================================================================

from __future__ import annotations
"""Адаптеры движков отображения (Electron и WebView2) с единым контрактом управления."""

import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Dict, Optional, Protocol
from urllib.parse import quote, unquote

from header import __root__
from logger import logger


class EngineAdapterProtocol(Protocol):
    """Единый контракт команд и событий для движка оболочки (Electron / WebView2)."""

    engine_id: str
    label: str

    def is_available(self) -> bool:
        """Проверяет доступность рантайма движка в текущей ОС."""
        ...

    def get_capabilities(self) -> Dict[str, Any]:
        """Возвращает паспорт возможностей движка."""
        ...

    def build_obsidian_uri(self, vault_path: Path, note_name: Optional[str] = None) -> str:
        """Формирует URI протокола `obsidian://open?path=...` для открытия Vault."""
        ...

    def open_obsidian_vault(self, vault_path: Path, note_name: Optional[str] = None) -> Dict[str, Any]:
        """Открывает папку рабочего пространства в Obsidian или файловом навигаторе."""
        ...

    def launch_shell(self, url: str, vault_path: Optional[Path] = None) -> Dict[str, Any]:
        """Запускает графическую оболочку соответствующего движка."""
        ...


class BaseEngineAdapter:
    """Базовая реализация общих операций с протоколом Obsidian и файловой системой."""

    engine_id: str = "base"
    label: str = "Base Engine"

    def build_obsidian_uri(self, vault_path: Path, note_name: Optional[str] = None) -> str:
        """Формирует протокольную ссылку `obsidian://open?path=...` для открытия Vault или заметки."""
        target = (vault_path / note_name) if note_name else vault_path
        encoded = quote(str(target.resolve()), safe="")
        return f"obsidian://open?path={encoded}"

    def open_obsidian_vault(self, vault_path: Path, note_name: Optional[str] = None) -> Dict[str, Any]:
        """Запускает протокол `obsidian://` через системный обработчик Windows (с fallback на папку)."""
        uri = self.build_obsidian_uri(vault_path, note_name=note_name)
        launched = False
        method = "uri_protocol"
        try:
            if hasattr(os, "startfile"):
                os.startfile(uri)  # type: ignore[attr-defined]
                launched = True
            else:
                subprocess.Popen(["cmd", "/c", "start", "", uri], shell=False)
                launched = True
        except Exception as exc:
            logger.warning(f"[EngineAdapter] Протокол obsidian:// недоступен ({exc}), открываем директорию Vault.")
            method = "explorer_fallback"
            try:
                if hasattr(os, "startfile") and vault_path.exists():
                    os.startfile(str(vault_path.resolve()))  # type: ignore[attr-defined]
                    launched = True
            except Exception as exp_exc:
                logger.warning(f"[EngineAdapter] Не удалось открыть проводник: {exp_exc}")

        return {
            "status": "ok" if launched else "uri_ready",
            "engine": self.engine_id,
            "method": method,
            "vault_path": str(vault_path.resolve()),
            "obsidian_uri": uri,
            "launched": launched,
        }


class ElectronEngineAdapter(BaseEngineAdapter):
    """Адаптер самостоятельной оболочки Electron (Chromium + Node.js + IPC)."""

    engine_id = "electron"
    label = "Electron Shell (Chromium + Node.js)"

    def __init__(self, electron_app_dir: Optional[Path] = None) -> None:
        """Инициализирует адаптер Electron с путём к каталогу `apps/ai_assistant/electron`."""
        default_dir = Path(__file__).resolve().parent.parent / "electron"
        self.app_dir = (electron_app_dir or default_dir).resolve()

    def _find_electron_binary(self) -> Optional[str]:
        """Ищет исполняемый файл Electron (локальный dist/electron.exe, node_modules/.bin/electron или глобальный npx/electron)."""
        dist_exe = self.app_dir / "node_modules" / "electron" / "dist" / ("electron.exe" if os.name == "nt" else "electron")
        if dist_exe.exists():
            return str(dist_exe)
        local_cmd = self.app_dir / "node_modules" / ".bin" / ("electron.cmd" if os.name == "nt" else "electron")
        if local_cmd.exists():
            return str(local_cmd)
        global_el = shutil.which("electron")
        if global_el:
            return global_el
        npx_bin = shutil.which("npx")
        if npx_bin:
            return npx_bin
        return None

    def is_available(self) -> bool:
        """Проверяет наличие конфигурации `electron/main.js` и среды Node.js / Electron."""
        has_shell_files = (self.app_dir / "package.json").exists() and (self.app_dir / "main.js").exists()
        has_node = shutil.which("node") is not None
        return bool(has_shell_files and has_node)

    def get_capabilities(self) -> Dict[str, Any]:
        """Возвращает характеристики среды Electron согласно архитектурной спецификации."""
        return {
            "engine_id": self.engine_id,
            "label": self.label,
            "role": "Самостоятельное приложение (Chromium + Node.js)",
            "chromium_env": "Chromium в составе Electron",
            "nodejs_in_ui": True,
            "windows_api_access": "Через IPC (contextBridge / ipcMain) и нативные модули",
            "obsidian_plugin_compat": True,
            "shell_dir": str(self.app_dir),
            "available": self.is_available(),
            "binary": self._find_electron_binary() or "node",
        }

    def get_running_pids(self) -> list[int]:
        """Возвращает список PID запущенных процессов Electron, принадлежащих данной оболочке."""
        pids: list[int] = []
        app_dir_norm = str(self.app_dir).lower().replace("\\", "/")
        try:
            import psutil

            for proc in psutil.process_iter(["pid", "name", "exe", "cmdline"]):
                try:
                    pname = (proc.info.get("name") or "").lower()
                    if "electron" not in pname:
                        continue
                    exe = (proc.info.get("exe") or "").lower().replace("\\", "/")
                    cmdline = " ".join(proc.info.get("cmdline") or []).lower().replace("\\", "/")
                    if app_dir_norm in exe or app_dir_norm in cmdline:
                        pids.append(int(proc.info["pid"]))
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except Exception as exc:
            logger.debug(f"[ElectronEngineAdapter] Не удалось опросить процессы Electron: {exc}")
        return pids

    def terminate_running_instances(self) -> int:
        """Завершает все активные или зависшие процессы оболочки Electron данного приложения."""
        pids = self.get_running_pids()
        if not pids:
            return 0
        terminated = 0
        try:
            import psutil

            procs = []
            for pid in pids:
                try:
                    p = psutil.Process(pid)
                    p.terminate()
                    procs.append(p)
                    terminated += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            _, alive = psutil.wait_procs(procs, timeout=2.0)
            for p in alive:
                try:
                    p.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as exc:
            logger.warning(f"[ElectronEngineAdapter] Ошибка завершения процессов Electron: {exc}")
        return terminated

    def launch_shell(
        self,
        url: str,
        vault_path: Optional[Path] = None,
        force_fresh: bool = False,
        profile_path: Optional[Path] = None,
        cache_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Запускает десктопную оболочку Electron с подключением к общему backend FastAPI.

        Гарантирует изоляцию данных: если пути к профилю и кэшу не переданы явно,
        они автоматически разрешаются в корневой каталог `data/chromium/` проекта,
        исключая загрязнение системного каталога `%APPDATA%`.

        Args:
            url (str): Канонический URL интерфейса WebGUI (включая активное рабочее пространство).
            vault_path (Optional[Path], optional): Путь к каталогу заметок Obsidian Vault. По умолчанию None.
            force_fresh (bool, optional): Флаг принудительного завершения предыдущих экземпляров. По умолчанию False.
            profile_path (Optional[Path], optional): Путь к каталогу профиля браузера (userData). Если не передан,
                разрешается в `data/chromium/profiles` в корне проекта.
            cache_path (Optional[Path], optional): Путь к дисковому кэшу Chromium. Если не передан,
                разрешается в `data/chromium/cache` в корне проекта.

        Returns:
            Dict[str, Any]: Словарь со статусом запуска (`"launched"` или `"failed"`), объектом процесса Popen и PID.
        """
        if force_fresh:
            self.terminate_running_instances()

        env = os.environ.copy()
        # Исключаем ELECTRON_RUN_AS_NODE, чтобы родительские IDE на базе Electron (VS Code / Antigravity)
        # не переводили дочерний процесс electron.exe в режим обычного интерпретатора Node.js
        env.pop("ELECTRON_RUN_AS_NODE", None)
        env["AI_ASSISTANT_BACKEND_URL"] = url
        if "workspace=" in url:
            ws_match = re.search(r"workspace=([^&#]+)", url)
            if ws_match:
                env["AI_ASSISTANT_ACTIVE_WORKSPACE"] = unquote(ws_match.group(1))
        if vault_path:
            env["AI_ASSISTANT_VAULT_PATH"] = str(vault_path.resolve())
        if profile_path is None:
            profile_path = (__root__ / "data" / "chromium" / "profiles").resolve()
        if cache_path is None:
            cache_path = (__root__ / "data" / "chromium" / "cache").resolve()

        if profile_path:
            env["AI_ASSISTANT_CHROMIUM_PROFILE"] = str(profile_path.resolve())
        if cache_path:
            env["AI_ASSISTANT_CHROMIUM_CACHE"] = str(cache_path.resolve())

        extra_args: list[str] = []
        if profile_path:
            extra_args.append(f"--user-data-dir={profile_path.resolve()}")
        if cache_path:
            extra_args.append(f"--disk-cache-dir={cache_path.resolve()}")

        dist_exe = self.app_dir / "node_modules" / "electron" / "dist" / ("electron.exe" if os.name == "nt" else "electron")
        local_cmd = self.app_dir / "node_modules" / ".bin" / ("electron.cmd" if os.name == "nt" else "electron")
        global_el = shutil.which("electron")
        npx_bin = shutil.which("npx")

        # Если рантайм Electron локально не собран, пробуем автоматическую установку через npm
        if not dist_exe.exists() and not local_cmd.exists() and not global_el:
            npm_bin = shutil.which("npm.cmd" if os.name == "nt" else "npm")
            if npm_bin and (self.app_dir / "package.json").exists():
                logger.console("[INFO] Зависимости Electron не обнаружены. Запуск автоматической установки через npm...")
                try:
                    subprocess.run(
                        [npm_bin, "install"],
                        cwd=str(self.app_dir),
                        check=False,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                except Exception as inst_exc:
                    logger.warning(f"[ElectronEngineAdapter] Ошибка автоматической установки зависимостей: {inst_exc}")

        cmd = None
        if dist_exe.exists():
            cmd = [str(dist_exe), str(self.app_dir), *extra_args]
        elif local_cmd.exists():
            cmd = [str(local_cmd), str(self.app_dir), *extra_args]
        elif global_el:
            cmd = [global_el, str(self.app_dir), *extra_args]
        elif npx_bin:
            cmd = [npx_bin, "-y", "electron", str(self.app_dir), *extra_args]

        if cmd:
            try:
                proc = subprocess.Popen(
                    cmd,
                    cwd=str(self.app_dir),
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return {
                    "status": "launched",
                    "engine": self.engine_id,
                    "pid": proc.pid,
                    "url": url,
                    "command": " ".join(cmd),
                    "process": proc,
                }
            except Exception as exc:
                logger.warning(f"[ElectronEngineAdapter] Сбой запуска процесса Electron: {exc}")

        return {
            "status": "ready_to_launch",
            "engine": self.engine_id,
            "url": url,
            "shell_dir": str(self.app_dir),
            "command": f'cd "{self.app_dir}" && npm start',
        }


class WebView2EngineAdapter(BaseEngineAdapter):
    """Адаптер встроенного Windows GUI хоста на базе Microsoft Edge WebView2 (`pywebview`)."""

    engine_id = "webview2"
    label = "Microsoft Edge WebView2 Host"

    def is_available(self) -> bool:
        """Проверяет доступность модуля `webview` (pywebview) в Python-окружении."""
        try:
            import importlib.util
            return importlib.util.find_spec("webview") is not None
        except Exception:
            return False

    def get_capabilities(self) -> Dict[str, Any]:
        """Возвращает характеристики среды WebView2 согласно архитектурной спецификации."""
        return {
            "engine_id": self.engine_id,
            "label": self.label,
            "role": "Встроенное окно Windows",
            "chromium_env": "WebView2 Runtime (Edge)",
            "nodejs_in_ui": False,
            "windows_api_access": "Через Python / .NET хост",
            "obsidian_plugin_compat": False,
            "available": self.is_available(),
        }

    def launch_shell(self, url: str, vault_path: Optional[Path] = None) -> Dict[str, Any]:
        """Возвращает параметры запуска легковесного окна WebView2."""
        return {
            "status": "ready_to_launch",
            "engine": self.engine_id,
            "url": url,
            "vault_path": str(vault_path.resolve()) if vault_path else "",
            "command": "python -m apps.ai_assistant.main --engine webview2",
        }


class EngineRuntimeManager:
    """Координатор двойного движка (Electron + WebView2) с общим интерфейсом и единым backend."""

    def __init__(self, preferred_engine: str = "electron") -> None:
        """Инициализирует менеджер движков (по умолчанию приоритет у `electron`)."""
        self.preferred_engine = preferred_engine if preferred_engine in ("electron", "webview2") else "electron"
        self.electron = ElectronEngineAdapter()
        self.webview2 = WebView2EngineAdapter()
        self._adapters: Dict[str, BaseEngineAdapter] = {
            "electron": self.electron,
            "webview2": self.webview2,
        }

    def get_adapter(self, engine_id: Optional[str] = None) -> BaseEngineAdapter:
        """Возвращает адаптер выбранного движка или приоритетный (`electron`)."""
        target = (engine_id or self.preferred_engine).lower()
        return self._adapters.get(target, self.electron)

    def set_preferred_engine(self, engine_id: str) -> Dict[str, Any]:
        """Переключает активный движок оболочки (`electron` или `webview2`)."""
        clean = engine_id.strip().lower()
        if clean not in self._adapters:
            raise ValueError(f"Неподдерживаемый движок: {engine_id}. Допустимы: electron, webview2")
        self.preferred_engine = clean
        return self.get_status()

    def get_status(self) -> Dict[str, Any]:
        """Возвращает сводный статус обоих движков и текущей конфигурации оболочки."""
        return {
            "status": "ok",
            "preferred_engine": self.preferred_engine,
            "architecture": "Dual-Engine Unified Shell (Electron + WebView2 -> FastAPI + Obsidian Vault + Git)",
            "engines": {
                "electron": self.electron.get_capabilities(),
                "webview2": self.webview2.get_capabilities(),
            },
        }
