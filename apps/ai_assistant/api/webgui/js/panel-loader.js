/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Universal Panel Loader
 * =============================================================================
 * Description:
 *   Клиентский модуль автоматической загрузки данных для панелей интерфейса.
 *   Каждая панель с div id="panel-{panel_id}" или data-panel-id="{panel_id}"
 *   при инициализации/активации страницы и вкладок вызывает эндпоинт:
 *   GET /api/v1/panel/{panel_id} -> выполнение SQL-запроса или выборки данных.
 *
 * Usage Examples:
 *   HTML:
 *     <div id="panel-timeline" class="ui-panel" data-panel-id="panel-timeline">...</div>
 *     <script src="/html/js/panel-loader.js?v=20261015_v1" type="module"></script>
 *
 *   JavaScript:
 *     import { loadPanelData, initPanels, registerPanelRenderer } from '/html/js/panel-loader.js';
 *     await loadPanelData('panel-timeline');
 *
 * File: panel-loader.js
 * Project: ai-windows-admin
 * Package: apps/ai_assistant/api/webgui/js
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-24 22:20:00
 * =============================================================================
 */

const panelRenderers = new Map();
const panelDataCache = new Map();
const pendingRequests = new Map();

/**
 * Загружает данные для панели через GET /api/v1/panel/{panel_id}.
 * @param {string} panelId - Идентификатор панели
 * @param {Object} [options] - Дополнительные параметры запроса (limit, force)
 * @returns {Promise<Object>} Данные ответа выборки/SQL-запроса
 */
export async function loadPanelData(panelId, options = {}) {
  if (!panelId) return null;
  const cleanId = panelId.trim();

  // Вкладка «О системе» обслуживается исключительно единым эндпоинтом /api/v1/about-system/bundle.
  // Разрозненные запросы отдельных панелей строго запрещены.
    // Панели рабочего пространства tab_workspace обслуживаются изолированно модулем tab_workspace.
  const WS_SUBPANELS = new Set([
    'panel-files', 'panel-documents', 'panel-qa', 'panel-chat', 'panel-sources', 'panel-facts', 'panel-workspace'
  ]);
  if (WS_SUBPANELS.has(cleanId)) {
    return null;
  }

  if (cleanId.startsWith('panel-about-') || cleanId.startsWith('about_system-')) {
    return null;
  }

  // Если уже выполняется запрос для этого panelId, возвращаем существующий промис
  if (pendingRequests.has(cleanId) && !options.force) {
    return pendingRequests.get(cleanId);
  }

  const limit = options.limit || 60;
  let activeWsId = options.workspace_id;
  if (!activeWsId && typeof window !== 'undefined' && typeof window.getActiveWorkspaceId === 'function') {
    activeWsId = window.getActiveWorkspaceId();
  }
  let activeRepo = options.repo_path;
  if (!activeRepo && typeof window !== 'undefined' && typeof window.getActiveRepoPath === 'function') {
    activeRepo = window.getActiveRepoPath();
  }

  let queryParams = `limit=${limit}&t=${Date.now()}`;
  if (activeWsId) queryParams += `&workspace_id=${encodeURIComponent(activeWsId)}`;
  if (activeRepo) queryParams += `&repo_path=${encodeURIComponent(activeRepo)}`;

  const url = `/api/v1/panel/${encodeURIComponent(cleanId)}?${queryParams}`;
  const el = document.getElementById(cleanId) || document.querySelector(`[data-panel-id="${cleanId}"]`);
  if (el) {
    el.setAttribute('data-panel-status', 'loading');
  }

  const fetchPromise = (async () => {
    try {
      let res = await fetch(url);
      if (!res.ok) {
        // Fallback на альтернативный префикс /v1/panel/
        const altUrl = `/v1/panel/${encodeURIComponent(cleanId)}?${queryParams}`;
        res = await fetch(altUrl);
      }
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }
      const result = await res.json();
      panelDataCache.set(cleanId, result);

      if (el) {
        el.setAttribute('data-panel-status', 'loaded');
        if (result.sql) {
          el.setAttribute('data-panel-sql', result.sql);
        }
        el._panelData = result;
      }

      // Вызов зарегистрированного рендерера
      const renderer = panelRenderers.get(cleanId);
      if (typeof renderer === 'function') {
        try {
          renderer(result, el);
        } catch (rErr) {
          console.warn(`[PanelLoader] Ошибка рендера панели ${cleanId}:`, rErr);
        }
      }

      // Диспетчеризация кастомных событий
      const eventDetail = { panelId: cleanId, result, data: result.data || [], sql: result.sql };
      document.dispatchEvent(new CustomEvent('panel:data', { detail: eventDetail }));
      document.dispatchEvent(new CustomEvent(`panel:${cleanId}:loaded`, { detail: eventDetail }));

      return result;
    } catch (err) {
      console.warn(`[PanelLoader] Ошибка загрузки данных панели ${cleanId}:`, err);
      if (el) {
        el.setAttribute('data-panel-status', 'error');
      }
      return { status: 'error', panel_id: cleanId, error: err.message, data: [] };
    } finally {
      pendingRequests.delete(cleanId);
    }
  })();

  pendingRequests.set(cleanId, fetchPromise);
  return fetchPromise;
}

/**
 * Регистрирует пользовательскую функцию отрисовки для панели.
 * @param {string} panelId 
 * @param {Function} renderFn 
 */
export function registerPanelRenderer(panelId, renderFn) {
  if (panelId && typeof renderFn === 'function') {
    panelRenderers.set(panelId, renderFn);
  }
}

