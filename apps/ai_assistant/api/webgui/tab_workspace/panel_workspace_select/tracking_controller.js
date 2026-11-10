/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Workspace File & Directory Tracking Controller
 * =============================================================================
 * Description:
 *   Контроллер выбора и включения множественных директорий и файлов в Git-слежение.
 *   Управляет списком выбранных объектов для слежения (staging list),
 *   динамическим отображением опций конвертации (PDF, OCR, Audio) и отображением
 *   актуального списка файлов и папок, находящихся под Git-слежением.
 *
 * File: tracking_controller.js
 * Package: apps/ai_assistant/api/webgui/tab_workspace/panel_workspace_select
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-30 16:13:00
 * =============================================================================
 */

import { fetchJson, t } from '../common/ui_utils.js';
import { mountTrackSourcesPicker } from '../../components/track_sources_picker/track_sources_picker.js';

let stagedItems = [];
let getWorkspaceIdFn = null;
let onItemsCommittedFn = null;

const AUDIO_EXTS = ['.mp3', '.wav', '.ogg', '.m4a', '.flac', '.aac', '.wma'];
const PDF_EXTS = ['.pdf'];
const IMAGE_EXTS = ['.png', '.jpg', '.jpeg', '.bmp', '.webp', '.tiff', '.gif'];


function extractFileExtension(filename) {
  if (!filename) return '';
  const idx = filename.lastIndexOf('.');
  return idx >= 0 ? filename.slice(idx).toLowerCase() : '';
}

function guessIsDirectory(rawPath) {
  if (!rawPath) return false;
  const p = String(rawPath).trim();
  if (p.endsWith('/') || p.endsWith('\\')) return true;
  const base = p.split(/[/\\]/).pop() || '';
  return !base.includes('.');
}

function getPathIconClass(path, isDir) {
  if (isDir) return 'bi-folder2-open text-warning';
  const ext = extractFileExtension(path);
  if (ext === '.pdf') return 'bi-filetype-pdf text-danger';
  if (IMAGE_EXTS.includes(ext)) return 'bi-file-earmark-image text-warning-emphasis';
  if (AUDIO_EXTS.includes(ext)) return 'bi-file-earmark-music text-success';
  if (['.md', '.txt', '.log'].includes(ext)) return 'bi-file-earmark-text text-primary';
  if (['.csv', '.tsv', '.xlsx', '.xls'].includes(ext)) return 'bi-file-earmark-spreadsheet text-success';
  if (['.docx', '.doc'].includes(ext)) return 'bi-file-earmark-word text-primary';
  if (['.py', '.js', '.json', '.html', '.css', '.yaml', '.yml'].includes(ext)) return 'bi-file-earmark-code text-info';
  return 'bi-file-earmark text-secondary';
}

/**
 * Возвращает массив путей, выбранных для включения в слежение.
 * @returns {Array<string>}
 */
export function getStagedPaths() {
  return stagedItems.map(item => item.path);
}

/**
 * Добавляет один путь в список выбранных объектов.
 * @param {string} rawPath
 * @param {boolean|null} [explicitIsDir=null]
 */
export function addStagedPath(rawPath, explicitIsDir = null) {
  if (!rawPath) return;
  const clean = String(rawPath).trim();
  if (!clean) return;

  const exists = stagedItems.some(item => item.path.toLowerCase() === clean.toLowerCase());
  if (exists) return;

  const isDir = explicitIsDir !== null ? Boolean(explicitIsDir) : guessIsDirectory(clean);
  const name = clean.split(/[/\\]/).filter(Boolean).pop() || clean;
  const ext = !isDir ? extractFileExtension(clean) : 'dir';

  stagedItems.push({ path: clean, name, isDir, ext });
  renderStagedItems();
  updateConvertersFromStaged();
}

/**
 * Добавляет сразу несколько путей в список выбранных объектов.
 * @param {Array<string>} paths
 */
export function addMultipleStagedPaths(paths) {
  if (!Array.isArray(paths)) return;
  paths.forEach(p => addStagedPath(p));
}

/**
 * Удаляет элемент из списка выбранных объектов по индексу.
 * @param {number} index
 */
