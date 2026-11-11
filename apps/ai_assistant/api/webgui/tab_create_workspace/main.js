/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Tab Create Workspace Orchestrator
 * =============================================================================
 * Description:
 *   Клиентский скрипт вкладки создания нового рабочего пространства:
 *   - Единый интерфейс создания пространства с именем, описанием и Git-репозиторием
 *   - Подключение внешних директорий и файлов для слежения на месте (copy_to_workspace = false)
 *   - Поддержка предварительного выбора (staging) источников до нажатия кнопки создания
 *   - Мгновенное добавление при выборе через диалог или ручной ввод (с поддержкой Enter)
 *   - Полное соответствие стандартам i18n (ru, en, he, uk) без захардкоженных строк
 *   - Интеграция с роутером вкладок и селектором пространств.
 *
 * File: main.js
 * Package: apps/ai_assistant/api/webgui/tab_create_workspace
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-10 20:30:00
 * =============================================================================
 */

let currentCreatedWorkspaceId = '';
let currentCreatedWorkspaceName = '';
let stagedItems = []; // Внешние директории и файлы, выбранные до создания пространства

/**
 * Вспомогательный метод получения локализованной строки из словарей i18n.
 * @param {string} key - Ключ локализации
 * @param {string} [fallback=''] - Текст по умолчанию
 * @returns {string}
 */
function t(key, fallback = '') {
  if (typeof window !== 'undefined') {
    if (window.i18n && typeof window.i18n.t === 'function') {
      const val = window.i18n.t(key, fallback);
      if (val && val !== key) return val;
    }
    if (window.i18next && typeof window.i18next.t === 'function') {
      const val = window.i18next.t(key);
      if (val && val !== key) return val;
    }
  }
  return fallback || key;
}

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
 * Управляет состоянием индикации загрузки для кнопок интерфейса.
 * @param {HTMLElement} btn 
 * @param {boolean} isLoading 
 * @param {string} [loadingKey] 
 * @param {string} [defaultText] 
 */
function setButtonLoading(btn, isLoading, loadingKey = '', defaultText = '') {
  if (!btn) return;
  btn.disabled = isLoading;
  if (isLoading) {
    if (!btn._originalContent) {
      btn._originalContent = btn.innerHTML;
    }
    const label = loadingKey ? t(loadingKey, defaultText) : defaultText;
    btn.innerHTML = `<span class="spinner-border spinner-border-sm me-1" role="status"></span><span>${label}</span>`;
  } else if (btn._originalContent) {
    btn.innerHTML = btn._originalContent;
    if (window.i18n && typeof window.i18n.applyTranslations === 'function') {
      window.i18n.applyTranslations(btn);
    }
  }
}

/**
 * Инициализирует связку кнопки выбора папки и нативного проводника.
 */
function setupFolderBrowser(btn, picker, onSelect) {
  if (!btn || btn._bound) return;
  btn._bound = true;
  btn.addEventListener('click', async () => {
    try {
      setButtonLoading(btn, true, 'ui.cws.btn_selecting', 'Выбор...');
      const res = await apiFetch('/api/v1/workspaces/browse-folder', { method: 'POST' });
      if (res && res.status === 'ok' && res.path) {
        onSelect(res.path);
        return;
      }
    } catch (err) {
      console.debug('[BrowseFolder] Fallback к проводнику браузера:', err);
    } finally {
      setButtonLoading(btn, false);
    }
    if (picker) picker.click();
  });
  if (picker && !picker._bound) {
    picker._bound = true;
    picker.addEventListener('change', (e) => {
      const files = e.target.files;
      if (files && files.length > 0) {
        const first = files[0];
        const dir = first.path
          ? first.path.substring(0, Math.max(first.path.lastIndexOf('\\'), first.path.lastIndexOf('/')))
          : (first.webkitRelativePath || '').split('/')[0] || first.name;
        if (dir) onSelect(dir);
      }
      picker.value = '';
    });
  }
}

/**
 * Инициализирует связку кнопки выбора файла и нативного проводника.
 */
