/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Workspace Creation & Git Tracking Wizard
 * =============================================================================
 * Description:
 *   Модальный пошаговый мастер создания рабочей области с уникальным именем
 *   и добавления в нее директорий и/или файлов с мгновенным запуском Git-отслеживания.
 *   Как только файлы или директории добавлены — Git фиксирует их в коммите
 *   и начинает непрерывное отслеживание изменений.
 *
 * File: workspace_wizard.js
 * Package: apps/ai_assistant/api/webgui/js
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-28 18:46:00
 * =============================================================================
 */

let activeWizardWorkspaceId = '';
let activeWizardWorkspaceName = '';

/**
 * Вспомогательная функция выполнения JSON-запросов.
 */
async function apiRequest(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok) {
    let errDetail = `HTTP ${res.status}`;
    try {
      const data = await res.json();
      errDetail = data.detail || data.message || errDetail;
    } catch {
      // Игнорируем ошибку парсинга ошибки
    }
    throw new Error(errDetail);
  }
  return res.json();
}

/**
 * Отображает список отслеживаемых Git файлов в окне мастера.
 */
function renderTrackedFilesList(files, gitHead) {
  const container = document.getElementById('ws-wizard-tracked-list');
  const countBadge = document.getElementById('ws-wizard-files-count-badge');
  const headBadge = document.getElementById('ws-wizard-git-head-badge');

  if (countBadge) countBadge.textContent = `${files.length} отслеживаемых файлов`;
  if (headBadge) {
    const shortHead = gitHead && gitHead !== 'init' ? gitHead.slice(0, 8) : 'HEAD';
    headBadge.textContent = `Git commit: ${shortHead}`;
  }

  if (!container) return;

  if (files.length === 0) {
    container.innerHTML = `
      <div class="p-3 text-center text-muted small border rounded bg-body-tertiary">
        <i class="bi bi-git fs-4 d-block mb-1 text-secondary"></i>
        В этой рабочей области пока нет отслеживаемых файлов. Добавьте директории или файлы ниже.
      </div>`;
    return;
  }

  container.innerHTML = files.map(f => `
    <div class="list-group-item d-flex align-items-center justify-content-between p-2 mb-1 rounded border">
      <div class="d-flex align-items-center gap-2 overflow-hidden">
        <i class="bi ${f.type === 'directory_file' ? 'bi-folder2-open text-warning' : 'bi-file-earmark-check-fill text-success'} fs-5 flex-shrink-0"></i>
        <div class="text-truncate">
          <div class="fw-semibold small text-truncate">${f.name}</div>
          <div class="text-muted font-monospace small text-truncate">${f.qualified_path || f.path || f.name}</div>
        </div>
      </div>
      <div class="d-flex align-items-center gap-1.5 flex-shrink-0 ms-2">
        <span class="badge bg-success-subtle text-success border">
          <i class="bi bi-git me-1"></i>Отслеживается Git
        </span>
      </div>
    </div>
  `).join('');
}

/**
 * Инициализирует интерактивный мастер создания рабочей области и добавления файлов.
 */