export function removeStagedItem(index) {
  if (index >= 0 && index < stagedItems.length) {
    stagedItems.splice(index, 1);
    renderStagedItems();
    updateConvertersFromStaged();
  }
}

/**
 * Очищает список выбранных объектов.
 */
export function clearStagedItems() {
  stagedItems = [];
  renderStagedItems();
  updateConvertersFromStaged();
}

/**
 * Обновляет отображение блока опций конвертации (PDF, OCR, Audio) на основе выбранных объектов.
 */
export function updateConvertersFromStaged() {
  const convBlock = document.getElementById('ws-converters-block');
  const secPdf = document.getElementById('ws-conv-section-pdf');
  const secOcr = document.getElementById('ws-conv-section-ocr');
  const secAudio = document.getElementById('ws-conv-section-audio');
  if (!convBlock) return;

  const fileUploadInput = document.getElementById('ws-track-upload-input');
  const detectedExts = new Set(stagedItems.filter(i => !i.isDir).map(i => i.ext));

  if (fileUploadInput?.files) {
    for (let i = 0; i < fileUploadInput.files.length; i++) {
      detectedExts.add(extractFileExtension(fileUploadInput.files[i].name));
    }
  }

  const hasAudio = [...detectedExts].some(ext => AUDIO_EXTS.includes(ext));
  const hasPdf = [...detectedExts].some(ext => PDF_EXTS.includes(ext));
  const hasImage = [...detectedExts].some(ext => IMAGE_EXTS.includes(ext));

  if (secAudio) secAudio.classList.toggle('d-none', !hasAudio);
  if (secPdf) secPdf.classList.toggle('d-none', !hasPdf);
  if (secOcr) secOcr.classList.toggle('d-none', !hasImage);

  const activeCount = (hasAudio ? 1 : 0) + (hasPdf ? 1 : 0) + (hasImage ? 1 : 0);
  const colClass = activeCount === 1 ? 'col-md-12' : (activeCount === 2 ? 'col-md-6' : 'col-md-4');

  [secAudio, secPdf, secOcr].forEach(sec => {
    if (sec) {
      sec.classList.remove('col-md-12', 'col-md-6', 'col-md-4');
      sec.classList.add(colClass);
    }
  });

  const shouldShow = hasAudio || hasPdf || hasImage;
  convBlock.classList.toggle('d-none', !shouldShow);
}

/**
 * Отрисовывает интерфейс списка выбранных объектов для слежения.
 */
export function renderStagedItems() {
  const container = document.getElementById('ws-staged-items-list');
  const countBadge = document.getElementById('ws-staged-count-badge');
  const clearBtn = document.getElementById('btn-track-clear-staged');

  if (countBadge) {
    const pattern = t('workspace.stagedCount', 'Выбрано: {count} объектов');
    countBadge.textContent = pattern.replace('{count}', stagedItems.length);
    countBadge.classList.toggle('bg-primary-subtle', stagedItems.length > 0);
    countBadge.classList.toggle('text-primary', stagedItems.length > 0);
    countBadge.classList.toggle('bg-secondary-subtle', stagedItems.length === 0);
    countBadge.classList.toggle('text-secondary', stagedItems.length === 0);
  }

  if (clearBtn) {
    clearBtn.classList.toggle('d-none', stagedItems.length === 0);
  }

  if (!container) return;

  if (stagedItems.length === 0) {
    container.innerHTML = `
      <div class="p-2.5 text-center text-muted small border rounded bg-body-tertiary" id="ws-staged-empty-msg">
        <i class="bi bi-info-circle me-1"></i>${t('workspace.stagedEmptyMsg', 'Объекты не выбраны. Нажмите «Обзор файлов...», «Обзор папки...» или введите путь выше, чтобы добавить их в список.')}
      </div>
    `;
    return;
  }

  container.innerHTML = stagedItems.map((item, index) => {
    const icon = getPathIconClass(item.path, item.isDir);
    const typeLabel = item.isDir ? t('workspace.badgeTypeFolder', 'Папка') : t('workspace.badgeTypeFile', 'Файл');
    const badgeClass = item.isDir ? 'bg-warning-subtle text-warning-emphasis' : 'bg-info-subtle text-info-emphasis';
    const escapedPath = item.path.replace(/"/g, '&quot;');
    const escapedName = item.name.replace(/"/g, '&quot;');

    return `
      <div class="list-group-item d-flex align-items-center justify-content-between p-2 mb-1 rounded border">
        <div class="d-flex align-items-center gap-2 overflow-hidden me-2">
          <i class="bi ${icon} fs-5 flex-shrink-0"></i>
          <div class="text-truncate">
            <div class="fw-semibold small text-truncate text-body">${escapedName}</div>
            <div class="text-muted font-monospace small text-truncate" title="${escapedPath}">${escapedPath}</div>
          </div>
        </div>
        <div class="d-flex align-items-center gap-1.5 flex-shrink-0">
          <span class="badge ${badgeClass} border">${typeLabel}</span>
          <button type="button" class="btn btn-sm btn-outline-danger py-0 px-1.5 rounded btn-remove-staged" data-staged-index="${index}" title="Исключить из списка">
            <i class="bi bi-x-lg"></i>
          </button>
        </div>
      </div>
    `;
  }).join('');

  container.querySelectorAll('.btn-remove-staged').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const idx = parseInt(btn.getAttribute('data-staged-index'), 10);
      removeStagedItem(idx);
    });
  });
}

