/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - IDE Activity Bar & Electron Navigation
 * =============================================================================
 * Description:
 *   Модуль вертикальной панели навигации в стиле стандартных IDE (Activity Bar)
 *   (VS Code / JetBrains / Cursor / Obsidian).
 *   Обеспечивает:
 *   - Вертикальную панель быстрого переключения рабочих разделов IDE слева
 *   - Индикацию и прямое взаимодействие с десктопной оболочкой Electron Shell
 *     (Node.js runtime + IPC мост `window.aiEngineBridge`)
 *   - Показ модального окна статуса Electron и Obsidian Vault
 *   - Поддержку IDE горячих клавиш (Alt+1..9, Ctrl+B, Ctrl+,)
 *   - Изолированное переключение вкладок без выезда левого меню при выборе элементов
 *
 * File: ide_navigation.js
 * Package: apps/ai_assistant/api/webgui/js
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-25 22:30:00
 * =============================================================================
 */

import { switchMainTab } from './main.js';
import { switchSidebarView, initExtensionsSidebar } from './ide_extensions_sidebar.js';

/**
 * Проверяет, запущено ли приложение внутри десктопной оболочки Electron.
 * @returns {boolean}
 */
export function isElectronRuntime() {
  if (typeof window !== 'undefined' && window.aiEngineBridge && window.aiEngineBridge.isElectron) {
    return true;
  }
  if (typeof navigator !== 'undefined' && /Electron/i.test(navigator.userAgent)) {
    return true;
  }
  return false;
}

/**
 * Закрывает левую выдвижную панель (Side Bar Offcanvas), если она открыта.
 */
export function closeSideBar() {
  const offcanvasEl = document.getElementById('leftSideNavOffcanvas');
  if (!offcanvasEl || !window.bootstrap) return;
  try {
    const oc = bootstrap.Offcanvas.getInstance(offcanvasEl);
    if (oc) {
      oc.hide();
    }
  } catch (_) {}
}

/**
 * Открывает или закрывает левую выдвижную панель (Side Bar Offcanvas).
 */
export function toggleSideBar() {
  const offcanvasEl = document.getElementById('leftSideNavOffcanvas');
  if (!offcanvasEl || !window.bootstrap) return;
  const oc = bootstrap.Offcanvas.getOrCreateInstance(offcanvasEl);
  if (offcanvasEl.classList.contains('show')) {
    oc.hide();
  } else {
    oc.show();
  }
}

/**
 * Загружает и отображает паспорт статуса оболочки Electron и Obsidian Vault в модальном окне.
 */