/**
 * Инициализирует и опрашивает все панели внутри контейнера.
 * @param {HTMLElement|Document} [container=document] 
 */
/**
 * Извлекает активную вкладку и активную панель из URL в соответствии со стандартом workspace-url-routing.
 * Например: http://localhost:8002/#tab-workspace#panel-files#workspace=%D7%93%D7%95%D7%93_%D7%9E%D7%95%D7%A9%D7%94
 * @param {string} [rawHash]
 * @returns {{ tabId: string, panelId: string|null, workspaceId: string|null }}
 */
export function getActiveTabAndPanelFromUrl(rawHash = null) {
  const hash = (rawHash !== null ? rawHash : (typeof location !== 'undefined' ? location.hash : '')) || '';
  const clean = hash.replace(/^#/, '');
  const parts = clean.split('#');

  const rawTab = parts[0] || 'tab-workspace';
  const tabId = rawTab.startsWith('tab-') ? rawTab : `tab-${rawTab}`;

  let panelId = null;
  let workspaceId = null;

  for (let i = 1; i < parts.length; i++) {
    const part = parts[i];
    if (part.startsWith('workspace=')) {
      try {
        workspaceId = decodeURIComponent(part.slice(10));
      } catch (_) {
        workspaceId = part.slice(10);
      }
    } else if (part.startsWith('panel-') || part.startsWith('step')) {
      panelId = part;
    } else if (!workspaceId && !part.includes('=')) {
      try {
        workspaceId = decodeURIComponent(part);
      } catch (_) {
        workspaceId = part;
      }
    }
  }

  if (!panelId) {
    if (tabId === 'tab-workspace' || tabId === 'workspace') {
      panelId = 'panel-files';
    } else if (tabId === 'tab-commits' || tabId === 'commits') {
      panelId = 'panel-commits';
    } else if (tabId === 'tab-timeline' || tabId === 'timeline') {
      panelId = 'panel-timeline';
    } else if (tabId === 'tab-diff' || tabId === 'diff') {
      panelId = 'panel-diff-stats';
    } else if (tabId === 'tab-wikillm' || tabId === 'wikillm') {
      panelId = 'panel-wikillm-entities';
    } else if (tabId === 'tab-graph' || tabId === 'graph') {
      panelId = 'panel-knowledge-links';
    } else if (tabId === 'tab-rag' || tabId === 'rag') {
      panelId = 'panel-rag-chunks';
    } else if (tabId === 'tab-verification' || tabId === 'verification') {
      panelId = 'panel-verification-pipeline';
    } else if (tabId === 'tab-status' || tabId === 'status') {
      panelId = 'panel-system-status';
    }
  }

  return { tabId, panelId, workspaceId };
}

/**
 * Инициализирует и опрашивает СТРОГО активную панель текущей активной вкладки.
 * @param {HTMLElement|Document} [container=document] 
 */
export function initPanels(container = document) {
  const { tabId, panelId, workspaceId } = getActiveTabAndPanelFromUrl();

  // Если открыта вкладка tab-workspace — её подпанели обслуживаются модулем tab_workspace
  if (tabId === 'tab-workspace' || tabId === 'workspace') {
    return;
  }

  if (panelId) {
    loadPanelData(panelId, { workspace_id: workspaceId });
  }
}

// Экспорт в глобальный контекст window
if (typeof window !== 'undefined') {
  window.loadPanelData = loadPanelData;
  window.registerPanelRenderer = registerPanelRenderer;
  window.initPanels = initPanels;
  window.getActiveTabAndPanelFromUrl = getActiveTabAndPanelFromUrl;

  // Слушатель единого события context:changed: опрашивает ТОЛЬКО активную панель на вкладке
  const onContextChanged = (e) => {
    panelDataCache.clear();
    const { tabId, panelId, workspaceId } = getActiveTabAndPanelFromUrl();
    const activeWs = e.detail?.workspaceId || workspaceId || (typeof window.getActiveWorkspaceId === 'function' ? window.getActiveWorkspaceId() : null);
    const activeRepo = e.detail?.repoPath || (typeof window.getActiveRepoPath === 'function' ? window.getActiveRepoPath() : null);

    // Если сейчас открыта вкладка tab-workspace, её опрашивает tab_workspace/main.js
    if (tabId === 'tab-workspace' || tabId === 'workspace') {
      if (typeof window.fetchActiveWorkspaceSubTab === 'function') {
        window.fetchActiveWorkspaceSubTab(true);
      }
      return;
    }

    // Для остальных вкладок опрашивается СТРОГО активная панель
    if (panelId) {
      loadPanelData(panelId, { force: true, workspace_id: activeWs, repo_path: activeRepo });
    }
  };
  document.addEventListener('context:changed', onContextChanged);
  document.addEventListener('workspace:changed', onContextChanged);
  document.addEventListener('repo:changed', onContextChanged);

  // Опрос активной панели при переключении вкладки
  document.addEventListener('tab:activated', (e) => {
    const targetTabId = e.detail?.tabId;
    if (!targetTabId || targetTabId === 'tab-workspace' || targetTabId === 'workspace') {
      return;
    }
    const { panelId, workspaceId } = getActiveTabAndPanelFromUrl();
    if (panelId) {
      loadPanelData(panelId, { workspace_id: workspaceId });
    }
  });

  // Первичный опрос только активной панели при готовности DOM
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => initPanels(document));
  } else {
    setTimeout(() => initPanels(document), 50);
  }
}
