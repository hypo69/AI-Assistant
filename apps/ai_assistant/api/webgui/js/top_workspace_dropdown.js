/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Top Repo & Workspace Selector Component
 * =============================================================================
 * Description:
 *   Компонент верхней панели навигации (раскрывающийся список top-select-git-repo),
 *   обеспечивающий выбор рабочего пространства на основе репозиториев с Git:
 *   - В Electron и в браузере сканирует директорию с Git-репозиториями (data)
 *     и выводит только пространства, содержащие инициализированный .git.
 *   - Синхронизирует выбор с нативным меню Electron (Menu Bar) через IPC.
 *   - Глобально устанавливает активный репозиторий и связанную рабочую область
 *     через POST /api/v1/git/maintenance/active-repo и POST /api/v1/workspaces/active.
 *   - Запоминает выбор в SQLite на сервере и в localStorage браузера.
 *   - Мгновенно переходит на канонический URL: #tab-workspace#panel-documents#workspace=<id>.
 *
 * File: top_workspace_dropdown.js
 * Package: apps/ai_assistant/api/webgui/js
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-28 20:02:00
 * =============================================================================
 */

let activeRepoPath = '';
let activeWorkspaceId = '';
let availableRepositories = [];

/**
 * Возвращает отображаемое имя активной рабочей области.
 * @param {string|null} [wsId=null] - Идентификатор рабочей области
 * @returns {string}
 */
export function getActiveWorkspaceDisplayName(wsId = null) {
  const targetId = wsId || getActiveWorkspaceId();
  if (!targetId) return '';
  let cleanId = targetId.replace(/^ws-/, '');
  try {
    cleanId = decodeURIComponent(cleanId);
  } catch (_) {}

  if (Array.isArray(availableRepositories) && availableRepositories.length > 0) {
    const found = availableRepositories.find((r) => {
      const rId = (r.workspace_id || (r.id ? r.id.replace(/^ws-/, '') : '')).normalize('NFC').toLowerCase();
      return rId === cleanId.normalize('NFC').toLowerCase();
    });
    if (found && found.name) {
      return found.name.replace(/^Workspace:\s*/i, '');
    }
  }
  return cleanId;
}

/**
 * Обновляет отображение названия активного рабочего пространства в верхней панели навигации.
 * @param {string|null} [wsId=null] - Идентификатор рабочей области
 */
export function updateActiveWorkspaceHeaderTitle(wsId = null) {
  const titleEl = document.getElementById('app-title');
  if (!titleEl) return;
  const displayName = getActiveWorkspaceDisplayName(wsId);
  if (displayName) {
    titleEl.textContent = displayName;
    titleEl.removeAttribute('data-i18n');
  }
}

/**
 * Возвращает идентификатор активной рабочей области.
 * @returns {string}
 */
