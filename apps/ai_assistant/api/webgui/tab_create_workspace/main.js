/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Tab Create Workspace Orchestrator
 * =============================================================================
 * Description:
 *   Клиентский скрипт вкладки создания нового рабочего пространства:
 *   - Создание пространства с именем, описанием и рабочей директорией (Git init)
 *   - Выбор директорий и файлов для непрерывного отслеживания изменений на месте
 *   - Объекты остаются на своих исходных местах без перемещения (copy_to_workspace = false)
 *   - Интеграция с роутером вкладок и селектором пространств.
 *
 * File: main.js
 * Package: apps/ai_assistant/api/webgui/tab_create_workspace
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-28 20:04:00
 * =============================================================================
 */

let currentCreatedWorkspaceId = '';
let currentCreatedWorkspaceName = '';

/**
 * Вспомогательный метод выполнения JSON-запросов к API.
 * @param {string} url 
 * @param {Object} options 
 * @returns {Promise<any>}
 */
async function apiFetch(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok) {
    let errMessage = `HTTP ${res.status}`;
    try {
      const data = await res.json();
      errMessage = data.detail || data.message || errMessage;
    } catch {
      // Игнорируем ошибку чтения JSON
    }
    throw new Error(errMessage);
  }
  return res.json();
}

/**
 * Отображает статусное сообщение в баннере вкладки.
 * @param {string} text 
 * @param {'success'|'danger'|'info'|'warning'} type 
 */
function showStatusBanner(text, type = 'info') {
  const banner = document.getElementById('create-ws-alert-banner');
  if (!banner) return;
  banner.className = `alert alert-${type} d-flex align-items-center gap-2 py-2 px-3 mb-3 small shadow-sm`;
  const icon = type === 'success' ? 'bi-check-circle-fill' : type === 'danger' ? 'bi-exclamation-triangle-fill' : 'bi-info-circle-fill';
  banner.innerHTML = `<i class="bi ${icon} fs-5 flex-shrink-0"></i><div>${text}</div>`;
  banner.classList.remove('d-none');
}

/**
 * Загружает и отображает список отслеживаемых на месте объектов пространства.
 * @param {string} wsId 
 */
export async function loadTrackedSources(wsId) {
  if (!wsId) return;
  const container = document.getElementById('create-ws-sources-list');
  const countBadge = document.getElementById('create-ws-tracked-count-badge');
  const gitHeadBadge = document.getElementById('create-ws-git-head-badge');

  try {
    const data = await apiFetch(`/api/v1/workspaces/${encodeURIComponent(wsId)}/sources`);
    const sources = data.sources || [];

    if (countBadge) {
      countBadge.textContent = `${sources.length} источников`;
    }

    // Загружаем актуальный Git HEAD
    try {
      const wsData = await apiFetch('/api/v1/workspaces');
      const found = (wsData.workspaces || []).find(w => w.workspace_id === wsId);
      if (found && found.git_head && gitHeadBadge) {
        gitHeadBadge.textContent = `HEAD: ${found.git_head.slice(0, 8)}`;
      }
    } catch (_) {}

    if (!container) return;

    if (sources.length === 0) {
      container.innerHTML = `
        <div class="p-3 text-center text-muted small bg-body-tertiary">
          <i class="bi bi-eye-slash text-secondary fs-4 d-block mb-1"></i>
          Директории и файлы пока не добавлены. Введите путь выше и нажмите кнопку добавления.
        </div>`;
      return;
    }

    container.innerHTML = sources.map(src => {
      const isDir = src.source_type === 'directory';
      const icon = isDir ? 'bi-folder2-open text-warning' : 'bi-file-earmark-check text-info';
      return `
        <div class="list-group-item d-flex align-items-center justify-content-between p-2 mb-1 rounded border">
          <div class="d-flex align-items-center gap-2 overflow-hidden me-2">
            <i class="bi ${icon} fs-5 flex-shrink-0"></i>
            <div class="text-truncate">
              <div class="fw-semibold text-truncate text-body">${src.display_name || src.source_path}</div>
              <div class="text-muted font-monospace small text-truncate">${src.qualified_path || src.source_path}</div>
            </div>
          </div>
          <div class="d-flex align-items-center gap-2 flex-shrink-0">
            <span class="badge bg-success-subtle text-success border font-size-75">
              <i class="bi bi-pin-angle me-1"></i>На месте (без перемещения)
            </span>
            <span class="badge bg-secondary-subtle text-secondary border font-size-75">
              ${src.item_count || 0} файлов
            </span>
            <button class="btn btn-sm btn-outline-danger py-0 px-1.5 font-size-75 btn-remove-source" data-source-id="${src.source_id}" title="Исключить из отслеживания">
              <i class="bi bi-trash3"></i>
            </button>
          </div>
        </div>
      `;
    }).join('');

    // Привязываем обработчики удаления источников
    container.querySelectorAll('.btn-remove-source').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const sid = e.currentTarget.getAttribute('data-source-id');
        if (!sid) return;
        try {
          await apiFetch(`/api/v1/workspaces/${encodeURIComponent(wsId)}/sources/${encodeURIComponent(sid)}`, {
            method: 'DELETE',
          });
          showStatusBanner('Источник исключен из наблюдения.', 'info');
          await loadTrackedSources(wsId);
        } catch (delErr) {
          showStatusBanner(`Ошибка удаления: ${delErr.message}`, 'danger');
        }
      });
    });

  } catch (err) {
    if (container) {
      container.innerHTML = `<div class="p-2 text-danger small">Ошибка загрузки источников: ${err.message}</div>`;
    }
  }
}

