/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Track Sources Picker Component
 * =============================================================================
 * Description:
 *   Единый переиспользуемый модуль выбора директорий и файлов для мониторинга и Git-слежения:
 *   - Две симметричные карточки: выбор директории (папки) и выбор файла
 *   - Нативные системные диалоги выбора через REST API (/browse-folder, /browse-file)
 *   - Браузерные fallback-пикеры (input type="file" и webkitdirectory)
 *   - Автоматическое включение выбранного объекта в слежение без дополнительных кнопок
 *   - Обработка нажатия клавиши Enter в полях ручного ввода путей
 *   - Единая интернационализация (i18n) без жесткого кодирования строк.
 *
 * File: track_sources_picker.js
 * Package: apps/ai_assistant/api/webgui/components/track_sources_picker
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-30 17:32:00
 * =============================================================================
 */

/**
 * Вспомогательный метод получения локализованной строки из словарей i18n.
 * @param {string} key - Ключ локализации
 * @param {string} [fallback=''] - Текст по умолчанию
 * @returns {string}
 */
function t(key, fallback = '') {
  if (typeof window !== 'undefined') {
    if (window.i18n && typeof window.i18n.t === 'function') {
      const val = window.i18n.t(key);
      if (val && val !== key) return val;
    }
    if (window.i18next && typeof window.i18next.t === 'function') {
      const val = window.i18next.t(key);
      if (val && val !== key) return val;
    }
  }
  return fallback;
}

/**
 * Выполняет JSON-запрос к бэкенду.
 * @param {string} url 
 * @param {Object} options 
 * @returns {Promise<any>}
 */
async function apiFetch(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok) {
    let errMessage = `HTTP ${res.status}`;
    try {
      const data = await res.json();
      errMessage = data.detail || data.message || errMessage;
    } catch {
      // Игнорируем ошибку чтения JSON
    }
    throw new Error(errMessage);
  }
  return res.json();
}

/**
 * Генерирует HTML-разметку двух карточек добавления папки и файла.
 * @param {string} prefix - Уникальный префикс идентификаторов элементов
 * @returns {string}
 */
export function renderTrackSourcesPickerHtml(prefix = 'track-picker') {
  return `
    <div class="row g-3" id="${prefix}-row">
      <!-- Добавление директории -->
      <div class="col-lg-6" id="${prefix}-dir-col">
        <div class="p-2.5 rounded border bg-body-tertiary h-100" id="${prefix}-dir-card">
          <label class="form-label small fw-semibold d-flex align-items-center gap-1.5 mb-1" for="${prefix}-dir-input" id="${prefix}-dir-label">
            <i class="bi bi-folder2-open text-warning"></i>
            <span data-i18n="ui.cws.txt_68a213c2" id="${prefix}-dir-label-text">${t('ui.cws.txt_68a213c2', 'Директория (папка) для отслеживания:')}</span>
          </label>
          <div class="input-group input-group-sm mb-2" id="${prefix}-dir-group">
            <input class="form-control font-monospace" data-i18n-placeholder="placeholders.cws.ph_e149f935" id="${prefix}-dir-input" placeholder="${t('placeholders.cws.ph_e149f935', 'C:\\Projects\\my_service\\docs')}" type="text" />
            <button class="btn btn-outline-secondary d-flex align-items-center gap-1 px-2" data-i18n-title="titles.cws.title_faf6b1ab" id="${prefix}-dir-browse-btn" title="${t('titles.cws.title_faf6b1ab', 'Выбрать папку на компьютере')}" type="button">
              <i class="bi bi-folder2-open text-warning"></i>
              <span data-i18n="ui.cws.txt_503b2cca" id="${prefix}-dir-browse-text">${t('ui.cws.txt_503b2cca', 'Обзор...')}</span>
            </button>
          </div>
          <input class="d-none" directory="" id="${prefix}-dir-picker" type="file" webkitdirectory="" />
          <div class="small text-muted font-size-78" data-i18n="ui.cws.txt_858c5e1a" id="${prefix}-dir-hint">
            ${t('ui.cws.txt_858c5e1a', 'Все вложенные файлы (md, txt, pdf, docx, xlsx, py и др.) будут сканироваться и ставиться на версионный учёт.')}
          </div>
        </div>
      </div>

      <!-- Добавление файла -->
      <div class="col-lg-6" id="${prefix}-file-col">
        <div class="p-2.5 rounded border bg-body-tertiary h-100" id="${prefix}-file-card">
          <label class="form-label small fw-semibold d-flex align-items-center gap-1.5 mb-1" for="${prefix}-file-input" id="${prefix}-file-label">
            <i class="bi bi-file-earmark-code text-info"></i>
            <span data-i18n="ui.cws.txt_a7db7b12" id="${prefix}-file-label-text">${t('ui.cws.txt_a7db7b12', 'Отдельный файл для отслеживания:')}</span>
          </label>
          <div class="input-group input-group-sm mb-2" id="${prefix}-file-group">
            <input class="form-control font-monospace" data-i18n-placeholder="placeholders.cws.ph_025dbb3b" id="${prefix}-file-input" placeholder="${t('placeholders.cws.ph_025dbb3b', 'C:\\Work\\notes.md или D:\\Configs\\settings.json')}" type="text" />
            <button class="btn btn-outline-secondary d-flex align-items-center gap-1 px-2" data-i18n-title="titles.cws.title_771266c7" id="${prefix}-file-browse-btn" title="${t('titles.cws.title_771266c7', 'Выбрать файл на компьютере')}" type="button">
              <i class="bi bi-file-earmark-plus text-info"></i>
              <span data-i18n="ui.cws.txt_503b2cca" id="${prefix}-file-browse-text">${t('ui.cws.txt_503b2cca', 'Обзор...')}</span>
            </button>
          </div>
          <input class="d-none" id="${prefix}-file-picker" multiple="" type="file" />
          <div class="small text-muted font-size-78" data-i18n="ui.cws.txt_e6d366ea" id="${prefix}-file-hint">
            ${t('ui.cws.txt_e6d366ea', 'Файл остаётся на своём месте. Каждое сохранение изменений регистрируется в темпоральной истории Git.')}
          </div>
        </div>
      </div>
    </div>
  `;
}