function setupFileBrowser(btn, picker, onSelect) {
  if (!btn || btn._bound) return;
  btn._bound = true;
  btn.addEventListener('click', async () => {
    try {
      setButtonLoading(btn, true, 'ui.cws.btn_selecting', 'Выбор...');
      const res = await apiFetch('/api/v1/workspaces/browse-file', { method: 'POST' });
      if (res && res.status === 'ok' && res.path) {
        onSelect(res.path);
        return;
      }
    } catch (err) {
      console.debug('[BrowseFile] Fallback к проводнику браузера:', err);
    } finally {
      setButtonLoading(btn, false);
    }
    if (picker) picker.click();
  });
  if (picker && !picker._bound) {
    picker._bound = true;
    picker.addEventListener('change', (e) => {
      const files = e.target.files;
      if (files && files.length > 0) {
        const filePath = files[0].path || files[0].name;
        if (filePath) onSelect(filePath);
      }
      picker.value = '';
    });
  }
}

/**
 * Назначает обработчик отправки по нажатию клавиши Enter.
 */
function setupEnterKey(input, onEnter) {
  if (!input || input._boundEnter) return;
  input._boundEnter = true;
  input.addEventListener('keydown', async (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      const val = input.value.trim();
      if (val) {
        await onEnter(val);
        input.value = '';
      }
    }
  });
}

/**
 * Отображает список предварительно добавленных (staged) источников до создания пространства.
 */
function renderStagedSources() {
  const container = document.getElementById('create-ws-sources-list');
  const countBadge = document.getElementById('create-ws-tracked-count-badge');

  if (countBadge) {
    countBadge.textContent = stagedItems.length > 0
      ? t('ui.cws.staged_count', '{count} в очереди').replace('{count}', stagedItems.length)
      : t('ui.cws.txt_13ea0390', '0 объектов');
  }

  if (!container) return;

  if (stagedItems.length === 0) {
    container.innerHTML = `
      <div class="p-3 text-center text-muted small bg-body-tertiary" id="cws-empty-staged-notice">
        <i class="bi bi-pin-angle text-secondary fs-4 d-block mb-1"></i>
        <span data-i18n="ui.cws.txt_fa42174b" id="cws-span-fa42174b">${t('ui.cws.txt_fa42174b', 'Директории и файлы пока не добавлены. Введите путь выше или нажмите кнопку «Обзор...» для выбора.')}</span>
      </div>`;
    return;
  }

  container.innerHTML = stagedItems.map((item, idx) => {
    const isDir = item.type === 'directory';
    const icon = isDir ? 'bi-folder2-open text-warning' : 'bi-file-earmark-check text-info';
    return `
      <div class="list-group-item d-flex align-items-center justify-content-between p-2 mb-1 rounded border" id="cws-staged-item-${idx}">
        <div class="d-flex align-items-center gap-2 overflow-hidden me-2">
          <i class="bi ${icon} fs-5 flex-shrink-0"></i>
          <div class="text-truncate">
            <div class="fw-semibold text-truncate text-body">${item.path}</div>
            <div class="text-muted font-monospace small text-truncate" id="cws-staged-desc-${idx}">
              <span data-i18n="ui.cws.ready_to_link" id="cws-staged-ready-link-${idx}">${t('ui.cws.ready_to_link', 'Готово к привязке на диске')}</span>
            </div>
          </div>
        </div>
        <div class="d-flex align-items-center gap-2 flex-shrink-0">
          <span class="badge bg-warning-subtle text-warning border font-size-75" id="cws-staged-badge-${idx}">
            <i class="bi bi-clock-history me-1"></i><span data-i18n="ui.cws.in_queue" id="cws-staged-inqueue-${idx}">${t('ui.cws.in_queue', 'В очереди на подключение')}</span>
          </span>
          <button class="btn btn-sm btn-outline-danger py-0 px-1.5 font-size-75 btn-remove-staged" data-index="${idx}" data-i18n-title="titles.cws.remove_from_queue" id="cws-btn-remove-staged-${idx}" title="${t('titles.cws.remove_from_queue', 'Удалить из очереди')}" type="button">
            <i class="bi bi-trash3"></i>
          </button>
        </div>
      </div>
    `;
  }).join('');

  container.querySelectorAll('.btn-remove-staged').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const idx = parseInt(e.currentTarget.getAttribute('data-index'), 10);
      if (!isNaN(idx) && idx >= 0 && idx < stagedItems.length) {
        stagedItems.splice(idx, 1);
        renderStagedSources();
      }
    });
  });
}

