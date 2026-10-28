/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - External Sources Panel
 * =============================================================================
 * Description:
 *   Панель управления связанными внешними источниками рабочей области.
 *   Обеспечивает привязку локальных файлов (PDF, Excel, Audio, DOCX, CSV),
 *   директорий на компьютере и Google Таблиц без копирования файлов,
 *   а также запуск синхронизации и индексации в базе знаний.
 *
 * File: panel.js
 * Package: apps/ai_assistant/api/webgui/tab_workspace/panel_sources
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-26 00:22:00
 * =============================================================================
 */

import { fetchJson } from '../common/ui_utils.js';

let currentWsId = 'default';
let onSourcesSyncedCallback = null;

function getSourceIcon(type) {
  switch (type) {
    case 'google_sheet':
      return 'bi-file-earmark-spreadsheet-fill text-success';
    case 'directory':
      return 'bi-folder2-open text-warning';
    case 'file':
      return 'bi-file-earmark-text text-primary';
    default:
      return 'bi-link-45deg text-info';
  }
}

function getSourceTypeLabel(type) {
  switch (type) {
    case 'google_sheet':
      return 'Google Таблица';
    case 'directory':
      return 'Директория ПК';
    case 'file':
      return 'Файл ПК';
    default:
      return type;
  }
}

export async function loadSources(workspaceId = null, force = false) {
  if (workspaceId) currentWsId = workspaceId;
  if (!force && typeof window !== 'undefined' && typeof window.isPanelActive === 'function') {
    if (!window.isPanelActive('tab-workspace', 'panel-sources')) return;
  }
  const listEl = document.getElementById('ws-sources-list');
  const countBadge = document.getElementById('ws-sources-count-badge');
  if (!listEl) return;

  try {
    const data = await fetchJson(`/api/v1/workspaces/${encodeURIComponent(currentWsId)}/sources`);
    const sources = data.sources || [];
    if (countBadge) countBadge.textContent = `${sources.length} связанных источников`;

    if (sources.length === 0) {
      listEl.innerHTML = `
        <div class="p-3 text-muted small border rounded bg-body-tertiary text-center">
          <i class="bi bi-link-45deg fs-4 d-block mb-1"></i>
          Нет связанных внешних источников. Добавьте путь к файлу/папке на диске или ссылку на Google Таблицу ниже.
        </div>`;
      return;
    }

    listEl.innerHTML = sources.map(s => {
      const icon = getSourceIcon(s.source_type);
      const typeLabel = getSourceTypeLabel(s.source_type);
      const isError = s.status === 'error';
      const isOtherHost = s.status === 'other_host' || s.is_current_host === false;
      const fullPath = s.qualified_path || s.source_path;
      const statusBadge = isError
        ? `<span class="badge bg-danger-subtle text-danger border">Ошибка</span>`
        : isOtherHost
          ? `<span class="badge bg-primary-subtle text-primary border"><i class="bi bi-usb-drive me-1"></i>На другом ПК (${s.host_name || 'ПК'})</span>`
          : `<span class="badge bg-success-subtle text-success border">Активен (${s.item_count || 0} файлов)</span>`;

      return `
        <div class="list-group-item d-flex align-items-center justify-content-between p-2 mb-1 rounded border">
          <div class="d-flex align-items-center gap-2 overflow-hidden">
            <i class="bi ${icon} fs-5 flex-shrink-0"></i>
            <div class="text-truncate">
              <div class="fw-semibold small text-truncate">${s.name || s.source_path}</div>
              <div class="text-muted font-monospace small text-truncate" title="${fullPath}">${fullPath}</div>
              ${s.error_message ? `<div class="text-danger small mt-0.5 text-truncate" title="${s.error_message}">⚠️ ${s.error_message}</div>` : ''}
            </div>
          </div>
          <div class="d-flex align-items-center gap-2 flex-shrink-0 ms-2">
            ${s.host_name ? `<span class="badge bg-info-subtle text-info-emphasis border font-monospace"><i class="bi bi-pc-display me-1"></i>${s.host_name}</span>` : ''}
            <span class="badge bg-secondary-subtle text-secondary border">${typeLabel}</span>
            ${statusBadge}
            <button class="btn btn-outline-danger btn-sm py-0 px-2 ws-source-delete-btn" data-source-id="${s.source_id}" title="Удалить привязку" type="button">
              <i class="bi bi-trash"></i>
            </button>
          </div>
        </div>
      `;
    }).join('');

    // Обработчики кнопок удаления
    listEl.querySelectorAll('.ws-source-delete-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const sid = btn.getAttribute('data-source-id');
        if (!confirm('Отвязать этот источник от рабочего пространства?')) return;
        try {
          await fetchJson(`/api/v1/workspaces/${encodeURIComponent(currentWsId)}/sources/${encodeURIComponent(sid)}`, {
            method: 'DELETE',
          });
          await loadSources(currentWsId);
        } catch (err) {
          alert(`Ошибка удаления: ${err.message}`);
        }
      });
    });
  } catch (err) {
    listEl.innerHTML = `<div class="text-danger small p-2">Ошибка загрузки источников: ${err.message}</div>`;
  }
}