/**
 * Добавляет указанный путь на диске для отслеживания изменений на месте (без перемещения).
 * @param {string} targetPath 
 */
async function addTrackedItemInPlace(targetPath) {
  if (!currentCreatedWorkspaceId) {
    showStatusBanner('Сначала создайте или выберите пространство на Шаге 1.', 'warning');
    return;
  }
  const cleanPath = (targetPath || '').trim();
  if (!cleanPath) {
    showStatusBanner('Пожалуйста, укажите абсолютный путь на диске.', 'warning');
    return;
  }

  showStatusBanner(`Подключение объекта <code>${cleanPath}</code> для слежения на месте...`, 'info');

  try {
    const res = await apiFetch(`/api/v1/workspaces/${encodeURIComponent(currentCreatedWorkspaceId)}/items`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        items: [cleanPath],
        copy_to_workspace: false, // Файлы остаются на своих исходных местах!
        commit_message: `Подключение ${cleanPath} для слежения на месте (Git linked)`,
      }),
    });

    const added = res.files_added || 0;
    const commitHead = res.git_head ? res.git_head.slice(0, 8) : 'HEAD';
    showStatusBanner(`
      <strong>Объект успешно подключен к наблюдению!</strong>
      <div>Файлы остаются на исходном месте. Добавлено под контроль: ${added}. Git commit: <code>${commitHead}</code>.</div>
    `, 'success');

    await loadTrackedSources(currentCreatedWorkspaceId);
  } catch (err) {
    showStatusBanner(`Ошибка подключения пути <code>${cleanPath}</code>: ${err.message}`, 'danger');
  }
}

/**
 * Переключает интерфейс в основную рабочую область и активирует созданное пространство.
 */
async function navigateToCreatedWorkspace() {
  const targetWsId = currentCreatedWorkspaceId || 'default';

  // 1. Переключаемся на вкладку Workspace
  if (typeof window.switchTab === 'function') {
    window.switchTab('tab-workspace');
  }

  // 2. Обновляем селектор пространств на вкладке tab_workspace
  const wsSelector = document.getElementById('ws-selector');
  if (wsSelector) {
    try {
      const data = await apiFetch('/api/v1/workspaces');
      const list = data.workspaces || [];
      wsSelector.innerHTML = list.map(ws => `
        <option value="${ws.workspace_id}" ${ws.workspace_id === targetWsId ? 'selected' : ''}>
          ${ws.name} [${ws.workspace_id}] — док: ${ws.documents_count || 0}, фактов: ${ws.active_facts_count || 0}
        </option>
      `).join('');
      wsSelector.value = targetWsId;
      wsSelector.dispatchEvent(new Event('change'));
    } catch (err) {
      console.warn('[CreateWorkspaceTab] Ошибка обновления списка пространств:', err);
    }
  }
}

