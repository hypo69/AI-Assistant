/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Google Drive Tab Controller
 * =============================================================================
 * Description:
 *   Клиентский контроллер управления файлами Google Drive: выборка,
 *   отображение списка, навигация по папкам, вызов модального редактора файлов,
 *   фильтрация, загрузка локальных документов и скачивание.
 *
 * File: main.js
 * Package: apps/ai_assistant/api/webgui/tab_drive
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-28 19:00:00
 * =============================================================================
 */

(function () {
  'use strict';

  let currentMime = '';
  let currentFolderId = '';
  let folderBreadcrumbs = [{ id: '', name: 'Google Диск' }];
  let allFiles = [];

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function formatBytes(bytes) {
    if (!bytes || isNaN(bytes)) return '-';
    const num = parseInt(bytes, 10);
    if (num < 1024) return num + ' B';
    if (num < 1024 * 1024) return (num / 1024).toFixed(1) + ' KB';
    return (num / (1024 * 1024)).toFixed(1) + ' MB';
  }

  function formatDateTime(isoStr) {
    if (!isoStr) return '-';
    try {
      const d = new Date(isoStr);
      return d.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return isoStr;
    }
  }

  function getFileIcon(mime) {
    if (!mime) return 'bi-file-earmark';
    if (mime.includes('folder')) return 'bi-folder-fill text-warning';
    if (mime.includes('spreadsheet') || mime.includes('excel')) return 'bi-file-earmark-spreadsheet-fill text-success';
    if (mime.includes('document') || mime.includes('word')) return 'bi-file-earmark-word-fill text-primary';
    if (mime.includes('presentation')) return 'bi-file-earmark-slides-fill text-danger';
    if (mime.includes('pdf')) return 'bi-file-earmark-pdf-fill text-danger';
    if (mime.includes('image')) return 'bi-file-earmark-image-fill text-info';
    if (mime.includes('zip') || mime.includes('tar') || mime.includes('compressed')) return 'bi-file-earmark-zip-fill text-secondary';
    return 'bi-file-earmark-text text-muted';
  }

  function renderBreadcrumbs() {
    const nav = document.getElementById('drive-breadcrumbs-nav');
    const list = document.getElementById('drive-breadcrumbs-list');
    if (!nav || !list) return;

    if (folderBreadcrumbs.length <= 1) {
      nav.classList.add('d-none');
      return;
    }

    nav.classList.remove('d-none');
    list.innerHTML = folderBreadcrumbs.map((b, idx) => {
      const isLast = idx === folderBreadcrumbs.length - 1;
      if (isLast) {
        return `<li class="breadcrumb-item active" aria-current="page">${escapeHtml(b.name)}</li>`;
      }
      return `<li class="breadcrumb-item"><a href="#" class="text-decoration-none drive-bc-link" data-folder-id="${escapeHtml(b.id)}" data-bc-idx="${idx}">${escapeHtml(b.name)}</a></li>`;
    }).join('');

    list.querySelectorAll('.drive-bc-link').forEach(link => {
      link.addEventListener('click', (e) => {
        e.preventDefault();
        const fId = link.getAttribute('data-folder-id') || '';
        const idx = parseInt(link.getAttribute('data-bc-idx'), 10);
        folderBreadcrumbs = folderBreadcrumbs.slice(0, idx + 1);
        currentFolderId = fId;
        renderBreadcrumbs();
        loadFiles();
      });
    });
  }

  function navigateToFolder(folderId, folderName) {
    currentFolderId = folderId;
    folderBreadcrumbs.push({ id: folderId, name: folderName });
    renderBreadcrumbs();
    loadFiles();
  }

  async function openDriveFileInEditor(file) {
    if (!file) return;

    const target = {
      isDir: false,
      relPath: file.name,
      name: file.name,
      driveFileId: file.id,
      id: file.id,
      mimeType: file.mimeType,
      webViewLink: file.webViewLink,
      source: 'drive',
    };

    if (typeof window.openEditorModal === 'function') {
      await window.openEditorModal(target, 'gdrive');
      return;
    }

    try {
      const module = await import('/html/js/ide_tree_context_menu.js?v=20261028_v1');
      if (typeof module.openEditorModal === 'function') {
        await module.openEditorModal(target, 'gdrive');
        return;
      }
    } catch (err) {
      console.warn('[TabDrive] Не удалось загрузить openEditorModal:', err);
    }
  }

  async function loadFiles() {
    const tbody = document.getElementById('drive-files-tbody');
    const emptyState = document.getElementById('drive-empty-state');
    if (!tbody) return;

    tbody.innerHTML = `
      <tr>
        <td colspan="5" class="text-center py-5">
          <div class="spinner-border text-primary spinner-border-sm" role="status"></div>
          <span class="ms-2 small text-muted">Загрузка файлов Google Drive...</span>
        </td>
      </tr>`;
    if (emptyState) emptyState.classList.add('d-none');

    try {
      const qInput = document.getElementById('drive-search-input');
      const query = qInput ? qInput.value.trim() : '';

      let url = `/api/v1/drive/files?limit=50`;
      if (query) url += `&q=${encodeURIComponent("name contains '" + query + "'")}`;
      if (currentMime) url += `&mime_type=${encodeURIComponent(currentMime)}`;
      if (currentFolderId) url += `&folder_id=${encodeURIComponent(currentFolderId)}`;

      const res = await fetch(url);
      const data = await res.json();

      if (!res.ok || data.status === 'error') {
        throw new Error(data.detail || data.error || 'Ошибка загрузки файлов');
      }

      allFiles = data.files || [];
      renderFiles(allFiles);
    } catch (err) {
      tbody.innerHTML = `
        <tr>
          <td colspan="5" class="text-center py-4 text-danger small">
            <i class="bi bi-exclamation-triangle-fill me-1"></i> ${escapeHtml(err.message)}
          </td>
        </tr>`;
    }
  }

  function renderFiles(files) {
    const tbody = document.getElementById('drive-files-tbody');
    const emptyState = document.getElementById('drive-empty-state');
    if (!tbody) return;

    if (!files || files.length === 0) {
      tbody.innerHTML = '';
      if (emptyState) emptyState.classList.remove('d-none');
      return;
    }

    if (emptyState) emptyState.classList.add('d-none');

    tbody.innerHTML = files.map((f, idx) => {
      const isFolder = f.mimeType && f.mimeType.includes('folder');
      const iconClass = getFileIcon(f.mimeType);
      const sizeStr = formatBytes(f.size);
      const dateStr = formatDateTime(f.modifiedTime);
      const openBtn = f.webViewLink ? `<a href="${escapeHtml(f.webViewLink)}" target="_blank" class="btn btn-sm btn-outline-primary py-0 px-2" title="Открыть в Google Диске"><i class="bi bi-box-arrow-up-right"></i></a>` : '';
      const editBtn = !isFolder ? `<button class="btn btn-sm btn-outline-primary py-0 px-2 btn-edit-file" data-file-id="${escapeHtml(f.id)}" title="Редактировать в модальном окне"><i class="bi bi-pencil-square"></i></button>` : '';
      const downloadBtn = !isFolder ? `<a href="/api/v1/drive/download/${escapeHtml(f.id)}" class="btn btn-sm btn-outline-success py-0 px-2" title="Скачать"><i class="bi bi-download"></i></a>` : '';

      return `
        <tr id="drive-row-${escapeHtml(f.id)}" class="drive-file-row align-middle cursor-pointer" data-file-id="${escapeHtml(f.id)}" title="${isFolder ? 'Открыть папку' : 'Редактировать в модальном окне'}">
          <td class="text-center small text-muted">${idx + 1}</td>
          <td>
            <div class="d-flex align-items-center gap-2">
              <i class="bi ${iconClass} fs-5"></i>
              <div>
                <div class="fw-semibold text-truncate max-w-400 drive-file-name" title="${escapeHtml(f.name)}">${escapeHtml(f.name)}</div>
                <div class="font-size-75 text-muted">${escapeHtml(f.mimeType || '')}</div>
              </div>
            </div>
          </td>
          <td class="small text-muted font-monospace">${sizeStr}</td>
          <td class="small text-muted">${dateStr}</td>
          <td class="text-end pe-3 drive-actions-cell">
            <div class="d-flex justify-content-end gap-1">
              ${editBtn}
              ${openBtn}
              ${downloadBtn}
              <button class="btn btn-sm btn-outline-danger py-0 px-2 btn-delete-file" data-file-id="${escapeHtml(f.id)}" title="Удалить">
                <i class="bi bi-trash3"></i>
              </button>
            </div>
          </td>
        </tr>
      `;
    }).join('');

    // Привязка клика по всей строке файла в панели
    tbody.querySelectorAll('.drive-file-row').forEach(row => {
      row.addEventListener('click', async (e) => {
        if (e.target.closest('.drive-actions-cell') || e.target.closest('a') || e.target.closest('button')) {
          return;
        }
        const fileId = row.getAttribute('data-file-id');
        const file = allFiles.find(item => item.id === fileId);
        if (!file) return;

        if (file.mimeType && file.mimeType.includes('folder')) {
          navigateToFolder(file.id, file.name);
          return;
        }

        await openDriveFileInEditor(file);
      });
    });

    // Привязка клика по кнопке редактирования
    tbody.querySelectorAll('.btn-edit-file').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const fileId = btn.getAttribute('data-file-id');
        const file = allFiles.find(item => item.id === fileId);
        if (!file) return;
        await openDriveFileInEditor(file);
      });
    });

    // Привязка клика по кнопке удаления
    tbody.querySelectorAll('.btn-delete-file').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const fileId = btn.getAttribute('data-file-id');
        if (!confirm('Удалить этот файл с Google Диска?')) return;
        try {
          btn.disabled = true;
          const res = await fetch(`/api/v1/drive/files/${fileId}`, { method: 'DELETE' });
          if (res.ok) {
            const row = document.getElementById(`drive-row-${fileId}`);
            if (row) row.remove();
          } else {
            alert('Не удалось удалить файл');
          }
        } catch (err) {
          alert('Ошибка при удалении: ' + err.message);
        }
      });
    });
  }

  function setupEventHandlers() {
    const btnRefresh = document.getElementById('btn-drive-refresh');
    if (btnRefresh) btnRefresh.addEventListener('click', loadFiles);

    const qInput = document.getElementById('drive-search-input');
    if (qInput) {
      qInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') loadFiles();
      });
    }

    const btnClear = document.getElementById('btn-drive-search-clear');
    if (btnClear && qInput) {
      btnClear.addEventListener('click', () => {
        qInput.value = '';
        loadFiles();
      });
    }

    // Фильтры по MIME типу
    document.querySelectorAll('#drive-type-filters .filter-type-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('#drive-type-filters .filter-type-btn').forEach(b => {
          b.classList.remove('btn-primary', 'active');
          b.classList.add('btn-outline-secondary');
        });
        btn.classList.remove('btn-outline-secondary');
        btn.classList.add('btn-primary', 'active');
        currentMime = btn.getAttribute('data-mime') || '';
        loadFiles();
      });
    });

    // Открытие модалки выгрузки
    const btnUpload = document.getElementById('btn-drive-upload');
    const modalEl = document.getElementById('modal-drive-upload');
    if (btnUpload && modalEl) {
      btnUpload.addEventListener('click', () => {
        const form = document.getElementById('form-drive-upload');
        if (form) form.reset();
        const folderIdInput = document.getElementById('drive-upload-folder-id');
        if (folderIdInput && currentFolderId) folderIdInput.value = currentFolderId;
        const errBox = document.getElementById('drive-upload-error');
        if (errBox) errBox.classList.add('d-none');
        const prg = document.getElementById('drive-upload-progress');
        if (prg) prg.classList.add('d-none');
        const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.show();
      });
    }

    // Запуск выгрузки файла
    const btnStartUpload = document.getElementById('btn-drive-start-upload');
    if (btnStartUpload) {
      btnStartUpload.addEventListener('click', async () => {
        const fileInput = document.getElementById('drive-upload-file-input');
        const folderIdInput = document.getElementById('drive-upload-folder-id');
        const errBox = document.getElementById('drive-upload-error');
        const prg = document.getElementById('drive-upload-progress');

        if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
          if (errBox) {
            errBox.textContent = 'Пожалуйста, выберите файл для загрузки';
            errBox.classList.remove('d-none');
          }
          return;
        }

        const file = fileInput.files[0];
        const folderId = folderIdInput ? folderIdInput.value.trim() : '';

        const formData = new FormData();
        formData.append('file', file);
        if (folderId) formData.append('folder_id', folderId);

        try {
          btnStartUpload.disabled = true;
          if (prg) prg.classList.remove('d-none');

          const res = await fetch('/api/v1/drive/upload', {
            method: 'POST',
            body: formData,
          });
          const data = await res.json();
          if (!res.ok || data.status === 'error') {
            throw new Error(data.detail || data.error || 'Ошибка загрузки файла');
          }

          const modal = bootstrap.Modal.getInstance(modalEl);
          if (modal) modal.hide();
          loadFiles();
        } catch (err) {
          if (errBox) {
            errBox.textContent = err.message;
            errBox.classList.remove('d-none');
          }
        } finally {
          btnStartUpload.disabled = false;
          if (prg) prg.classList.add('d-none');
        }
      });
    }
  }

  window.initDriveTab = function () {
    setupEventHandlers();
    loadFiles();
  };

  window.refreshDriveFiles = function () {
    loadFiles();
  };

  window.deactivateDriveTab = function () {
    allFiles = [];
    currentFolderId = '';
    folderBreadcrumbs = [{ id: '', name: 'Google Диск' }];
  };
})();
