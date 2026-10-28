# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant - Main Application Entrypoint
# =============================================================================
# Description:
#   Точка входа автономного микросервиса AI Assistant (Умная история версий,
#   WikiLLM и RAG FAISS). Предоставляет REST API и обслуживает WebGUI на порту 8002.
#
# Usage Examples:
#   CLI:
#     python -m apps.ai_assistant.main
#     uvicorn apps.ai_assistant.main:app --host 0.0.0.0 --port 8002
#
# File: main.py
# Project: ai-windows-admin
# Package: apps.ai_assistant
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 20:38:00
# =============================================================================

from __future__ import annotations
"""Основное FastAPI приложение микросервиса AI Assistant."""

import asyncio
import json
import os
import shutil
import sys
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Dict, Optional
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from logger import logger
from apps.common.webgui import SmartMultiDirStaticFiles, COMMON_WEBGUI_DIR
from apps.ai_assistant.api.routers.router_file_history import router as history_router
from apps.ai_assistant.api.routers.router_git_wikillm import router as wikillm_router
from apps.ai_assistant.api.routers.router_git_maintenance import router as git_maintenance_router
from apps.ai_assistant.api.routers.router_knowledge import router as knowledge_router
from apps.ai_assistant.api.routers.router_obsidian import router as obsidian_router
from apps.ai_assistant.api.routers.router_models import router as models_router
from apps.ai_assistant.api.routers.router_auth import router as auth_router
from apps.ai_assistant.api.routers.router_panel import router as panel_router
from apps.ai_assistant.core.git_maintenance import git_maintenance_service
from apps.ai_assistant.api.routers.router_gmail import router as gmail_router
from apps.ai_assistant.api.routers.router_calendar import router as calendar_router
from apps.ai_assistant.api.routers.router_drive import router as drive_router
from apps.ai_assistant.api.routers.router_contacts import router as contacts_router
from apps.ai_assistant.api.routers.router_keys import router as keys_router
from apps.ai_assistant.api.routers.router_plugins import router as plugins_router
from apps.common.file_editor import file_editor_router

from header import __root__
BASE_DIR:Path = __root__  / "apps" / "ai_assistant" 
CONFIG_PATH:Path = BASE_DIR /  "config.json"
WEBGUI_DIR:Path  = BASE_DIR / "api" / "webgui"


def resolve_app_path(path_str: str) -> Path:
    """Разрешает относительный или абсолютный путь к каталогу модуля ai_assistant или проекта.

    Args:
        path_str: Строка пути из конфигурации (относительная или абсолютная).

    Returns:
        Абсолютный путь к файлу или каталогу.
    """
    p = Path(path_str)
    if p.is_absolute():
        return p
    normalized = str(p).replace("\\", "/")
    if normalized.startswith("data/"):
        return (__root__ / p).resolve()
    if normalized.startswith("apps/ai_assistant/"):
        return (__root__ / p).resolve()
    return (BASE_DIR / p).resolve()


def load_app_config() -> Dict[str, any]:
    """Загружает параметры конфигурации из файла config.json приложения и корневого config.json."""
    cfg: Dict[str, any] = {}
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception as exc:
            logger.warning(f"[AIAssistant] Ошибка чтения config.json: {exc}")

    # Корневой config.json имеет приоритет для путей Chromium и глобальных хранилищ
    root_cfg_path = __root__ / "config.json"
    if root_cfg_path.exists():
        try:
            with open(root_cfg_path, "r", encoding="utf-8") as f:
                root_cfg = json.load(f)
                if isinstance(root_cfg, dict) and "chromium" in root_cfg:
                    cfg["chromium"] = root_cfg["chromium"]
        except Exception as exc:
            logger.warning(f"[AIAssistant] Ошибка чтения корневого config.json: {exc}")

    return cfg


