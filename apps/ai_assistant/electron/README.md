# ⚡ Electron Shell — Десктопная оболочка AI Assistant и Obsidian Vault

**Статус:** ✅ Активно  
**Пакет:** `apps.ai_assistant.electron`  
**Автор:** hypo69  
**Updated:** 2026-10-28 17:18:00  

---

## 📋 Обзор и Назначение

Модуль представляет собой автономную высокопроизводительную десктопную оболочку на базе **Electron (Chromium + Node.js runtime)** для комплексного интерфейса **AI Assistant**.

Оболочка решает ключевые инженерные задачи:
1. **Нативная изоляция данных:** Полный отказ от сохранения временных файлов и кэша в системном каталоге `%APPDATA%`. Все данные браузера, кэш, профили пользователей и рабочие пространства хранятся строго в локальном каталоге `data/` в корне проекта.
2. **Интеграция с Git-репозиториями:** Автоматическое обнаружение, сканирование и отображение активных рабочих пространств с ветками Git через нативное системное меню и верхний селектор.
3. **Бесшовная работа с Obsidian Vault:** Прямое взаимодействие с файловой системой локальных заметок, протоколом `obsidian://` и двусторонней синхронизацией базы знаний.
4. **Контракт Engine Adapter API:** Поддержка единого интерфейса переключения между легковесным Windows WebView2 и полнофункциональным Electron с безопасным IPC-мостом `window.aiEngineBridge`.

---

## 🏗️ Архитектура хранения данных

Согласно стандартам проекта, десктопная оболочка не загрязняет системные директории ОС Windows (`%APPDATA%\Roaming\ai-assistant-electron-shell`). Все пути разрешаются относительно корня репозитория `AI-Assistant/data/`:

```
AI-Assistant/
├── data/
│   ├── chromium/
│   │   ├── profiles/       <-- app.getPath('userData'): LocalStorage, IndexedDB, Cookies, Preferences
│   │   └── cache/          <-- --disk-cache-dir: дисковый кэш HTTP, скриптов V8 и шейдеров
│   ├── workspaces/         <-- Рабочие пространства с индивидуальными .git репозиториями
│   │   ├── <workspace_id>/
│   │   │   ├── .git/
│   │   │   └── _Knowledge_Base.md
│   └── electron_state.json <-- Состояние последнего активного рабочего пространства
```

### Механизм переопределения путей

При инициализации процесса в `main.js` вызываются:
- `app.setPath('userData', ...)` — перенаправляет пользовательский профиль браузера в `data/chromium/profiles`.
- `app.commandLine.appendSwitch('disk-cache-dir', ...)` — фиксирует кэш в `data/chromium/cache`.

Если запуск происходит через Python (`apps.ai_assistant.main` / `ElectronEngineAdapter`), пути автоматически передаются через переменные окружения `AI_ASSISTANT_CHROMIUM_PROFILE` и `AI_ASSISTANT_CHROMIUM_CACHE` с аргументами `--user-data-dir` и `--disk-cache-dir`. При прямом запуске через `npm start` срабатывает автоматический fallback на корневую директорию проекта.

---

## 📂 Структура файлов модуля

| Файл | Назначение |
|---|---|
| `package.json` | Манифест пакета, зависимости Electron и скрипты запуска (`npm start`). |
| `main.js` | Главный процесс Electron: управление жизненным циклом окон, треем, нативным меню, безопасным IPC и маршрутизацией. |
| `preload.js` | Изолированный мост `contextBridge` (`window.aiEngineBridge`) для предоставления API браузерному WebGUI без включения `nodeIntegration`. |
| `README.md` | Инженерная документация архитектуры, протоколов и правил запуска модуля. |

---

## 🔌 IPC-контракт (Engine Adapter API)

Связь между фронтендом WebGUI и средой Node.js реализована через строгую изоляцию контекста (`contextIsolation: true`, `nodeIntegration: false`).

Объект `window.aiEngineBridge` в веб-интерфейсе предоставляет методы:

### Управление рабочими пространствами
- `listGitWorkspaces()` — возвращает список рабочих пространств с ветками Git, метаданными и путями.
- `setActiveWorkspace(workspaceId, repoPath)` — активирует выбранное пространство, обновляет меню и сохраняет состояние.
- `getActiveWorkspace()` — возвращает идентификатор текущего активного пространства.
- `onWorkspaceSwitched(callback)` — подписка на событие смены пространства из нативного меню Electron.
- `onWorkspaceListUpdated(callback)` — подписка на событие изменения состава репозиториев.

### Интеграция с Obsidian
- `openObsidianVault(vaultPath, noteName)` — открывает хранилище через зарегистрированный обработчик протокола `obsidian://open?path=...`.
- `openVaultFolder(vaultPath)` — открывает папку хранилища в Проводнике Windows (`shell.openPath`).
- `readMarkdownNote(filePath)` / `writeMarkdownNote(filePath, content)` — прямое атомарное чтение и запись Markdown-файлов заметок.

---

## 🧭 Маршрутизация URL рабочих пространств

Оболочка строго соблюдает стандарт канонической маршрутизации проекта:
`#tab-workspace#panel-files#workspace=<workspace_id>`

При запуске окна Electron:
1. Проверяется переданный аргумент окружения `AI_ASSISTANT_ACTIVE_WORKSPACE`.
2. Если аргумент отсутствует — анализируется хэш URL бэкенда (`BACKEND_URL`).
3. Если URL не содержит идентификатора — считывается `data/electron_state.json`.
4. При первом запуске выбирается первое доступное пространство из `data/workspaces`.

---

## ⚙️ Переменные окружения

| Переменная | Описание | По умолчанию |
|---|---|---|
| `AI_ASSISTANT_BACKEND_URL` | Базовый адрес FastAPI бэкенда | `http://127.0.0.1:8002` |
| `AI_ASSISTANT_CHROMIUM_PROFILE` | Абсолютный путь к каталогу профиля браузера | `<root>/data/chromium/profiles` |
| `AI_ASSISTANT_CHROMIUM_CACHE` | Абсолютный путь к каталогу дискового кэша | `<root>/data/chromium/cache` |
| `AI_ASSISTANT_WORKSPACES_DIR` | Каталог с Git-репозиториями рабочих пространств | `<root>/data/workspaces` |
| `AI_ASSISTANT_ACTIVE_WORKSPACE` | Идентификатор принудительно активируемого пространства | `""` (из состояния) |

> [!NOTE]
> При запуске из среды IDE (VS Code, Antigravity) переменная `ELECTRON_RUN_AS_NODE` автоматически удаляется адаптером `ElectronEngineAdapter`, предотвращая сбой инициализации графического окна Electron.

---

## 🚀 Запуск и Отладка

### 1. Штатный запуск через инфраструктуру Python (Рекомендуется)
```powershell
# Запуск ассистента с графической оболочкой Electron
py -m apps.ai_assistant.main --engine electron

# Или через управляющий скрипт
.\assist.ps1
```

### 2. Автономный запуск Electron для отладки фронтенда
```powershell
cd apps/ai_assistant/electron
npm install
npm start
```

### 3. Запуск тестов подсистемы Electron и путей хранения
```powershell
py -m pytest apps/ai_assistant/tests/test_chromium_storage_paths.py apps/ai_assistant/tests/test_obsidian_electron_architecture.py -v
```