/**
 * Загружает и отображает сводный список всех файлов и папок, находящихся в Git-слежении.
 * @param {string} [wsId]
 */
export async function loadTrackedItemsList(wsId = null) {
  const targetId = wsId || (getWorkspaceIdFn ? getWorkspaceIdFn() : '');
  const tbody = document.getElementById('ws-tracked-items-table-body');
  const countBadge = document.getElementById('ws-tracked-items-summary-badge');
  if (!tbody || !targetId) return;

  try {
    const [dirRes, sourcesRes] = await Promise.all([
      fetchJson(`/api/v1/workspaces/${encodeURIComponent(targetId)}/directory-contents`).catch(() => ({ items: [] })),
      fetchJson(`/api/v1/workspaces/${encodeURIComponent(targetId)}/sources`).catch(() => ({ sources: [] })),
    ]);

    const dirItems = dirRes.items || [];
    const extSources = sourcesRes.sources || [];
    const trackedDirItems = dirItems.filter(i => i.tracked_by_git || i.git_status !== 'Не отслеживается');
    const totalCount = trackedDirItems.length + extSources.length;

    if (countBadge) {
      countBadge.textContent = `${totalCount} ${t('workspace.trackedItemsSuffix', 'объектов в слежении')}`;
    }

    if (totalCount === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="5" class="text-center py-4 text-muted font-sans-serif">
            <i class="bi bi-inbox me-1"></i>${t('workspace.trackedEmptyMsg', 'В этой рабочей области пока нет файлов и папок на слежении. Выберите объекты выше для добавления.')}
          </td>
        </tr>
      `;
      return;
    }

    let rowsHtml = '';

    // 1. Внешние привязанные источники
    extSources.forEach(s => {
      const isDir = s.source_type === 'directory';
      const isSheet = s.source_type === 'google_sheet';
      const icon = isSheet ? 'bi-file-earmark-spreadsheet-fill text-success' : (isDir ? 'bi-folder2-open text-warning' : 'bi-file-earmark-text text-primary');
      const typeLabel = isSheet ? 'Google Sheets' : (isDir ? t('workspace.badgeTypeFolder', 'Папка') : t('workspace.badgeTypeFile', 'Файл'));
      const modeBadge = `<span class="badge bg-info-subtle text-info-emphasis border"><i class="bi bi-pin-angle me-1"></i>${t('workspace.badgeModeLinked', 'На диске (без копирования)')}</span>`;
      const statusBadge = s.status === 'error'
        ? `<span class="badge bg-danger-subtle text-danger border">Ошибка</span>`
        : `<span class="badge bg-success-subtle text-success border">Активен (${s.item_count || 0})</span>`;
      const fullPath = s.qualified_path || s.source_path;
      const escapedPath = fullPath.replace(/"/g, '&quot;');
      const escapedName = (s.name || s.source_path).replace(/"/g, '&quot;');

      rowsHtml += `
        <tr class="tracked-source-row" data-source-id="${s.source_id}">
          <td>
            <div class="d-flex align-items-center gap-1.5 overflow-hidden text-truncate">
              <i class="bi ${icon} fs-5 flex-shrink-0"></i>
              <div class="text-truncate">
                <span class="fw-semibold text-truncate">${escapedName}</span>
                <span class="text-muted font-monospace small text-truncate d-block" title="${escapedPath}">${escapedPath}</span>
              </div>
            </div>
          </td>
          <td class="text-nowrap"><span class="badge bg-secondary-subtle text-secondary border">${typeLabel}</span></td>
          <td class="text-nowrap">${modeBadge}</td>
          <td class="text-nowrap">${statusBadge}</td>
          <td class="text-nowrap text-end">
            <button type="button" class="btn btn-sm btn-outline-danger py-0 px-2 rounded btn-unlink-tracked-source" data-source-id="${s.source_id}" data-source-name="${escapedName}" title="${t('workspace.actionUnlink', 'Отвязать')}">
              <i class="bi bi-trash3 me-1"></i><span class="d-none d-lg-inline">${t('workspace.actionUnlink', 'Отвязать')}</span>
            </button>
          </td>
        </tr>
      `;
    });

    // 2. Файлы и папки директории рабочей области
    trackedDirItems.forEach(item => {
      const isDir = Boolean(item.is_dir);
      const icon = getPathIconClass(item.rel_path, isDir);
      const typeLabel = isDir ? t('workspace.badgeTypeFolder', 'Папка') : (item.extension || t('workspace.badgeTypeFile', 'Файл'));
      const isLinked = item.source_mode === 'linked';
      const modeBadge = isLinked
        ? `<span class="badge bg-info-subtle text-info-emphasis border"><i class="bi bi-pin-angle me-1"></i>${t('workspace.badgeModeLinked', 'На диске (без копирования)')}</span>`
        : `<span class="badge bg-primary-subtle text-primary border"><i class="bi bi-git me-1"></i>${t('workspace.badgeModeRepo', 'В репозитории (Git)')}</span>`;

      let statusBadge = `<span class="badge bg-success-subtle text-success border"><i class="bi bi-check2 me-1"></i>Отслеживается</span>`;
      if (item.git_status === 'Изменён' || item.git_status === 'Изменён (на диске)') {
        statusBadge = `<span class="badge bg-warning-subtle text-warning-emphasis border"><i class="bi bi-pencil me-1"></i>Изменён</span>`;
      } else if (item.git_status === 'Добавлен') {
        statusBadge = `<span class="badge bg-info-subtle text-info border"><i class="bi bi-plus me-1"></i>Добавлен</span>`;
      } else if (String(item.git_status || '').startsWith('На другом ПК')) {
        statusBadge = `<span class="badge bg-primary-subtle text-primary border"><i class="bi bi-pc-display me-1"></i>${item.git_status}</span>`;
      }

      const escapedRel = (item.rel_path || '').replace(/"/g, '&quot;');
      const actionWasmTitle = t('workspace.openInWasmEditor', 'Открыть во встроенном редакторе (Rust + Wasm)');
      const actionSysTitle = t('workspace.openInSystemEditor', 'Открыть в системном приложении');

      rowsHtml += `
        <tr class="tracked-dir-item-row" data-rel-path="${escapedRel}" data-is-dir="${isDir}">
          <td>
            <div class="d-flex align-items-center gap-1.5 overflow-hidden text-truncate">
              <i class="bi ${icon}"></i>
              <div class="text-truncate">
                <span class="fw-semibold text-truncate">${escapedRel}</span>
                ${item.local_path || item.qualified_path ? `<span class="text-muted font-monospace small text-truncate d-block" title="${item.qualified_path || item.local_path}">${item.qualified_path || item.local_path}</span>` : ''}
              </div>
            </div>
          </td>
          <td class="text-nowrap text-secondary font-monospace small">${typeLabel}</td>
          <td class="text-nowrap">${modeBadge}</td>
          <td class="text-nowrap">${statusBadge}</td>
          <td class="text-nowrap text-end">
            ${!isDir ? `
              <div class="d-inline-flex align-items-center gap-1">
                <button type="button" class="btn btn-sm btn-outline-primary py-0 px-2 rounded btn-open-wasm-editor" data-rel-path="${escapedRel}" title="${actionWasmTitle}">
                  <i class="bi bi-pencil-square me-1"></i><span class="d-none d-lg-inline">${t('workspace.actionEditWasm', 'Редактор')}</span>
                </button>
                <button type="button" class="btn btn-sm btn-outline-secondary py-0 px-1.5 rounded btn-open-system-editor" data-rel-path="${escapedRel}" title="${actionSysTitle}">
                  <i class="bi bi-box-arrow-up-right"></i>
                </button>
              </div>
            ` : ''}
          </td>
        </tr>
      `;
    });

    tbody.innerHTML = rowsHtml;

    // Обработчик отвязки источников
    tbody.querySelectorAll('.btn-unlink-tracked-source').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const sid = btn.getAttribute('data-source-id');
        const sName = btn.getAttribute('data-source-name') || '';
        const pattern = t('workspace.unlinkSourceConfirm', 'Отвязать «{name}» от отслеживания Git в этом рабочем пространстве?');
        if (!confirm(pattern.replace('{name}', sName))) return;

        try {
          await fetchJson(`/api/v1/workspaces/${encodeURIComponent(targetId)}/sources/${encodeURIComponent(sid)}`, {
            method: 'DELETE',
          });
          await loadTrackedItemsList(targetId);
          if (onItemsCommittedFn) await onItemsCommittedFn(targetId);
          if (typeof window.showToast === 'function') {
            window.showToast(t('workspace.sourceUnlinkedSuccess', 'Источник отвязан от слежения'), 'info');
          }
        } catch (err) {
          alert(`${t('workspace.errorLabel', 'Ошибка:')} ${err.message}`);
        }
      });
    });

  } catch (err) {
    console.warn('[TrackingController] Ошибка загрузки списка отслеживаемых объектов:', err);
    tbody.innerHTML = `
      <tr>
        <td colspan="5" class="text-center py-3 text-danger font-sans-serif">
          <i class="bi bi-exclamation-triangle me-1"></i>Ошибка загрузки: ${err.message}
        </td>
      </tr>
    `;
  }
}

/**
 * Инициализирует обработчики событий для добавления файлов/директорий и управления слежением.
 * @param {Function} getWsId
 * @param {Function} onCommitted
 */
export function initTrackingController(getWsId, onCommitted) {
  getWorkspaceIdFn = getWsId;
  onItemsCommittedFn = onCommitted;

  const clearStagedBtn = document.getElementById('btn-track-clear-staged');
  const refreshTrackedBtn = document.getElementById('btn-refresh-tracked-list');
  const addItemsBtn = document.getElementById('btn-track-add-items');
  const uploadInput = document.getElementById('ws-track-upload-input');

  // Монтирование единого модуля добавления директорий и файлов
  const pickerMount = document.getElementById('ws-track-picker-container');
  let trackSourcesPicker = null;
  if (pickerMount && !pickerMount._mounted) {
    pickerMount._mounted = true;
    trackSourcesPicker = mountTrackSourcesPicker(pickerMount, {
      prefix: 'wst-picker',
      onItemAdded: async (itemPath, itemType) => {
        addStagedPath(itemPath, itemType === 'directory');
      },
    });
  }

  // Очистка выбранного списка
  clearStagedBtn?.addEventListener('click', () => {
    clearStagedItems();
  });

  // Обновление таблицы отслеживаемых объектов
  refreshTrackedBtn?.addEventListener('click', async () => {
    const wsId = getWorkspaceIdFn ? getWorkspaceIdFn() : '';
    await loadTrackedItemsList(wsId);
  });

  uploadInput?.addEventListener('change', updateConvertersFromStaged);

  // Кнопка запуска Git-слежения
  addItemsBtn?.addEventListener('click', async () => {
    const currentWsId = getWorkspaceIdFn ? getWorkspaceIdFn() : '';
    if (!currentWsId) {
      alert(t('workspace.alertSelectOrCreateWsFirst', 'Сначала выберите или создайте рабочую область.'));
      return;
    }

    // Если в полях единого модуля введен путь, добавляем его перед отправкой
    const entered = trackSourcesPicker ? trackSourcesPicker.getEnteredPaths() : [];
    entered.forEach(e => addStagedPath(e.path, e.type === 'directory'));

    const pathsToCommit = getStagedPaths();
    const hasUploadFiles = uploadInput && uploadInput.files && uploadInput.files.length > 0;

    if (pathsToCommit.length === 0 && !hasUploadFiles) {
      alert(t('workspace.alertSelectFileOrFolderToTrack', 'Пожалуйста, выберите или укажите хотя бы один файл или папку для слежения.'));
      return;
    }

    const commitMsgInput = document.getElementById('ws-track-commit-msg');
    const statusText = document.getElementById('ws-track-status-text');
    const pdfMode = document.querySelector('input[name="ws-conv-pdf-mode"]:checked')?.value || 'local';
    const ocrMode = document.querySelector('input[name="ws-conv-ocr-mode"]:checked')?.value || 'model';
    const audioMode = document.querySelector('input[name="ws-conv-audio-mode"]:checked')?.value || 'model';
    const commitMsg = commitMsgInput?.value?.trim() || null;
    const copyToWorkspace = Boolean(document.getElementById('ws-track-copy-checkbox')?.checked);

    if (statusText) {
      statusText.innerHTML = `<span class="text-primary"><i class="bi bi-hourglass-split me-1"></i>${t('workspace.trackingProcessingCommit', 'Обработка и коммит в Git...')}</span>`;
    }
    addItemsBtn.disabled = true;

    try {
      let filesCount = 0;

      // 1. Загрузка файлов через multipart/form-data
      if (hasUploadFiles) {
        const formData = new FormData();
        for (let i = 0; i < uploadInput.files.length; i++) {
          formData.append('files', uploadInput.files[i]);
        }
        if (commitMsg) formData.append('commit_message', commitMsg);
        formData.append('pdf_mode', pdfMode);
        formData.append('ocr_mode', ocrMode);
        formData.append('audio_mode', audioMode);

        const resUpload = await fetch(`/api/v1/workspaces/${encodeURIComponent(currentWsId)}/files/upload`, {
          method: 'POST',
          body: formData,
        });
        if (!resUpload.ok) {
          throw new Error(`${t('workspace.uploadErrorHttp', 'Ошибка загрузки: HTTP')} ${resUpload.status}`);
        }
        const uploadData = await resUpload.json();
        filesCount += uploadData.files_added || uploadInput.files.length;
        uploadInput.value = '';
      }

      // 2. Добавление путей на диске
      if (pathsToCommit.length > 0) {
        const resItems = await fetchJson(`/api/v1/workspaces/${encodeURIComponent(currentWsId)}/items`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            items: pathsToCommit,
            copy_to_workspace: copyToWorkspace,
            commit_message: commitMsg,
            pdf_mode: pdfMode,
            ocr_mode: ocrMode,
            audio_mode: audioMode,
          }),
        });
        filesCount += resItems.files_added || pathsToCommit.length;
      }

      clearStagedItems();
      if (commitMsgInput) commitMsgInput.value = '';
      if (trackSourcesPicker) trackSourcesPicker.clearInputs();

      if (statusText) {
        statusText.innerHTML = `<span class="text-success"><i class="bi bi-check-circle-fill me-1"></i>${t('workspace.trackingSuccessAdded', 'Успешно добавлено в Git:')} ${filesCount} ${t('workspace.filesSuffix', 'файлов.')}</span>`;
      }

      if (typeof window.showToast === 'function') {
        window.showToast(`${t('workspace.trackingToastStarted', 'Git начал отслеживание:')} ${filesCount} ${t('workspace.filesCommittedSuffix', 'файлов зафиксировано')}`, 'success');
      }

      await loadTrackedItemsList(currentWsId);
      if (onItemsCommittedFn) {
        await onItemsCommittedFn(currentWsId);
      }
    } catch (err) {
      console.error('[TrackingController] Ошибка добавления объектов в Git:', err);
      if (statusText) {
        statusText.innerHTML = `<span class="text-danger"><i class="bi bi-x-circle-fill me-1"></i>${t('workspace.errorLabel', 'Ошибка:')} ${err.message}</span>`;
      }
      alert(`${t('workspace.alertTrackingAddError', 'Ошибка добавления в Git:')} ${err.message}`);
    } finally {
      addItemsBtn.disabled = false;
    }
  });

  renderStagedItems();
}