export async function showElectronStatusModal() {
  const modalEl = document.getElementById('electronStatusModal');
  if (!modalEl || !window.bootstrap) return;

  const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
  modal.show();

  const container = document.getElementById('electron-status-content');
  if (!container) return;

  container.innerHTML = `
    <div class="text-center py-4">
      <div class="spinner-border spinner-border-sm text-primary" role="status"></div>
      <div class="small text-muted mt-2">Опрос состояния Electron Shell и Obsidian Vault...</div>
    </div>
  `;

  let info = null;
  const isElectron = isElectronRuntime();

  // 1. Попытка получить информацию напрямую через Electron IPC
  if (isElectron && window.aiEngineBridge?.getInfo) {
    try {
      info = await window.aiEngineBridge.getInfo();
    } catch (e) {
      console.warn('[IDE Nav] IPC getInfo error:', e);
    }
  }

  // 2. Получение паспорта сервера через REST API
  let serverStatus = null;
  try {
    const res = await fetch('/api/v1/engine/status');
    if (res.ok) {
      serverStatus = await res.json();
    }
  } catch (e) {
    console.warn('[IDE Nav] Server status error:', e);
  }

  const activeEngine = isElectron ? 'Electron Desktop (Chromium + Node.js)' : 'Web Browser GUI';
  const nodeVer = info?.versions?.node || processVerSafe('node') || 'Внешний Node.js';
  const chromeVer = info?.versions?.chrome || processVerSafe('chrome') || 'Chromium';
  const electronVer = info?.versions?.electron || processVerSafe('electron') || (isElectron ? 'Active' : 'Не активен');

  container.innerHTML = `
    <div class="d-flex align-items-center gap-3 p-3 mb-3 rounded border ${isElectron ? 'bg-success-subtle border-success-subtle' : 'bg-body-secondary border-secondary-subtle'}">
      <div class="rounded-circle p-2 d-flex align-items-center justify-content-center ${isElectron ? 'bg-success text-white' : 'bg-primary text-white'}" style="width: 44px; height: 44px;">
        <i class="bi ${isElectron ? 'bi-lightning-charge-fill' : 'bi-browser-edge'} fs-4"></i>
      </div>
      <div>
        <div class="fw-bold fs-6">${activeEngine}</div>
        <div class="small text-muted">
          ${isElectron ? 'Полноценный нативный десктопный режим с поддержкой IPC и прямого доступа к Obsidian Vault' : 'Интерфейс запущен в веб-браузере. Доступен запуск в десктопной оболочке Electron'}
        </div>
      </div>
    </div>

    <div class="card border-secondary-subtle mb-3">
      <div class="card-header py-1.5 px-3 small fw-bold bg-body-tertiary d-flex align-items-center gap-2">
        <i class="bi bi-info-circle text-primary"></i>
        <span>Параметры среды выполнения</span>
      </div>
      <div class="card-body p-3 font-size-85">
        <div class="row g-2">
          <div class="col-sm-6">
            <span class="text-muted">Electron Engine:</span>
            <strong class="ms-1 ${isElectron ? 'text-success' : 'text-secondary'}">${electronVer}</strong>
          </div>
          <div class="col-sm-6">
            <span class="text-muted">Node.js Runtime:</span>
            <strong class="ms-1">${nodeVer}</strong>
          </div>
          <div class="col-sm-6">
            <span class="text-muted">Chromium:</span>
            <strong class="ms-1">${chromeVer}</strong>
          </div>
          <div class="col-sm-6">
            <span class="text-muted">Приоритет движка:</span>
            <strong class="ms-1 text-primary">${serverStatus?.preferred_engine || 'electron'}</strong>
          </div>
        </div>
      </div>
    </div>

    <div class="card border-secondary-subtle mb-3">
      <div class="card-header py-1.5 px-3 small fw-bold bg-body-tertiary d-flex align-items-center gap-2">
        <i class="bi bi-journal-code text-success"></i>
        <span>Интеграция с Obsidian Vault</span>
      </div>
      <div class="card-body p-3 font-size-85">
        <p class="text-muted mb-2">
          Каждое рабочее пространство автоматически хранит Markdown-документы в стандарте Obsidian Vault с YAML-метаданными и графом [[wikilinks]].
        </p>
        <div class="d-flex flex-wrap gap-2">
          <button class="btn btn-sm btn-outline-success d-flex align-items-center gap-1.5" id="btn-ide-open-obsidian" type="button">
            <i class="bi bi-box-arrow-up-right"></i>
            <span>Открыть в Obsidian</span>
          </button>
          <button class="btn btn-sm btn-outline-secondary d-flex align-items-center gap-1.5" id="btn-ide-open-folder" type="button">
            <i class="bi bi-folder2-open"></i>
            <span>Открыть папку в проводнике</span>
          </button>
        </div>
      </div>
    </div>

    ${!isElectron ? `
      <div class="alert alert-info py-2 px-3 small mb-0 d-flex align-items-center gap-2">
        <i class="bi bi-terminal fs-5"></i>
        <div>
          <strong>Запуск приложения как Electron:</strong>
          <code class="d-block mt-0.5 user-select-all">py -m apps.ai_assistant.main --engine electron</code>
        </div>
      </div>
    ` : ''}
  `;

  // Привязка обработчиков открытия Obsidian
  const openObsBtn = document.getElementById('btn-ide-open-obsidian');
  if (openObsBtn) {
    openObsBtn.addEventListener('click', async () => {
      const activeWs = (typeof window.getActiveWorkspaceId === 'function')
        ? window.getActiveWorkspaceId()
        : 'default';
      try {
        const res = await fetch(`/api/v1/workspaces/${encodeURIComponent(activeWs)}/obsidian/open`, { method: 'POST' });
        const data = await res.json();
        if (data.status === 'ok') {
          if (window.showToast) window.showToast('Запущен протокол Obsidian Vault', 'success');
        } else {
          if (window.showToast) window.showToast(data.message || 'Ошибка запуска Obsidian', 'warning');
        }
      } catch (err) {
        if (window.showToast) window.showToast('Не удалось вызвать запуск Obsidian: ' + err.message, 'danger');
      }
    });
  }

  const openFolderBtn = document.getElementById('btn-ide-open-folder');
  if (openFolderBtn) {
    openFolderBtn.addEventListener('click', async () => {
      const activeWs = (typeof window.getActiveWorkspaceId === 'function')
        ? window.getActiveWorkspaceId()
        : 'default';
      try {
        const res = await fetch(`/api/v1/workspaces/${encodeURIComponent(activeWs)}/open-folder`, { credentials: 'same-origin' });
        const data = await res.json();
        if (data.status === 'success') {
          if (window.showToast) window.showToast('Папка открыта в проводнике', 'info');
        }
      } catch (_) {}
    });
  }
}

/**
 * Безопасное чтение версий из process.versions, если доступно.
 * @param {string} key 
 * @returns {string|null}
 */
function processVerSafe(key) {
  try {
    return window.process?.versions?.[key] || null;
  } catch (_) {
    return null;
  }
}

/**
 * Регистрация глобальных горячих клавиш в стиле стандартных IDE.
 */
