/**
 * =============================================================================
 * Process Name: AI Assistant Electron Shell - Main Process
 * =============================================================================
 * Description:
 *   Главный процесс десктопной оболочки Electron (Chromium + Node.js runtime).
 *   Обеспечивает:
 *   - Запуск окна Chromium с каноническим URL (#tab-workspace#panel-files#workspace=<id>)
 *   - Верхнее нативное меню с раскрывающимся списком рабочих пространств с Git
 *   - Сканирование корневой директории с Git-репозиториями рабочих пространств (data)
 *   - Сохранение и восстановление выбранного рабочего пространства (data/electron_state.json)
 *   - Двустороннюю синхронизацию выбора пространства с верхним раскрывающимся списком
 *   - Сворачивание окна в системный трей при нажатии кнопки закрытия
 *   - Прямой доступ к файловой системе компактного Obsidian Vault и протоколу obsidian://
 *
 * File: main.js
 * Package: apps/ai_assistant/electron
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-28 20:38:00
 * =============================================================================
 */

const { app, BrowserWindow, ipcMain, shell, Tray, Menu } = require('electron');
const path = require('path');
const fs = require('fs');

// Корень проекта: apps/ai_assistant/electron -> 3 уровня вверх до корня AI-Assistant
const PROJECT_ROOT_DIR = path.resolve(__dirname, '..', '..', '..');
const ROOT_DATA_DIR = path.resolve(PROJECT_ROOT_DIR, 'data');

// Настройка путей пользовательского профиля и кэша Chromium строго в корневой директории data/.
// Предотвращает нежелательное создание системного каталога %APPDATA%\Roaming\ai-assistant-electron-shell.
const defaultProfileDir = path.resolve(ROOT_DATA_DIR, 'chromium', 'profiles');
const defaultCacheDir = path.resolve(ROOT_DATA_DIR, 'chromium', 'cache');

const chromiumProfileDir = process.env.AI_ASSISTANT_CHROMIUM_PROFILE || defaultProfileDir;
const chromiumCacheDir = process.env.AI_ASSISTANT_CHROMIUM_CACHE || defaultCacheDir;

try {
  app.setPath('userData', path.resolve(chromiumProfileDir));
} catch (err) {
  console.warn('[Electron] Ошибка установки пути userData:', err);
}
try {
  app.commandLine.appendSwitch('disk-cache-dir', path.resolve(chromiumCacheDir));
} catch (err) {
  console.warn('[Electron] Ошибка установки ключа disk-cache-dir:', err);
}

const BACKEND_URL = process.env.AI_ASSISTANT_BACKEND_URL || 'http://127.0.0.1:8002';
let mainWindow = null;
let tray = null;
let isQuitting = false;
let currentActiveWorkspaceId = '';

/**
 * Возвращает абсолютный путь к каталогу рабочих пространств.
 * @returns {string}
 */
function getWorkspacesDir() {
  if (process.env.AI_ASSISTANT_WORKSPACES_DIR) {
    return path.resolve(process.env.AI_ASSISTANT_WORKSPACES_DIR);
  }
  const wsSubDir = path.resolve(ROOT_DATA_DIR, 'workspaces');
  if (fs.existsSync(wsSubDir)) {
    return wsSubDir;
  }
  return path.resolve(ROOT_DATA_DIR);
}

/**
 * Возвращает путь к файлу сохранённого состояния оболочки Electron.
 * @returns {string}
 */
function getStateFilePath() {
  return path.resolve(ROOT_DATA_DIR, 'electron_state.json');
}

/**
 * Читает сохранённый идентификатор активного рабочего пространства из файла состояния.
 * @returns {string}
 */
function loadSavedWorkspaceId() {
  try {
    const file = getStateFilePath();
    if (fs.existsSync(file)) {
      const data = JSON.parse(fs.readFileSync(file, 'utf-8'));
      if (data && data.active_workspace_id) {
        return String(data.active_workspace_id).trim();
      }
    }
  } catch (err) {
    console.warn('[Electron] Ошибка чтения electron_state.json:', err);
  }
  return '';
}

/**
 * Сохраняет идентификатор активного рабочего пространства в файл состояния.
 * @param {string} wsId 
 */
