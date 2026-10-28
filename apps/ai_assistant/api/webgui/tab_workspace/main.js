/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Tab Workspace Main Orchestrator
 * =============================================================================
 * Description:
 *   Главный клиентский скрипт-оркестратор вкладки рабочих пространств (tab_workspace).
 *   Координирует жизненный цикл, формирование URL с активной суб-панелью
 *   (#tab-workspace#<panel_id>) и отправку изолированных API-запросов строго
 *   для активной панели в полном соответствии с архитектурой apps/windows/api/webgui.
 *
 * File: main.js
 * Package: apps/ai_assistant/api/webgui/tab_workspace
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-28 05:06:00
 * =============================================================================
 */

import {
  TAB_ID,
  isWorkspaceTabActive,
  normalizeSubTabId,
  getActiveSubTabId,
  getPanelFromHash,
  getWorkspaceIdFromHash,
  updateUrlWithPanel,
} from './common/ui_utils.js';

import {
  initWorkspaceSelectPanel,
  loadWorkspaces,
  loadDirectoryContents,
  getCurrentWorkspaceId,
  setCurrentWorkspaceId,
  deleteCurrentWorkspace,
} from './panel_workspace_select/panel.js?v=20261028_v1';
import {
  initDocumentsPanel,
  loadDocuments,
  loadWorkspaceCommits,
} from './panel_documents/panel.js';
import { initFactsPanel, loadFacts } from './panel_facts/panel.js';
import { initQaPanel, executeAskQuestion } from './panel_qa/panel.js';
import { initSourcesPanel, loadSources } from './panel_sources/panel.js';
import { initChatPanel } from './panel_chat/panel.js?v=20261023_v2';
import {
  initCommitsPanel,
  loadWorkspaceCommitsPanel,
} from './panel_commits/panel.js';
import {
  initTreePanel,
  loadWorkspaceTreePanel,
} from './panel_tree/panel.js';

let initialized = false;

/**
 * Программный выбор активного пространства на вкладке tab_workspace с обновлением всех суб-панелей.
 * @param {string} wsId - Идентификатор рабочего пространства
 */
export async function selectWorkspaceInTab(wsId, force = false) {
  if (!wsId) return;
  const cleanId = String(wsId).trim().normalize('NFC');
  const isDifferent = (getCurrentWorkspaceId() || '').normalize('NFC') !== cleanId;
  setCurrentWorkspaceId(cleanId);
  const selector = document.getElementById('ws-selector');
  if (selector && selector.value !== cleanId) {
    selector.value = cleanId;
  }
  if (isDifferent || force) {
    await loadWorkspaces(cleanId, false);
    // Опрашиваем СТРОГО активную суб-панель на вкладке
    await fetchActiveSubTabOnly(true);
  }
}

/**
 * Выполняет раздельные API-запросы строго для активной панели вкладки.
 * @param {boolean} [force=false] - Принудительное обновление данных.
 */
export async function fetchActiveSubTabOnly(force = false) {
  const activeSub = getActiveSubTabId();
  const wsId = getCurrentWorkspaceId();
  if (!wsId) return;

  if (activeSub === 'panel-files' || activeSub === 'panel-workspace' || activeSub === 'panel-workspace-select') {
    // API запросы строго для активной панели Файлы (директория Git, источники: loadWorkspaces(), loadSources)
    await Promise.all([
      loadDirectoryContents(wsId),
      loadSources(wsId, force),
    ]);
  } else if (activeSub === 'panel-documents') {
    // API запросы строго для активной панели Документы (Git-коммиты, SQLite-факты)
    await Promise.all([
      loadDocuments(wsId, force),
      loadWorkspaceCommits(wsId, force),
      loadFacts(wsId, force),
    ]);
  } else if (activeSub === 'panel-qa') {
    // Шаг 3: QA готов к диалогу (без фонового опроса)
  } else if (activeSub === 'panel-chat') {
    // Панель Чат: готов к диалогу (без фонового опроса)
  } else if (activeSub === 'panel-commits') {
    // API запросы строго для активной панели Коммиты
    await loadWorkspaceCommitsPanel(wsId, force);
  } else if (activeSub === 'panel-tree') {
    // API запросы строго для активной панели Дерево файлов
    await loadWorkspaceTreePanel(wsId, force);
  }
}

export function getActiveWorkspaceSubTabId() {
  return getActiveSubTabId();
}

/**
 * Программное переключение между суб-вкладками раздела Файлы (ws-files).
 * @param {string} subtabId - Идентификатор подвкладки ('dir', 'track', 'obsidian', 'sources')
 */
export function switchFilesSubTab(subtabId) {
  let btnId = 'subtab-ws-files-dir-btn';
  let paneId = 'subpane-ws-files-dir';

  switch (subtabId) {
    case 'track':
    case 'tracking':
    case 'add':
      btnId = 'subtab-ws-files-track-btn';
      paneId = 'subpane-ws-files-track';
      break;
    case 'obsidian':
    case 'vault':
      btnId = 'subtab-ws-files-obsidian-btn';
      paneId = 'subpane-ws-files-obsidian';
      break;
    case 'sources':
    case 'external':
    case 'panel-sources':
      btnId = 'subtab-ws-files-sources-btn';
      paneId = 'subpane-ws-files-sources';
      break;
    case 'dir':
    case 'directory':
    case 'files':
    default:
      btnId = 'subtab-ws-files-dir-btn';
      paneId = 'subpane-ws-files-dir';
      break;
  }

  const btn = document.getElementById(btnId);
  if (btn) {
    if (window.bootstrap && window.bootstrap.Tab) {
      const tabInst = window.bootstrap.Tab.getInstance(btn) || new window.bootstrap.Tab(btn);
      tabInst.show();
    } else {
      document.querySelectorAll('#ws-files-subtabs-nav button').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      document.querySelectorAll('#ws-files-subtabs-content > .tab-pane').forEach((p) => {
        p.classList.remove('show', 'active');
      });
      const pane = document.getElementById(paneId);
      if (pane) {
        pane.classList.add('show', 'active');
      }
    }
  }
}
window.switchFilesSubTab = switchFilesSubTab;

/**
 * Программное переключение между суб-панелями вкладки Workspace с обновлением URL.
 * @param {string} subtabId - Идентификатор подвкладки или panel_id.
 * @param {boolean} [updateUrl=true] - Обновлять ли URL hash в адресной строке браузера.
 */
export function switchWorkspaceSubTab(subtabId, updateUrl = true) {
  const canonical = normalizeSubTabId(subtabId);
  let targetBtnId = 'subtab-ws-step1-btn';
  let targetPaneId = 'subpane-ws-step1';

  switch (canonical) {
    case 'panel-tree':
      targetBtnId = 'subtab-ws-tree-btn';
      targetPaneId = 'subpane-ws-tree';
      break;
    case 'panel-commits':
      targetBtnId = 'subtab-ws-commits-btn';
      targetPaneId = 'subpane-ws-commits';
      break;
    case 'panel-chat':
      targetBtnId = 'subtab-ws-chat-btn';
      targetPaneId = 'subpane-ws-chat';
      break;
    case 'panel-qa':
      targetBtnId = 'subtab-ws-step3-btn';
      targetPaneId = 'subpane-ws-step3';
      break;
    case 'panel-documents':
      targetBtnId = 'subtab-ws-step2-btn';
      targetPaneId = 'subpane-ws-step2';
      break;
    case 'panel-sources':
      targetBtnId = 'subtab-ws-step1-btn';
      targetPaneId = 'subpane-ws-step1';
      switchFilesSubTab('sources');
      break;
    case 'panel-files':
    case 'panel-workspace':
    case 'panel-workspace-select':
    default:
      targetBtnId = 'subtab-ws-step1-btn';
      targetPaneId = 'subpane-ws-step1';
      break;
  }

  const btn = document.getElementById(targetBtnId);
  if (btn) {
    if (window.bootstrap && window.bootstrap.Tab) {
      const tabInst = window.bootstrap.Tab.getInstance(btn) || new window.bootstrap.Tab(btn);
      tabInst.show();
    } else {
      document.querySelectorAll('#workspace-subtabs-nav button').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      document.querySelectorAll('#workspace-subtabs-content .tab-pane').forEach((p) => {
        p.classList.remove('show', 'active');
      });
      const pane = document.getElementById(targetPaneId);
      if (pane) {
        pane.classList.add('show', 'active');
      }
    }
  }

  if (updateUrl) {
    updateUrlWithPanel(canonical);
  }

  if (isWorkspaceTabActive()) {
    fetchActiveSubTabOnly();
  }
}

/**
 * Инициализирует вкладку Workspace, навигацию и связывает панели между собой.
 */
export async function initWorkspaceTab() {
  if (initialized) return;
  initialized = true;

  const getWorkspaceId = () => getCurrentWorkspaceId();

  const handleWorkspaceChange = async (wsId) => {
    await fetchActiveSubTabOnly(true);
  };

  const handleDocSaved = async () => {
    const wsId = getWorkspaceId();
    await Promise.all([
      loadDocuments(wsId, true),
      loadWorkspaceCommits(wsId, true),
      loadFacts(wsId, true),
      loadDirectoryContents(wsId),
      loadWorkspaceTreePanel(wsId, true),
    ]);
  };

  const handleSourcesSynced = async () => {
    const wsId = getWorkspaceId();
    await Promise.all([
      loadSources(wsId, true),
      loadDirectoryContents(wsId),
      loadWorkspaceTreePanel(wsId, true),
    ]);
  };

  const handleAskDemoQuestion = async (qText) => {
    switchWorkspaceSubTab('panel-qa', true);
    await executeAskQuestion(qText, getWorkspaceId());
  };

  // Навигация по суб-вкладкам и автоматическое обновление URL hash
  // Навигация по под-вкладкам панели Файлы (ws-files-subtabs-nav)
  const filesSubtabsNav = document.getElementById('ws-files-subtabs-nav');
  if (filesSubtabsNav) {
    filesSubtabsNav.querySelectorAll('button[data-bs-toggle="pill"]').forEach((btn) => {
      btn.addEventListener('click', () => {
        if (!window.bootstrap || !window.bootstrap.Tab) {
          filesSubtabsNav.querySelectorAll('button').forEach((b) => b.classList.remove('active'));
          btn.classList.add('active');
          const targetSelector = btn.getAttribute('data-bs-target');
          if (targetSelector) {
            document.querySelectorAll('#ws-files-subtabs-content > .tab-pane').forEach((p) => {
              p.classList.remove('show', 'active');
            });
            document.querySelector(targetSelector)?.classList.add('show', 'active');
          }
        }
      });
    });
  }

  const subtabsNav = document.getElementById('workspace-subtabs-nav');
  if (subtabsNav) {
    subtabsNav.querySelectorAll('button[data-bs-toggle="pill"]').forEach((btn) => {
      btn.addEventListener('shown.bs.tab', (e) => {
        const targetId = e.target.getAttribute('data-bs-target') || e.target.getAttribute('data-panel-id') || '';
        const canonical = normalizeSubTabId(targetId);
        updateUrlWithPanel(canonical);
        fetchActiveSubTabOnly();
      });
    });
  }

  const syncWorkspaceFromUrl = async () => {
    const wsId = getWorkspaceIdFromHash();
    if (wsId && wsId !== (getCurrentWorkspaceId() || '').normalize('NFC')) {
      await selectWorkspaceInTab(wsId);
    }
  };

  // Реакция на изменение URL hash браузера (навигация вперед/назад или переход по ссылке)
  window.addEventListener('hashchange', async () => {
    if (!isWorkspaceTabActive()) return;
    await syncWorkspaceFromUrl();
    const targetPanel = getPanelFromHash();
    if (targetPanel && targetPanel !== getActiveSubTabId()) {
      switchWorkspaceSubTab(targetPanel, false);
    }
  });

  initWorkspaceSelectPanel(handleWorkspaceChange, handleAskDemoQuestion);
  initDocumentsPanel(handleDocSaved);
  initFactsPanel(getWorkspaceId);
  initQaPanel(getWorkspaceId);
  initSourcesPanel(handleSourcesSynced);
  initChatPanel();
  initCommitsPanel();
  initTreePanel(handleSourcesSynced);

  const initialWsId = getWorkspaceIdFromHash();
  await loadWorkspaces(initialWsId);

  // Определение начальной суб-панели из URL hash или активация дефолтной
  const panelFromHash = getPanelFromHash();
  if (panelFromHash) {
    switchWorkspaceSubTab(panelFromHash, false);
  } else {
    updateUrlWithPanel(getActiveSubTabId());
  }

  // Опрашиваем ТОЛЬКО активную суб-панель
  await fetchActiveSubTabOnly(true);

  // Слушатель единого события context:changed
  document.addEventListener('context:changed', async (e) => {
    if (!isWorkspaceTabActive()) return;
    const wsId = e.detail?.workspaceId || getWorkspaceIdFromHash();
    if (wsId) {
      await selectWorkspaceInTab(wsId);
    } else {
      await fetchActiveSubTabOnly(true);
    }
  });

  // Реакция на глобальное переключение на вкладку tab-workspace
  document.addEventListener('tab:activated', async (e) => {
    if (e.detail?.tabId === TAB_ID || e.detail?.tabId === 'workspace') {
      const targetFromHash = getPanelFromHash();
      if (targetFromHash && targetFromHash !== getActiveSubTabId()) {
        switchWorkspaceSubTab(targetFromHash, false);
      }
      await fetchActiveSubTabOnly();
    }
  });
}

// Экспорт для глобального доступа и совместимости
window.initWorkspaceTab = initWorkspaceTab;
window.switchFilesSubTab = switchFilesSubTab;
window.switchWorkspaceSubTab = switchWorkspaceSubTab;
window.getActiveWorkspaceSubTabId = getActiveWorkspaceSubTabId;
window.getWorkspacePanelFromHash = getPanelFromHash;
window.updateWorkspaceUrlWithPanel = updateUrlWithPanel;
window.normalizeWorkspaceSubTabId = normalizeSubTabId;
window.fetchActiveWorkspaceSubTab = fetchActiveSubTabOnly;
export { deleteCurrentWorkspace };
window.deleteCurrentWorkspace = deleteCurrentWorkspace;
window.selectWorkspaceInTab = selectWorkspaceInTab;

// Auto-initialize when loaded
initWorkspaceTab();
