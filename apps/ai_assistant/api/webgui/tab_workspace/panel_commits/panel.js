/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Tab Workspace Commits Panel
 * =============================================================================
 * Description:
 *   Панель истории коммитов (panel-commits) внутри вкладки tab_workspace.
 *   Отображает таблицу коммитов текущего репозитория Git активного рабочего
 *   пространства, фильтрацию, автообновление и переход к Diff.
 *
 * File: panel.js
 * Package: apps/ai_assistant/api/webgui/tab_workspace/panel_commits
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-25 21:15:00
 * =============================================================================
 */

import { registerPanelRenderer, loadPanelData } from '../../js/panel-loader.js';

let allCommits = [];

/**
 * Отрисовывает таблицу коммитов в теле таблицы #commits-table-body.
 * @param {Array<Object>} commits - Список объектов коммитов Git.
 */
export function renderCommitsTable(commits) {
  const tbody = document.getElementById('commits-table-body');
  const countBadge = document.getElementById('commits-count-badge');
  if (!tbody) return;

  if (countBadge) countBadge.textContent = `${commits ? commits.length : 0} коммитов`;

  if (!commits || commits.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" class="text-center py-3 text-muted">Коммиты не найдены</td></tr>';
    return;
  }

  tbody.innerHTML = commits.map((c) => {
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
          <button class="btn btn-outline-primary btn-sm py-0 px-2 commit-diff-btn" data-hash="${fullHash}" type="button">
            Diff
          </button>
        </td>
      </tr>
    `;
  }).join('');

  tbody.querySelectorAll('.commit-diff-btn').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      const h = e.currentTarget.getAttribute('data-hash');
      if (h && typeof window.switchTab === 'function') {
        window._selectedCommitHash = h;
        window.switchTab('tab-diff');
      }
    });
  });
}

/**
 * Функция-обработчик результата ответа REST API роутера panel-commits.
 * @param {Object} result - Ответ от /v1/panel/panel-commits.
 * @param {HTMLElement} [panelEl] - Элемент карточки панели.
 */
export function renderCommitsPanel(result, panelEl) {
  allCommits = result?.data || [];
  renderCommitsTable(allCommits);
}

/**
 * Загружает данные коммитов для указанного рабочего пространства.
 * @param {string|null} [workspaceId=null] - Идентификатор рабочей области.
 * @param {boolean} [force=false] - Флаг принудительного обновления.
 */
export async function loadWorkspaceCommitsPanel(workspaceId = null, force = false) {
  return await loadPanelData('panel-commits', { force, workspace_id: workspaceId });
}

/**
 * Инициализирует обработчики событий и регистрацию рендерера панели panel-commits.
 */
export function initCommitsPanel() {
  registerPanelRenderer('panel-commits', renderCommitsPanel);

  document.getElementById('commits-refresh-btn')?.addEventListener('click', () => {
    const wsId = typeof window.getActiveWorkspaceId === 'function' ? window.getActiveWorkspaceId() : null;
    loadWorkspaceCommitsPanel(wsId, true);
  });

  document.getElementById('commits-search-input')?.addEventListener('input', (e) => {
    const q = e.target.value.toLowerCase().trim();
    if (!q) {
      renderCommitsTable(allCommits);
      return;
    }
    const filtered = allCommits.filter((c) =>
      (c.message && c.message.toLowerCase().includes(q)) ||
      (c.author && c.author.toLowerCase().includes(q)) ||
      (c.commit_hash && c.commit_hash.toLowerCase().includes(q))
    );
    renderCommitsTable(filtered);
  });
}