export function initSourcesPanel(onSyncedCallback) {
  onSourcesSyncedCallback = onSyncedCallback;

  const addBtn = document.getElementById('ws-source-add-btn');
  const syncBtn = document.getElementById('ws-sources-sync-btn');
  const previewBtn = document.getElementById('ws-source-preview-btn');
  const targetInput = document.getElementById('ws-source-target-input');
  const nameInput = document.getElementById('ws-source-name-input');
  const statusIndicator = document.getElementById('ws-sources-status-indicator');

  if (addBtn && targetInput) {
    addBtn.addEventListener('click', async () => {
      const target = targetInput.value.trim();
      const name = nameInput ? nameInput.value.trim() : '';
      if (!target) {
        alert('Укажите путь к файлу/директории на диске или ссылку на Google Таблицу.');
        return;
      }

      addBtn.disabled = true;
      if (statusIndicator) statusIndicator.textContent = 'Привязка источника...';

      try {
        await fetchJson(`/api/v1/workspaces/${encodeURIComponent(currentWsId)}/sources`, {
          method: 'POST',
          body: JSON.stringify({ target, name, auto_watch: true }),
        });
        if (statusIndicator) statusIndicator.textContent = 'Запуск Git-отслеживания и индексации...';
        await fetchJson(`/api/v1/workspaces/${encodeURIComponent(currentWsId)}/sources/sync`, {
          method: 'POST',
        });
        targetInput.value = '';
        if (nameInput) nameInput.value = '';
        if (statusIndicator) statusIndicator.textContent = 'Источник добавлен. Git начал отслеживание!';
        await loadSources(currentWsId);
        if (onSourcesSyncedCallback) await onSourcesSyncedCallback(currentWsId);
      } catch (err) {
        if (statusIndicator) statusIndicator.textContent = `Ошибка: ${err.message}`;
        alert(`Ошибка привязки источника: ${err.message}`);
      } finally {
        addBtn.disabled = false;
      }
    });
  }

  if (syncBtn) {
    syncBtn.addEventListener('click', async () => {
      syncBtn.disabled = true;
      syncBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Синхронизация...';
      if (statusIndicator) statusIndicator.textContent = 'Анализ и индексация связанных файлов (PDF/Excel/Аудио/Таблицы)...';

      try {
        const res = await fetchJson(`/api/v1/workspaces/${encodeURIComponent(currentWsId)}/sources/sync`, {
          method: 'POST',
          body: JSON.stringify({ force_reanalyze: false }),
        });
        if (statusIndicator) {
          statusIndicator.textContent = `Синхронизировано файлов: ${res.total_indexed || 0}`;
        }
        await loadSources(currentWsId);
        if (onSourcesSyncedCallback) {
          await onSourcesSyncedCallback(currentWsId);
        }
      } catch (err) {
        if (statusIndicator) statusIndicator.textContent = `Ошибка синхронизации: ${err.message}`;
        alert(`Ошибка синхронизации: ${err.message}`);
      } finally {
        syncBtn.disabled = false;
        syncBtn.innerHTML = '<i class="bi bi-arrow-repeat me-1"></i>Синхронизировать и Индексировать';
      }
    });
  }

  if (previewBtn && targetInput) {
    previewBtn.addEventListener('click', async () => {
      const target = targetInput.value.trim();
      if (!target) {
        alert('Введите путь или ссылку для предпросмотра.');
        return;
      }
      previewBtn.disabled = true;
      try {
        const preview = await fetchJson('/api/v1/extract-preview', {
          method: 'POST',
          body: JSON.stringify({ target }),
        });
        const contentBox = document.getElementById('ws-fact-json-viewer');
        if (contentBox) {
          contentBox.textContent = `[Предпросмотр: ${preview.title} (${preview.source_type})]\n\n${preview.text || ''}`;
        }
        if (statusIndicator) statusIndicator.textContent = `Конвертировано успешно (${preview.source_type})`;
      } catch (err) {
        alert(`Ошибка конвертации: ${err.message}`);
      } finally {
        previewBtn.disabled = false;
      }
    });
  }
}
