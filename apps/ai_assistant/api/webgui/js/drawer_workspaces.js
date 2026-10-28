/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Left Drawer Workspaces Navigator
 * =============================================================================
 * Description:
 *   Модуль динамического управления списком рабочих областей в боковом меню (Offcanvas).
 *   Обеспечивает:
 *   - Загрузку и отрисовку списка рабочих областей из REST API /api/v1/workspaces.
 *   - Каноническую навигацию по клику: переход на #tab-workspace#panel-files#workspace=<id>.
 *   - Мгновенное переключение активного рабочего пространства и закрытие выдвижного меню.
 *   - Подсветку активного пространства и синхронизацию с верхним меню и вкладками.
 *   - Надежный поиск рабочих областей с поддержкой Unicode (NFC), иврита и URL encoding.
 *
 * File: drawer_workspaces.js
 * Package: apps/ai_assistant/api/webgui/js
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-28 02:35:00
 * =============================================================================
 */

let cachedWorkspaces = [];
let currentDrawerActiveId = '';

/**
 * Находит рабочую область в списке по ID, имени или закодированному URI.
 * Поддерживает нормализацию Unicode (NFC), нечувствительность к регистру и замену пробелов.
 * @param {Array} list - Список объектов рабочих областей
 * @param {string} target - Идентификатор или имя для поиска
 * @returns {Object|null}
 */
export function findWorkspaceMatch(list, target) {
  if (!target || !Array.isArray(list) || list.length === 0) return null;

  let decoded = target;
  try {
    decoded = decodeURIComponent(target);
  } catch (_) {}

  const cleanTarget = String(decoded).trim().normalize('NFC');
  const cleanTargetLower = cleanTarget.toLowerCase();

  // 1. Точное совпадение по workspace_id (с NFC нормализацией)
  let found = list.find((w) => (w.workspace_id || '').normalize('NFC') === cleanTarget);
  if (found) return found;

  // 2. Без учета регистра
  found = list.find(
    (w) => (w.workspace_id || '').normalize('NFC').toLowerCase() === cleanTargetLower
  );
  if (found) return found;

  // 3. По отображаемому имени name
  found = list.find(
    (w) => (w.name || '').normalize('NFC').toLowerCase() === cleanTargetLower
  );
  if (found) return found;

  // 4. По замене подчеркиваний на пробелы и наоборот
  const targetWithSpaces = cleanTargetLower.replace(/_/g, ' ');
  const targetWithUnderscores = cleanTargetLower.replace(/\s+/g, '_');

  found = list.find((w) => {
    const idLower = (w.workspace_id || '').normalize('NFC').toLowerCase();
    const nameLower = (w.name || '').normalize('NFC').toLowerCase();
    return (
      idLower === targetWithUnderscores ||
      nameLower === targetWithSpaces ||
      idLower.replace(/_/g, ' ') === targetWithSpaces ||
      nameLower.replace(/\s+/g, '_') === targetWithUnderscores
    );
  });

  return found || null;
}

/**
 * Экранирует спецсимволы для безопасной вставки в HTML.
 * @param {string} str 
 * @returns {string}
 */
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * Закрывает открытые боковые меню Offcanvas и снимает оверлеи.
 */
export function closeOffcanvasDrawer() {
  const ocEl = document.getElementById('leftSideNavOffcanvas');
  if (ocEl && window.bootstrap && window.bootstrap.Offcanvas) {
    try {
      const oc = window.bootstrap.Offcanvas.getInstance(ocEl);
      if (oc) oc.hide();
    } catch (_) {}
  }
  setTimeout(() => {
    document.querySelectorAll('.offcanvas-backdrop, .modal-backdrop').forEach((b) => b.remove());
    document.body.classList.remove('modal-open');
    document.body.style.overflow = '';
    document.body.style.pointerEvents = '';
  }, 50);
}

/**
 * Подсвечивает активное рабочее пространство в левом меню.
 * @param {string} wsId 
 */
