/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - IDE Tree View Context Menu
 * =============================================================================
 * Description:
 *   Контекстное меню по правому клику мыши (ПКМ) для интерактивного дерева
 *   файлов и папок проводника (#ide-file-tree-container).
 *   Реализует операции:
 *   - Добавить: создание файла или директории в выбранной папке с коммитом в Git
 *   - Удалить: удаление файла/каталога с подтверждением и коммитом в Git
 *   - Редактировать: модальный редактор текста с горячей клавишей Ctrl+S
 *   - Версии: просмотр истории версий Git для файла с просмотром ревизии и diff
 *
 * File: ide_tree_context_menu.js
 * Package: apps/ai_assistant/api/webgui/js
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-28 19:00:00
 * =============================================================================
 */

import { getActiveWorkspaceId } from './top_workspace_dropdown.js';
import { refreshFileTree } from './ide_file_explorer.js';

let menuElement = null;
let currentTarget = {
  isDir: true,
  relPath: '',
  name: '',
};

/**
 * Создает DOM-структуру контекстного меню проводника, если она еще не создана.
 */
function ensureTreeContextMenuDOM() {
  if (menuElement) return;

  const menu = document.createElement('div');
  menu.id = 'ide-tree-context-menu';
  menu.className = 'custom-context-menu d-none';
  menu.innerHTML = `
    <div class="custom-context-menu-header" id="cm-tree-target-header">Проводник</div>
    <div class="custom-context-menu-item" data-tree-action="add" id="cm-tree-item-add" title="Создать новый файл или папку">
      <span class="custom-context-menu-icon"><i class="bi bi-plus-circle text-success"></i></span>
      <span class="custom-context-menu-label">Добавить</span>
      <span class="text-muted font-size-80">Файл/Папка</span>
    </div>
    <div class="custom-context-menu-item" data-tree-action="edit" id="cm-tree-item-edit" title="Редактировать текстовый файл">
      <span class="custom-context-menu-icon"><i class="bi bi-pencil text-primary"></i></span>
      <span class="custom-context-menu-label">Редактировать</span>
    </div>
    <div class="custom-context-menu-item" data-tree-action="wasm-editor" id="cm-tree-item-wasm-editor" title="Открыть в универсальном редакторе Rust + WebAssembly (все типы файлов VS Code)">
      <span class="custom-context-menu-icon"><i class="bi bi-code-square text-warning"></i></span>
      <span class="custom-context-menu-label">Wasm Редактор</span>
      <span class="badge bg-warning-subtle text-warning custom-context-menu-badge">Wasm</span>
    </div>
    <div class="custom-context-menu-item" data-tree-action="versions" id="cm-tree-item-versions" title="Посмотреть историю версий Git">
      <span class="custom-context-menu-icon"><i class="bi bi-clock-history text-info"></i></span>
      <span class="custom-context-menu-label">Версии</span>
      <span class="badge bg-secondary-subtle text-secondary custom-context-menu-badge">Git</span>
    </div>
    <div class="custom-context-menu-divider"></div>
    <div class="custom-context-menu-item text-danger" data-tree-action="delete" id="cm-tree-item-delete" title="Удалить файл или папку">
      <span class="custom-context-menu-icon"><i class="bi bi-trash text-danger"></i></span>
      <span class="custom-context-menu-label text-danger">Удалить</span>
      <span class="text-muted font-size-80">Del</span>
    </div>
  `;

  document.body.appendChild(menu);
  menuElement = menu;

  // Слушатель кликов по пунктам меню
  menuElement.addEventListener('click', (e) => {
    const item = e.target.closest('.custom-context-menu-item');
    if (!item) return;
    const action = item.getAttribute('data-tree-action');
    if (action) {
      handleTreeAction(action);
    }
  });
}

/**
 * Скрывает контекстное меню проводника.
 */
export function hideTreeContextMenu() {
  if (menuElement && !menuElement.classList.contains('d-none')) {
    menuElement.classList.add('d-none');
  }
}

/**
 * Показывает Toast сообщение.
 * @param {string} msg 
 * @param {string} type 
 */
function showToast(msg, type = 'info') {
  if (typeof window.showToast === 'function') {
    window.showToast(msg, type);
  } else if (typeof window.showNotificationToast === 'function') {
    window.showNotificationToast(msg, type);
  } else {
    console.log(`[Toast ${type}] ${msg}`);
  }
}

/**
 * Обрабатывает выбранное действие из контекстного меню.
 * @param {string} action 
 */
async function handleTreeAction(action) {
  hideTreeContextMenu();
  const wsId = getActiveWorkspaceId() || 'default';

  switch (action) {
    case 'add':
      openCreateModal(currentTarget);
      break;

    case 'edit':
      if (currentTarget.isDir) {
        showToast('ℹ️ Редактирование доступно только для файлов', 'secondary');
        return;
      }
      openEditorModal(currentTarget, wsId);
      break;

    case 'wasm-editor':
      if (currentTarget.isDir) {
        showToast('ℹ️ Редактирование доступно только для файлов', 'secondary');
        return;
      }
      if (typeof window.switchTab === 'function') {
        await window.switchTab('tab-file-editor');
      }
      if (typeof window.openFileInWasmEditor === 'function') {
        await window.openFileInWasmEditor(currentTarget.relPath, wsId, false);
      }
      break;

    case 'versions':
      openVersionsModal(currentTarget, wsId);
      break;

    case 'delete':
      openDeleteModal(currentTarget, wsId);
      break;
  }
}

/**
 * Открывает модальное окно добавления файла или папки.
 * @param {{isDir: boolean, relPath: string, name: string}} target 
 */
function openCreateModal(target) {
  const modalEl = document.getElementById('modal-ide-create-item');
  if (!modalEl || !window.bootstrap) return;

  const parentPathEl = document.getElementById('ide-create-parent-path');
  const nameInput = document.getElementById('ide-create-item-name');
  const contentInput = document.getElementById('ide-create-item-content');
  const contentGroup = document.getElementById('ide-create-content-group');
  const radioFile = document.getElementById('ide-create-type-file');
  const radioFolder = document.getElementById('ide-create-type-folder');

  // Вычисляем целевую родительскую папку
  let parentFolder = '';
  if (target.isDir) {
    parentFolder = target.relPath || '';
  } else if (target.relPath) {
    const parts = target.relPath.split('/');
    parts.pop();
    parentFolder = parts.join('/');
  }

  if (parentPathEl) {
    parentPathEl.textContent = parentFolder ? `/${parentFolder}/` : '/ (корень)';
    parentPathEl.dataset.parentDir = parentFolder;
  }

  if (nameInput) {
    nameInput.value = '';
    setTimeout(() => nameInput.focus(), 300);
  }
  if (contentInput) contentInput.value = '';
  if (radioFile) radioFile.checked = true;
  if (contentGroup) contentGroup.classList.remove('d-none');

  radioFolder?.addEventListener('change', () => {
    if (radioFolder.checked) contentGroup?.classList.add('d-none');
  });
  radioFile?.addEventListener('change', () => {
    if (radioFile.checked) contentGroup?.classList.remove('d-none');
  });

  const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
  modal.show();
}

/**
 * Инициализирует обработчик отправки формы создания в модальном окне.
 */
function initCreateModalSubmit() {
  const submitBtn = document.getElementById('ide-btn-submit-create');
  submitBtn?.addEventListener('click', async () => {
    const modalEl = document.getElementById('modal-ide-create-item');
    const parentPathEl = document.getElementById('ide-create-parent-path');
    const nameInput = document.getElementById('ide-create-item-name');
    const contentInput = document.getElementById('ide-create-item-content');
    const isFolder = document.getElementById('ide-create-type-folder')?.checked || false;

    const name = (nameInput?.value || '').trim();
    if (!name) {
      alert('Пожалуйста, укажите имя создаваемого объекта.');
      nameInput?.focus();
      return;
    }

    const parentDir = parentPathEl?.dataset.parentDir || '';
    const fullRelPath = parentDir ? `${parentDir}/${name}` : name;
    const wsId = getActiveWorkspaceId() || 'default';
    const content = contentInput?.value || '';

    submitBtn.disabled = true;
    try {
      const res = await fetch(`/api/v1/workspaces/${encodeURIComponent(wsId)}/items/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          rel_path: fullRelPath,
          is_dir: isFolder,
          content: isFolder ? '' : content,
        }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Ошибка создания объекта');

      if (modalEl && window.bootstrap) {
        bootstrap.Modal.getInstance(modalEl)?.hide();
      }

      showToast(`✅ ${isFolder ? 'Папка' : 'Файл'} "${fullRelPath}" успешно создан`, 'success');
      await refreshFileTree(wsId);
    } catch (err) {
      showToast(`❌ Ошибка создания: ${err.message}`, 'danger');
    } finally {
      submitBtn.disabled = false;
    }
  });
}

/**
 * Открывает модальное окно текстового редактора файла (встроенный редактор для txt, md и других форматов).
 * @param {{isDir: boolean, relPath: string, name: string}} target 
 * @param {string} wsId 
 */
export async function openEditorModal(target, wsId) {
  const modalEl = document.getElementById('modal-ide-file-editor');
  if (!modalEl || !window.bootstrap) return;

  const titleEl = document.getElementById('ide-editor-file-path');
  const textarea = document.getElementById('ide-editor-textarea');
  const statsEl = document.getElementById('ide-editor-stats');
  const binaryNotice = document.getElementById('ide-editor-binary-notice');
  const textContainer = document.getElementById('ide-editor-text-container');
  const saveBtn = document.getElementById('ide-editor-btn-save');
  const commitMsgInput = document.getElementById('ide-editor-commit-msg');
  const statusEl = document.getElementById('ide-editor-save-status');

  // Элементы переключения режима Редактор / Предпросмотр для Markdown
  const viewModeGroup = document.getElementById('ide-editor-view-mode-group');
  const btnCode = document.getElementById('ide-editor-tab-code');
  const btnPreview = document.getElementById('ide-editor-tab-preview');
  const mdPreview = document.getElementById('ide-editor-markdown-preview');

  const isDrive = Boolean(target.driveFileId || target.source === 'drive' || wsId === 'gdrive');
  const driveFileId = target.driveFileId || target.id;

  const fileName = target.name || target.relPath || 'file';
  const ext = (fileName.split('.').pop() || '').toLowerCase();
  const isMarkdown = ext === 'md' || ext === 'markdown';

  if (titleEl) {
    titleEl.textContent = isDrive ? `Google Drive: ${fileName}` : target.relPath;
  }
  if (statusEl) statusEl.textContent = '';
  if (commitMsgInput) {
    commitMsgInput.value = '';
    if (isDrive) {
      commitMsgInput.parentElement?.classList.add('d-none');
    } else {
      commitMsgInput.parentElement?.classList.remove('d-none');
    }
  }

  // Сброс режима просмотра на вкладку редактора
  if (viewModeGroup) {
    if (isMarkdown) {
      viewModeGroup.classList.remove('d-none');
    } else {
      viewModeGroup.classList.add('d-none');
    }
  }
  btnCode?.classList.add('active');
  btnPreview?.classList.remove('active');
  textarea?.classList.remove('d-none');
  mdPreview?.classList.add('d-none');

  const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
  modal.show();

  if (textarea) {
    textarea.value = 'Загрузка содержимого файла...';
    textarea.disabled = true;
  }
  if (saveBtn) saveBtn.disabled = true;

  try {
    const fetchUrl = isDrive
      ? `/api/v1/drive/files/${encodeURIComponent(driveFileId)}/content`
      : `/api/v1/workspaces/${encodeURIComponent(wsId)}/file-content?rel_path=${encodeURIComponent(target.relPath)}`;

    const res = await fetch(fetchUrl);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.error || 'Не удалось прочитать файл');

    if (data.is_binary) {
      binaryNotice?.classList.remove('d-none');
      textContainer?.classList.add('d-none');
      viewModeGroup?.classList.add('d-none');
      if (saveBtn) saveBtn.classList.add('d-none');
    } else {
      binaryNotice?.classList.add('d-none');
      textContainer?.classList.remove('d-none');
      if (saveBtn) saveBtn.classList.remove('d-none');

      if (textarea) {
        textarea.value = data.content ?? '';
        textarea.disabled = false;
        setTimeout(() => textarea.focus(), 250);
      }
      if (saveBtn) saveBtn.disabled = false;

      const updateStats = () => {
        const val = textarea?.value || '';
        const lines = val.split('\n').length;
        if (statsEl) statsEl.textContent = `Строк: ${lines} | Символов: ${val.length}`;
      };
      updateStats();
      textarea?.addEventListener('input', updateStats);
    }
  } catch (err) {
    if (textarea) textarea.value = `Ошибка загрузки файла: ${err.message}`;
    showToast(`❌ Ошибка открытия: ${err.message}`, 'danger');
  }

  // Переключение режимов: Редактор / Предпросмотр Markdown
  const switchToCode = () => {
    btnCode?.classList.add('active');
    btnPreview?.classList.remove('active');
    mdPreview?.classList.add('d-none');
    textarea?.classList.remove('d-none');
    textarea?.focus();
  };

  const switchToPreview = () => {
    btnPreview?.classList.add('active');
    btnCode?.classList.remove('active');
    textarea?.classList.add('d-none');
    if (mdPreview) {
      mdPreview.classList.remove('d-none');
      const raw = textarea?.value || '';
      if (typeof window.marked !== 'undefined' && typeof window.marked.parse === 'function') {
        mdPreview.innerHTML = window.marked.parse(raw);
      } else {
        mdPreview.textContent = raw;
      }
    }
  };

  if (btnCode) btnCode.onclick = switchToCode;
  if (btnPreview) btnPreview.onclick = switchToPreview;

  // Привязка кнопки открытия в системном приложении / веб-ссылке
  const openInSystem = async () => {
    if (isDrive) {
      if (target.webViewLink) {
        window.open(target.webViewLink, '_blank');
      } else {
        window.location.href = `/api/v1/drive/download/${encodeURIComponent(driveFileId)}`;
      }
      return;
    }
    try {
      await fetch(`/api/v1/workspaces/${encodeURIComponent(wsId)}/open-file`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rel_path: target.relPath }),
      });
      showToast(`🚀 Файл ${target.name} открыт в системном приложении`, 'info');
    } catch (_) {}
  };

  const sysOpenBtn = document.getElementById('ide-editor-btn-system-open');
  if (sysOpenBtn) {
    if (isDrive) {
      sysOpenBtn.innerHTML = '<i class="bi bi-box-arrow-up-right me-1"></i>В Google Диске';
    } else {
      sysOpenBtn.innerHTML = '<i class="bi bi-box-arrow-up-right me-1"></i>В системе';
    }
    sysOpenBtn.onclick = openInSystem;
  }
  const binOpenBtn = document.getElementById('ide-editor-btn-binary-open');
  if (binOpenBtn) {
    if (isDrive) {
      binOpenBtn.innerHTML = '<i class="bi bi-download me-1"></i>Скачать с Google Диска';
    } else {
      binOpenBtn.textContent = 'Открыть в ассоциированном приложении';
    }
    binOpenBtn.onclick = openInSystem;
  }

  // Сохранение изменений
  const performSave = async () => {
    if (!textarea || textarea.disabled) return;
    const newContent = textarea.value;
    const commitMsg = commitMsgInput?.value?.trim() || null;

    if (saveBtn) saveBtn.disabled = true;
    if (statusEl) statusEl.textContent = isDrive ? '⏳ Сохранение на Google Диск...' : '⏳ Сохранение в Git...';

    try {
      if (isDrive) {
        const res = await fetch(`/api/v1/drive/files/${encodeURIComponent(driveFileId)}/content`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            content: newContent,
          }),
        });
        const resData = await res.json();
        if (!res.ok) throw new Error(resData.detail || resData.error || 'Ошибка сохранения');

        if (statusEl) statusEl.textContent = `✅ Сохранено на Google Диск (${new Date().toLocaleTimeString()})`;
        showToast(`✅ Файл ${fileName} успешно сохранен на Google Диск`, 'success');
        if (typeof window.refreshDriveFiles === 'function') {
          window.refreshDriveFiles();
        }
      } else {
        const res = await fetch(`/api/v1/workspaces/${encodeURIComponent(wsId)}/file-content`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            rel_path: target.relPath,
            content: newContent,
            commit_message: commitMsg,
          }),
        });
        const resData = await res.json();
        if (!res.ok) throw new Error(resData.detail || 'Ошибка сохранения');

        if (statusEl) statusEl.textContent = `✅ Сохранено (${new Date().toLocaleTimeString()})`;
        showToast(`✅ Файл ${target.name} успешно сохранен в Git`, 'success');
        await refreshFileTree(wsId);
      }
    } catch (err) {
      if (statusEl) statusEl.textContent = `❌ Ошибка: ${err.message}`;
      showToast(`❌ Ошибка сохранения: ${err.message}`, 'danger');
    } finally {
      if (saveBtn) saveBtn.disabled = false;
    }
  };

  if (saveBtn) saveBtn.onclick = performSave;

  // Горячая клавиша Ctrl+S внутри редактора
  textarea?.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      e.preventDefault();
      performSave();
    }
  });
}
window.openEditorModal = openEditorModal;

/**
 * Открывает модальное окно истории версий файла.
 * @param {{isDir: boolean, relPath: string, name: string}} target 
 * @param {string} wsId 
 */
async function openVersionsModal(target, wsId) {
  const modalEl = document.getElementById('modal-ide-file-versions');
  if (!modalEl || !window.bootstrap) return;

  const pathEl = document.getElementById('ide-versions-file-path');
  const tbody = document.getElementById('ide-versions-table-body');
  const previewContent = document.getElementById('ide-versions-preview-content');
  const previewBadge = document.getElementById('ide-versions-preview-badge');
  const previewTitle = document.getElementById('ide-versions-preview-title');

  if (pathEl) pathEl.textContent = target.relPath || '(все файлы репозитория)';
  if (tbody) tbody.innerHTML = `<tr><td colspan="5" class="text-center py-3 text-muted"><div class="spinner-border spinner-border-sm text-primary me-2"></div>Загрузка версий Git...</td></tr>`;
  if (previewContent) previewContent.textContent = 'Выберите коммит в таблице для предпросмотра содержимого или различий';
  if (previewBadge) previewBadge.textContent = 'HEAD';

  const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
  modal.show();

  try {
    const qRel = target.relPath ? `&file_path=${encodeURIComponent(target.relPath)}` : '';
    const res = await fetch(`/api/v1/history?workspace_id=${encodeURIComponent(wsId)}${qRel}&limit=50`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const commits = await res.json();

    if (!commits || commits.length === 0) {
      if (tbody) tbody.innerHTML = `<tr><td colspan="5" class="text-center py-3 text-muted">Для данного файла коммиты еще не зафиксированы</td></tr>`;
      return;
    }

    if (tbody) {
      tbody.innerHTML = commits.map((c) => {
        const hash = c.short_hash || (c.commit_hash ? c.commit_hash.slice(0, 7) : '---');
        const fullHash = c.commit_hash || '';
        const date = c.timestamp ? c.timestamp.replace('T', ' ').slice(0, 19) : '';
        const author = c.author || 'Неизвестно';
        const msg = c.message || '';

        return `
          <tr data-commit-hash="${fullHash}">
            <td><span class="badge bg-secondary font-monospace">${hash}</span></td>
            <td class="text-muted small">${date}</td>
            <td><span class="fw-medium">${author}</span></td>
            <td class="text-truncate" style="max-width: 320px;" title="${msg}">${msg}</td>
            <td class="text-end">
              <button class="btn btn-xs btn-outline-primary py-0 px-1.5 btn-ver-view me-1" data-hash="${fullHash}" title="Просмотр содержимого на этом коммите">
                <i class="bi bi-eye me-0.5"></i>Текст
              </button>
              <button class="btn btn-xs btn-outline-info py-0 px-1.5 btn-ver-diff" data-hash="${fullHash}" title="Просмотр diff изменений коммита">
                <i class="bi bi-file-diff me-0.5"></i>Diff
              </button>
            </td>
          </tr>
        `;
      }).join('');

      // Привязка просмотра контента ревизии
      tbody.querySelectorAll('.btn-ver-view').forEach((btn) => {
        btn.addEventListener('click', async (e) => {
          e.stopPropagation();
          const hash = btn.dataset.hash;
          if (previewTitle) previewTitle.textContent = `Содержимое ревизии: ${target.name}`;
          if (previewBadge) previewBadge.textContent = hash.slice(0, 7);
          if (previewContent) previewContent.textContent = 'Загрузка ревизии из Git...';

          try {
            const cRes = await fetch(`/api/v1/content?workspace_id=${encodeURIComponent(wsId)}&file_path=${encodeURIComponent(target.relPath)}&commit_hash=${encodeURIComponent(hash)}`);
            const cData = await cRes.json();
            if (previewContent) previewContent.textContent = cData.content || '(файл пуст на этой ревизии)';
          } catch (err) {
            if (previewContent) previewContent.textContent = `Ошибка чтения ревизии: ${err.message}`;
          }
        });
      });

      // Привязка просмотра Diff
      tbody.querySelectorAll('.btn-ver-diff').forEach((btn) => {
        btn.addEventListener('click', async (e) => {
          e.stopPropagation();
          const hash = btn.dataset.hash;
          if (previewTitle) previewTitle.textContent = `Diff изменений коммита: ${target.name}`;
          if (previewBadge) previewBadge.textContent = `diff:${hash.slice(0, 7)}`;
          if (previewContent) previewContent.textContent = 'Загрузка diff...';

          try {
            const dRes = await fetch(`/api/v1/diff?workspace_id=${encodeURIComponent(wsId)}&file_path=${encodeURIComponent(target.relPath)}&commit_hash=${encodeURIComponent(hash)}`);
            const dData = await dRes.json();
            const hunks = dData.hunks || [];
            if (hunks.length === 0) {
              if (previewContent) previewContent.textContent = 'Нет текстовых различий для этого файла в коммите.';
            } else {
              const diffText = hunks.map((h) => `${h.header}\n${(h.lines || []).join('\n')}`).join('\n\n');
              if (previewContent) previewContent.textContent = diffText;
            }
          } catch (err) {
            if (previewContent) previewContent.textContent = `Ошибка формирования diff: ${err.message}`;
          }
        });
      });
    }
  } catch (err) {
    if (tbody) tbody.innerHTML = `<tr><td colspan="5" class="text-danger py-3 text-center">Не удалось загрузить историю: ${err.message}</td></tr>`;
  }
}

/**
 * Открывает модальное окно подтверждения удаления.
 * @param {{isDir: boolean, relPath: string, name: string}} target 
 * @param {string} wsId 
 */
function openDeleteModal(target, wsId) {
  const modalEl = document.getElementById('modal-ide-confirm-delete');
  if (!modalEl || !window.bootstrap) return;

  const targetPathEl = document.getElementById('ide-delete-target-path');
  const itemTypeEl = document.getElementById('ide-delete-item-type');
  const confirmBtn = document.getElementById('ide-btn-confirm-delete');

  if (targetPathEl) targetPathEl.textContent = target.relPath;
  if (itemTypeEl) itemTypeEl.textContent = target.isDir ? 'каталог и всё его содержимое' : 'файл';

  const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
  modal.show();

  if (confirmBtn) {
    confirmBtn.onclick = async () => {
      confirmBtn.disabled = true;
      try {
        const res = await fetch(`/api/v1/workspaces/${encodeURIComponent(wsId)}/items?rel_path=${encodeURIComponent(target.relPath)}`, {
          method: 'DELETE',
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Ошибка удаления');

        modal.hide();
        showToast(`🗑️ ${target.isDir ? 'Каталог' : 'Файл'} "${target.relPath}" удален из Git`, 'success');
        await refreshFileTree(wsId);
      } catch (err) {
        showToast(`❌ Ошибка удаления: ${err.message}`, 'danger');
      } finally {
        confirmBtn.disabled = false;
      }
    };
  }
}

/**
 * Отображает контекстное меню проводника по координатам клика.
 * @param {MouseEvent} e 
 */
function showTreeContextMenu(e) {
  ensureTreeContextMenuDOM();
  e.preventDefault();
  e.stopPropagation();

  // Определяем, по какому элементу кликнули
  const fileEl = e.target.closest('.ide-tree-file');
  const folderEl = e.target.closest('.ide-tree-folder');

  if (fileEl) {
    currentTarget = {
      isDir: false,
      relPath: fileEl.dataset.relPath || '',
      name: fileEl.dataset.name || fileEl.dataset.relPath || '',
    };
  } else if (folderEl) {
    currentTarget = {
      isDir: true,
      relPath: folderEl.dataset.folderPath || '',
      name: (folderEl.dataset.folderPath || '').split('/').pop() || 'Папка',
    };
  } else {
    currentTarget = {
      isDir: true,
      relPath: '',
      name: 'Корень рабочей области',
    };
  }

  // Обновляем визуальный заголовок контекстного меню
  const headerEl = document.getElementById('cm-tree-target-header');
  const editItem = document.getElementById('cm-tree-item-edit');
  const deleteItem = document.getElementById('cm-tree-item-delete');

  if (headerEl) {
    const icon = currentTarget.isDir ? '📁' : '📄';
    headerEl.textContent = `${icon} ${currentTarget.name}`;
  }

  // Редактирование доступно только для файлов
  if (editItem) {
    if (currentTarget.isDir) {
      editItem.classList.add('disabled');
      editItem.title = 'Редактирование доступно только для файлов';
    } else {
      editItem.classList.remove('disabled');
      editItem.title = 'Редактировать текстовый файл';
    }
  }

  // Удаление недоступно только для пустого корня
  if (deleteItem) {
    if (!currentTarget.relPath) {
      deleteItem.classList.add('disabled');
    } else {
      deleteItem.classList.remove('disabled');
    }
  }

  // Позиционирование с проверкой границ окна
  const menuWidth = 240;
  const menuHeight = 210;
  let x = e.clientX;
  let y = e.clientY;

  if (x + menuWidth > window.innerWidth) {
    x = Math.max(10, window.innerWidth - menuWidth - 10);
  }
  if (y + menuHeight > window.innerHeight) {
    y = Math.max(10, window.innerHeight - menuHeight - 10);
  }

  menuElement.style.left = `${x}px`;
  menuElement.style.top = `${y}px`;
  menuElement.classList.remove('d-none');
}

/**
 * Инициализирует контекстное меню дерева проводника.
 */
export function initIdeTreeContextMenu() {
  ensureTreeContextMenuDOM();
  initCreateModalSubmit();

  const treeContainer = document.getElementById('ide-file-tree-container');
  const navigatorSidebar = document.getElementById('ide-file-navigator');

  // Слушатель контекстного меню на контейнере дерева файлов
  treeContainer?.addEventListener('contextmenu', (e) => {
    showTreeContextMenu(e);
  });

  // Также перехватываем ПКМ на свободной области навигатора
  navigatorSidebar?.addEventListener('contextmenu', (e) => {
    // Если клик не в других интерактивных блоках
    if (!e.target.closest('.ide-explorer-header, .ide-explorer-section-title')) {
      showTreeContextMenu(e);
    }
  });

  // Закрытие меню при клике в любом месте
  document.addEventListener('click', (e) => {
    if (menuElement && !menuElement.contains(e.target)) {
      hideTreeContextMenu();
    }
  });

  // Закрытие по клавише Escape
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      hideTreeContextMenu();
    }
  });

  // Закрытие при прокрутке
  window.addEventListener('scroll', hideTreeContextMenu, true);
}