export function getActiveWorkspaceId() {
  if (activeWorkspaceId) return activeWorkspaceId;
  if (typeof location !== 'undefined' && location.hash) {
    const match = location.hash.match(/workspace=([^&/#]+)/i);
    if (match && match[1]) {
      try {
        activeWorkspaceId = decodeURIComponent(match[1]);
      } catch (_) {
        activeWorkspaceId = match[1];
      }
      return activeWorkspaceId;
    }
  }
  try {
    const stored = localStorage.getItem('ai_assistant_active_workspace');
    if (stored) {
      activeWorkspaceId = stored;
      return activeWorkspaceId;
    }
  } catch (_) {}
  return '';
}

/**
 * Возвращает путь к активному Git-репозиторию.
 * @returns {string}
 */
export function getActiveRepoPath() {
  if (activeRepoPath) return activeRepoPath;
  try {
    const stored = localStorage.getItem('ai_assistant_active_repo');
    if (stored) {
      activeRepoPath = stored;
      return activeRepoPath;
    }
  } catch (_) {}
  return '';
}

if (typeof window !== 'undefined') {
  window.getActiveWorkspaceId = getActiveWorkspaceId;
  window.getActiveRepoPath = getActiveRepoPath;
  window.getActiveWorkspaceDisplayName = getActiveWorkspaceDisplayName;
  window.updateActiveWorkspaceHeaderTitle = updateActiveWorkspaceHeaderTitle;
}

/**
 * Загружает список доступных рабочих пространств, основываясь на тех, что есть в директории с Git.
 * @returns {Promise<Array>}
 */
export async function fetchAvailableRepositories() {
  let repos = [];

  // 1. Попытка получить пространства напрямую через Electron IPC
  if (typeof window !== 'undefined' && window.aiEngineBridge?.listGitWorkspaces) {
    try {
      const electronWs = await window.aiEngineBridge.listGitWorkspaces();
      if (Array.isArray(electronWs) && electronWs.length > 0) {
        repos = electronWs.map((w) => ({
          id: `ws-${w.workspace_id}`,
          workspace_id: w.workspace_id,
          name: w.name || w.workspace_id,
          path: (w.path || '').replace(/\\/g, '/'),
          branch: w.branch || 'master',
          has_git: true,
        }));
      }
    } catch (e) {
      console.warn('[TopRepoSelector] Ошибка IPC listGitWorkspaces:', e);
    }
  }

  // 2. Если список ещё пуст — запрашиваем REST API сервера (/api/v1/git/maintenance/repositories)
  if (repos.length === 0) {
    try {
      const res = await fetch('/api/v1/git/maintenance/repositories');
      if (res.ok) {
        const serverRepos = await res.json();
        if (Array.isArray(serverRepos)) {
          repos = serverRepos.filter((r) => r.id && r.id.startsWith('ws-'));
        }
      }
    } catch (err) {
      console.warn('[TopRepoSelector] Ошибка загрузки списка репозиториев с сервера:', err);
    }
  }

  availableRepositories = Array.isArray(repos) ? repos : [];
  return availableRepositories;
}

/**
 * Запрашивает текущий глобально активный репозиторий с сервера.
 * @returns {Promise<Object|null>}
 */
export async function fetchGlobalActiveRepoFromServer() {
  try {
    const res = await fetch('/api/v1/git/maintenance/active-repo');
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.warn('[TopRepoSelector] Ошибка получения активного репозитория с сервера:', err);
    return null;
  }
}

/**
 * Глобально устанавливает активный репозиторий и связанную рабочую область.
 * @param {string} chosenPath - Путь к выбранному репозиторию Git
 * @param {string|null} [explicitWsId=null] - Опциональный идентификатор рабочей области
 */
export async function setGlobalActiveRepo(chosenPath, explicitWsId = null) {
  if (!chosenPath) return;

  const normTarget = chosenPath.replace(/\\/g, '/');
  activeRepoPath = normTarget;

  // Определение workspace_id по переданному значению, реестру или пути
  let wsId = explicitWsId;
  if (!wsId && availableRepositories.length > 0) {
    const found = availableRepositories.find(
      (r) => (r.path || '').replace(/\\/g, '/').toLowerCase() === normTarget.toLowerCase()
    );
    if (found) {
      wsId = found.workspace_id || (found.id && found.id.startsWith('ws-') ? found.id.slice(3) : null);
    }
  }

  // Если путь содержит /workspaces/, извлекаем имя рабочей области
  if (!wsId) {
    const match = normTarget.match(/\/(?:workspaces|data)\/([^/]+)$/i);
    if (match && match[1]) {
      try {
        wsId = decodeURIComponent(match[1]);
      } catch (_) {
        wsId = match[1];
      }
    }
  }

  activeWorkspaceId = wsId || '';
  updateActiveWorkspaceHeaderTitle(activeWorkspaceId);

  // 1. Сохраняем в localStorage для мгновенного восстановления
  try {
    localStorage.setItem('ai_assistant_active_repo', normTarget);
    if (wsId) {
      localStorage.setItem('ai_assistant_active_workspace', wsId);
    } else {
      localStorage.removeItem('ai_assistant_active_workspace');
    }
  } catch (_) {}

  // 2. В Electron синхронизируем выбор с главным процессом и нативным меню
  if (typeof window !== 'undefined' && window.aiEngineBridge?.setActiveWorkspace && wsId) {
    try {
      window.aiEngineBridge.setActiveWorkspace(wsId, normTarget);
    } catch (_) {}
  }

  // 3. Отправляем API запросы на сервер для глобальной фиксации
  try {
    fetch('/api/v1/git/maintenance/active-repo', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ repo_path: normTarget, workspace_id: wsId }),
    });

    if (wsId) {
      fetch('/api/v1/workspaces/active', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workspace_id: wsId }),
      });
    }
  } catch (err) {
    console.warn('[TopRepoSelector] Ошибка сохранения активного репозитория на сервере:', err);
  }

  // 4. Синхронизируем значение в верхнем выпадающем списке
  const topSelect = document.getElementById('top-select-git-repo');
  if (topSelect && topSelect.value !== normTarget) {
    for (const opt of topSelect.options) {
      if ((opt.value || '').replace(/\\/g, '/').toLowerCase() === normTarget.toLowerCase()) {
        topSelect.value = opt.value;
        break;
      }
    }
  }

  // 5. Синхронизируем значение в списке контекста вкладки tab_git_maintenance (#select-git-repo)
  const maintSelect = document.getElementById('select-git-repo');
  if (maintSelect && maintSelect.value !== normTarget) {
    for (const opt of maintSelect.options) {
      if ((opt.value || '').replace(/\\/g, '/').toLowerCase() === normTarget.toLowerCase()) {
        maintSelect.value = opt.value;
        break;
      }
    }
  }

  // 6. Синхронизируем селектор на вкладке tab_workspace (#ws-selector) и переключаем на URL рабочей области
  if (wsId) {
    const wsSelector = document.getElementById('ws-selector');
    if (wsSelector && wsSelector.value !== wsId) {
      wsSelector.value = wsId;
    }
    if (typeof window.selectWorkspaceInTab === 'function') {
      window.selectWorkspaceInTab(wsId);
    }
    if (typeof window.switchWorkspaceSubTab === 'function') {
      window.switchWorkspaceSubTab('step2');
    }

    // 6.1 Формируем канонический URL (#tab-workspace#panel-files#workspace=<wsId>)
    const currentSub = (typeof window.getWorkspacePanelFromHash === 'function' ? window.getWorkspacePanelFromHash() : null) || 'panel-files';
    const targetHash = `#tab-workspace#${currentSub}#workspace=${encodeURIComponent(wsId)}`;
    if (typeof location !== 'undefined' && location.hash !== targetHash) {
      location.hash = targetHash;
    }
  }

  // 7. Оповещаем систему о смене контекста событиями context:changed, workspace:changed, repo:changed
  const eventDetail = { repoPath: normTarget, workspaceId: wsId };
  document.dispatchEvent(new CustomEvent('context:changed', { detail: eventDetail }));
  document.dispatchEvent(new CustomEvent('workspace:changed', { detail: eventDetail }));
  document.dispatchEvent(new CustomEvent('repo:changed', { detail: eventDetail }));

  // 8. Если открыта вкладка обслуживания Git, обновляем диагностику
  if (typeof window.loadDiagnosis === 'function') {
    window.loadDiagnosis(normTarget);
  }
}
window.setGlobalActiveRepo = setGlobalActiveRepo;

