/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Graph Panel
 * =============================================================================
 * Description:
 *   Изолированная панель темпорального графа (panel-knowledge-links).
 *   Отображает связи между ревизиями Git и фактами WikiLLM, поддерживает
 *   фильтрацию статусов и мягкую инвалидацию связей (POST /api/v1/supersede).
 *
 * File: panel.js
 * Package: apps/ai_assistant/api/webgui/tab_graph/panel_graph
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-17 00:47:00
 * =============================================================================
 */

import { registerPanelRenderer, loadPanelData } from '../../js/panel-loader.js';

let rawLinks = [];

export function renderGraphTable(links) {
  const tbody = document.getElementById('graph-table-body');
  const countBadge = document.getElementById('graph-count-badge');
  if (!tbody) return;

  if (countBadge) countBadge.textContent = `${links.length} связей`;

  if (links.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="text-center py-3 text-muted">Связи темпорального графа не зафиксированы.</td></tr>`;
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

      try {
        const res = await fetch('/api/v1/supersede', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ source_id: sourceId, target_id: targetId, invalidating_commit: commit })
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        loadPanelData('panel-knowledge-links', { force: true });
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

export function initGraphPanel() {
  registerPanelRenderer('panel-knowledge-links', renderGraphPanel);

  document.getElementById('graph-status-filter')?.addEventListener('change', filterLinks);
  document.getElementById('graph-refresh-btn')?.addEventListener('click', () => {
    loadPanelData('panel-knowledge-links', { force: true });
  });

  loadPanelData('panel-knowledge-links');
}
