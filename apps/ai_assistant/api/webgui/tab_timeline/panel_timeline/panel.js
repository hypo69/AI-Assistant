/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Timeline Panel
 * =============================================================================
 * Description:
 *   Изолированная панель шкалы времени (panel-timeline).
 *   Отображает хронологический срез эволюции кодовой базы, связывается с
 *   эндпоинтом /api/v1/panel/panel-timeline и обрабатывает переходы к Diff.
 *
 * File: panel.js
 * Package: apps/ai_assistant/api/webgui/tab_timeline/panel_timeline
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-24 22:20:00
 * =============================================================================
 */

import { registerPanelRenderer, loadPanelData } from '../../js/panel-loader.js';

export function renderTimelinePanel(result, panelEl) {
  const container = document.getElementById('timeline-nodes-container');
  const countBadge = document.getElementById('timeline-count-badge');
  const statusBadge = document.getElementById('timeline-status-badge');

  if (!container) return;

  const data = result?.data || [];
  if (countBadge) countBadge.textContent = `${data.length} точек`;
  if (statusBadge) {
    statusBadge.textContent = 'Подключено к /api/v1/panel/panel-timeline';
    statusBadge.className = 'badge bg-success-subtle text-success border';
  }

  if (data.length === 0) {
    container.innerHTML = `<div class="alert alert-warning small mb-0">Точки истории не найдены или репозиторий пуст.</div>`;
    return;
  }

  const html = data.map((item, idx) => {
    const hash = item.short_hash || (item.commit_hash ? item.commit_hash.slice(0, 8) : '---');
    const author = item.author || 'Неизвестный автор';
    const date = item.timestamp ? item.timestamp.replace('T', ' ').slice(0, 19) : '';
    const message = item.message || '';

    return `
      <div class="d-flex gap-3 mb-3 pb-3 border-bottom border-secondary-subtle align-items-start timeline-node-item">
        <div class="rounded-circle bg-primary-subtle text-primary p-2 d-flex align-items-center justify-content-center flex-shrink-0" style="width: 32px; height: 32px; font-size: 0.8rem;">
          ${idx + 1}
        </div>
        <div class="flex-grow-1">
          <div class="d-flex align-items-center justify-content-between mb-1">
            <span class="badge bg-secondary font-monospace">${hash}</span>
            <span class="small text-muted" style="font-size: 0.75rem;">${date}</span>
          </div>
          <div class="fw-medium text-body mb-1" style="font-size: 0.9rem;">${message}</div>
          <div class="small text-muted d-flex align-items-center gap-2">
            <i class="bi bi-person"></i>
            <span>${author}</span>
            <button class="btn btn-link btn-sm p-0 ms-auto text-decoration-none small view-diff-btn" data-hash="${item.commit_hash || ''}">
              Смотреть Diff →
            </button>
          </div>
        </div>
      </div>
    `;
  }).join('');

  container.innerHTML = html;

  container.querySelectorAll('.view-diff-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const h = e.currentTarget.getAttribute('data-hash');
      if (h && typeof window.switchTab === 'function') {
        window._selectedCommitHash = h;
        window.switchTab('tab-diff');
      }
    });
  });
}

export function initTimelinePanel() {
  registerPanelRenderer('panel-timeline', renderTimelinePanel);

  document.getElementById('timeline-refresh-btn')?.addEventListener('click', () => {
    loadPanelData('panel-timeline', { force: true });
  });

  document.addEventListener('context:changed', (e) => {
  });
  document.addEventListener('repo:changed', (e) => {
    const pane = document.getElementById('tab-timeline') || document.getElementById('timeline');
    const isActive = pane && (pane.classList.contains('active') || pane.classList.contains('show'));
    if (!isActive) return;
    loadPanelData('panel-timeline', { force: true, repo_path: e.detail?.repoPath, workspace_id: e.detail?.workspaceId });
  });

  const pane = document.getElementById('tab-timeline') || document.getElementById('timeline');
  if (pane && (pane.classList.contains('active') || pane.classList.contains('show'))) {
    loadPanelData('panel-timeline');
  }
}