/**
 * Перезагружает список репозиториев верхней панели и выбирает рабочую область.
 * @param {string} wsId - Идентификатор рабочей области
 * @returns {Promise<void>}
 */
export async function updateTopWorkspaceDropdown(wsId) {
  let decoded = wsId;
  try { decoded = decodeURIComponent(wsId); } catch (_) {}
  const cleanWs = (decoded || '').trim().normalize('NFC');
  const cleanLower = cleanWs.toLowerCase();

  const repos = await fetchAvailableRepositories();
  const found = cleanWs
    ? repos.find((r) => {
        const rId = (r.workspace_id || (r.id || '').replace(/^ws-/, '')).normalize('NFC').toLowerCase();
        const rName = (r.name || '').replace(/^Workspace:\s*/i, '').normalize('NFC').toLowerCase();
        const rPath = (r.path || '').replace(/\\/g, '/').toLowerCase();
        return (
          rId === cleanLower ||
          rName === cleanLower ||
          rPath.endsWith(`/${cleanLower}`) ||
          rPath.endsWith(`/${cleanLower.replace(/\s+/g, '_')}`)
        );
      })
    : null;

  renderTopRepoSelector(repos, found ? found.path : getActiveRepoPath());

  if (typeof window.highlightActiveDrawerWorkspace === 'function') {
    window.highlightActiveDrawerWorkspace(cleanWs);
  }

  if (!found) {
    if (cleanWs) {
      activeWorkspaceId = cleanWs;
      updateActiveWorkspaceHeaderTitle(cleanWs);
    }
    return;
  }
  updateActiveWorkspaceHeaderTitle(cleanWs);
  if (cleanWs.toLowerCase() === (activeWorkspaceId || '').toLowerCase() && (found.path || '').replace(/\\/g, '/').toLowerCase() === (activeRepoPath || '').toLowerCase()) return;
  await setGlobalActiveRepo(found.path, cleanWs);
}
window.updateTopWorkspaceDropdown = updateTopWorkspaceDropdown;

