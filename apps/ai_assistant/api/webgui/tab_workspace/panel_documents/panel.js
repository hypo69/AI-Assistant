/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Documents Panel
 * =============================================================================
 * Description:
 *   Панель управления документами и автокоммитами Git (Шаг 2).
 *   Обеспечивает просмотр, редактирование, создание и коммит документов в репозиторий.
 *
 * File: panel.js
 * Package: apps/ai_assistant/api/webgui/tab_workspace/panel_documents
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-28 20:05:00
 * =============================================================================
 */

import { fetchJson } from '../common/ui_utils.js';

let currentWsId = 'default';
let onDocSavedCallback = null;
let docsInFlight = false;
let commitsInFlight = false;

export async function loadDocuments(workspaceId = null, force = false) {
  if (workspaceId) currentWsId = workspaceId;
  if (!force && typeof window !== 'undefined' && typeof window.isPanelActive === 'function') {
    if (!window.isPanelActive('tab-workspace', 'panel-documents')) return;
  }
  const listEl = document.getElementById('ws-documents-list');
  if (!listEl) return;
  if (docsInFlight) return;
  docsInFlight = true;

  try {
    const data = await fetchJson(`/api/v1/workspaces/${encodeURIComponent(currentWsId)}/documents`);
    const docs = data.documents || [];
    const docsBadge = document.getElementById('ws-docs-count-badge');
    if (docsBadge) docsBadge.textContent = `${docs.length} документов`;

    if (docs.length === 0) {
      listEl.innerHTML = `<div class="p-2 text-muted small border rounded">В этой рабочей области пока нет документов. Нажмите «Загрузить демо-примеры» или сохраните файл ниже.</div>`;
      return;
    }

    listEl.innerHTML = docs.map(d => {
      const shortCommit = d.commit_hash ? d.commit_hash.slice(0, 7) : 'HEAD';
      return `
        <button type="button" class="list-group-item list-group-item-action d-flex align-items-center justify-content-between py-2 px-3 ws-doc-item" data-doc-id="${d.document_id}">
          <div>
            <div class="fw-semibold small d-flex align-items-center gap-2">
              <i class="bi bi-file-earmark-text text-primary"></i>
              <span>${d.document_id}</span>
              <span class="badge bg-secondary-subtle text-secondary border">${d.language}</span>
              <span class="badge bg-info-subtle text-info border">v${d.current_version}</span>
            </div>
            <div class="text-muted text-truncate small mt-1" style="max-width: 280px;">${d.content || ''}</div>
          </div>
          <div class="text-end">
            <span class="badge bg-success-subtle text-success border d-block mb-1">${d.active_facts_count || 0} фактов</span>
            <span class="font-monospace text-muted small"><i class="bi bi-git"></i> ${shortCommit}</span>
          </div>
        </button>
      `;
    }).join('');

    listEl.querySelectorAll('.ws-doc-item').forEach(btn => {
      btn.addEventListener('click', () => {
        const docId = btn.getAttribute('data-doc-id');
        const docObj = docs.find(x => x.document_id === docId);
        if (docObj) {
          const fnameInput = document.getElementById('doc-filename-input');
          const contentInput = document.getElementById('doc-content-input');
          const langInput = document.getElementById('doc-lang-input');
          if (fnameInput) fnameInput.value = docObj.document_id;
          if (contentInput) contentInput.value = docObj.content || '';
          if (langInput) langInput.value = docObj.language || '';
        }
      });
    });
  } catch (err) {
    listEl.innerHTML = `<div class="text-danger small p-2">Ошибка чтения документов: ${err.message}</div>`;
  } finally {
    docsInFlight = false;
  }
}

export async function loadWorkspaceCommits(workspaceId = null, force = false) {
  if (workspaceId) currentWsId = workspaceId;
  if (!force && typeof window !== 'undefined' && typeof window.isPanelActive === 'function') {
    if (!window.isPanelActive('tab-workspace', 'panel-documents')) return;
  }
  const box = document.getElementById('ws-git-commits-mini');
  if (!box) return;
  if (commitsInFlight) return;
  commitsInFlight = true;

  try {
    const data = await fetchJson(`/api/v1/workspaces/${encodeURIComponent(currentWsId)}/commits?limit=5`);
    const commits = data.commits || [];
    if (commits.length === 0) {
      box.innerHTML = '<div class="text-muted small">История коммитов пуста.</div>';
      return;
    }
    box.innerHTML = commits.map(c => `
      <div class="p-1.5 px-2 rounded bg-body-tertiary border d-flex align-items-center justify-content-between">
        <div class="text-truncate">
          <span class="badge bg-secondary-subtle text-secondary border font-monospace me-1">${(c.commit_hash || '').slice(0, 7)}</span>
          <span>${c.message || ''}</span>
        </div>
        <span class="text-muted ms-2 flex-shrink-0">${(c.timestamp || '').slice(0, 16).replace('T', ' ')}</span>
      </div>
    `).join('');
  } catch (err) {
    box.innerHTML = `<div class="text-muted small">Git лог недоступен: ${err.message}</div>`;
  } finally {
    commitsInFlight = false;
  }
}

export function initDocumentsPanel(onDocSaved) {
  onDocSavedCallback = onDocSaved;

  document.getElementById('doc-new-clear-btn')?.addEventListener('click', () => {
    const fname = document.getElementById('doc-filename-input');
    const content = document.getElementById('doc-content-input');
    const msg = document.getElementById('doc-commit-msg-input');
    if (fname) fname.value = 'new_doc.txt';
    if (content) content.value = '';
    if (msg) msg.value = '';
    content?.focus();
  });

  document.getElementById('doc-save-btn')?.addEventListener('click', async () => {
    const docId = document.getElementById('doc-filename-input')?.value.trim();
    const content = document.getElementById('doc-content-input')?.value || '';
    const lang = document.getElementById('doc-lang-input')?.value || null;
    const commitMsg = document.getElementById('doc-commit-msg-input')?.value.trim() || null;

    if (!docId || !content.trim()) {
      alert('Укажите имя файла и текст документа.');
      return;
    }

    try {
      await fetchJson('/api/v1/documents/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workspace_id: currentWsId,
          document_id: docId,
          content: content,
          language: lang,
          commit_message: commitMsg,
          force_reanalyze: true,
        }),
      });
      if (onDocSavedCallback) {
        await onDocSavedCallback(currentWsId);
      }
    } catch (err) {
      alert(`Ошибка сохранения документа: ${err.message}`);
    }
  });
}
