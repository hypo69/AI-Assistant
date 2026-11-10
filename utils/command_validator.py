# -*- coding: utf-8 -*-
# =============================================================================
# Файл: utils/command_validator.py
# Описание: Модуль для безопасного выполнения команд PowerShell/CLI с поддержкой dry‑run,
#           защитой от Command Injection и обязательными таймаутами.
#
# Требования проекта:
#   • Все сообщения в консоль выводятся через logger.console()
#   • Докстринги и комментарии – на русском языке
#   • При изменении файла обновляется шапка с датой/временем
# =============================================================================
# Updated: 2026-11-10 14:35:45
# =============================================================================

"""hypo69 docblock
Модуль предоставляет функции для:
* Проверки синтаксиса, безопасности и наличия команд перед их выполнением (dry‑run).
* Выполнения команды с обязательным таймаутом и защитой от разрушительных инъекций.
* Формирования единого словаря результата, пригодного для последующей обработки
  другими компонентами проекта.

Все функции используют `logger.console()` для вывода сообщений пользователю, без
записи в файлы журнала, согласно правилам проекта.
"""

from __future__ import annotations

from datetime import datetime, timezone
import os
import re
import shlex
import subprocess
from typing import Any, Dict

try:
    from logger import logger  # type: ignore
except ImportError:  # fallback для автономной разработки
    class _DummyLogger:
        @staticmethod
        def console(msg: str) -> None:
            print(msg)
    logger = _DummyLogger()

# Стандартный таймаут выполнения внешней команды (секунды)
DEFAULT_COMMAND_TIMEOUT_SEC: int = 30

# Предкомпилированные множества и регулярные выражения для O(1) проверки командлетов и опасных паттернов
_PS_CMDLET_VERBS: frozenset[str] = frozenset({
    "stop-", "start-", "get-", "set-", "write-", "remove-", "new-",
    "invoke-", "select-", "where-", "foreach-", "test-", "clear-",
})

_DANGEROUS_COMMAND_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\brm\s+-rf\s+[/\\]", re.IGNORECASE),
    re.compile(r"\bformat\s+[a-z]:", re.IGNORECASE),
    re.compile(r"\bdel\s+/[fqs].*[/\\]\*", re.IGNORECASE),
    re.compile(r"\bremove-item\b.*-recurse.*-force.*([a-z]:\\|/)", re.IGNORECASE),
    re.compile(r"\b(invoke-expression|iex)\b.*(downloadstring| invoke-webrequest|iwr|curl|wget)", re.IGNORECASE),
    re.compile(r"\bshutdown\b\s+/[sr]", re.IGNORECASE),
)


