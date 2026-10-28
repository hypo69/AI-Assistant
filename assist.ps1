<#
=============================================================================
Process Name: AI-Windows-Admin Launcher - Assist
=============================================================================
Description:
  Быстрый лончер микросервиса AI Assistant.
  Вся прикладная логика (проверка портов, запуск веб-сервера, UI-движков,
  управление процессами и CLI-команды) инкапсулирована внутри Python-модуля
  apps.ai_assistant.

Usage Examples:
  .\assist.ps1
  .\assist.ps1 -c            # Подключиться к запущенному процессору и открыть GUI
  .\assist.ps1 -r            # Перезапустить: завершить процесс на порту и поднять новый
  .\assist.ps1 serve --connect
  .\assist.ps1 serve --restart
  .\assist.ps1 status
  .\assist.ps1 query "Когда был последний коммит?"

File: assist.ps1
Project: ai-windows-admin
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-10-25 19:40:00
=============================================================================
#>

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvActivate = Join-Path $scriptDir "venv\Scripts\Activate.ps1"
if (Test-Path $venvActivate) {
    . $venvActivate
}

python -m apps.ai_assistant @Args
