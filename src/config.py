# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin CORE - Config Module
# =============================================================================
# Description:
#   Модуль основной системы (`config`).
#   Управляет конфигурацией, параметрами сервера, AI-провайдерами,
#   а также системными путями (рабочая директория, data, logs, tmp).
#
# Usage Examples:
#   Python API:
#     from src.config import app_name, WORKING_DIR, DATA_DIR, LOGS_DIR, TMP_DIR
#     print(app_name, DATA_DIR, LOGS_DIR, TMP_DIR)
#
# File: config.py
# Project: ai-windows-admin
# Package: src
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 16:47:30
# =============================================================================

"""Модуль основной системы (`config`)."""

import os
from pathlib import Path
from types import SimpleNamespace
from src.utils.jjson import j_loads_ns
from header import __root__
from logger import logger

_cfg_env = os.getenv('AIWINDOWSADMIN_CONFIG') or os.getenv('CONFIG_FILE')
if _cfg_env:
    _cfg_path = Path(_cfg_env)
    if _cfg_path.is_absolute() and _cfg_path.exists():
        CONFIG_FILE = _cfg_path
    elif (__root__ / _cfg_env).exists():
        CONFIG_FILE = __root__ / _cfg_env
    elif (__root__ / 'apps' / 'windows' / _cfg_path.name).exists():
        CONFIG_FILE = __root__ / 'apps' / 'windows' / _cfg_path.name
    elif (__root__ / 'config' / _cfg_path.name).exists():
        CONFIG_FILE = __root__ / 'config' / _cfg_path.name
    else:
        CONFIG_FILE = __root__ / 'config.json'
else:
    CONFIG_FILE = __root__ / 'config.json'

if not CONFIG_FILE.exists() and (__root__ / 'config.json').exists():
    CONFIG_FILE = __root__ / 'config.json'

global_settings = j_loads_ns(CONFIG_FILE)

# Название рабочей директории из конфигурации (по умолчанию 'AI-Assistant')
app_name: str = str(getattr(global_settings, 'app_name', None) or 'AI-Assistant')
APP_NAME: str = app_name

# Базовые системные каталоги окружения
_localappdata_env: str = os.environ.get('LOCALAPPDATA') or str(Path.home() / 'AppData' / 'Local')
_appdata_env: str = os.environ.get('APPDATA') or str(Path.home() / 'AppData' / 'Roaming')

LOCALAPPDATA_DIR: Path = Path(_localappdata_env)
APPDATA_DIR: Path = Path(_appdata_env)

# Рабочая директория: %LOCALAPPDATA% / app_name
WORKING_DIR: Path = LOCALAPPDATA_DIR / APP_NAME

# Внутренний путь к data
if (WORKING_DIR / 'data').exists():
    DATA_DIR: Path = WORKING_DIR / 'data'
else:
    DATA_DIR: Path = __root__ / 'data'

# Внутренние пути в %APPDATA% для логов и временных файлов tmp
LOGS_DIR: Path = APPDATA_DIR / APP_NAME / 'logs'
TMP_DIR: Path = APPDATA_DIR / APP_NAME / 'tmp'
TEMP_DIR: Path = TMP_DIR


def get_app_paths() -> dict[str, Path]:
    """Возвращает словарь основных системных путей приложения.

    Returns:
        dict[str, Path]: Словарь с путями working_dir, data_dir, logs_dir, tmp_dir.
    """
    return {
        'working_dir': WORKING_DIR,
        'data_dir': DATA_DIR,
        'logs_dir': LOGS_DIR,
        'tmp_dir': TMP_DIR,
    }


def ensure_app_dirs() -> None:
    """Создает основные рабочие директории (data, logs, tmp) при их отсутствии."""
    for directory in (DATA_DIR, LOGS_DIR, TMP_DIR):
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            logger.warning(f'Не удалось создать директорию {directory}: {exc}')


# Гарантируем создание необходимых системных папок
ensure_app_dirs()

server_cfg = getattr(global_settings, 'server', SimpleNamespace())