export function initWorkspaceWizard() {
  const modalEl = document.getElementById('modal-create-workspace-wizard');
  if (!modalEl) return;

  const step1Block = document.getElementById('ws-wizard-step1-block');
  const step2Block = document.getElementById('ws-wizard-step2-block');
  const statusBanner = document.getElementById('ws-wizard-status-banner');

  const nameInput = document.getElementById('ws-wizard-name-input');
  const langSelect = document.getElementById('ws-wizard-lang-select');
  const pathInput = document.getElementById('ws-wizard-path-input');
  const createBtn = document.getElementById('ws-wizard-create-btn');

  const diskPathInput = document.getElementById('ws-wizard-target-path-input');
  const addDiskPathBtn = document.getElementById('ws-wizard-add-path-btn');
  const copyFilesCheckbox = document.getElementById('ws-wizard-copy-checkbox');

  const filePicker = document.getElementById('ws-wizard-files-input');
  const uploadFilesBtn = document.getElementById('ws-wizard-upload-files-btn');

  const folderPicker = document.getElementById('ws-wizard-folder-input');
  const uploadFolderBtn = document.getElementById('ws-wizard-upload-folder-btn');

  const doneBtn = document.getElementById('ws-wizard-done-btn');

  // Сброс состояния при открытии модального окна
  modalEl.addEventListener('show.bs.modal', () => {
    if (!activeWizardWorkspaceId) {
      if (step2Block) step2Block.classList.add('d-none');
      if (statusBanner) statusBanner.classList.add('d-none');
      if (nameInput) {
        nameInput.value = '';
        setTimeout(() => nameInput.focus(), 300);
      }
      if (pathInput) pathInput.value = '';
      if (diskPathInput) diskPathInput.value = '';
      if (langSelect) {
        const curLang = (typeof window !== 'undefined' && window.i18n?.lang) || localStorage.getItem('app_language') || 'ru';
        const cleanCur = curLang.toLowerCase().slice(0, 2);
        if (['he', 'ru', 'en', 'uk'].includes(cleanCur)) {
          langSelect.value = cleanCur;
        }
      }
      renderTrackedFilesList([], '');
    }
  });

  // Шаг 1: Создание рабочей области с уникальным именем
  if (createBtn) {
    createBtn.addEventListener('click', async () => {
      const nameVal = nameInput ? nameInput.value.trim() : '';
      const pathVal = pathInput ? pathInput.value.trim() : '';
      const langVal = langSelect ? langSelect.value : 'ru';

      if (!nameVal) {
        alert('Пожалуйста, введите имя рабочей области.');
        if (nameInput) nameInput.focus();
        return;
      }

      createBtn.disabled = true;
      createBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Создание...';

      try {
        // Поддержка всех символов Unicode (иврит, кириллица, латиница) с нормализацией разделителей
        const cleanId = nameVal
          .trim()
          .replace(/[^\p{L}\p{N}_-]+/gu, '_')
          .replace(/^_+|_+$/g, '') || 'workspace';
        const res = await apiRequest('/api/v1/workspaces', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            workspace_id: cleanId,
            name: nameVal,
            custom_path: pathVal || null,
            language: langVal,
          }),
        });

        activeWizardWorkspaceId = res.workspace?.workspace_id || cleanId;
        activeWizardWorkspaceName = res.workspace?.name || nameVal;

        // Показываем сообщение об успешной инициализации Git
        if (statusBanner) {
          statusBanner.classList.remove('d-none');
          statusBanner.className = 'alert alert-success d-flex align-items-center gap-2 py-2 px-3 mb-3 small shadow-sm';
          statusBanner.innerHTML = `
            <i class="bi bi-check-circle-fill fs-5 text-success"></i>
            <div>
              <strong>Рабочая область &laquo;${activeWizardWorkspaceName}&raquo; создана!</strong>
              <div>Git-репозиторий успешно инициализирован. Теперь добавьте директории или файлы — Git начнет отслеживать их сразу же.</div>
            </div>`;
        }

        // Активируем Шаг 2
        if (step2Block) {
          step2Block.classList.remove('d-none');
          step2Block.scrollIntoView({ behavior: 'smooth' });
        }

        renderTrackedFilesList([], res.workspace?.git_head || '');
      } catch (err) {
        alert(`Ошибка создания рабочей области: ${err.message}`);
      } finally {
        createBtn.disabled = false;
        createBtn.innerHTML = '<i class="bi bi-check-circle me-1"></i>Создать область (Git Init)';
      }
    });
  }

  // Шаг 2 (Вариант А): Добавление файлов/папок по локальному пути с диска
  if (addDiskPathBtn && diskPathInput) {
    addDiskPathBtn.addEventListener('click', async () => {
      const targetPath = diskPathInput.value.trim();
      if (!targetPath) {
        alert('Укажите путь к директории или файлу на диске.');
        return;
      }

      if (!activeWizardWorkspaceId) {
        alert('Сначала создайте рабочую область (Шаг 1).');
        return;
      }

      addDiskPathBtn.disabled = true;
      addDiskPathBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Добавление и Git commit...';

      try {
        const copyToWs = copyFilesCheckbox ? Boolean(copyFilesCheckbox.checked) : false;
        const res = await apiRequest(`/api/v1/workspaces/${encodeURIComponent(activeWizardWorkspaceId)}/items`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            items: [targetPath],
            copy_to_workspace: copyToWs,
            commit_message: `Добавлен объект ${targetPath} (Git tracking)`,
          }),
        });

        diskPathInput.value = '';
        renderTrackedFilesList(res.tracked_files || [], res.git_head || '');

        if (statusBanner) {
          statusBanner.className = 'alert alert-success d-flex align-items-center gap-2 py-2 px-3 mb-3 small shadow-sm';
          statusBanner.innerHTML = `
            <i class="bi bi-git fs-5 text-success"></i>
            <div>
              <strong>Git начал отслеживать добавленные данные!</strong>
              <div>Зафиксирован коммит: <code>${(res.git_head || '').slice(0, 8)}</code>. Файлов добавлено: ${res.files_added}.</div>
            </div>`;
        }
      } catch (err) {
        alert(`Ошибка добавления в Git: ${err.message}`);
      } finally {
        addDiskPathBtn.disabled = false;
        addDiskPathBtn.innerHTML = '<i class="bi bi-git me-1"></i>Добавить и начать отслеживание Git';
      }
    });
  }

  // Шаг 2 (Вариант Б): Загрузка файлов через браузер
  if (uploadFilesBtn && filePicker) {
    uploadFilesBtn.addEventListener('click', async () => {
      const files = filePicker.files;
      if (!files || files.length === 0) {
        alert('Выберите один или несколько файлов для добавления.');
        return;
      }

      if (!activeWizardWorkspaceId) {
        alert('Сначала создайте рабочую область (Шаг 1).');
        return;
      }

      uploadFilesBtn.disabled = true;
      uploadFilesBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Git commit...';

      try {
        const formData = new FormData();
        for (let i = 0; i < files.length; i++) {
          formData.append('files', files[i]);
        }
        formData.append('commit_message', `Загрузка файлов (${files.length} шт.) в Git`);

        const res = await apiRequest(`/api/v1/workspaces/${encodeURIComponent(activeWizardWorkspaceId)}/files/upload`, {
          method: 'POST',
          body: formData,
        });

        filePicker.value = '';
        renderTrackedFilesList(res.tracked_files || [], res.git_head || '');

        if (statusBanner) {
          statusBanner.className = 'alert alert-success d-flex align-items-center gap-2 py-2 px-3 mb-3 small shadow-sm';
          statusBanner.innerHTML = `
            <i class="bi bi-git fs-5 text-success"></i>
            <div>
              <strong>Файлы загружены и переданы под контроль Git!</strong>
              <div>Коммит: <code>${(res.git_head || '').slice(0, 8)}</code>. Добавлено файлов: ${res.files_added}.</div>
            </div>`;
        }
      } catch (err) {
        alert(`Ошибка загрузки файлов: ${err.message}`);
      } finally {
        uploadFilesBtn.disabled = false;
        uploadFilesBtn.innerHTML = '<i class="bi bi-cloud-arrow-up me-1"></i>Загрузить и начать отслеживание Git';
      }
    });
  }

  // Шаг 2 (Вариант В): Загрузка папки целиком через браузер
  if (uploadFolderBtn && folderPicker) {
    uploadFolderBtn.addEventListener('click', async () => {
      const files = folderPicker.files;
      if (!files || files.length === 0) {
        alert('Выберите папку на диске для загрузки.');
        return;
      }

      if (!activeWizardWorkspaceId) {
        alert('Сначала создайте рабочую область (Шаг 1).');
        return;
      }

      uploadFolderBtn.disabled = true;
      uploadFolderBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Импорт папки в Git...';

      try {
        const formData = new FormData();
        for (let i = 0; i < files.length; i++) {
          formData.append('files', files[i]);
        }
        formData.append('commit_message', `Импорт директории (${files.length} файлов) в Git`);

        const res = await apiRequest(`/api/v1/workspaces/${encodeURIComponent(activeWizardWorkspaceId)}/files/upload`, {
          method: 'POST',
          body: formData,
        });

        folderPicker.value = '';
        renderTrackedFilesList(res.tracked_files || [], res.git_head || '');

        if (statusBanner) {
          statusBanner.className = 'alert alert-success d-flex align-items-center gap-2 py-2 px-3 mb-3 small shadow-sm';
          statusBanner.innerHTML = `
            <i class="bi bi-git fs-5 text-success"></i>
            <div>
              <strong>Папка успешно зафиксирована в Git!</strong>
              <div>Коммит: <code>${(res.git_head || '').slice(0, 8)}</code>. Добавлено файлов: ${res.files_added}.</div>
            </div>`;
        }
      } catch (err) {
        alert(`Ошибка импорта папки: ${err.message}`);
      } finally {
        uploadFolderBtn.disabled = false;
        uploadFolderBtn.innerHTML = '<i class="bi bi-folder-check me-1"></i>Загрузить папку и начать отслеживание Git';
      }
    });
  }

  // Завершение работы мастера: переход в рабочую область
  if (doneBtn) {
    doneBtn.addEventListener('click', async () => {
      const targetWs = activeWizardWorkspaceId || 'default';

      // Закрываем модальное окно
      if (window.bootstrap) {
        const modalInstance = bootstrap.Modal.getInstance(modalEl);
        if (modalInstance) modalInstance.hide();
      }

      // Переключаемся на вкладку Workspace
      if (typeof window.switchTab === 'function') {
        window.switchTab('tab-workspace');
      }

      // Обновляем список рабочих областей и выбираем созданную
      const wsSelector = document.getElementById('ws-selector');
      if (wsSelector) {
        try {
          const data = await apiRequest('/api/v1/workspaces');
          const list = data.workspaces || [];
          wsSelector.innerHTML = list.map(ws => `
            <option value="${ws.workspace_id}" ${ws.workspace_id === targetWs ? 'selected' : ''}>
              ${ws.name} [${ws.workspace_id}] — док: ${ws.documents_count || 0}, фактов: ${ws.active_facts_count || 0}
            </option>
          `).join('');
          wsSelector.value = targetWs;
          wsSelector.dispatchEvent(new Event('change'));
        } catch (err) {
          console.warn('[WorkspaceWizard] Ошибка обновления селектора областей:', err);
        }
      }

      // Сбрасываем id для следующего открытия
      activeWizardWorkspaceId = '';
      activeWizardWorkspaceName = '';
    });
  }
}

// Автоматическая инициализация
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initWorkspaceWizard);
} else {
  initWorkspaceWizard();
}