function saveActiveWorkspaceId(wsId) {
  if (!wsId) return;
  try {
    const file = getStateFilePath();
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(
      file,
      JSON.stringify({ active_workspace_id: wsId, updated_at: new Date().toISOString() }, null, 2),
      'utf-8'
    );
  } catch (err) {
    console.warn('[Electron] Ошибка записи electron_state.json:', err);
  }

  // Синхронизация с config.json модуля ai_assistant
  try {
    const appCfgPath = path.resolve(PROJECT_ROOT_DIR, 'apps', 'ai_assistant', 'config.json');
    if (fs.existsSync(appCfgPath)) {
      const cfg = JSON.parse(fs.readFileSync(appCfgPath, 'utf-8'));
      cfg.active_workspace = wsId;
      cfg.last_active_workspace = wsId;
      fs.writeFileSync(appCfgPath, JSON.stringify(cfg, null, 2), 'utf-8');
    }
  } catch (_) {}
}

/**
 * Определяет первичное активное рабочее пространство из env, URL, файла состояния или первого доступного.
 * @param {Array<Object>} gitWorkspaces 
 * @returns {string}
 */
function resolveInitialActiveWorkspace(gitWorkspaces) {
  if (process.env.AI_ASSISTANT_ACTIVE_WORKSPACE) {
    const fromEnv = process.env.AI_ASSISTANT_ACTIVE_WORKSPACE.trim();
    if (gitWorkspaces.some((w) => w.workspace_id === fromEnv)) {
      return fromEnv;
    }
  }

  const urlMatch = BACKEND_URL.match(/workspace=([^&#]+)/i);
  if (urlMatch && urlMatch[1]) {
    try {
      const fromUrl = decodeURIComponent(urlMatch[1]).trim();
      if (gitWorkspaces.some((w) => w.workspace_id === fromUrl)) {
        return fromUrl;
      }
    } catch (_) {}
  }

  // Считываем сохранённое пространство из apps/ai_assistant/config.json
  try {
    const appCfgPath = path.resolve(PROJECT_ROOT_DIR, 'apps', 'ai_assistant', 'config.json');
    if (fs.existsSync(appCfgPath)) {
      const cfg = JSON.parse(fs.readFileSync(appCfgPath, 'utf-8'));
      const activeWs = cfg.active_workspace || cfg.last_active_workspace;
      if (activeWs && gitWorkspaces.some((w) => w.workspace_id === activeWs)) {
        return activeWs;
      }
    }
  } catch (_) {}

  const saved = loadSavedWorkspaceId();
  if (saved && gitWorkspaces.some((w) => w.workspace_id === saved)) {
    return saved;
  }

  return gitWorkspaces.length > 0 ? gitWorkspaces[0].workspace_id : '';
}

/**
 * Сканирует каталог и возвращает список рабочих пространств, основываясь на тех,
 * что реально содержат инициализированную директорию .git.
 * @returns {Array<Object>}
 */
function scanGitWorkspaces() {
  const SYSTEM_DATA_DIRS = new Set([
  'ai_assistant', 'chromium', 'rag', 'rag_index', 'telegram_rag',
  'users', 'windows_wikillm', 'workspaces', 'cache', 'logs', 'temp', 'tmp'
]);

  const wsDir = getWorkspacesDir();
  if (!fs.existsSync(wsDir)) {
    return [];
  }

  const entries = fs.readdirSync(wsDir, { withFileTypes: true });
  const results = [];

  for (const entry of entries) {
    if (!entry.isDirectory() || entry.name.startsWith('.') || entry.name.startsWith('~') || SYSTEM_DATA_DIRS.has(entry.name.toLowerCase())) {
      continue;
    }

    const wsPath = path.join(wsDir, entry.name);
    const gitDir = path.join(wsPath, '.git');
    if (!fs.existsSync(gitDir)) {
      continue;
    }

    let name = entry.name;
    let description = '';

    const cfgFile = path.join(wsPath, '.workspace', 'config.json');
    if (fs.existsSync(cfgFile)) {
      try {
        const cfg = JSON.parse(fs.readFileSync(cfgFile, 'utf-8'));
        if (cfg.name) name = cfg.name;
        if (cfg.description) description = cfg.description;
      } catch (_) {}
    }

    let branch = 'master';
    try {
      const headFile = path.join(gitDir, 'HEAD');
      if (fs.existsSync(headFile)) {
        const headContent = fs.readFileSync(headFile, 'utf-8').trim();
        if (headContent.startsWith('ref: refs/heads/')) {
          branch = headContent.replace('ref: refs/heads/', '');
        }
      }
    } catch (_) {}

    results.push({
      workspace_id: entry.name,
      name,
      description,
      path: wsPath.replace(/\\/g, '/'),
      branch,
      has_git: true,
    });
  }

  return results.sort((a, b) => a.workspace_id.localeCompare(b.workspace_id));
}

/**
 * Создаёт или обновляет верхнее нативное меню приложения со списком рабочих пространств с Git.
 * @param {string|null} selectedWsId 
 */
function updateApplicationMenu(selectedWsId = null) {
  const gitWorkspaces = scanGitWorkspaces();

  if (selectedWsId) {
    currentActiveWorkspaceId = selectedWsId;
    saveActiveWorkspaceId(selectedWsId);
  } else if (!currentActiveWorkspaceId) {
    currentActiveWorkspaceId = resolveInitialActiveWorkspace(gitWorkspaces);
    if (currentActiveWorkspaceId) {
      saveActiveWorkspaceId(currentActiveWorkspaceId);
    }
  }

  const workspaceMenuItems = gitWorkspaces.length > 0
    ? gitWorkspaces.map((ws) => ({
        label: `${ws.name} [git: ${ws.branch}]`,
        type: 'radio',
        checked: ws.workspace_id === currentActiveWorkspaceId,
        click: () => {
          currentActiveWorkspaceId = ws.workspace_id;
          saveActiveWorkspaceId(ws.workspace_id);
          if (mainWindow) {
            mainWindow.webContents.send('workspace:switched', {
              workspaceId: ws.workspace_id,
              repoPath: ws.path,
            });
          }
        },
      }))
    : [{ label: 'Нет рабочих пространств с Git', enabled: false }];

  const template = [
    {
      label: 'Рабочее пространство',
      submenu: [
        ...workspaceMenuItems,
        { type: 'separator' },
        {
          label: '📁 Открыть папку репозиториев Git...',
          click: async () => {
            await shell.openPath(getWorkspacesDir());
          },
        },
        {
          label: '🔄 Обновить список репозиториев',
          click: () => {
            updateApplicationMenu(currentActiveWorkspaceId);
            if (mainWindow) {
              mainWindow.webContents.send('workspace:list-updated');
            }
          },
        },
      ],
    },
    {
      label: 'Вид',
      submenu: [
        { role: 'reload', label: 'Перезагрузить' },
        { role: 'forceReload', label: 'Принудительная перезагрузка' },
        { role: 'toggleDevTools', label: 'Инструменты разработчика (DevTools)' },
        { type: 'separator' },
        { role: 'resetZoom', label: 'Масштаб по умолчанию' },
        { role: 'zoomIn', label: 'Увеличить' },
        { role: 'zoomOut', label: 'Уменьшить' },
        { type: 'separator' },
        { role: 'togglefullscreen', label: 'Полноэкранный режим' },
      ],
    },
    {
      label: 'Окно',
      submenu: [
        { role: 'minimize', label: 'Свернуть' },
        {
          label: 'Свернуть в системный трей',
          accelerator: 'CmdOrCtrl+W',
          click: () => {
            if (mainWindow) {
              mainWindow.hide();
            }
          },
        },
        { type: 'separator' },
        {
          label: 'Выход из AI Assistant',
          accelerator: 'CmdOrCtrl+Q',
          click: () => {
            isQuitting = true;
            app.quit();
          },
        },
      ],
    },
  ];

  const appMenu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(appMenu);
}

/**
 * Отображает окно приложения, восстанавливает его из минимизированного состояния,
 * разворачивает на весь экран и передаёт ему фокус ввода.
 */
function showMainWindow() {
  if (!mainWindow) {
    createWindow();
    return;
  }
  if (mainWindow.isMinimized()) {
    mainWindow.restore();
  }
  if (!mainWindow.isVisible()) {
    mainWindow.show();
  }
  mainWindow.maximize();
  mainWindow.setAlwaysOnTop(true);
  mainWindow.focus();
  mainWindow.setAlwaysOnTop(false);
}

/**
 * Инициализирует и настраивает системный трей приложения Windows.
 * Добавляет иконку в панель задач, контекстное меню быстрого доступа
 * и обработчики клика для развёртывания окна.
 */
function createTray() {
  if (tray) return;

  const iconCandidates = [
    path.join(__dirname, '..', 'api', 'webgui', 'assets', 'favicon.ico'),
    path.join(__dirname, '..', 'api', 'webgui', 'assets', 'icon256.png'),
  ];
  const finalIcon = iconCandidates.find((p) => fs.existsSync(p)) || iconCandidates[0];

  try {
    tray = new Tray(finalIcon);

    const contextMenu = Menu.buildFromTemplate([
      {
        label: 'Развернуть AI Assistant (на весь экран)',
        click: () => {
          showMainWindow();
        },
      },
      { type: 'separator' },
      {
        label: 'Выход',
        click: () => {
          isQuitting = true;
          app.quit();
        },
      },
    ]);

    tray.setToolTip('AI Assistant — Десктопная оболочка');
    tray.setContextMenu(contextMenu);

    tray.on('click', () => {
      showMainWindow();
    });

    tray.on('double-click', () => {
      showMainWindow();
    });
  } catch (err) {
    console.error('[Electron] Ошибка создания системного трея:', err);
  }
}

/**
 * Создаёт главное графическое окно BrowserWindow с изоляцией контекста,
 * мостом preload.js и загрузкой канонического URL с активным пространством.
 */
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 960,
    minHeight: 640,
    title: 'AI Assistant — Obsidian Vault & Git (Electron Shell)',
    autoHideMenuBar: false,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  // Принудительно разворачиваем окно на весь экран при создании
  mainWindow.maximize();

  updateApplicationMenu();

  mainWindow.once('ready-to-show', () => {
    mainWindow.maximize();
    mainWindow.show();
    mainWindow.focus();
  });

  setTimeout(() => {
    if (mainWindow && !mainWindow.isVisible()) {
      mainWindow.maximize();
      mainWindow.show();
      mainWindow.focus();
    }
  }, 2500);

  mainWindow.webContents.on('did-fail-load', (_event, errorCode, _errorDescription, validatedURL) => {
    if (errorCode === -102 || errorCode === -105 || errorCode === -106) {
      setTimeout(() => {
        if (mainWindow) {
          mainWindow.loadURL(validatedURL);
        }
      }, 500);
    }
  });

  let targetUrl = BACKEND_URL;
  if (!targetUrl.includes('workspace=') && currentActiveWorkspaceId) {
    const base = targetUrl.split('#')[0].replace(/\/+$/, '');
    targetUrl = `${base}/#tab-workspace#panel-files#workspace=${encodeURIComponent(currentActiveWorkspaceId)}`;
  }

  mainWindow.loadURL(targetUrl);

  mainWindow.on('close', (event) => {
    if (!isQuitting) {
      event.preventDefault();
      mainWindow.hide();
      if (tray && process.platform === 'win32') {
        try {
          tray.displayBalloon({
            title: 'AI Assistant',
            content: 'Приложение свёрнуто в системный трей и продолжает работать. Кликните по значку для развёртывания на весь экран.',
          });
        } catch (_) {}
      }
      return false;
    }
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// -----------------------------------------------------------------------------
// IPC Контракт команд Engine Adapter API (Electron Main <-> Preload <-> WebGUI)
// -----------------------------------------------------------------------------

/**
 * Обработчик IPC для получения метаданных и статуса движка Electron.
 * @returns {Promise<Object>}
 */
ipcMain.handle('engine:get-info', async () => {
  return {
    engine_id: 'electron',
    versions: process.versions,
    backend_url: BACKEND_URL,
    vault_path: process.env.AI_ASSISTANT_VAULT_PATH || '',
    workspaces_dir: getWorkspacesDir(),
    active_workspace_id: currentActiveWorkspaceId,
  };
});

/**
 * Обработчик IPC для получения списка рабочих пространств с репозиториями Git.
 * @returns {Promise<Array<Object>>}
 */
ipcMain.handle('workspaces:list-git', async () => {
  return scanGitWorkspaces();
});

/**
 * Обработчик IPC для переключения активного пространства, сохранения состояния и обновления меню.
 * @param {Electron.IpcMainInvokeEvent} _event
 * @param {{ workspaceId: string, repoPath: string }} params
 * @returns {Promise<Object>}
 */
ipcMain.handle('workspaces:set-active', async (_event, { workspaceId, repoPath }) => {
  if (workspaceId) {
    currentActiveWorkspaceId = workspaceId;
    saveActiveWorkspaceId(workspaceId);
    updateApplicationMenu(workspaceId);
  }
  return { status: 'ok', workspaceId, repoPath };
});

/**
 * Обработчик IPC для чтения текущего активного идентификатора пространства.
 * @returns {Promise<string>}
 */
ipcMain.handle('workspaces:get-active', async () => {
  if (!currentActiveWorkspaceId) {
    const saved = loadSavedWorkspaceId();
    if (saved) currentActiveWorkspaceId = saved;
  }
  return currentActiveWorkspaceId;
});

/**
 * Обработчик IPC для открытия хранилища или заметки в приложении Obsidian по протоколу obsidian://.
 * @param {Electron.IpcMainInvokeEvent} _event
 * @param {{ vaultPath: string, noteName?: string }} params
 * @returns {Promise<Object>}
 */
ipcMain.handle('obsidian:open-vault', async (_event, { vaultPath, noteName }) => {
  const target = noteName ? path.join(vaultPath, noteName) : vaultPath;
  const encoded = encodeURIComponent(path.resolve(target));
  const uri = `obsidian://open?path=${encoded}`;
  await shell.openExternal(uri);
  return { status: 'ok', uri, target };
});

/**
 * Обработчик IPC для открытия папки хранилища в нативном Проводнике Windows.
 * @param {Electron.IpcMainInvokeEvent} _event
 * @param {{ vaultPath: string }} params
 * @returns {Promise<Object>}
 */
ipcMain.handle('obsidian:open-folder', async (_event, { vaultPath }) => {
  const resolved = path.resolve(vaultPath);
  const err = await shell.openPath(resolved);
  return { status: err ? 'error' : 'ok', error: err || null, path: resolved };
});

/**
 * Обработчик IPC для безопасного чтения Markdown-заметки Obsidian.
 * @param {Electron.IpcMainInvokeEvent} _event
 * @param {{ filePath: string }} params
 * @returns {Promise<Object>}
 */
ipcMain.handle('obsidian:read-note', async (_event, { filePath }) => {
  const resolved = path.resolve(filePath);
  if (!fs.existsSync(resolved)) {
    return { status: 'not_found', content: '' };
  }
  const content = fs.readFileSync(resolved, 'utf-8');
  return { status: 'ok', path: resolved, content };
});

/**
 * Обработчик IPC для атомарной записи содержимого Markdown-заметки Obsidian.
 * @param {Electron.IpcMainInvokeEvent} _event
 * @param {{ filePath: string, content: string }} params
 * @returns {Promise<Object>}
 */
ipcMain.handle('obsidian:write-note', async (_event, { filePath, content }) => {
  const resolved = path.resolve(filePath);
  fs.mkdirSync(path.dirname(resolved), { recursive: true });
  fs.writeFileSync(resolved, content, 'utf-8');
  return { status: 'ok', path: resolved };
});

const gotTheLock = app.requestSingleInstanceLock();

if (!gotTheLock) {
  // Второй экземпляр закрывается, передавая фокус первому
  app.quit();
} else {
  app.on('second-instance', () => {
    // При повторном запуске сценария assist.ps1 разворачиваем существующее окно на весь экран
    showMainWindow();
  });

  app.whenReady().then(() => {
    createWindow();
    createTray();

    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0) {
        createWindow();
      } else {
        showMainWindow();
      }
    });
  });
}

app.on('before-quit', () => {
  isQuitting = true;
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin' && isQuitting) {
    app.quit();
  }
});
