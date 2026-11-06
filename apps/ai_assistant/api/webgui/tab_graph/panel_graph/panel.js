/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Graph Panel
 * =============================================================================
 * Description:
 *   Изолированная панель темпорального графа (panel-knowledge-links).
 *   Отображает связи между ревизиями Git и фактами активного рабочего пространства,
 *   поддерживает фильтрацию статусов и мягкую инвалидацию связей (POST /api/v1/supersede).
 *
 * File: panel.js
 * Package: apps/ai_assistant/api/webgui/tab_graph/panel_graph
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-06 23:15:00
 * =============================================================================
 */

import { registerPanelRenderer, loadPanelData } from '../../js/panel-loader.js';

let rawLinks = [];

export function getActiveWorkspace() {
  if (typeof window !== 'undefined' && typeof window.getActiveWorkspaceId === 'function') {
    return window.getActiveWorkspaceId() || null;
  }
  return null;
}

export function updateWorkspaceBadge(wsId) {
  const badge = document.getElementById('graph-workspace-badge');
  if (badge) {
    badge.textContent = wsId ? `Рабочая область: ${wsId}` : 'Рабочая область: не выбрана';
  }
}

export function renderGraphTable(links) {
  const tbody = document.getElementById('graph-table-body');
  const countBadge = document.getElementById('graph-count-badge');
  const currentWs = getActiveWorkspace();
  updateWorkspaceBadge(currentWs);

  if (!tbody) return;

  if (countBadge) countBadge.textContent = `${links.length} связей`;

  if (links.length === 0) {
    const emptyMsg = currentWs
      ? `В рабочей области «${currentWs}» связи темпорального графа пока не зафиксированы.`
      : 'Рабочая область не выбрана. Выберите рабочую область для просмотра темпорального графа.';
    tbody.innerHTML = `<tr><td colspan="6" class="text-center py-4 text-muted">${emptyMsg}</td></tr>`;
    return;
  }

  tbody.innerHTML = links.map(l => {
    const src = l.source_id || '';
    const rel = l.relation_type || '';
    const tgt = l.target_id || '';
    const valid = `${(l.valid_from || 'HEAD').slice(0, 8)} → ${(l.valid_to || '∞').slice(0, 8)}`;
    const status = l.status || 'ACTIVE';
    const isSup = status === 'SUPERSEDED';
    const badgeClass = isSup ? 'bg-secondary text-secondary-emphasis' : 'bg-success-subtle text-success border';

    return `
      <tr>
        <td><span class="badge bg-body-secondary text-body font-monospace">${src.slice(0, 10)}</span></td>
        <td><span class="badge bg-primary-subtle text-primary border">${rel}</span></td>
        <td><span class="fw-medium">${tgt}</span></td>
        <td class="font-monospace small text-muted">${valid}</td>
        <td><span class="badge ${badgeClass}">${status}</span></td>
        <td class="text-end">
          ${!isSup ? `
            <button class="btn btn-outline-danger btn-sm py-0 px-2 supersede-btn" data-src="${src}" data-tgt="${tgt}">
              Инвалидировать
            </button>
          ` : '<span class="text-muted small">Архив</span>'}
        </td>
      </tr>
    `;
  }).join('');

  tbody.querySelectorAll('.supersede-btn').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      const sourceId = e.currentTarget.getAttribute('data-src');
      const targetId = e.currentTarget.getAttribute('data-tgt');
      const commit = prompt('Введите хэш отменяющего коммита:', 'HEAD');
      if (!commit) return;

      const wsId = getActiveWorkspace();

      try {
        const res = await fetch('/api/v1/supersede', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            source_id: sourceId,
            target_id: targetId,
            invalidating_commit: commit,
            workspace_id: wsId
          })
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        refreshGraphData();
      } catch (err) {
        alert(`Ошибка инвалидации: ${err.message}`);
      }
    });
  });
}

export function filterLinks() {
  const filterVal = document.getElementById('graph-status-filter')?.value || 'ALL';
  if (filterVal === 'ALL') {
    renderGraphTable(rawLinks);
  } else {
    renderGraphTable(rawLinks.filter(l => (l.status || 'ACTIVE') === filterVal));
  }
}

export function renderGraphPanel(result, panelEl) {
  rawLinks = result?.data || [];
  filterLinks();
}

export function refreshGraphData() {
  const wsId = getActiveWorkspace();
  updateWorkspaceBadge(wsId);
  loadPanelData('panel-knowledge-links', { force: true, workspace_id: wsId });
}

export function initGraphPanel() {
  registerPanelRenderer('panel-knowledge-links', renderGraphPanel);

  document.getElementById('graph-status-filter')?.addEventListener('change', filterLinks);
  document.getElementById('graph-refresh-btn')?.addEventListener('click', refreshGraphData);

  // Автоматическое обновление графа при переключении рабочего пространства
  window.addEventListener('workspace-changed', refreshGraphData);
  window.addEventListener('workspace:switched', refreshGraphData);
  window.addEventListener('hashchange', () => {
    const curWs = getActiveWorkspace();
    updateWorkspaceBadge(curWs);
  });

  refreshGraphData();
}