/**
 * Главная инициализация вкладки «Создать новое пространство».
 */
export function initCreateWorkspaceTab() {
  const submitBtn = document.getElementById('btn-create-ws-submit');
  const nameInput = document.getElementById('create-ws-name-input');
  const langSelect = document.getElementById('create-ws-lang-select');
  const pathInput = document.getElementById('create-ws-path-input');
  const descInput = document.getElementById('create-ws-desc-input');

  if (langSelect) {
    const curLang = (typeof window !== 'undefined' && window.i18n?.lang) || localStorage.getItem('app_language') || 'ru';
    const cleanCur = curLang.toLowerCase().slice(0, 2);
    if (['he', 'ru', 'en', 'uk'].includes(cleanCur)) {
      langSelect.value = cleanCur;
    }
  }

  const trackingCard = document.getElementById('create-ws-tracking-card');
  const idBadge = document.getElementById('create-ws-active-id-badge');

  const addDirBtn = document.getElementById('btn-add-watch-directory');
  const dirInput = document.getElementById('input-watch-directory-path');

  const addFileBtn = document.getElementById('btn-add-watch-file');
  const fileInput = document.getElementById('input-watch-file-path');

  const refreshSourcesBtn = document.getElementById('btn-refresh-tracked-sources');
  const backBtn = document.getElementById('btn-back-to-workspaces');
  const goToWsBtn = document.getElementById('btn-go-to-workspace');

  // Установка языка интерфейса программы по умолчанию в селекторе
  if (langSelect && !langSelect._initialized) {
    langSelect._initialized = true;
    let uiLang = 'ru';
    if (window.i18n && window.i18n.currentLocale) {
      uiLang = window.i18n.currentLocale;
    } else {
      try {
        uiLang = localStorage.getItem('ai_assistant_lang') || localStorage.getItem('language') || 'ru';
      } catch (_) {}
    }
    if (uiLang === 'uk') uiLang = 'ua';
    for (const opt of langSelect.options) {
      if (opt.value === uiLang) {
        langSelect.value = opt.value;
        break;
      }
    }
  }

  // Кнопка выбора рабочей директории на компьютере (Шаг 1)
  const browseWsPathBtn = document.getElementById('btn-browse-ws-path');
  const wsPathPicker = document.getElementById('picker-create-ws-path');

  if (browseWsPathBtn && !browseWsPathBtn._bound) {
    browseWsPathBtn._bound = true;
    browseWsPathBtn.addEventListener('click', async () => {
      try {
        browseWsPathBtn.disabled = true;
        browseWsPathBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Выбор...';
        const res = await apiFetch('/api/v1/workspaces/browse-folder', { method: 'POST' });
        if (res && res.status === 'ok' && res.path) {
          if (pathInput) pathInput.value = res.path;
          return;
        }
      } catch (err) {
        console.debug('[BrowseFolder] Fallback к проводнику браузера:', err);
      } finally {
        browseWsPathBtn.disabled = false;
        browseWsPathBtn.innerHTML = '<i class="bi bi-folder2-open text-primary me-1"></i><span>Обзор...</span>';
      }
      if (wsPathPicker) wsPathPicker.click();
    });
  }

  if (wsPathPicker && !wsPathPicker._bound) {
    wsPathPicker._bound = true;
    wsPathPicker.addEventListener('change', (e) => {
      const files = e.target.files;
      if (files && files.length > 0) {
        const first = files[0];
        const folderName = (first.webkitRelativePath || '').split('/')[0] || first.name;
        if (first.path) {
          const dir = first.path.substring(0, Math.max(first.path.lastIndexOf('\\'), first.path.lastIndexOf('/')));
          if (pathInput) pathInput.value = dir;
        } else if (pathInput && !pathInput.value) {
          pathInput.value = folderName;
        }
      }
      wsPathPicker.value = '';
    });
  }

  // Кнопка выбора директории для слежения (Шаг 2)
  const browseWatchDirBtn = document.getElementById('btn-browse-watch-dir');
  const watchDirPicker = document.getElementById('picker-watch-dir');

  if (browseWatchDirBtn && !browseWatchDirBtn._bound) {
    browseWatchDirBtn._bound = true;
    browseWatchDirBtn.addEventListener('click', async () => {
      try {
        browseWatchDirBtn.disabled = true;
        browseWatchDirBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Выбор...';
        const res = await apiFetch('/api/v1/workspaces/browse-folder', { method: 'POST' });
        if (res && res.status === 'ok' && res.path) {
          if (dirInput) dirInput.value = res.path;
          return;
        }
      } catch (err) {
        console.debug('[BrowseFolder] Fallback к проводнику браузера:', err);
      } finally {
        browseWatchDirBtn.disabled = false;
        browseWatchDirBtn.innerHTML = '<i class="bi bi-folder2-open text-warning me-1"></i><span>Обзор...</span>';
      }
      if (watchDirPicker) watchDirPicker.click();
    });
  }

  if (watchDirPicker && !watchDirPicker._bound) {
    watchDirPicker._bound = true;
    watchDirPicker.addEventListener('change', (e) => {
      const files = e.target.files;
      if (files && files.length > 0) {
        const first = files[0];
        const folderName = (first.webkitRelativePath || '').split('/')[0] || first.name;
        if (first.path) {
          const dir = first.path.substring(0, Math.max(first.path.lastIndexOf('\\'), first.path.lastIndexOf('/')));
          if (dirInput) dirInput.value = dir;
        } else if (dirInput && !dirInput.value) {
          dirInput.value = folderName;
        }
      }
      watchDirPicker.value = '';
    });
  }

  // Кнопка выбора файла для слежения (Шаг 2)
  const browseWatchFileBtn = document.getElementById('btn-browse-watch-file');
  const watchFilePicker = document.getElementById('picker-watch-file');

  if (browseWatchFileBtn && !browseWatchFileBtn._bound) {
    browseWatchFileBtn._bound = true;
    browseWatchFileBtn.addEventListener('click', async () => {
      try {
        browseWatchFileBtn.disabled = true;
        browseWatchFileBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Выбор...';
        const res = await apiFetch('/api/v1/workspaces/browse-file', { method: 'POST' });
        if (res && res.status === 'ok' && res.path) {
          if (fileInput) fileInput.value = res.path;
          return;
        }
      } catch (err) {
        console.debug('[BrowseFile] Fallback к проводнику браузера:', err);
      } finally {
        browseWatchFileBtn.disabled = false;
        browseWatchFileBtn.innerHTML = '<i class="bi bi-file-earmark-plus text-info me-1"></i><span>Обзор...</span>';
      }
      if (watchFilePicker) watchFilePicker.click();
    });
  }

  if (watchFilePicker && !watchFilePicker._bound) {
    watchFilePicker._bound = true;
    watchFilePicker.addEventListener('change', (e) => {
      const files = e.target.files;
      if (files && files.length > 0) {
        const first = files[0];
        if (first.path) {
          if (fileInput) fileInput.value = first.path;
        } else if (fileInput && !fileInput.value) {
          fileInput.value = first.name;
        }
      }
      watchFilePicker.value = '';
    });
  }

  // Шаг 1: Создание рабочего пространства
  if (submitBtn && !submitBtn._bound) {
    submitBtn._bound = true;
    submitBtn.addEventListener('click', async () => {
      const nameVal = nameInput ? nameInput.value.trim() : '';
      const pathVal = pathInput ? pathInput.value.trim() : '';
      const descVal = descInput ? descInput.value.trim() : '';
      let langVal = langSelect ? langSelect.value : 'ru';
      if (langVal === 'uk') langVal = 'ua';

      if (!nameVal) {
        showStatusBanner('Пожалуйста, укажите имя рабочего пространства.', 'warning');
        if (nameInput) nameInput.focus();
        return;
      }

      submitBtn.disabled = true;
      submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Инициализация Git и README.md...';

      try {
        // Поддержка всех символов Unicode (иврит, кириллица, латиница) с нормализацией разделителей
        const cleanId = nameVal
          .trim()
          .replace(/[^\p{L}\p{N}_-]+/gu, '_')
          .replace(/^_+|_+$/g, '') || 'workspace';
        const res = await apiFetch('/api/v1/workspaces', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            workspace_id: cleanId,
            name: nameVal,
            custom_path: pathVal || null,
            description: descVal,
            language: langVal,
          }),
        });

        currentCreatedWorkspaceId = res.workspace?.workspace_id || cleanId;
        currentCreatedWorkspaceName = res.workspace?.name || nameVal;

        if (idBadge) {
          idBadge.textContent = `ID: ${currentCreatedWorkspaceId}`;
          idBadge.className = 'badge bg-success-subtle text-success border font-monospace small';
        }

        if (trackingCard) {
          trackingCard.classList.remove('d-none');
        }

        const headSha = res.workspace?.git_head ? res.workspace.git_head.slice(0, 8) : 'HEAD';
        const wsDiskPath = res.workspace?.path || pathVal || 'auto-path';

        showStatusBanner(`
          <strong>Пространство &laquo;${currentCreatedWorkspaceName}&raquo; успешно создано!</strong>
          <div>Git-репозиторий инициализирован в <code>${wsDiskPath}</code>. Создан файл <code>README.md</code> (lang=${langVal}). Начальный HEAD: <code>${headSha}</code>. Теперь укажите папки или файлы на Шаге 2 для мониторинга изменений на месте.</div>
        `, 'success');

        await loadTrackedSources(currentCreatedWorkspaceId);

        // Обновляем выпадающий список рабочих пространств в верхней панели навигации
        if (typeof window.updateTopWorkspaceDropdown === 'function') {
          window.updateTopWorkspaceDropdown(currentCreatedWorkspaceId);
        }

        // Плавная прокрутка к Шагу 2
        if (trackingCard) {
          trackingCard.scrollIntoView({ behavior: 'smooth' });
        }
      } catch (err) {
        showStatusBanner(`Ошибка создания пространства: ${err.message}`, 'danger');
      } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i class="bi bi-check2-circle me-1"></i>Создать пространство и инициализировать Git';
      }
    });
  }

  // Шаг 2: Добавление директории для слежения на месте
  if (addDirBtn && !addDirBtn._bound) {
    addDirBtn._bound = true;
    addDirBtn.addEventListener('click', async () => {
      const val = dirInput ? dirInput.value : '';
      if (!val) {
        showStatusBanner('Укажите путь к директории для слежения.', 'warning');
        return;
      }
      await addTrackedItemInPlace(val);
      if (dirInput) dirInput.value = '';
    });
  }

  // Шаг 2: Добавление файла для слежения на месте
  if (addFileBtn && !addFileBtn._bound) {
    addFileBtn._bound = true;
    addFileBtn.addEventListener('click', async () => {
      const val = fileInput ? fileInput.value : '';
      if (!val) {
        showStatusBanner('Укажите путь к файлу для слежения.', 'warning');
        return;
      }
      await addTrackedItemInPlace(val);
      if (fileInput) fileInput.value = '';
    });
  }

  // Кнопка обновления списка источников
  if (refreshSourcesBtn && !refreshSourcesBtn._bound) {
    refreshSourcesBtn._bound = true;
    refreshSourcesBtn.addEventListener('click', async () => {
      await loadTrackedSources(currentCreatedWorkspaceId);
    });
  }

  // Кнопки перехода в рабочую область
  if (backBtn && !backBtn._bound) {
    backBtn._bound = true;
    backBtn.addEventListener('click', navigateToCreatedWorkspace);
  }
  if (goToWsBtn && !goToWsBtn._bound) {
    goToWsBtn._bound = true;
    goToWsBtn.addEventListener('click', navigateToCreatedWorkspace);
  }
}

// Экспорт в глобальную область видимости для tab-core
window.initCreateWorkspaceTab = initCreateWorkspaceTab;

// Автоматическая инициализация при загрузке DOM
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initCreateWorkspaceTab);
} else {
  initCreateWorkspaceTab();
}