# Читаем единую конфигурацию ai_providers_and_models_configuration
ai_cfg_section = getattr(global_settings, 'ai_providers_and_models_configuration', None)
if ai_cfg_section is None:
    ai_cfg_section = getattr(global_settings, 'ai', SimpleNamespace())
ai_cfg = ai_cfg_section
tts_cfg = getattr(global_settings, 'tts', SimpleNamespace())
logging_cfg = getattr(global_settings, 'logging', SimpleNamespace())
pprint_cfg = getattr(global_settings, 'pprint', getattr(global_settings, 'printer', SimpleNamespace()))
printer_cfg = pprint_cfg
storage_cfg = getattr(global_settings, 'storage', SimpleNamespace())

# Устанавливаем значение по умолчанию, если users_dir не задан
if not getattr(storage_cfg, 'users_dir', None):
    storage_cfg.users_dir = str(DATA_DIR / 'users')

raw_dir = getattr(storage_cfg, 'users_dir', None)
if isinstance(raw_dir, str):
    if '%APPDATA%' in raw_dir:
        raw_dir = raw_dir.replace('%APPDATA%', str(APPDATA_DIR))
    if '%LOCALAPPDATA%' in raw_dir:
        raw_dir = raw_dir.replace('%LOCALAPPDATA%', str(LOCALAPPDATA_DIR))
    storage_cfg.users_dir = raw_dir
    logger.info(f'Resolved users_dir to {raw_dir}')

plugins_cfg = getattr(global_settings, 'plugins', SimpleNamespace())
schedulers_cfg = getattr(global_settings, 'schedulers', getattr(global_settings, 'scheduler', SimpleNamespace()))
apps_cfg = getattr(global_settings, 'apps', SimpleNamespace())


def is_app_enabled(target_app_name: str) -> bool:
    """Проверяет, активно ли приложение согласно текущей конфигурации.

    Args:
        target_app_name (str): Идентификатор приложения (например, 'wikipedia_research', 'network_terminal').

    Returns:
        bool: True, если приложение разрешено и не находится в списке отключенных; иначе False.
    """
    apps_section = getattr(global_settings, 'apps', None)
    if not apps_section:
        return True
    enabled = getattr(apps_section, 'enabled', None)
    disabled = getattr(apps_section, 'disabled', None)
    if disabled is not None:
        disabled_list = list(disabled) if hasattr(disabled, '__iter__') and (not isinstance(disabled, str)) else [disabled]
        if target_app_name in disabled_list:
            return False
    if enabled is not None:
        enabled_list = list(enabled) if hasattr(enabled, '__iter__') and (not isinstance(enabled, str)) else [enabled]
        if len(enabled_list) > 0:
            return target_app_name in enabled_list
    return True


def is_debug_mode() -> bool:
    """Проверяет, активен ли режим отладки (DEBUG / DEV).

    Режим отладки считается активным, если:
    - переменная окружения DEBUG установлена в ('1', 'true', 'yes', 'on', 'dev', 'debug')
    - переменная окружения MODE установлена в ('DEV', 'DEBUG')
    - в server_cfg параметр debug == True или mode == 'DEV'/'DEBUG'
    (Исключается при запуске юнит-тестов под pytest).

    Returns:
        bool: True, если активен режим DEBUG, иначе False.
    """
    if os.getenv('PYTEST_CURRENT_TEST'):
        return False
    env_debug = os.getenv('DEBUG', '').strip().lower()
    if env_debug in ('0', 'false', 'no', 'off', 'prod', 'production'):
        return False
    if env_debug in ('1', 'true', 'yes', 'on', 'dev', 'debug'):
        return True
    env_mode = os.getenv('MODE', '').strip().upper()
    if env_mode in ('PROD', 'PRODUCTION'):
        return False
    if env_mode in ('DEV', 'DEBUG'):
        return True
    if getattr(server_cfg, 'debug', False) is True:
        return True
    if str(getattr(server_cfg, 'mode', '')).upper() in ('DEV', 'DEBUG'):
        return True
    return False


from src.utils.ports import load_ports_config, PORTS_FILE
ports_cfg = load_ports_config(PORTS_FILE)
