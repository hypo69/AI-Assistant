/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Facts Panel
 * =============================================================================
 * Description:
 *   Панель активных фактов, сущностей и связей графа знаний.
 *   Отображает факты с морфологическими предикатами, статусы валидации (validated / stale / rejected)
 *   и JSON-инспектор факта.
 *
 * File: panel.js
 * Package: apps/ai_assistant/api/webgui/tab_workspace/panel_facts
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-26 01:58:00
 * =============================================================================
 */

import { fetchJson } from '../common/ui_utils.js';

let currentWsId = 'default';
let cachedFacts = [];

function t(key, fallback = '') {
  if (typeof window !== 'undefined' && window.i18n && typeof window.i18n.t === 'function') {
    return window.i18n.t(key, fallback);
  }
  return fallback;
}

export async function loadFacts(workspaceId = null, force = false) {
  if (workspaceId) currentWsId = workspaceId;
  if (!force && typeof window !== 'undefined' && typeof window.isPanelActive === 'function') {
    if (!window.isPanelActive('tab-workspace', 'panel-facts')) return;
  }
  const tbody = document.getElementById('ws-facts-table-body');
  const showStale = document.getElementById('facts-show-stale-toggle')?.checked || false;
  if (!tbody) return;

  try {
    const data = await fetchJson(`/api/v1/facts?workspace_id=${encodeURIComponent(currentWsId)}&include_stale=${showStale}`);
    cachedFacts = data.facts || [];
    const activeCount = cachedFacts.filter(f => f.status !== 'stale' && f.status !== 'rejected').length;
    const factsBadge = document.getElementById('ws-facts-count-badge');
    if (factsBadge) {
      factsBadge.textContent = t('workspace.activeFactsBadge', '{count} активных фактов').replace('{count}', activeCount);
    }

    if (cachedFacts.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" class="text-center py-4 text-muted">${t('workspace.factsEmpty', 'Факты не найдены. Добавьте документ или загрузите демо-примеры.')}</td></tr>`;
      return;
    }

    tbody.innerHTML = cachedFacts.map((f, idx) => {
      const fType = f.fact_type || 'action';
      let summaryHtml = '';
      if (fType === 'possession') {
        const own = f.owner?.text || f.owner?.normalized || '';
        const poss = f.possessed_entity?.text || f.possessed_entity?.normalized || '';
        const relLabel = t('workspace.possessionRelation', 'has (владеет)');
        summaryHtml = `<strong>${own}</strong> <span class="badge bg-info-subtle text-info border mx-1">${relLabel}</span> <strong>${poss}</strong>`;
      } else {
        const subj = f.subject?.text || '';
        const pred = f.predicate?.text || '';
        const obj = f.object?.text || '';
        summaryHtml = `<strong>${subj}</strong> &rarr; <span class="text-primary fw-semibold">${pred}</span> &rarr; <strong>${obj}</strong>`;
      }

      const docId = f.source?.document_id || f.document_id || '';
      const ver = f.version_num || 1;
      const st = f.status || 'extracted';
      let stBadgeClass = 'bg-info-subtle text-info';
      if (st === 'validated') stBadgeClass = 'bg-success-subtle text-success';
      else if (st === 'stale') stBadgeClass = 'bg-secondary-subtle text-secondary';
      else if (st === 'rejected') stBadgeClass = 'bg-danger-subtle text-danger';

      const sentInfo = t('workspace.factSentenceNum', '(v{ver}, предл. #{idx})')
        .replace('{ver}', ver)
        .replace('{idx}', f.source?.sentence_index ?? 0);
      const titleConfirm = t('workspace.confirmFact', 'Подтвердить факт');
      const titleReject = t('workspace.rejectFact', 'Отклонить факт');

      return `
        <tr class="ws-fact-row" data-fact-idx="${idx}" style="cursor: pointer;">
          <td>
            <span class="badge bg-primary-subtle text-primary border">${fType}</span>
            <span class="badge bg-secondary-subtle text-secondary border">${f.language || 'ru'}</span>
          </td>
          <td>${summaryHtml}</td>
          <td>
            <span class="fw-medium">${docId}</span>
            <span class="text-muted">${sentInfo}</span>
          </td>
          <td><span class="badge ${stBadgeClass} border">${st}</span></td>
          <td>
            <div class="btn-group btn-group-sm">
              <button type="button" class="btn btn-outline-success py-0 px-1 fact-status-btn" data-fact-id="${f.fact_id}" data-status="validated" title="${titleConfirm}">
                <i class="bi bi-check-lg"></i>
              </button>
              <button type="button" class="btn btn-outline-danger py-0 px-1 fact-status-btn" data-fact-id="${f.fact_id}" data-status="rejected" title="${titleReject}">
                <i class="bi bi-x-lg"></i>
              </button>
            </div>
          </td>
        </tr>
      `;
    }).join('');

    const jsonViewer = document.getElementById('ws-fact-json-viewer');
    if (jsonViewer && cachedFacts.length > 0) {
      jsonViewer.textContent = JSON.stringify(cachedFacts[0], null, 2);
    }

    tbody.querySelectorAll('.ws-fact-row').forEach(row => {
      row.addEventListener('click', (e) => {
        if (e.target.closest('.fact-status-btn')) return;
        const idx = parseInt(row.getAttribute('data-fact-idx'), 10);
        if (jsonViewer && cachedFacts[idx]) {
          jsonViewer.textContent = JSON.stringify(cachedFacts[idx], null, 2);
        }
      });
    });

    tbody.querySelectorAll('.fact-status-btn').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const factId = btn.getAttribute('data-fact-id');
        const newStatus = btn.getAttribute('data-status');
        try {
          await fetchJson(`/api/v1/facts/${encodeURIComponent(factId)}/status`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus }),
          });
          await loadFacts();
        } catch (err) {
          alert(`${t('workspace.factStatusUpdateError', 'Ошибка обновления статуса факта: ')}${err.message}`);
        }
      });
    });
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5" class="text-danger p-3">${t('workspace.factsLoadError', 'Ошибка загрузки фактов: ')}${err.message}</td></tr>`;
  }
}

export function initFactsPanel(getWorkspaceId) {
  document.getElementById('facts-show-stale-toggle')?.addEventListener('change', () => {
    loadFacts(getWorkspaceId());
  });
}
