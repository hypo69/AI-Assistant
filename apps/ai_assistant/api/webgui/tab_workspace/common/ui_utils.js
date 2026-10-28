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
 * Updated: 2026-10-26 01:21:00
 * =============================================================================
 */

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
  if (!subtabId) return 'panel-files';
  const s = String(subtabId).toLowerCase().trim().replace(/^#/, '');
  if (s.includes('tree')) {
    return 'panel-tree';
  }
  if (s.includes('commit')) {
    return 'panel-commits';
  }
  if (s.includes('chat') || s.includes('talk') || s.includes('dialog')) {
    return 'panel-chat';
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
  return 'panel-files';
}

/**
 * Возвращает идентификатор текущей активной суб-панели.
 * @returns {'panel-workspace' | 'panel-documents' | 'panel-qa'}
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
  return 'panel-files';
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
        if (seg.startsWith('panel-') || seg.startsWith('step') || seg === 'qa' || seg === 'documents' || seg === 'files' || seg === 'commits' || seg === 'chat' || seg === 'tree') {
          return normalizeSubTabId(seg);
        }
      }
      // Если передана рабочая область (workspace=), но панель не указана явно,
      // по стандарту workspace-url-routing дефолтной панелью является panel-files!
      const hasWs = parts.some((p) => p.startsWith('workspace='));
      if (hasWs) {
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
  if (parts.length >= 2 && !parts[1].startsWith('panel-') && !parts[1].startsWith('step') && parts[1] !== 'qa') {
    try {
      return decodeURIComponent(parts[1]).trim().normalize('NFC');
    } catch (_) {
      return parts[1].trim().normalize('NFC');
    }
  }
  return null;
}

/**
 * Обновляет URL hash активной суб-панелью и пространством:
 * #tab-workspace#panel-files#workspace=<wsId> без перезагрузки страницы.
 * @param {string} panelId - Идентификатор панели
 * @param {string|null} [workspaceId=null] - Идентификатор рабочего пространства
 */
export function updateUrlWithPanel(panelId, workspaceId = null) {
  if (typeof history === 'undefined' || typeof location === 'undefined') return;
  const canonical = normalizeSubTabId(panelId);
  const search = location.search || '';

  let wsId = workspaceId;
  if (!wsId && typeof location !== 'undefined') {
    const parts = (location.hash || '').replace(/^#/, '').split('#');
    const wsPart = parts.find(p => p.startsWith('workspace='));
    if (wsPart) {
      wsId = decodeURIComponent(wsPart.slice(10));
    }
  }

  const wsSuffix = wsId ? `#workspace=${encodeURIComponent(wsId)}` : '';
  const newHash = `#${TAB_ID}#${canonical}${wsSuffix}`;
  if (location.hash !== newHash) {
    try {
      history.replaceState(null, null, `${location.pathname}${search}${newHash}`);
      document.dispatchEvent(new CustomEvent('panel:activated', { detail: { tabId: TAB_ID, panelId: canonical, workspaceId: wsId } }));
    } catch (_) {}
  }
}

/**
 * Выполняет сетевой запрос с автоматической распаковкой JSON и обработкой ошибок.
 * @param {string} url - URL эндпоинта
 * @param {Object} [options] - Параметры fetch
 * @returns {Promise<any>}
 */
export async function fetchJson(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const err = await res.json();
      if (err.detail) detail = err.detail;
    } catch (_) {}
    throw new Error(detail);
  }
  return res.json();
}