/**
 * Отрисовывает опции выпадающего списка репозиториев в верхнем меню.
 * Основывается строго на рабочих пространствах, имеющих директорию с Git.
 * @param {Array} repos 
 * @param {string} currentPath 
 */
export function renderTopRepoSelector(repos, currentPath) {
  const select = document.getElementById('top-select-git-repo');
  if (!select) return;

  const wsRepos = (repos || []).filter((r) => (r.id && r.id.startsWith('ws-')) || r.has_git === true);

  if (wsRepos.length === 0) {
    select.innerHTML = `<option value="">Нет рабочих пространств с Git</option><option value="__create_new__">+ Создать / Добавить новое рабочее пространство...</option>`;
    if (typeof window.switchTab === 'function' && typeof location !== 'undefined' && !location.hash.includes('tab-create-workspace')) {
      window.switchTab('tab-create-workspace');
    }
    return;
  }

  const normActive = (currentPath || '').replace(/\\/g, '/').toLowerCase();
  const renderOption = (r) => {
    const normR = (r.path || '').replace(/\\/g, '/').toLowerCase();
    const isSelected = normR === normActive ? 'selected' : '';
    const wsId = r.workspace_id || (r.id && r.id.startsWith('ws-') ? r.id.slice(3) : '');
    const cleanName = (r.name || wsId).replace(/^Workspace:\s*/i, '');
    const branchInfo = r.branch ? ` [git: ${r.branch}]` : ' [git]';
    return `<option value="${r.path}" data-ws-id="${wsId}" ${isSelected}>📂 ${cleanName}${branchInfo}</option>`;
  };

  let html = `<optgroup label="Рабочие пространства с Git (Мои пространства)">${wsRepos.map(renderOption).join('')}</optgroup>`;
  html += '<option value="__create_new__">+ Создать / Добавить новое рабочее пространство...</option>';

  select.innerHTML = html;
  updateActiveWorkspaceHeaderTitle(activeWorkspaceId);
}

/**
 * Инициализирует верхний селектор репозитория и восстанавливает сохранённый выбор.
 */