/**
 * Загружает и отображает список отслеживаемых на месте объектов пространства.
 * @param {string} wsId 
 */
export async function loadTrackedSources(wsId) {
  if (!wsId) {
    renderStagedSources();
    return;
  }
  const container = document.getElementById('create-ws-sources-list');
  const countBadge = document.getElementById('create-ws-tracked-count-badge');
  const gitHeadBadge = document.getElementById('create-ws-git-head-badge');

  try {
    const data = await apiFetch(`/api/v1/workspaces/${encodeURIComponent(wsId)}/sources`);
    const sources = data.sources || [];

    if (countBadge) {
      countBadge.textContent = t('ui.cws.sources_count', '{count} источников').replace('{count}', sources.length);
    }

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
        <div class="p-3 text-center text-muted small bg-body-tertiary" id="cws-empty-tracked-notice">
          <i class="bi bi-eye-slash text-secondary fs-4 d-block mb-1"></i>
          <span data-i18n="ui.cws.txt_fa42174b" id="cws-span-fa42174b-tracked">${t('ui.cws.txt_fa42174b', 'Директории и файлы пока не добавлены. Введите путь выше и нажмите кнопку добавления.')}</span>
        </div>`;
      return;
    }

    container.innerHTML = sources.map((src, idx) => {
      const isDir = src.source_type === 'directory';
      const icon = isDir ? 'bi-folder2-open text-warning' : 'bi-file-earmark-check text-info';
      const filesCountText = t('ui.cws.files_count', '{count} файлов').replace('{count}', src.item_count || 0);
      return `
        <div class="list-group-item d-flex align-items-center justify-content-between p-2 mb-1 rounded border" id="cws-source-item-${idx}">
          <div class="d-flex align-items-center gap-2 overflow-hidden me-2">
            <i class="bi ${icon} fs-5 flex-shrink-0"></i>
            <div class="text-truncate">
              <div class="fw-semibold text-truncate text-body">${src.display_name || src.source_path}</div>
              <div class="text-muted font-monospace small text-truncate">${src.qualified_path || src.source_path}</div>
            </div>
          </div>
          <div class="d-flex align-items-center gap-2 flex-shrink-0">
            <span class="badge bg-success-subtle text-success border font-size-75" id="cws-source-badge-${idx}">
              <i class="bi bi-pin-angle me-1"></i><span data-i18n="ui.cws.in_place" id="cws-source-inplace-${idx}">${t('ui.cws.in_place', 'На месте (без перемещения)')}</span>
            </span>
            <span class="badge bg-secondary-subtle text-secondary border font-size-75" id="cws-source-count-badge-${idx}">
              ${filesCountText}
            </span>
            <button class="btn btn-sm btn-outline-danger py-0 px-1.5 font-size-75 btn-remove-source" data-source-id="${src.source_id}" data-i18n-title="titles.cws.exclude_from_tracking" id="cws-btn-remove-source-${idx}" title="${t('titles.cws.exclude_from_tracking', 'Исключить из отслеживания')}" type="button">
              <i class="bi bi-trash3"></i>
            </button>
          </div>
        </div>
      `;
    }).join('');

    container.querySelectorAll('.btn-remove-source').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const sid = e.currentTarget.getAttribute('data-source-id');
        if (!sid) return;
        try {
          await apiFetch(`/api/v1/workspaces/${encodeURIComponent(wsId)}/sources/${encodeURIComponent(sid)}`, {
            method: 'DELETE',
          });
          showStatusBanner(t('ui.cws.source_excluded', 'Источник исключен из наблюдения.'), 'info');
          await loadTrackedSources(wsId);
        } catch (delErr) {
          showStatusBanner(t('ui.cws.err_deleting', 'Ошибка удаления: {error}').replace('{error}', delErr.message), 'danger');
        }
      });
    });

  } catch (err) {
    if (container) {
      container.innerHTML = `<div class="p-2 text-danger small" id="cws-sources-load-err">${t('ui.cws.err_loading_sources', 'Ошибка загрузки источников: {error}').replace('{error}', err.message)}</div>`;
    }
  }
}

/**
 * Добавляет указанный путь на диске для отслеживания изменений на месте (без перемещения).
 * @param {string} targetPath 
 * @param {'directory'|'file'} [itemType='directory']
 */
async function addTrackedItemInPlace(targetPath, itemType = 'directory') {
  const cleanPath = (targetPath || '').trim();
  if (!cleanPath) {
    showStatusBanner(t('ui.cws.warn_specify_path', 'Пожалуйста, укажите абсолютный путь на диске.'), 'warning');
    return;
  }

  if (!currentCreatedWorkspaceId) {
    if (stagedItems.some(it => it.path.toLowerCase() === cleanPath.toLowerCase())) {
      showStatusBanner(t('ui.cws.warn_item_already_staged', 'Объект <code>{path}</code> уже находится в списке.').replace('{path}', cleanPath), 'info');
      return;
    }
    stagedItems.push({ path: cleanPath, type: itemType });
    renderStagedSources();
    showStatusBanner(t('ui.cws.info_item_staged', 'Объект <code>{path}</code> добавлен в список. Он будет подключен сразу при создании пространства.').replace('{path}', cleanPath), 'info');
    return;
  }

  showStatusBanner(t('ui.cws.info_connecting_item', 'Подключение объекта <code>{path}</code> для слежения на месте...').replace('{path}', cleanPath), 'info');

  try {
    const commitMsg = t('ui.cws.init_git_commit', 'Подключение {path} для слежения на месте (Git linked)').replace('{path}', cleanPath);
    const res = await apiFetch(`/api/v1/workspaces/${encodeURIComponent(currentCreatedWorkspaceId)}/items`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        items: [cleanPath],
        copy_to_workspace: false,
        commit_message: commitMsg,
      }),
    });

    const added = res.files_added || 0;
    const commitHead = res.git_head ? res.git_head.slice(0, 8) : 'HEAD';

    showStatusBanner(
      t('ui.cws.success_item_connected', '<strong>Объект успешно подключен к наблюдению!</strong><div>Файлы остаются на исходном месте. Добавлено под контроль: {added}. Git commit: <code>{commit}</code>.</div>')
        .replace('{added}', added)
        .replace('{commit}', commitHead),
      'success'
    );

    await loadTrackedSources(currentCreatedWorkspaceId);
  } catch (err) {
    showStatusBanner(t('ui.cws.err_connecting_item', 'Ошибка подключения пути <code>{path}</code>: {error}').replace('{path}', cleanPath).replace('{error}', err.message), 'danger');
  }
}

/**
 * Переключает интерфейс в основную рабочую область и активирует созданное пространство.
 */
async function navigateToCreatedWorkspace() {
  const targetWsId = currentCreatedWorkspaceId || 'default';

  if (typeof window.switchTab === 'function') {
    window.switchTab('tab-workspace');
  }

  const wsSelector = document.getElementById('ws-selector');
  if (wsSelector) {
    try {
      const data = await apiFetch('/api/v1/workspaces');
      const list = data.workspaces || [];
      wsSelector.innerHTML = list.map(ws => {
        const itemLabel = t('ui.cws.ws_select_item', '{name} [{id}] — док: {docs}, фактов: {facts}')
          .replace('{name}', ws.name)
          .replace('{id}', ws.workspace_id)
          .replace('{docs}', ws.documents_count || 0)
          .replace('{facts}', ws.active_facts_count || 0);
        return `
          <option value="${ws.workspace_id}" ${ws.workspace_id === targetWsId ? 'selected' : ''}>
            ${itemLabel}
          </option>
        `;
      }).join('');
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
  const submitBtnBottom = document.getElementById('btn-create-ws-submit-bottom');
  const nameInput = document.getElementById('create-ws-name-input');
  const langSelect = document.getElementById('create-ws-lang-select');
  const pathInput = document.getElementById('create-ws-path-input');
  const descInput = document.getElementById('create-ws-desc-input');
  const idBadge = document.getElementById('create-ws-active-id-badge');

  const addDirBtn = document.getElementById('btn-add-watch-directory');
  const dirInput = document.getElementById('input-watch-directory-path');
  const addFileBtn = document.getElementById('btn-add-watch-file');
  const fileInput = document.getElementById('input-watch-file-path');

  const refreshSourcesBtn = document.getElementById('btn-refresh-tracked-sources');
  const backBtn = document.getElementById('btn-back-to-workspaces');
  const goToWsBtn = document.getElementById('btn-go-to-workspace');

  if (currentCreatedWorkspaceId) {
    loadTrackedSources(currentCreatedWorkspaceId);
  } else {
    renderStagedSources();
  }

  // Установка языка интерфейса по умолчанию в селекторе
  if (langSelect && !langSelect._initialized) {
    langSelect._initialized = true;
    let uiLang = (typeof window !== 'undefined' && window.i18n?.lang) || localStorage.getItem('app_language') || 'ru';
    if (uiLang === 'uk') uiLang = 'ua';
    for (const opt of langSelect.options) {
      if (opt.value === uiLang) {
        langSelect.value = opt.value;
        break;
      }
    }
  }

  // Настройка диалогов выбора путей
  setupFolderBrowser(
    document.getElementById('btn-browse-ws-path'),
    document.getElementById('picker-create-ws-path'),
    (dir) => { if (pathInput) pathInput.value = dir; }
  );

  setupFolderBrowser(
    document.getElementById('btn-browse-watch-dir'),
    document.getElementById('picker-watch-dir'),
    async (dir) => {
      if (dirInput) dirInput.value = '';
      await addTrackedItemInPlace(dir, 'directory');
    }
  );

  setupFileBrowser(
    document.getElementById('btn-browse-watch-file'),
    document.getElementById('picker-watch-file'),
    async (file) => {
      if (fileInput) fileInput.value = '';
      await addTrackedItemInPlace(file, 'file');
    }
  );

  // Быстрый ввод путей по клавише Enter
  setupEnterKey(dirInput, async (val) => { await addTrackedItemInPlace(val, 'directory'); });
  setupEnterKey(fileInput, async (val) => { await addTrackedItemInPlace(val, 'file'); });

  // Создание рабочего пространства
  const handleCreateWorkspace = async () => {
    const nameVal = nameInput ? nameInput.value.trim() : '';
    const pathVal = pathInput ? pathInput.value.trim() : '';
    const descVal = descInput ? descInput.value.trim() : '';
    let langVal = langSelect ? langSelect.value : 'ru';
    if (langVal === 'uk') langVal = 'ua';

    if (!nameVal) {
      showStatusBanner(t('ui.cws.warn_specify_name', 'Пожалуйста, укажите имя рабочего пространства.'), 'warning');
      if (nameInput) nameInput.focus();
      return;
    }

    if (submitBtnBottom) {
      setButtonLoading(submitBtnBottom, true, 'ui.cws.btn_creating_ws', 'Инициализация Git и создание пространства...');
    }

    try {
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
        idBadge.textContent = `${t('ui.cws.id_prefix', 'ID: ')}${currentCreatedWorkspaceId}`;
        idBadge.className = 'badge bg-success-subtle text-success border font-monospace small';
      }

      let stagedAddedCount = 0;
      if (stagedItems.length > 0) {
        try {
          const attachCommitMsg = t('ui.cws.init_git_commit_multiple', 'Подключение внешних объектов ({count}) для слежения на месте').replace('{count}', stagedItems.length);
          const linkRes = await apiFetch(`/api/v1/workspaces/${encodeURIComponent(currentCreatedWorkspaceId)}/items`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              items: stagedItems.map(it => it.path),
              copy_to_workspace: false,
              commit_message: attachCommitMsg,
            }),
          });
          stagedAddedCount = linkRes.files_added || stagedItems.length;
          stagedItems = [];
        } catch (linkErr) {
          console.error('[CreateWorkspaceTab] Ошибка подключения предварительных объектов:', linkErr);
          showStatusBanner(t('ui.cws.err_attach_staged', 'Пространство создано, но возникла ошибка при подключении объектов: {error}').replace('{error}', linkErr.message), 'warning');
        }
      }

      const headSha = res.workspace?.git_head ? res.workspace.git_head.slice(0, 8) : 'HEAD';
      const wsDiskPath = res.workspace?.path || pathVal || 'auto-path';

      showStatusBanner(
        t('ui.cws.success_ws_created', '<strong>Пространство &laquo;{name}&raquo; успешно создано!</strong><div>Git-репозиторий: <code>{path}</code>. Язык: <code>{lang}</code>. HEAD: <code>{head}</code>. Подключено источников: {count}.</div>')
          .replace('{name}', currentCreatedWorkspaceName)
          .replace('{path}', wsDiskPath)
          .replace('{lang}', langVal)
          .replace('{head}', headSha)
          .replace('{count}', stagedAddedCount),
        'success'
      );

      await loadTrackedSources(currentCreatedWorkspaceId);

      if (typeof window.updateTopWorkspaceDropdown === 'function') {
        window.updateTopWorkspaceDropdown(currentCreatedWorkspaceId);
      }

      if (goToWsBtn) {
        goToWsBtn.classList.remove('d-none');
      }
      const syncStatusMsg = document.getElementById('create-ws-sync-status-msg');
      if (syncStatusMsg) {
        syncStatusMsg.innerHTML = `<i class="bi bi-check-circle-fill text-success"></i><span data-i18n="ui.cws.status_ws_ready" id="cws-span-status-ready">${t('ui.cws.status_ws_ready', 'Пространство настроено. Вы можете сразу перейти к работе с ним.')}</span>`;
      }

    } catch (err) {
      showStatusBanner(t('ui.cws.err_creating_ws', 'Ошибка создания пространства: {error}').replace('{error}', err.message), 'danger');
    } finally {
      if (submitBtnBottom) {
        setButtonLoading(submitBtnBottom, false);
      }
    }
  };

  if (submitBtnBottom && !submitBtnBottom._bound) {
    submitBtnBottom._bound = true;
    submitBtnBottom.addEventListener('click', handleCreateWorkspace);
  }

  if (addDirBtn && !addDirBtn._bound) {
    addDirBtn._bound = true;
    addDirBtn.addEventListener('click', async () => {
      const val = dirInput ? dirInput.value.trim() : '';
      if (!val) {
        showStatusBanner(t('ui.cws.warn_specify_dir', 'Укажите путь к директории для слежения.'), 'warning');
        return;
      }
      await addTrackedItemInPlace(val, 'directory');
      if (dirInput) dirInput.value = '';
    });
  }

  if (addFileBtn && !addFileBtn._bound) {
    addFileBtn._bound = true;
    addFileBtn.addEventListener('click', async () => {
      const val = fileInput ? fileInput.value.trim() : '';
      if (!val) {
        showStatusBanner(t('ui.cws.warn_specify_file', 'Укажите путь к файлу для слежения.'), 'warning');
        return;
      }
      await addTrackedItemInPlace(val, 'file');
      if (fileInput) fileInput.value = '';
    });
  }

  if (refreshSourcesBtn && !refreshSourcesBtn._bound) {
    refreshSourcesBtn._bound = true;
    refreshSourcesBtn.addEventListener('click', async () => {
      if (currentCreatedWorkspaceId) {
        await loadTrackedSources(currentCreatedWorkspaceId);
      } else {
        renderStagedSources();
      }
    });
  }

  if (backBtn && !backBtn._bound) {
    backBtn._bound = true;
    backBtn.addEventListener('click', navigateToCreatedWorkspace);
  }
  if (goToWsBtn && !goToWsBtn._bound) {
    goToWsBtn._bound = true;
    goToWsBtn.addEventListener('click', navigateToCreatedWorkspace);
  }

  // Подписка на изменение языка интерфейса для динамической перерисовки списков и бейджей
  if (!window._cwsLangListenerAttached) {
    window._cwsLangListenerAttached = true;
    const reRenderSources = () => {
      if (currentCreatedWorkspaceId) {
        loadTrackedSources(currentCreatedWorkspaceId);
      } else {
        renderStagedSources();
      }
      if (typeof window.applyTranslations === 'function') {
        window.applyTranslations();
      } else if (window.i18n && typeof window.i18n.applyTranslations === 'function') {
        const container = document.getElementById('cws-main-container');
        if (container) window.i18n.applyTranslations(container);
      }
    };
    window.addEventListener('languageChanged', reRenderSources);
    window.addEventListener('i18n:languageChanged', reRenderSources);
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
