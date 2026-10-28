/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Commits Panel
 * =============================================================================
 * Description:
 *   Изолированная панель истории коммитов (panel-commits).
 *   Отображает таблицу коммитов из Git, фильтрацию по автору/сообщению/хэшу
 *   и переход к Diff.
 *
 * File: panel.js
 * Package: apps/ai_assistant/api/webgui/tab_commits/panel_commits
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-24 22:20:00
 * =============================================================================
 */

import { registerPanelRenderer, loadPanelData } from '../../js/panel-loader.js';

let allCommits = [];

export function renderCommitsTable(commits) {
  const tbody = document.getElementById('commits-table-body');
  const countBadge = document.getElementById('commits-count-badge');
  if (!tbody) return;

  if (countBadge) countBadge.textContent = `${commits.length} коммитов`;

  if (commits.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" class="text-center py-3 text-muted">Коммиты не найдены</td></tr>`;
    return;
  }

  tbody.innerHTML = commits.map(c => {
    const hash = c.short_hash || (c.commit_hash ? c.commit_hash.slice(0, 8) : '---');
    const fullHash = c.commit_hash || '';
    const date = c.timestamp ? c.timestamp.replace('T', ' ').slice(0, 19) : '';
    const author = c.author || 'Неизвестно';
    const msg = c.message || '';

    return `
      <tr>
        <td><span class="badge bg-secondary font-monospace">${hash}</span></td>
        <td class="text-muted small">${date}</td>
        <td><span class="fw-medium">${author}</span></td>
        <td class="text-truncate" style="max-width: 400px;" title="${msg}">${msg}</td>
        <td class="text-end">
          <button class="btn btn-outline-primary btn-sm py-0 px-2 commit-diff-btn" data-hash="${fullHash}">
            Diff
          </button>
        </td>
      </tr>
    `;
  }).join('');

  tbody.querySelectorAll('.commit-diff-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const h = e.currentTarget.getAttribute('data-hash');
      if (h && typeof window.switchTab === 'function') {
        window._selectedCommitHash = h;
        window.switchTab('tab-diff');
      }
    });
  });
}

export function renderCommitsPanel(result, panelEl) {
  allCommits = result?.data || [];
  renderCommitsTable(allCommits);
}

export function initCommitsPanel() {
  registerPanelRenderer('panel-commits', renderCommitsPanel);

  document.getElementById('commits-refresh-btn')?.addEventListener('click', () => {
    loadPanelData('panel-commits', { force: true });
  });

  document.getElementById('commits-search-input')?.addEventListener('input', (e) => {
    const q = e.target.value.toLowerCase().trim();
    if (!q) {
      renderCommitsTable(allCommits);
      return;
    }
    const filtered = allCommits.filter(c => 
      (c.message && c.message.toLowerCase().includes(q)) ||
      (c.author && c.author.toLowerCase().includes(q)) ||
      (c.commit_hash && c.commit_hash.toLowerCase().includes(q))
    );
    renderCommitsTable(filtered);
  });

  document.addEventListener('context:changed', (e) => {
  });
  document.addEventListener('repo:changed', (e) => {
    const pane = document.getElementById('tab-commits') || document.getElementById('commits');
    const isActive = pane && (pane.classList.contains('active') || pane.classList.contains('show'));
    if (!isActive) return;
    loadPanelData('panel-commits', { force: true, repo_path: e.detail?.repoPath, workspace_id: e.detail?.workspaceId });
  });

  const pane = document.getElementById('tab-commits') || document.getElementById('commits');
  if (pane && (pane.classList.contains('active') || pane.classList.contains('show'))) {
    loadPanelData('panel-commits');
  }
}