function setupIdeKeyboardShortcuts() {
  document.addEventListener('keydown', (e) => {
    // Не перехватываем ввод в текстовых полях
    const targetTag = (e.target.tagName || '').toLowerCase();
    if (targetTag === 'input' || targetTag === 'textarea' || e.target.isContentEditable) {
      return;
    }

    // Ctrl+B или Alt+B: Свернуть/развернуть боковое меню (Side Bar)
    if ((e.ctrlKey && e.key.toLowerCase() === 'b') || (e.altKey && e.key.toLowerCase() === 'b')) {
      e.preventDefault();
      toggleSideBar();
      return;
    }

    // Ctrl+,: Открыть параметры / настройки
    if (e.ctrlKey && e.key === ',') {
      e.preventDefault();
      const settingsModalEl = document.getElementById('userSettingsModal');
      if (settingsModalEl && window.bootstrap) {
        bootstrap.Modal.getOrCreateInstance(settingsModalEl).show();
      }
      return;
    }

    // Alt+1 .. Alt+9: Быстрый переход по вкладкам инструментов IDE (меню не открывается)
    if (e.altKey && !e.ctrlKey && !e.metaKey) {
      const shortcutMap = {
        '1': 'tab-workspace',
        '2': 'tab-commits',
        '3': 'tab-diff',
        '4': 'tab-timeline',
        '5': 'tab-wikillm',
        '6': 'tab-graph',
        '7': 'tab-models',
        '8': 'tab-rag',
        '9': 'tab-verification',
      };
      const targetTab = shortcutMap[e.key];
      if (targetTab) {
        e.preventDefault();
        closeSideBar();
        switchMainTab(targetTab);
      }
    }
  });
}

/**
 * Инициализирует вертикальную панель навигации в стиле стандартных IDE (Activity Bar).
 */
export function initIdeNavigation() {
  const activityBar = document.getElementById('ide-activity-bar');
  if (!activityBar) return;

  const isElectron = isElectronRuntime();
  if (isElectron) {
    document.documentElement.classList.add('is-electron');
    document.body.classList.add('is-electron');
  }

  // 1. Настройка индикатора Electron в Activity Bar
  const electronBtn = document.getElementById('ide-nav-electron-btn');
  if (electronBtn) {
    const dot = electronBtn.querySelector('.ide-status-dot');
    if (isElectron) {
      electronBtn.classList.add('text-success');
      electronBtn.setAttribute('title', 'Electron Shell Active (Node.js + Chromium + Obsidian IPC) — Нажмите для подробностей');
      if (dot) dot.classList.add('bg-success');
    } else {
      electronBtn.classList.add('text-muted');
      electronBtn.setAttribute('title', 'Web GUI Mode (Electron Shell Ready) — Нажмите для справки о запуске');
      if (dot) dot.classList.add('bg-secondary');
    }
    electronBtn.addEventListener('click', (e) => {
      e.preventDefault();
      showElectronStatusModal();
    });
  }

  // 2. Обработка клика по верхней кнопке Side Bar в Activity Bar (ЕДИНСТВЕННЫЙ способ открыть меню с панели)
  const toggleBtn = document.getElementById('ide-nav-toggle-sidebar');
  if (toggleBtn) {
    toggleBtn.addEventListener('click', (e) => {
      e.preventDefault();
      toggleSideBar();
    });
  }

  // 3. Обработка кликов по элементам инструментов Activity Bar:
  // При клике на инструмент меню НЕ выезжает, а наоборот гарантированно скрывается!
  activityBar.querySelectorAll('.ide-activity-item[data-tab]').forEach((item) => {
    item.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      const tabId = item.dataset.tab;
      if (!tabId) return;

      // Гарантированно закрываем боковое выезжающее меню при выборе инструмента
      closeSideBar();

      // Переключение представления боковой панели в зависимости от инструмента (VS Code Side Bar Views)
      if (tabId === 'tab-plugins') {
        switchSidebarView('extensions');
      } else if (tabId === 'tab-workspace') {
        switchSidebarView('explorer');
      }

      switchMainTab(tabId);
    });
  });

  // 4. Служебные кнопки в нижней части Activity Bar
  const settingsBtn = document.getElementById('ide-nav-settings');
  if (settingsBtn) {
    settingsBtn.addEventListener('click', (e) => {
      e.preventDefault();
      closeSideBar();
      const settingsModalEl = document.getElementById('userSettingsModal');
      if (settingsModalEl && window.bootstrap) {
        bootstrap.Modal.getOrCreateInstance(settingsModalEl).show();
      }
    });
  }

  const themeBtn = document.getElementById('ide-nav-theme-btn');
  if (themeBtn) {
    themeBtn.addEventListener('click', (e) => {
      e.preventDefault();
      closeSideBar();
      const userSettingsModal = document.getElementById('userSettingsModal');
      if (userSettingsModal && typeof bootstrap !== 'undefined' && bootstrap.Modal) {
        bootstrap.Modal.getOrCreateInstance(userSettingsModal).show();
      }
    });
  }

  const tourBtn = document.getElementById('ide-nav-tour-btn');
  if (tourBtn) {
    tourBtn.addEventListener('click', (e) => {
      e.preventDefault();
      closeSideBar();
      const mainTourBtn = document.getElementById('btn-start-system-tour');
      if (mainTourBtn) {
        mainTourBtn.click();
      }
    });
  }

  // 5. Инициализация боковой панели расширений
  initExtensionsSidebar();

  // 6. Инициализация IDE клавиатурных комбинаций
  setupIdeKeyboardShortcuts();
}