/**
 * Монтирует единый модуль добавления директорий и файлов в указанный контейнер.
 * @param {HTMLElement|string} container - Контейнер DOM или селектор
 * @param {Object} options - Параметры инициализации
 * @param {string} [options.prefix='track-picker'] - Префикс идентификаторов элементов
 * @param {Function} options.onItemAdded - Асинхронный callback (path: string, type: 'directory'|'file') => Promise<void>
 * @param {Function} [options.onNotification] - Callback для показа статусов (text: string, type: string)
 * @returns {Object} Контроллер виджета
 */
export function mountTrackSourcesPicker(container, options = {}) {
  const root = typeof container === 'string' ? document.querySelector(container) : container;
  if (!root) {
    console.warn('[TrackSourcesPicker] Целевой контейнер не найден:', container);
    return null;
  }

  const prefix = options.prefix || 'track-picker';
  const onItemAdded = typeof options.onItemAdded === 'function' ? options.onItemAdded : async () => {};
  const notify = typeof options.onNotification === 'function' ? options.onNotification : () => {};

  root.innerHTML = renderTrackSourcesPickerHtml(prefix);

  if (typeof window.applyTranslations === 'function') {
    window.applyTranslations();
  } else if (window.i18n && typeof window.i18n.applyTranslations === 'function') {
    window.i18n.applyTranslations(root);
  }

  const dirInput = root.querySelector(`#${prefix}-dir-input`);
  const dirBrowseBtn = root.querySelector(`#${prefix}-dir-browse-btn`);
  const dirPicker = root.querySelector(`#${prefix}-dir-picker`);

  const fileInput = root.querySelector(`#${prefix}-file-input`);
  const fileBrowseBtn = root.querySelector(`#${prefix}-file-browse-btn`);
  const filePicker = root.querySelector(`#${prefix}-file-picker`);

  // Обзор директории
  if (dirBrowseBtn && !dirBrowseBtn._bound) {
    dirBrowseBtn._bound = true;
    dirBrowseBtn.addEventListener('click', async () => {
      let chosenPath = '';
      try {
        dirBrowseBtn.disabled = true;
        dirBrowseBtn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span>${t('ui.cws.btn_selecting', 'Выбор...')}`;
        const res = await apiFetch('/api/v1/workspaces/browse-folder', { method: 'POST' });
        if (res && res.status === 'ok' && res.path) {
          chosenPath = res.path;
          if (dirInput) dirInput.value = '';
          await onItemAdded(chosenPath, 'directory');
          return;
        }
      } catch (err) {
        console.debug('[TrackSourcesPicker] Fallback к проводнику браузера:', err);
      } finally {
        dirBrowseBtn.disabled = false;
        dirBrowseBtn.innerHTML = `<i class="bi bi-folder2-open text-warning me-1"></i><span>${t('ui.cws.txt_503b2cca', 'Обзор...')}</span>`;
      }
      if (!chosenPath && dirPicker) dirPicker.click();
    });
  }

  // Fallback выбора директории
  if (dirPicker && !dirPicker._bound) {
    dirPicker._bound = true;
    dirPicker.addEventListener('change', async (e) => {
      const files = e.target.files;
      if (files && files.length > 0) {
        const first = files[0];
        const folderName = (first.webkitRelativePath || '').split('/')[0] || first.name;
        let dir = '';
        if (first.path) {
          dir = first.path.substring(0, Math.max(first.path.lastIndexOf('\\'), first.path.lastIndexOf('/')));
        } else {
          dir = folderName;
        }
        if (dir) {
          if (dirInput) dirInput.value = '';
          await onItemAdded(dir, 'directory');
        }
      }
      dirPicker.value = '';
    });
  }

  // Ввод пути к директории по клавише Enter
  if (dirInput && !dirInput._boundEnter) {
    dirInput._boundEnter = true;
    dirInput.addEventListener('keydown', async (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        const val = dirInput.value.trim();
        if (val) {
          await onItemAdded(val, 'directory');
          dirInput.value = '';
        }
      }
    });
  }

  // Обзор файла
  if (fileBrowseBtn && !fileBrowseBtn._bound) {
    fileBrowseBtn._bound = true;
    fileBrowseBtn.addEventListener('click', async () => {
      let chosenFile = '';
      try {
        fileBrowseBtn.disabled = true;
        fileBrowseBtn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span>${t('ui.cws.btn_selecting', 'Выбор...')}`;
        const res = await apiFetch('/api/v1/workspaces/browse-file', { method: 'POST' });
        if (res && res.status === 'ok' && res.path) {
          chosenFile = res.path;
          if (fileInput) fileInput.value = '';
          await onItemAdded(chosenFile, 'file');
          return;
        }
      } catch (err) {
        console.debug('[TrackSourcesPicker] Fallback к проводнику браузера:', err);
      } finally {
        fileBrowseBtn.disabled = false;
        fileBrowseBtn.innerHTML = `<i class="bi bi-file-earmark-plus text-info me-1"></i><span>${t('ui.cws.txt_503b2cca', 'Обзор...')}</span>`;
      }
      if (!chosenFile && filePicker) filePicker.click();
    });
  }

  // Fallback выбора файла
  if (filePicker && !filePicker._bound) {
    filePicker._bound = true;
    filePicker.addEventListener('change', async (e) => {
      const files = e.target.files;
      if (files && files.length > 0) {
        for (let i = 0; i < files.length; i++) {
          const first = files[i];
          const filePath = first.path || first.name;
          if (filePath) {
            await onItemAdded(filePath, 'file');
          }
        }
        if (fileInput) fileInput.value = '';
      }
      filePicker.value = '';
    });
  }

  // Ввод пути к файлу по клавише Enter
  if (fileInput && !fileInput._boundEnter) {
    fileInput._boundEnter = true;
    fileInput.addEventListener('keydown', async (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        const val = fileInput.value.trim();
        if (val) {
          await onItemAdded(val, 'file');
          fileInput.value = '';
        }
      }
    });
  }

  return {
    /**
     * Возвращает значения, которые пользователь ввёл в поля ввода, но ещё не зафиксировал.
     * @returns {Array<{path: string, type: 'directory'|'file'}>}
     */
    getEnteredPaths() {
      const items = [];
      const dirVal = dirInput ? dirInput.value.trim() : '';
      const fileVal = fileInput ? fileInput.value.trim() : '';
      if (dirVal) items.push({ path: dirVal, type: 'directory' });
      if (fileVal) items.push({ path: fileVal, type: 'file' });
      return items;
    },

    /**
     * Очищает текстовые поля ввода компонента.
     */
    clearInputs() {
      if (dirInput) dirInput.value = '';
      if (fileInput) fileInput.value = '';
    },
  };
}