export async function initTopWorkspaceDropdown() {
  const select = document.getElementById('top-select-git-repo');
  const repos = await fetchAvailableRepositories();

  // 1. Подписка на IPC события переключения из нативного меню Electron
  if (typeof window !== 'undefined' && window.aiEngineBridge?.onWorkspaceSwitched) {
    window.aiEngineBridge.onWorkspaceSwitched((data) => {
      const targetWs = (data && data.workspaceId) ? data.workspaceId : data;
      if (targetWs) {
        updateTopWorkspaceDropdown(targetWs);
      }
    });
  }

  if (typeof window !== 'undefined' && window.aiEngineBridge?.onWorkspaceListUpdated) {
    window.aiEngineBridge.onWorkspaceListUpdated(async () => {
      const updatedRepos = await fetchAvailableRepositories();
      renderTopRepoSelector(updatedRepos, getActiveRepoPath());
    });
  }

  // 2. Определяем сохранённый репозиторий: серверная БД -> localStorage -> URL hash -> первое доступное
  let initialPath = '';

  const serverState = await fetchGlobalActiveRepoFromServer();
  if (serverState && serverState.repo_path) {
    initialPath = serverState.repo_path;
    if (serverState.workspace_id) {
      activeWorkspaceId = serverState.workspace_id;
    }
  }

  if (!initialPath) {
    initialPath = getActiveRepoPath();
  }

  if (!initialPath && typeof location !== 'undefined' && location.hash) {
    const match = location.hash.match(/workspace=([^&/#]+)/i);
    if (match && match[1]) {
      let wsId = match[1];
      try { wsId = decodeURIComponent(wsId); } catch (_) {}
      const found = repos.find((r) => {
        const rId = r.workspace_id || (r.id ? r.id.replace(/^ws-/, '') : '');
        return rId === wsId || (r.path || '').replace(/\\/g, '/').endsWith(`/${wsId}`);
      });
      if (found) initialPath = found.path;
    }
  }

  let matchedRepo = repos.find((r) => (r.path || '').replace(/\\/g, '/').toLowerCase() === (initialPath || '').replace(/\\/g, '/').toLowerCase());
  if (!matchedRepo && activeWorkspaceId) {
    matchedRepo = repos.find((r) =>
      (r.workspace_id || '').toLowerCase() === activeWorkspaceId.toLowerCase() ||
      (r.id || '').replace(/^ws-/, '').toLowerCase() === activeWorkspaceId.toLowerCase()
    );
    if (matchedRepo) {
      initialPath = matchedRepo.path;
    }
  }

  if (matchedRepo) {
    initialPath = matchedRepo.path;
    activeWorkspaceId = matchedRepo.workspace_id || (matchedRepo.id ? matchedRepo.id.slice(3) : activeWorkspaceId);
  } else {
    initialPath = '';
    activeWorkspaceId = '';
  }

  activeRepoPath = initialPath;

  // 3. Наполняем верхний раскрывающийся список опциями с Git
  renderTopRepoSelector(repos, initialPath);

  // 4. Слушатель изменения выбора в раскрывающемся списке
  if (select) {
    select.onchange = (e) => {
      const chosen = e.target.value;
      if (chosen === '__create_new__' || chosen === '__create__') {
        if (typeof window.switchTab === 'function') {
          window.switchTab('tab-create-workspace');
        }
        return;
      }
      const opt = select.selectedOptions ? select.selectedOptions[0] : null;
      const wsId = opt ? (opt.getAttribute('data-ws-id') || null) : null;
      setGlobalActiveRepo(chosen, wsId);
    };
  }

  // 5. Применяем глобальную установку для синхронизации всех подсистем только если репозиторий найден в конфиге
  if (initialPath && activeWorkspaceId) {
    setGlobalActiveRepo(initialPath, activeWorkspaceId);
  }
}

// Глобальные подписчики на события смены рабочего пространства
if (typeof document !== 'undefined') {
  document.addEventListener('workspace:changed', (e) => {
    if (e.detail?.workspaceId) {
      updateActiveWorkspaceHeaderTitle(e.detail.workspaceId);
    }
  });

  document.addEventListener('context:changed', (e) => {
    if (e.detail?.workspaceId) {
      updateActiveWorkspaceHeaderTitle(e.detail.workspaceId);
    }
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      updateActiveWorkspaceHeaderTitle();
    });
  } else {
    updateActiveWorkspaceHeaderTitle();
  }
}