export function highlightActiveDrawerWorkspace(wsId) {
  currentDrawerActiveId = wsId || '';
  const container = document.getElementById('drawer-workspaces-dynamic-items');
  if (!container) return;

  const matched = findWorkspaceMatch(cachedWorkspaces, wsId);
  const matchedId = matched ? matched.workspace_id : wsId;

  container.querySelectorAll('.drawer-ws-item').forEach((btn) => {
    const btnWsId = btn.getAttribute('data-ws-id');
    const isTarget = btnWsId === matchedId;
    btn.classList.toggle('active', isTarget);

    const icon = btn.querySelector('.drawer-ws-icon');
    if (icon) {
      if (isTarget) {
        icon.className = 'bi bi-folder-check text-success fs-6 flex-shrink-0 drawer-ws-icon';
      } else {
        icon.className = 'bi bi-folder text-muted fs-6 flex-shrink-0 drawer-ws-icon';
      }
    }

    const badge = btn.querySelector('.drawer-ws-status-badge');
    if (badge && isTarget) {
      badge.className = 'badge bg-success-subtle text-success border font-size-75 drawer-ws-status-badge';
      badge.textContent = 'активно';
    }
  });
}

/**
 * Отрисовывает динамический список рабочих пространств в боковом меню.
 * @param {Array} workspaces - Список рабочих пространств
 * @param {string} [activeWsId] - Идентификатор текущей активной области
 */
export function renderDrawerWorkspaces(workspaces, activeWsId = '') {
  const container = document.getElementById('drawer-workspaces-dynamic-items');
  const countBadge = document.getElementById('drawer-ws-count-badge');
  if (!container) return;

  const list = Array.isArray(workspaces) ? workspaces : [];
  cachedWorkspaces = list;

  if (countBadge) {
    countBadge.textContent = String(list.length);
  }

  const effectiveActive = activeWsId || currentDrawerActiveId || (list[0]?.workspace_id || '');
  const matchedActive = findWorkspaceMatch(list, effectiveActive);
  const activeId = matchedActive ? matchedActive.workspace_id : effectiveActive;
  currentDrawerActiveId = activeId;

  if (list.length === 0) {
    container.innerHTML = `
      <div class="p-3 text-center text-muted small">
        <i class="bi bi-folder2-open d-block mb-1 fs-5"></i>
        <span>Нет рабочих областей</span>
      </div>
    `;
    return;
  }

  container.innerHTML = list
    .map((ws) => {
      const isTarget = ws.workspace_id === activeId;
      const docsCount = ws.documents_count || 0;
      const factsCount = ws.active_facts_count || 0;
      const title = escapeHtml(ws.name || ws.workspace_id);
      const subInfo = `${docsCount} док. | ${factsCount} факт.`;

      return `
        <button class="list-group-item list-group-item-action d-flex align-items-center justify-content-between py-2 px-3 drawer-ws-item ${
          isTarget ? 'active' : ''
        }" data-ws-id="${escapeHtml(ws.workspace_id)}" type="button" title="Рабочее пространство: ${title}">
          <div class="d-flex align-items-center gap-2 overflow-hidden text-truncate">
            <i class="bi ${
              isTarget ? 'bi-folder-check text-success' : 'bi-folder text-muted'
            } fs-6 flex-shrink-0 drawer-ws-icon"></i>
            <div class="text-truncate text-start">
              <div class="fw-medium text-truncate">${title}</div>
              <div class="small text-muted text-truncate font-size-75">${subInfo}</div>
            </div>
          </div>
          <span class="badge ${
            isTarget
              ? 'bg-success-subtle text-success border'
              : 'bg-secondary-subtle text-secondary border'
          } font-size-75 flex-shrink-0 ms-2 drawer-ws-status-badge">
            ${isTarget ? 'активно' : `${docsCount} док.`}
          </span>
        </button>
      `;
    })
    .join('');
}

/**
 * Переключает на указанную рабочую область по каноническому стандарту URL.
 * Формат: #tab-workspace#panel-files#workspace=<id>
 * @param {string} workspaceId - Идентификатор рабочей области
 * @param {string} [panelId='panel-files'] - Идентификатор целевой панели
 */
