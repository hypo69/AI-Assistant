<#
=============================================================================
Process Name: AI-Windows-Admin Launcher - Assist
=============================================================================
Description:
  Быстрый лончер микросервиса AI Assistant.
  Перед запуском основного приложения поднимает отдельное окно консоли
  с Docker-окружением Paperless-ngx (запуск контейнеров и стриминг логов).
  Вся прикладная логика (проверка портов, запуск веб-сервера, UI-движков,
  управление процессами и CLI-команды) инкапсулирована внутри Python-модуля
  apps.ai_assistant.

Usage Examples:
  .\assist.ps1
  .\assist.ps1 --engine electron
  .\assist.ps1 -c            # Подключиться к запущенному процессору и открыть GUI
  .\assist.ps1 -r            # Перезапустить: завершить процесс на порту и поднять новый
  .\assist.ps1 -NoPaperless  # Запуск без открытия отдельного окна Paperless
  .\assist.ps1 serve --connect
  .\assist.ps1 serve --restart
  .\assist.ps1 status
  .\assist.ps1 query "Когда был последний коммит?"

File: assist.ps1
Project: ai-windows-admin
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-11-11 19:45:00
=============================================================================
#>

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Добавление пути к Docker Desktop в PATH при необходимости
$dockerCmd = Get-Command "docker" -ErrorAction SilentlyContinue
$dockerPath = if ($dockerCmd) { $dockerCmd.Source } else { $null }
if (-not $dockerPath) {
    $fallbackDockerDir = Join-Path $env:ProgramFiles "Docker\Docker\resources\bin"
    if (Test-Path (Join-Path $fallbackDockerDir "docker.exe")) {
        $env:PATH = "$fallbackDockerDir;$env:PATH"
    }
}

# Функция запуска отдельного окна консоли с Paperless в Docker
function Start-PaperlessConsoleWindow {
    param (
        [string]$ProjectRoot
    )
    $paperlessDir = Join-Path $ProjectRoot "paperless-ngx\runtime"
    if (-not (Test-Path $paperlessDir)) {
        $altDir = Join-Path $ProjectRoot "paperless-ngx\docker\compose"
        if (Test-Path $altDir) {
            $paperlessDir = $altDir
        }
    }

    $paperlessScript = @"
`$host.UI.RawUI.WindowTitle = 'Paperless-ngx (Docker)'
Write-Host '============================================================' -ForegroundColor Cyan
Write-Host '  Paperless-ngx Docker Console' -ForegroundColor Cyan
Write-Host '============================================================' -ForegroundColor Cyan

if (-not (Get-Command 'docker' -ErrorAction SilentlyContinue)) {
    `$fallback = Join-Path `$env:ProgramFiles 'Docker\Docker\resources\bin'
    if (Test-Path (Join-Path `$fallback 'docker.exe')) {
        `$env:PATH = "`$fallback;`$env:PATH"
    }
}

`$running = docker ps --filter "name=paperless" --format "{{.Names}}" 2>`$null
if (`$running) {
    Write-Host '[INFO] Обнаружены работающие контейнеры Paperless-ngx:' -ForegroundColor Green
    `$running | ForEach-Object { Write-Host "  - `$_" -ForegroundColor DarkCyan }
    `$web = (`$running | Where-Object { `$_ -match 'webserver' } | Select-Object -First 1)
    if (-not `$web) { `$web = `$running | Select-Object -First 1 }
    Write-Host "[INFO] Подключение к логам контейнера `$web (Ctrl+C для выхода к консоли)..." -ForegroundColor Yellow
    docker logs -f --tail 50 `$web
} else {
    Write-Host '[INFO] Запуск стека Paperless-ngx через Docker Compose...' -ForegroundColor Yellow
    Set-Location '$paperlessDir'
    docker compose up -d
    Write-Host '[INFO] Контейнеры запущены. Вывод логов (Ctrl+C для выхода к консоли)...' -ForegroundColor Green
    docker compose logs -f --tail 50
}
"@

    Start-Process powershell.exe -ArgumentList "-NoExit", "-NoProfile", "-Command", $paperlessScript
}

# Обработка аргументов командной строки
$skipPaperless = $false
$filteredArgs = @()

foreach ($arg in $Args) {
    if ($arg -eq "-NoPaperless" -or $arg -eq "--no-paperless") {
        $skipPaperless = $true
    } else {
        $filteredArgs += $arg
    }
}

# Проверка: является ли запуск разовой CLI-командой
$cliOnlyCommands = @("query", "commits", "index", "status", "-h", "--help", "/?")
$isCliOnly = $false
if ($filteredArgs.Count -gt 0 -and $cliOnlyCommands -contains $filteredArgs[0]) {
    $isCliOnly = $true
}

# Запуск консоли Paperless для серверных/GUI сценариев (только если Docker daemon запущен)
if (-not $skipPaperless -and -not $isCliOnly) {
    $dockerReady = $false
    if (Get-Command "docker" -ErrorAction SilentlyContinue) {
        docker info --format '{{.ServerVersion}}' *> $null
        $dockerReady = ($LASTEXITCODE -eq 0)
    }
    if ($dockerReady) {
        Start-PaperlessConsoleWindow -ProjectRoot $scriptDir
        $env:AI_ASSISTANT_PAPERLESS_WINDOW_LAUNCHED = "1"
    } else {
        Write-Host "[INFO] Docker Desktop не запущен — консоль Paperless-ngx пропущена." -ForegroundColor Yellow
    }
}

# Активация виртуального окружения
$venvActivate = Join-Path $scriptDir "venv\Scripts\Activate.ps1"
if (Test-Path $venvActivate) {
    . $venvActivate
}

# Запуск основного модуля AI Assistant
python -m apps.ai_assistant @filteredArgs