def _migrate_legacy_chromium_data(target_profile: Path, target_cache: Path) -> None:
    """Переносит устаревший каталог chromium из apps/ai_assistant/data/chromium в единый data/chromium."""
    legacy_dir = BASE_DIR / "data" / "chromium"
    if not legacy_dir.exists():
        return
    target_root = __root__ / "data" / "chromium"
    if legacy_dir.resolve() == target_root.resolve():
        return
    try:
        target_root.mkdir(parents=True, exist_ok=True)
        for item in legacy_dir.iterdir():
            dest = target_root / item.name
            if not dest.exists():
                try:
                    shutil.move(str(item), str(dest))
                    logger.console(f"[AI Assistant] Данные Chromium перемещены: {item} -> {dest}")
                except Exception:
                    try:
                        if item.is_dir():
                            shutil.copytree(str(item), str(dest), dirs_exist_ok=True)
                        else:
                            shutil.copy2(str(item), str(dest))
                    except Exception:
                        pass
        try:
            if not any(legacy_dir.iterdir()):
                legacy_dir.rmdir()
        except Exception:
            pass
    except Exception as exc:
        logger.warning(f"[AIAssistant] Ошибка миграции legacy данных Chromium: {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Управление жизненным циклом сервиса при запуске и завершении."""
    logger.console("=" * 60)
    logger.console(" [AI Assistant] Сервис умной истории версий запускается...")
    logger.console(" [AI Assistant] REST API: http://127.0.0.1:8002/api/v1")
    logger.console(" [AI Assistant] WebGUI:   http://127.0.0.1:8002/")
    logger.console("=" * 60)

    # Фоновый воркер обслуживания Git
    async def _periodic_maintenance_worker():
        await asyncio.sleep(10)  # Первичная пауза после старта
        while True:
            try:
                await asyncio.to_thread(git_maintenance_service.check_and_run_scheduled)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning(f"[GitMaintenance] Ошибка фоновой проверки: {exc}")
            await asyncio.sleep(1800)  # Проверка каждые 30 минут

    # Автозапуск Telegram-бота при старте сервиса AI Assistant (если задан TELEGRAM_BOT_TOKEN)
    tg_plugin = None
    try:
        from dotenv import load_dotenv
        load_dotenv(__root__ / ".env")
        from apps.ai_assistant.api.routers.router_plugins import get_plugins_registry
        registry = get_plugins_registry()
        tg_plugin = registry.get("telegram_bot")
        if tg_plugin and getattr(tg_plugin, "enabled", True):
            await tg_plugin.start()
    except Exception as tg_exc:
        logger.warning(f"[AIAssistant] Не удалось запустить плагин telegram_bot при старте: {tg_exc}")

    worker_task = asyncio.create_task(_periodic_maintenance_worker())
    try:
        yield
    finally:
        worker_task.cancel()
        if tg_plugin and getattr(tg_plugin, "is_running", False):
            try:
                await tg_plugin.stop()
            except Exception:
                pass
        logger.console(" [AI Assistant] Остановка сервиса.")

app = FastAPI(
    title="AI-Windows-Admin Smart Version History & WikiLLM Assistant",
    description="Микросервис темпоральной истории версий Git, базы знаний WikiLLM и RAG FAISS.",
    version="1.0.0",
    lifespan=lifespan,
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение маршрутизаторов API
app.include_router(knowledge_router)
app.include_router(obsidian_router)
app.include_router(history_router)
app.include_router(wikillm_router)
app.include_router(git_maintenance_router)
app.include_router(panel_router)
app.include_router(models_router)
app.include_router(auth_router)
app.include_router(keys_router)
app.include_router(gmail_router)
app.include_router(calendar_router)
app.include_router(drive_router)
app.include_router(contacts_router)
app.include_router(plugins_router)
app.include_router(file_editor_router)

# ----------------------------------------------------------------------
#  Основные маршруты UI
# ----------------------------------------------------------------------

@app.get("/", include_in_schema=False)
async def root() -> FileResponse:
    """Главная страница WebGUI (по умолчанию) без редиректа."""
    logger.console("[INFO] Обслуживание корневого URL - отдаём index.html")
    index_file = WEBGUI_DIR / "index.html"
    return FileResponse(str(index_file))

@app.get("/ai_assistant", summary="Главная страница WebGUI (по умолчанию)")
async def serve_index() -> FileResponse:
    """Отдаёт index.html, используемый в WebGUI AI Assistant."""
    index_file = WEBGUI_DIR / "index.html"
    return FileResponse(str(index_file))


# Обслуживание статических файлов WebGUI
if WEBGUI_DIR.exists():
    app.mount("/static", SmartMultiDirStaticFiles(WEBGUI_DIR, COMMON_WEBGUI_DIR), name="static")
    app.mount("/html", SmartMultiDirStaticFiles(WEBGUI_DIR, COMMON_WEBGUI_DIR), name="html")

    @app.get("/health", summary="Проверка статуса сервиса")
    async def health_check() -> Dict[str, str]:
        """Возвращает статус готовности микросервиса."""
        return {"status": "ok", "service": "apps.ai_assistant", "version": "1.0.0"}

    @app.get("/api/themes", summary="Каталог тем оформления WebGUI")
    async def get_themes_catalog() -> FileResponse:
        """Отдаёт общий каталог тем `apps/common/webgui/themes/themes_catalog.json`."""
        return FileResponse(str(COMMON_WEBGUI_DIR / "themes" / "themes_catalog.json"))


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Проверяет, занят ли указанный сетевой порт.

    Args:
        port: Номер проверяемого порта.
        host: Сетевой интерфейс (по умолчанию 127.0.0.1).

    Returns:
        True, если порт занят другим процессом, иначе False.
    """
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, port))
            return False
    except OSError:
        return True


def kill_process_on_port(port: int, max_wait_sec: float = 5.0) -> bool:
    """Завершает процесс, удерживающий сетевой порт, и ожидает его освобождения.

    Args:
        port: Номер порта.
        max_wait_sec: Максимальное время ожидания освобождения порта (в секундах).

    Returns:
        True, если порт успешно освобождён, иначе False.
    """
    from scripts.cli.utils import get_process_on_port, kill_process
    proc_info = get_process_on_port(port)
    if proc_info:
        pid, proc_name = proc_info
        logger.console(f"[AI Assistant] Завершение процесса {proc_name} (PID: {pid}) на порту {port}...")
        kill_process(pid, force=True)
    else:
        logger.warning(f"[AI Assistant] Процесс на порту {port} не определен через netstat.")

    start_time = time.time()
    while time.time() - start_time < max_wait_sec:
        if not is_port_in_use(port):
            logger.console(f"[AI Assistant] Порт {port} успешно освобождён.")
            return True
        time.sleep(0.3)
    return not is_port_in_use(port)


def resolve_occupied_port_action(
    port: int,
    host: str = "127.0.0.1",
    user_choice: Optional[str] = None,
    on_occupied_config: Optional[str] = None,
) -> str:
    """Определяет стратегию при занятом сетевом порте: подключение или перезапуск.

    Args:
        port: Номер занятого порта.
        host: Сетевой хост.
        user_choice: Явный выбор пользователя ("connect" или "restart").
        on_occupied_config: Значение из config.json ("connect", "restart" или "prompt").

    Returns:
        Строка "connect" (подключиться к текущему) или "restart" (убить и перезапустить).
    """
    if user_choice in ("connect", "restart"):
        return user_choice

    strategy = (on_occupied_config or "prompt").lower().strip()
    if strategy in ("connect", "restart"):
        return strategy

    from scripts.cli.utils import get_process_on_port
    proc_info = get_process_on_port(port)
    pid_str = f"PID: {proc_info[0]} ({proc_info[1]})" if proc_info else "PID неизвестен"

    is_interactive = bool(sys.stdin and hasattr(sys.stdin, "isatty") and sys.stdin.isatty())
    if is_interactive:
        logger.console("=" * 64)
        logger.console(f"[AI Assistant] Порт {port} уже используется ({pid_str}).")
        logger.console("Сервис AI Assistant уже запущен.")
        logger.console("=" * 64)
        logger.console("Выберите действие:")
        logger.console("  [1] Подключиться к текущему процессу (запустить GUI) [по умолчанию]")
        logger.console("  [2] Завершить процесс и запустить новый сервер")
        try:
            choice = input("Ваш выбор [1/2] (Enter = 1): ").strip().lower()
            if choice in ("2", "r", "restart", "new"):
                return "restart"
        except (EOFError, KeyboardInterrupt):
            logger.console("\n[AI Assistant] Прервано пользователем. Подключение к текущему процессу.")
        return "connect"

    logger.console(f"[AI Assistant] Порт {port} занят ({pid_str}). Неинтерактивный режим: подключение к текущему процессу.")
    return "connect"


def _setup_webview_tray(window: Any, is_force_exit: list[bool]) -> None:
    """Инициализирует и запускает системный трей для окна WebView2.

    Args:
        window: Объект окна pywebview.
        is_force_exit: Ссылочный флаг принудительного закрытия приложения.
    """
    try:
        import pystray
        from PIL import Image

        icon_path = WEBGUI_DIR / "assets" / "icon256.png"
        if not icon_path.exists():
            icon_path = WEBGUI_DIR / "assets" / "favicon.ico"

        if icon_path.exists():
            img = Image.open(icon_path)
        else:
            img = Image.new("RGBA", (64, 64), (37, 99, 235, 255))

        tray_state: Dict[str, Any] = {"tray": None}

        def _on_show(icon: Any, item: Any = None) -> None:
            """Восстанавливает и отображает окно приложения из трея."""
            window.show()
            window.restore()

        def _on_quit(icon: Any, item: Any = None) -> None:
            """Завершает работу приложения и закрывает окно."""
            is_force_exit[0] = True
            if tray_state["tray"]:
                tray_state["tray"].stop()
            window.destroy()

        menu = pystray.Menu(
            pystray.MenuItem("Показать AI Assistant", _on_show, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Выход", _on_quit),
        )

        tray = pystray.Icon("AIAssistant", img, "AI Assistant", menu)
        tray_state["tray"] = tray
        tray.run()
    except Exception as exc:
        logger.warning(f"[WARN] Не удалось инициализировать системный трей pywebview: {exc}")


def launch_gui(
    url: str,
    engine: str,
    profile_path: Path,
    cache_path: Path,
    server_thread: Optional[threading.Thread] = None,
) -> None:
    """Запускает графическую оболочку (Electron, WebView2 или системный браузер).

    Args:
        url: URL веб-приложения для отображения.
        engine: Идентификатор движка оболочки ("electron", "webview2", "browser", "headless").
        profile_path: Путь к пользовательскому профилю Chromium / WebView2.
        cache_path: Путь к дисковому кэшу.
        server_thread: Поток фонового сервера (если запущен локально).
    """
    if engine == "headless":
        logger.console(f"[INFO] Режим headless: интерфейс доступен по адресу {url}")
        if server_thread:
            try:
                while server_thread.is_alive():
                    server_thread.join(timeout=1.0)
            except (KeyboardInterrupt, SystemExit):
                pass
        return

    # Попытка запуска оболочки Electron
    if engine == "electron":
        from apps.ai_assistant.core.engine_adapter import ElectronEngineAdapter

        el_adapter = ElectronEngineAdapter()
        if el_adapter._find_electron_binary():
            launch_info = el_adapter.launch_shell(
                url=url,
                force_fresh=bool(server_thread),
                profile_path=profile_path,
                cache_path=cache_path,
            )
            if launch_info.get("status") == "launched":
                proc = launch_info.get("process")
                time.sleep(0.5)
                if proc and proc.poll() is not None and proc.returncode != 0:
                    logger.warning(
                        f"[ElectronEngineAdapter] Процесс Electron завершился с кодом {proc.returncode}. Переключение на резервный интерфейс..."
                    )
                else:
                    logger.console(f"[INFO] Запущена оболочка Electron (PID: {launch_info.get('pid')})")
                    if proc and not server_thread:
                        try:
                            proc.wait()
                        except (KeyboardInterrupt, SystemExit):
                            pass
                        return
                    if server_thread:
                        try:
                            while server_thread.is_alive():
                                if proc and proc.poll() is not None:
                                    # Если новый процесс передал фокус уже активному экземпляру Electron (код 0),
                                    # удерживаем сервер активным, пока работает основное окно Electron
                                    if proc.returncode == 0 and el_adapter.get_running_pids():
                                        server_thread.join(timeout=1.0)
                                        continue
                                    break
                                server_thread.join(timeout=1.0)
                        except (KeyboardInterrupt, SystemExit):
                            pass
                        finally:
                            el_adapter.terminate_running_instances()
                        return

    # Fallback / режим WebView2 (pywebview)
    try:
        import webview
        window = webview.create_window("AI Assistant", url, width=1200, height=800)
        is_force_exit = [False]

        def _on_closing() -> bool:
            if not is_force_exit[0]:
                window.hide()
                return False
            return True

        window.events.closing += _on_closing
        threading.Thread(target=_setup_webview_tray, args=(window, is_force_exit), daemon=True).start()
        webview.start(storage_path=str(profile_path), private_mode=False)
        return
    except Exception as exc:
        logger.warning(f"[WARN] Окно WebView недоступно ({exc}). Запуск в браузере: {url}")

    import webbrowser
    webbrowser.open(url)
    if server_thread:
        try:
            while server_thread.is_alive():
                server_thread.join(timeout=1.0)
        except (KeyboardInterrupt, SystemExit):
            pass


def run(
    port: Optional[int] = None,
    host: Optional[str] = None,
    no_gui: bool = False,
    engine: Optional[str] = None,
    action: Optional[str] = None,
) -> None:
    """Запускает сервис AI Assistant и открывает интерфейс пользователя.

    Если порт уже занят работающей системой, предлагает подключиться к ней или перезапустить.

    Args:
        port: Сетевой порт сервиса.
        host: Сетевой хост сервиса.
        no_gui: Флаг отключения графического интерфейса.
        engine: Движок оболочки ("electron", "webview2", "browser", "headless").
        action: Стратегия при занятом порте ("connect", "restart", "prompt" или None).
    """
    cfg = load_app_config()
    server_cfg = cfg.get("server", {})
    target_port = int(port if port is not None else server_cfg.get("port", cfg.get("port", 8002)))
    target_host = str(host if host is not None else server_cfg.get("host", cfg.get("host", "127.0.0.1")))
    preferred_engine = (engine or cfg.get("engine", {}).get("preferred", "electron")).lower()

    # Определение активного рабочего пространства для канонического URL (#tab-workspace#panel-files#workspace=<id>)
    active_ws_id = ""
    try:
        from apps.ai_assistant.core.workspace_manager import WorkspaceManager
        wm = WorkspaceManager()
        all_workspaces = wm.list_workspaces()
        existing_ids = {w.get("workspace_id") for w in all_workspaces if w.get("workspace_id")}

        # 1. Проверяем последнее активное рабочее пространство из config.json / store
        saved_active = wm.get_active_workspace_id() or ""
        if saved_active and saved_active in existing_ids:
            active_ws_id = saved_active

        # 2. Проверяем сохранённое состояние в electron_state.json
        if not active_ws_id:
            el_state_file = __root__ / "data" / "electron_state.json"
            if el_state_file.exists():
                try:
                    el_data = json.loads(el_state_file.read_text(encoding="utf-8"))
                    el_ws = el_data.get("active_workspace_id")
                    if el_ws and el_ws in existing_ids:
                        active_ws_id = el_ws
                except Exception:
                    pass

        # 3. Проверяем сохранённый активный репозиторий
        if not active_ws_id:
            saved_repo = wm.store.get_active_repo()
            repo_ws = saved_repo.get("workspace_id") or ""
            if repo_ws and repo_ws in existing_ids:
                active_ws_id = repo_ws

        # 4. Резервный выбор: первое доступное пространство
        if not active_ws_id and all_workspaces:
            active_ws_id = all_workspaces[0].get("workspace_id", "")
    except Exception as exc:
        logger.warning(f"[AIAssistant] Ошибка определения активного пространства: {exc}")

    url = f"http://{target_host}:{target_port}"
    if active_ws_id:
        from urllib.parse import quote
        url = f"{url}/#tab-workspace#panel-files#workspace={quote(active_ws_id)}"
    else:
        # Если ни одного рабочего пространства нет — сразу переходим на менеджер создания
        url = f"{url}/#tab-create-workspace"

    chromium_cfg = cfg.get("chromium") or cfg.get("browser", {})
    raw_profile = chromium_cfg.get("profile_dir", "data/chromium/profiles")
    raw_cache = chromium_cfg.get("cache_dir", "data/chromium/cache")

    profile_path = resolve_app_path(raw_profile)
    cache_path = resolve_app_path(raw_cache)

    # Миграция устаревших файлов кэша из подкаталога приложения в data/chromium
    _migrate_legacy_chromium_data(profile_path, cache_path)

    try:
        profile_path.mkdir(parents=True, exist_ok=True)
        cache_path.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        logger.warning(f"[AIAssistant] Ошибка создания директорий Chromium: {exc}")

    os.environ["WEBVIEW2_USER_DATA_FOLDER"] = str(profile_path)
    current_args = os.environ.get("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", "")
    cache_arg = f'--disk-cache-dir="{cache_path}"'
    if "--disk-cache-dir" not in current_args:
        os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = f"{current_args} {cache_arg}".strip()

    # Проверка занятости сетевого порта
    if is_port_in_use(target_port, target_host):
        chosen_action = resolve_occupied_port_action(
            port=target_port,
            host=target_host,
            user_choice=action,
            on_occupied_config=server_cfg.get("on_occupied"),
        )
        if chosen_action == "connect":
            logger.console(f"[INFO] Подключение к работающему сервису AI Assistant: {url}")
            if not no_gui:
                launch_gui(url, preferred_engine, profile_path, cache_path)
            return

        logger.console(f"[INFO] Перезапуск: освобождение порта {target_port}...")
        kill_process_on_port(target_port)

    logger.console(f"[INFO] Запуск сервера на {url} (движок оболочки: {preferred_engine})…")
    from uvicorn import Config, Server

    if no_gui:
        config = Config("apps.ai_assistant.main:app", host=target_host, port=target_port, log_level="info")
        server = Server(config)
        server.run()
        return

    def _run_server():
        config = Config("apps.ai_assistant.main:app", host=target_host, port=target_port, log_level="info")
        server = Server(config)
        server.run()

    server_thread = threading.Thread(target=_run_server, daemon=True)
    server_thread.start()
    time.sleep(1.0)

    launch_gui(url, preferred_engine, profile_path, cache_path, server_thread=server_thread)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="AI Assistant Main Service Launcher")
    parser.add_argument("--port", type=int, default=None, help="Порт сервера (по умолчанию из config.json или 8002)")
    parser.add_argument("--host", type=str, default=None, help="Хост сервера (по умолчанию из config.json или 127.0.0.1)")
    parser.add_argument("--engine", type=str, default=None, choices=["electron", "webview2", "browser", "headless"], help="Движок GUI")
    parser.add_argument("--no-gui", action="store_true", help="Запуск без графического интерфейса")
    parser.add_argument("-c", "--connect", action="store_true", help="Подключиться к текущему запущенному процессу и открыть GUI")
    parser.add_argument("-r", "--restart", action="store_true", help="Завершить старый процесс на порту и запустить новый")
    parser.add_argument("--action", type=str, choices=["connect", "restart", "prompt"], default=None, help="Действие при занятом порте")

    cli_args = parser.parse_args()
    selected_action = "restart" if cli_args.restart else ("connect" if cli_args.connect else cli_args.action)
    run(
        port=cli_args.port,
        host=cli_args.host,
        no_gui=cli_args.no_gui,
        engine=cli_args.engine,
        action=selected_action,
    )