export async function switchToWorkspace(workspaceId, panelId = 'panel-files') {
  if (!workspaceId) return;

  const matched = findWorkspaceMatch(cachedWorkspaces, workspaceId);
  const finalWsId = matched ? matched.workspace_id : workspaceId;

  // 1. Формирование канонического URL стандарта workspace-url-routing
  const targetHash = `#tab-workspace#${panelId}#workspace=${encodeURIComponent(finalWsId)}`;
  try {
    if (typeof location !== 'undefined' && location.hash !== targetHash) {
      history.pushState(null, null, targetHash);
    }
  } catch (_) {}

  // 2. Активация вкладки tab-workspace (с lazyLoad при необходимости)
  if (typeof window.switchTab === 'function') {
    await window.switchTab('tab-workspace');
  }

  // 3. Выбор рабочей области на вкладке Workspace
  if (typeof window.selectWorkspaceInTab === 'function') {
    await window.selectWorkspaceInTab(finalWsId);
  }

  // 4. Переключение на суб-панель файлов/документов
  if (typeof window.switchWorkspaceSubTab === 'function') {
    window.switchWorkspaceSubTab(panelId, false);
  }

  // 5. Синхронизация верхнего выпадающего селектора репозитория
  if (typeof window.updateTopWorkspaceDropdown === 'function') {
    await window.updateTopWorkspaceDropdown(finalWsId);
  }

  // 6. Подсветка в боковом меню
  highlightActiveDrawerWorkspace(finalWsId);

  // 7. Закрытие оффканвас панели
  closeOffcanvasDrawer();
}

/**
 * Запрашивает актуальный список рабочих пространств с сервера и отрисовывает их в меню.
 * @param {string} [activeWsId] - Опциональный идентификатор активной области
 * @param {number} [retries=2] - Количество повторных попыток при сбое
 * @returns {Promise<Array>}
 */
export async function fetchAndRenderDrawerWorkspaces(activeWsId = '', retries = 2) {
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const res = await fetch('/api/v1/workspaces');
      if (res.ok) {
        const data = await res.json();
        const list = data.workspaces || [];
        cachedWorkspaces = list;
        renderDrawerWorkspaces(list, activeWsId);
        return list;
      }
      if (attempt < retries) {
        await new Promise((r) => setTimeout(r, 600));
      }
    } catch (err) {
      if (attempt < retries) {
        await new Promise((r) => setTimeout(r, 600));
      } else {
        console.warn('[DrawerWorkspaces] Ошибка загрузки списка рабочих пространств:', err);
      }
    }
  }
  return cachedWorkspaces || [];
}

/**
 * Инициализирует модуль навигации по рабочим областям бокового меню.
 */
export async function initDrawerWorkspaces() {
  // 1. Делегированный слушатель кликов по элементам рабочих пространств в левом меню
  const group = document.getElementById('drawer-workspaces-group');
  if (group) {
    group.addEventListener('click', (e) => {
      const wsBtn = e.target.closest('.drawer-ws-item, [data-ws-id]');
      if (wsBtn) {
        const wsId = wsBtn.getAttribute('data-ws-id');
        if (wsId) {
          e.preventDefault();
          switchToWorkspace(wsId, 'panel-files');
        }
      }
    });
  }

  // 2. Загружаем и отрисовываем текущие пространства
  const currentWs = typeof window.getActiveWorkspaceId === 'function' ? window.getActiveWorkspaceId() : '';
  await fetchAndRenderDrawerWorkspaces(currentWs);

  // 3. Слушаем единое событие context:changed
  document.addEventListener('context:changed', (e) => {
    const wsId = e.detail?.workspaceId;
    if (wsId) {
      highlightActiveDrawerWorkspace(wsId);
    }
  });
}

// Экспорт в глобальный контекст для взаимодействия между модулями
if (typeof window !== 'undefined') {
  window.switchToWorkspace = switchToWorkspace;
  window.renderDrawerWorkspaces = renderDrawerWorkspaces;
  window.fetchAndRenderDrawerWorkspaces = fetchAndRenderDrawerWorkspaces;
  window.highlightActiveDrawerWorkspace = highlightActiveDrawerWorkspace;
  window.findWorkspaceMatch = findWorkspaceMatch;
  window.initDrawerWorkspaces = initDrawerWorkspaces;
}
