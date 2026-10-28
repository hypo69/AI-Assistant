/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Diff Stats Panel
 * =============================================================================
 * Description:
 *   Изолированная панель статистики Diff (panel-diff-stats).
 *   Отображает файлы с количеством изменений, загружает унифицированный diff
 *   и запускает ИИ-суммаризацию архитектурных последствий коммита.
 *
 * File: panel.js
 * Package: apps/ai_assistant/api/webgui/tab_diff/panel_diff_stats
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-28 02:35:00
 * =============================================================================
 */

import { registerPanelRenderer, loadPanelData } from '../../js/panel-loader.js';

export function renderDiffStatsPanel(result, panelEl) {
  const container = document.getElementById('diff-stats-body');
  const countBadge = document.getElementById('diff-stats-count-badge');
  if (!container) return;

  const data = result?.data || [];
  if (countBadge) countBadge.textContent = `${data.length} изменений`;

  if (data.length === 0) {
    container.innerHTML = `<div class="small text-muted text-center py-2">Нет данных по недавним изменениям файлов.</div>`;
    return;
  }

  const html = `
    <div class="d-flex flex-wrap gap-2">
      ${data.map(item => `
        <div class="badge bg-body-tertiary text-body border p-2 d-flex align-items-center gap-2 file-diff-chip" style="cursor: pointer;" data-hash="${item.commit_hash}" data-path="${item.file_path}">
          <span class="text-truncate" style="max-width: 220px;">${item.file_path}</span>
          <span class="text-success small">+${item.insertions || 0}</span>
          <span class="text-danger small">-${item.deletions || 0}</span>
        </div>
      `).join('')}
    </div>
  `;
  container.innerHTML = html;

  container.querySelectorAll('.file-diff-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const h = chip.getAttribute('data-hash');
      const p = chip.getAttribute('data-path');
      loadDiff(h, p);
    });
  });
}

export async function loadDiff(commitHash, filePath = null) {
  const pre = document.getElementById('diff-code-pre');
  const title = document.getElementById('diff-header-title');
  const indicator = document.getElementById('diff-status-indicator');

  if (!pre) return;
  pre.textContent = 'Загрузка diff...';
  if (indicator) indicator.textContent = 'Загрузка...';

  try {
    let url = `/api/v1/diff?commit_hash=${encodeURIComponent(commitHash)}`;
    const wsId = typeof window.getActiveWorkspaceId === 'function' ? window.getActiveWorkspaceId() : '';
    if (wsId) url += `&workspace_id=${encodeURIComponent(wsId)}`;
    if (filePath) url += `&file_path=${encodeURIComponent(filePath)}`;

    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const diffText = data.diff_text || data.diff || 'Нет различий в выбранном фрагменте.';
    pre.textContent = diffText;
    if (title) title.textContent = `${commitHash.slice(0, 10)} :: ${filePath || 'Все файлы'}`;
    if (indicator) indicator.textContent = 'Загружен';
  } catch (err) {
    pre.textContent = `Ошибка загрузки diff: ${err.message}`;
    if (indicator) indicator.textContent = 'Ошибка';
  }
}

export async function loadAIInsights(commitHash, filePath = null) {
  const card = document.getElementById('diff-ai-card');
  const textEl = document.getElementById('diff-ai-summary-text');
  const entitiesBox = document.getElementById('diff-ai-entities-box');

  if (!card || !textEl) return;
  card.style.display = 'block';
  textEl.textContent = '🤖 ИИ анализирует архитектурные последствия коммита...';
  if (entitiesBox) entitiesBox.innerHTML = '';

  try {
    const res = await fetch('/api/v1/insights', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ commit_hash: commitHash, file_path: filePath })
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    textEl.textContent = data.summary || data.explanation || 'Анализ завершен.';
    if (entitiesBox && Array.isArray(data.entities_affected)) {
      entitiesBox.innerHTML = data.entities_affected.map(e => `
        <span class="badge bg-secondary-subtle text-secondary border font-monospace">${e}</span>
      `).join('');
    }
  } catch (err) {
    textEl.textContent = `Ошибка получения инсайтов: ${err.message}`;
  }
}

export function initDiffStatsPanel() {
  registerPanelRenderer('panel-diff-stats', renderDiffStatsPanel);

  document.getElementById('diff-load-btn')?.addEventListener('click', () => {
    const h = document.getElementById('diff-commit-input')?.value.trim() || 'HEAD';
    loadDiff(h);
  });

  document.getElementById('diff-ai-insights-btn')?.addEventListener('click', () => {
    const h = document.getElementById('diff-commit-input')?.value.trim() || 'HEAD';
    loadAIInsights(h);
  });

  const handleContextOrRepoChange = (e) => {
    const pane = document.getElementById('tab-diff') || document.getElementById('diff');
    const isActive = pane && (pane.classList.contains('active') || pane.classList.contains('show'));
    if (!isActive) return;
    loadPanelData('panel-diff-stats', { force: true, repo_path: e.detail?.repoPath, workspace_id: e.detail?.workspaceId });
  };
  document.addEventListener('context:changed', handleContextOrRepoChange);
  document.addEventListener('repo:changed', handleContextOrRepoChange);
  document.addEventListener('workspace:changed', handleContextOrRepoChange);

  const diffPane = document.getElementById('tab-diff') || document.getElementById('diff');
  if (diffPane && (diffPane.classList.contains('active') || diffPane.classList.contains('show'))) {
    loadPanelData('panel-diff-stats');
  }

  if (window._selectedCommitHash) {
    const input = document.getElementById('diff-commit-input');
    if (input) input.value = window._selectedCommitHash;
    loadDiff(window._selectedCommitHash);
    window._selectedCommitHash = null;
  }
}