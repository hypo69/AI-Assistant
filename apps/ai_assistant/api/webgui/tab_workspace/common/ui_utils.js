/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Workspace UI Utilities
 * =============================================================================
 * Description:
 *   Вспомогательные утилиты для сетевых запросов, нормализации и формирования
 *   составного URL с активной суб-панелью (#tab-workspace#<panel_id>) в стиле
 *   интерфейса apps/windows/api/webgui.
 *
 * File: ui_utils.js
 * Package: apps/ai_assistant/api/webgui/tab_workspace/common
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-10 13:15:00
 * =============================================================================
 */

/**
 * Единая функция локализации через window.i18n (I18nManager) или window.i18next с fallback.
 * @param {string} key - Ключ локализации
 * @param {string} [fallback=''] - Значение по умолчанию
 * @returns {string}
 */
export function t(key, fallback = '') {
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
  return fallback;
}

if (typeof window !== 'undefined') {
  window.t = t;
}

export const TAB_ID = 'tab-workspace';

/**
 * Проверяет, активна ли данная вкладка в текущий момент.
 * @returns {boolean}
 */
export function isWorkspaceTabActive() {
  if (typeof document !== 'undefined' && document.hidden) {
    return false;
  }
  if (typeof window.isTabActive === 'function') {
    return Boolean(window.isTabActive(TAB_ID) || window.isTabActive('workspace'));
  }
  const pane = document.getElementById(TAB_ID) || document.getElementById('workspace');
  return pane ? pane.classList.contains('active') : false;
}

/**
 * Нормализует идентификатор суб-панели к каноническому panel_id.
 * @param {string} subtabId 
 * @returns {'panel-workspace' | 'panel-files' | 'panel-qa' | 'panel-tree'}
 */
export function normalizeSubTabId(subtabId) {
  if (!subtabId) return 'panel-chat';
  const s = String(subtabId).toLowerCase().trim().replace(/^#/, '');
  if (s.includes('file-editor') || s.includes('editor')) {
    return 'panel-file-editor';
  }
  if (s.includes('chat') || s.includes('talk') || s.includes('dialog')) {
    return 'panel-chat';
  }
  if (s.includes('tree')) {
    return 'panel-tree';
  }
  if (s.includes('commit')) {
    return 'panel-commits';
  }
  if (s.includes('qa') || s.includes('step3') || s.includes('ask') || s.includes('question') || s.includes('search')) {
    return 'panel-qa';
  }
  if (s.includes('doc') || s.includes('step2') || s.includes('fact')) {
    return 'panel-documents';
  }
  if (s.includes('file') || s.includes('workspace') || s.includes('step1') || s.includes('select') || s.includes('source') || s.includes('git')) {
    return 'panel-files';
  }
  return 'panel-chat';
}

/**
 * Нормализует идентификатор блока подменю панели Файлы.
 * @param {string} blockId
 * @returns {'dir' | 'track' | 'obsidian' | 'sources'}
 */
export function normalizeBlockId(blockId) {
  if (!blockId) return 'dir';
  const clean = String(blockId).toLowerCase().trim().replace(/^#/, '').replace(/^block-/, '');
  if (clean.includes('track') || clean.includes('add')) return 'track';
  if (clean.includes('obsidian') || clean.includes('vault')) return 'obsidian';
  if (clean.includes('source') || clean.includes('external')) return 'sources';
  return 'dir';
}

/**
 * Возвращает идентификатор активного подменю/блока панели Файлы.
 * @returns {string}
 */
export function getActiveFilesBlockId() {
  const activeBtn = document.querySelector('#ws-files-subtabs-nav button.active');
  if (activeBtn) {
    const bId = activeBtn.getAttribute('data-block-id');
    if (bId) return normalizeBlockId(bId);
    const target = activeBtn.getAttribute('data-bs-target') || '';
    return normalizeBlockId(target);
  }
  return 'dir';
}

/**
 * Извлекает блок подменю (block-<id>) из URL hash.
 * @param {string|null} [hash=null]
 * @returns {string|null}
 */
export function getBlockFromHash(hash = null) {
  const raw = (hash !== null ? hash : (typeof location !== 'undefined' ? location.hash : '')) || '';
  if (!raw) return null;
  const clean = raw.replace(/^#/, '');
  const parts = clean.split('#');
  const blockPart = parts.find((p) => p.startsWith('block-'));
  if (blockPart) {
    return normalizeBlockId(blockPart.slice('block-'.length));
  }
  return null;
}

/**
 * Возвращает идентификатор текущей активной суб-панели.
 * @returns {'panel-chat' | 'panel-files' | 'panel-documents' | 'panel-qa' | 'panel-commits' | 'panel-tree'}
 */
export function getActiveSubTabId() {
  const activeBtn = document.querySelector('#workspace-subtabs-nav button.active');
  if (activeBtn) {
    const pId = activeBtn.getAttribute('data-panel-id');
    if (pId) return normalizeSubTabId(pId);
    const target = activeBtn.getAttribute('data-bs-target') || '';
    return normalizeSubTabId(target);
  }
  const activePane = document.querySelector('#workspace-subtabs-content .tab-pane.active');
  if (activePane) {
    const pId = activePane.getAttribute('data-panel-id');
    if (pId) return normalizeSubTabId(pId);
    return normalizeSubTabId(activePane.id);
  }
  return 'panel-chat';
}

/**
 * Считывает суб-панель из URL hash (#tab-workspace#<panel_id>).
 * @returns {string|null} ID суб-панели или null
 */
export function getPanelFromHash() {
  const hash = (typeof location !== 'undefined' ? location.hash : '') || '';
  if (!hash) return null;
  const cleanHash = hash.replace(/^#/, '');
  const parts = cleanHash.split('#');
  if (parts.length >= 2) {
    const mainPart = parts[0];
    if (mainPart === TAB_ID || mainPart === 'workspace' || mainPart === 'tab_workspace') {
      for (let i = 1; i < parts.length; i++) {
        const seg = parts[i];
        if (seg.startsWith('block-')) continue;
        if (seg.startsWith('panel-') || seg.startsWith('step') || seg === 'qa' || seg === 'documents' || seg === 'files' || seg === 'commits' || seg === 'chat' || seg === 'tree') {
          return normalizeSubTabId(seg);
        }
      }
      // Если передана рабочая область (workspace=) или блок (block-), но панель не указана явно,
      // по стандарту workspace-url-routing дефолтной панелью является panel-files!
      const hasWs = parts.some((p) => p.startsWith('workspace='));
      const hasBlock = parts.some((p) => p.startsWith('block-'));
      if (hasWs || hasBlock) {
        return 'panel-files';
      }
    }
  } else if (parts.length === 1) {
    const single = parts[0];
    if (single !== TAB_ID && single !== 'workspace' && (single.startsWith('panel-') || single.startsWith('step'))) {
      return normalizeSubTabId(single);
    }
  }
  return null;
}

/**
 * Извлекает идентификатор рабочего пространства из URL hash.
 * @param {string|null} [hash=null]
 * @returns {string|null}
 */
export function getWorkspaceIdFromHash(hash = null) {
  const raw = (hash !== null ? hash : (typeof location !== 'undefined' ? location.hash : '')) || '';
  const clean = raw.replace(/^#/, '');
  const parts = clean.split('#');
  const wsPart = parts.find((p) => p.startsWith('workspace='));
  if (wsPart) {
    try {
      return decodeURIComponent(wsPart.slice('workspace='.length)).trim().normalize('NFC');
    } catch (_) {
      return wsPart.slice('workspace='.length).trim().normalize('NFC');
    }
  }
  for (let i = 1; i < parts.length; i++) {
    const part = parts[i];
    if (part.startsWith('panel-') || part.startsWith('step') || part.startsWith('block-') || part === 'qa') {
      continue;
    }
    try {
      return decodeURIComponent(part).trim().normalize('NFC');
    } catch (_) {
      return part.trim().normalize('NFC');
    }
  }
  return null;
}

/**
 * Обновляет URL hash активной суб-панелью, блоком подменю и пространством:
 * #tab-workspace#panel-files#block-<block_id>#workspace=<wsId> без перезагрузки страницы.
 * @param {string} panelId - Идентификатор панели
 * @param {string|null} [workspaceId=null] - Идентификатор рабочего пространства
 * @param {string|null} [blockId=null] - Идентификатор блока подменю
 */
export function updateUrlWithPanel(panelId, workspaceId = null, blockId = null) {
  if (typeof history === 'undefined' || typeof location === 'undefined') return;
  const canonical = normalizeSubTabId(panelId);
  const search = location.search || '';

  let wsId = workspaceId;
  let currentBlock = blockId;
  if (typeof location !== 'undefined') {
    const parts = (location.hash || '').replace(/^#/, '').split('#');
    if (!wsId) {
      const wsPart = parts.find((p) => p.startsWith('workspace='));
      if (wsPart) {
        wsId = decodeURIComponent(wsPart.slice(10));
      }
    }
    if (!currentBlock && canonical === 'panel-files') {
      const blkPart = parts.find((p) => p.startsWith('block-'));
      if (blkPart) {
        currentBlock = blkPart.replace(/^block-/, '');
      }
    }
  }

  if (!currentBlock && canonical === 'panel-files') {
    currentBlock = getActiveFilesBlockId() || 'dir';
  }

  const blockSuffix = (canonical === 'panel-files' && currentBlock)
    ? `#block-${currentBlock.replace(/^block-/, '')}`
    : '';
  const wsSuffix = wsId ? `#workspace=${encodeURIComponent(wsId)}` : '';
  const newHash = `#${TAB_ID}#${canonical}${blockSuffix}${wsSuffix}`;
  if (location.hash !== newHash) {
    try {
      history.replaceState(null, null, `${location.pathname}${search}${newHash}`);
      document.dispatchEvent(new CustomEvent('panel:activated', {
        detail: { tabId: TAB_ID, panelId: canonical, blockId: currentBlock, workspaceId: wsId }
      }));
    } catch (_) {}
  }
}

const inFlightRequests = new Map();

/**
 * Нормализует идентификатор рабочего пространства:
 * декодирование URL, приведение к NFC, удаление префикса ws-, замена пробелов на _, нижний регистр.
 * @param {string|null} id
 * @returns {string}
 */
export function normalizeWorkspaceId(id) {
  if (!id) return '';
  let clean = String(id).trim();
  try {
    clean = decodeURIComponent(clean);
  } catch (_) {}
  return clean
    .normalize('NFC')
    .replace(/^ws-/, '')
    .trim()
    .replace(/\s+/g, '_')
    .toLowerCase();
}

/**
 * Проверяет эквивалентность двух идентификаторов рабочих областей независимо от пробелов, подчеркиваний и URL-кодирования.
 * @param {string|null} id1
 * @param {string|null} id2
 * @returns {boolean}
 */
export function areWorkspacesEqual(id1, id2) {
  if (!id1 && !id2) return true;
  if (!id1 || !id2) return false;
  return normalizeWorkspaceId(id1) === normalizeWorkspaceId(id2);
}

if (typeof window !== 'undefined') {
  window.normalizeWorkspaceId = normalizeWorkspaceId;
  window.areWorkspacesEqual = areWorkspacesEqual;
}

/**
 * Выполняет сетевой запрос с автоматической распаковкой JSON, обработкой ошибок и дедупликацией GET-запросов на лету.
 * @param {string} url - URL эндпоинта
 * @param {Object} [options] - Параметры fetch
 * @returns {Promise<any>}
 */
export async function fetchJson(url, options = {}) {
  const isGet = !options.method || options.method.toUpperCase() === 'GET';
  if (isGet && inFlightRequests.has(url)) {
    return inFlightRequests.get(url);
  }

  const promise = (async () => {
    try {
      const res = await fetch(url, options);
      if (!res.ok) {
        let detail = `HTTP ${res.status}`;
        try {
          const err = await res.json();
          if (err.detail) detail = err.detail;
        } catch (_) {}
        throw new Error(detail);
      }
      return await res.json();
    } finally {
      if (isGet) {
        inFlightRequests.delete(url);
      }
    }
  })();

  if (isGet) {
    inFlightRequests.set(url, promise);
  }
  return promise;
}