def _log(message: str) -> None:
    """Вспомогательная обёртка над logger.console() со строгой UTC меткой времени.

    Args:
        message: Текст сообщения.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    logger.console(f"[{timestamp}] {message}")


def is_command_safe(command: str) -> bool:
    """Проверяет строку команды на отсутствие разрушительных паттернов и нулевых байтов.

    Args:
        command: Проверяемая командная строка.

    Returns:
        bool: True, если команда не содержит запрещённых конструкций.
    """
    if not command or not command.strip() or "\x00" in command:
        return False
    for pattern in _DANGEROUS_COMMAND_PATTERNS:
        if pattern.search(command):
            return False
    return True


def _is_powershell_cmdlet(command: str) -> bool:
    """Определяет за O(1), является ли строка PowerShell‑командой/cmdlet."""
    if not command or not command.strip():
        return False
    first_token = command.strip().split()[0].lower()
    dash_idx = first_token.find("-")
    if dash_idx <= 0:
        return False
    verb_prefix = first_token[: dash_idx + 1]
    return verb_prefix in _PS_CMDLET_VERBS


def _dry_run_powershell(command: str, timeout: int = DEFAULT_COMMAND_TIMEOUT_SEC) -> Dict[str, Any]:
    """Выполняет PowerShell‑команду в режиме *WhatIf* или проверяет синтаксис AST.

    Args:
        command: Команда PowerShell.
        timeout: Таймаут выполнения в секундах.

    Returns:
        Словарь с результатом dry-run.
    """
    first_cmd = re.sub(r"[^a-zA-Z0-9_\-\.]", "", command.strip().split()[0])
    check_cmd = (
        f"Get-Command '{first_cmd}' -ErrorAction SilentlyContinue | "
        "Select-Object -ExpandProperty Parameters | "
        "Where-Object { $_.Keys -contains 'WhatIf' }"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", check_cmd],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.stdout.strip() and "|" not in command and ";" not in command:
            whatif_cmd = f"{command} -WhatIf"
            _log(f"Dry‑run (WhatIf) для командлета: {whatif_cmd}")
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", whatif_cmd],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return {
                "dry_run": True,
                "output": proc.stdout,
                "error": proc.stderr,
                "returncode": proc.returncode,
            }
        # Безопасная проверка синтаксиса через парсер AST PowerShell без реального исполнения
        escaped_for_ps = command.replace("'", "''")
        ast_check = (
            f"$errors = $null; [void][System.Management.Automation.Language.Parser]::ParseInput('{escaped_for_ps}', [ref]$null, [ref]$errors); "
            "if ($errors) { $errors | ForEach-Object { Write-Error $_.Message }; exit 1 }"
        )
        _log(f"Синтаксическая проверка PowerShell команды: {command}")
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ast_check],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "dry_run": True,
            "output": proc.stdout,
            "error": proc.stderr,
            "returncode": proc.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "dry_run": True,
            "output": "",
            "error": f"Превышен таймаут ({timeout} с) при проверке команды PowerShell.",
            "returncode": 124,
        }


def run_safe(
    command: str,
    dry_run: bool = False,
    timeout: int = DEFAULT_COMMAND_TIMEOUT_SEC,
) -> Dict[str, Any]:
    """Выполняет команду с проверкой безопасности, поддержкой dry‑run и обязательным таймаутом.

    Args:
        command: Строка команды, которую необходимо выполнить.
        dry_run: Если ``True``, команда проверяется без реального воздействия.
        timeout: Максимальное время ожидания завершения процесса в секундах.

    Returns:
        dict: ``{"dry_run": bool, "output": str, "error": str, "returncode": int}``
    """
    if not is_command_safe(command):
        err_msg = "Команда заблокирована политикой безопасности (пустая команда или опасный паттерн)."
        _log(err_msg)
        return {
            "dry_run": dry_run,
            "output": "",
            "error": err_msg,
            "returncode": 1,
        }

    _log(f"Запуск команды: '{command}' (dry_run={dry_run})")
    if dry_run:
        if _is_powershell_cmdlet(command):
            return _dry_run_powershell(command, timeout=timeout)
        exe_name = re.sub(r"[^a-zA-Z0-9_\-\.\\/:]", "", command.strip().split()[0])
        try:
            where_proc = subprocess.run(
                ["where", exe_name],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return {
                "dry_run": True,
                "output": "",
                "error": f"Таймаут при поиске исполняемого файла '{exe_name}'.",
                "returncode": 124,
            }
        if where_proc.returncode != 0:
            return {
                "dry_run": True,
                "output": "",
                "error": f"Команда '{exe_name}' не найдена в PATH.",
                "returncode": where_proc.returncode,
            }
        _log(f"Dry‑run прошёл: исполняемый файл найден ({exe_name}).")
        return {"dry_run": True, "output": "", "error": "", "returncode": 0}

    # Реальное выполнение без опасного shell=True
    try:
        if _is_powershell_cmdlet(command) or "|" in command or ";" in command:
            args = ["powershell", "-NoProfile", "-NonInteractive", "-Command", command]
        else:
            args = shlex.split(command, posix=(os.name != "nt"))
            if not args:
                raise ValueError("Пустой список аргументов команды.")
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        result = {
            "dry_run": False,
            "output": proc.stdout,
            "error": proc.stderr,
            "returncode": proc.returncode,
        }
        if proc.returncode == 0:
            _log("Команда завершена успешно. Код возврата 0.")
        else:
            _log(f"Ошибка выполнения команды. Код: {proc.returncode}. Ошибка: {proc.stderr.strip()}")
        return result
    except subprocess.TimeoutExpired:
        err_msg = f"Превышен таймаут выполнения команды ({timeout} с)."
        _log(err_msg)
        return {"dry_run": False, "output": "", "error": err_msg, "returncode": 124}
    except Exception as exc:
        err_msg = f"Исключение при выполнении команды: {exc}"
        _log(err_msg)
        return {"dry_run": False, "output": "", "error": err_msg, "returncode": 1}


# Пример использования (можно удалить после тестов)
if __name__ == "__main__":
    test_cmd = "Stop-Service -Name TrustedInstaller -Force"
    res = run_safe(test_cmd, dry_run=True)
    _log(f"Результат dry‑run: {res}")
    # real execution (будет выполнена, будьте осторожны)
    # res_real = run_safe(test_cmd, dry_run=False)
    # _log(f"Результат реального выполнения: {res_real}")
