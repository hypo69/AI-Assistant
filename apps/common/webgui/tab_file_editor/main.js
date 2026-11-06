/**
 * =============================================================================
 * Process Name: Common WebGUI - Studio Code Central File Editor Orchestrator
 * =============================================================================
 * Description:
 *   Главный клиентский оркестратор центрального окна редактора файлов Studio Code
 *   (apps/common/webgui/tab_file_editor).
 *   Управляет открытыми вкладками файлов в центральной области (#fe-open-tabs-bar),
 *   переключением активного файла, встроенным видеоплеером (HTML5 Video),
 *   аудиоплеером, просмотром изображений, подсчётом строк и символов,
 *   предпросмотром Markdown, автосохранением/сохранением с коммитом в Git (Ctrl+S)
 *   и синхронизацией с навигатором файлов (#ide-file-navigator).
 *
 * File: main.js
 * Project: ai-assistant
 * Package: apps/common/webgui/tab_file_editor
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-06 23:15:00
 * =============================================================================
 */

let isInitialized = false;
const openDocuments = new Map(); // key: `${wsId}:${relPath}` -> docState
let activeDocKey = null;

const VIDEO_EXTENSIONS = new Set(['mp4', 'webm', 'ogg', 'ogv', 'mov', 'mkv', 'avi', 'm4v']);
const AUDIO_EXTENSIONS = new Set(['mp3', 'wav', 'flac', 'aac', 'm4a', 'wma']);
const IMAGE_EXTENSIONS = new Set(['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'ico', 'bmp']);

function notifyToast(msg, type = 'info') {
  if (typeof window.showToast === 'function') {
    window.showToast(msg, type);
  } else if (typeof window.showNotificationToast === 'function') {
    window.showNotificationToast(msg, type);
  }
}

function getActiveWorkspaceId() {
  if (typeof window.getActiveWorkspaceId === 'function') {
    const ws = window.getActiveWorkspaceId();
    if (ws) return ws;
  }
  const sel = document.getElementById('top-workspace-select') || document.getElementById('drawer-workspace-select');
  if (sel && sel.value) return sel.value;
  return 'default';
}

function makeDocKey(wsId, relPath) {
  return `${wsId || 'default'}:${(relPath || '').trim()}`;
}

function getFileIconClass(fileName, isMedia, mediaType) {
  if (isMedia) {
    if (mediaType === 'video') return 'bi-file-earmark-play-fill text-danger';
    if (mediaType === 'audio') return 'bi-file-earmark-music-fill text-info';
    if (mediaType === 'image') return 'bi-file-earmark-image-fill text-success';
  }
  const ext = (fileName.split('.').pop() || '').toLowerCase();
  switch (ext) {
    case 'py': return 'bi-filetype-py text-primary';
    case 'js':
    case 'mjs': return 'bi-filetype-js text-warning';
    case 'json': return 'bi-filetype-json text-info';
    case 'html': return 'bi-filetype-html text-danger';
    case 'css': return 'bi-filetype-css text-info';
    case 'md': return 'bi-markdown-fill text-primary';
    case 'sh':
    case 'ps1': return 'bi-terminal text-success';
    default: return 'bi-file-earmark-text text-secondary';
  }
}

/**
 * Инициализирует модуль редактора при первом монтировании вкладки.
 */
export function initFileEditorTab() {
  if (isInitialized) return;
  isInitialized = true;

  bindToolbarEvents();
  bindEditorEvents();
  renderTabsBar();
  renderActiveDocument();
}

/**
 * Привязывает обработчики кнопок верхней и нижней панелей.
 */
function bindToolbarEvents() {
  // Кнопка сохранения Ctrl+S
  document.getElementById('fe-btn-save')?.addEventListener('click', () => {
    saveActiveDocument();
  });

  // Кнопка нового файла (+)
  document.getElementById('fe-btn-new-file')?.addEventListener('click', () => {
    handleCreateNewFilePrompt();
  });

  // Кнопка закрытия всех вкладок
  document.getElementById('fe-btn-close-all')?.addEventListener('click', () => {
    closeAllDocuments();
  });

  // Кнопка открытия в системном приложении
  document.getElementById('fe-btn-system-open')?.addEventListener('click', () => {
    handleOpenSystem();
  });
  document.getElementById('fe-btn-binary-open')?.addEventListener('click', () => {
    handleOpenSystem();
  });

  // Переключение режимов Редактор / Предпросмотр (Markdown)
  document.getElementById('fe-tab-mode-code')?.addEventListener('click', () => {
    switchActiveViewMode('code');
  });
  document.getElementById('fe-tab-mode-preview')?.addEventListener('click', () => {
    switchActiveViewMode('preview');
  });
}

/**
 * Привязывает обработчики к textarea (счетчики строк, Tab, скролл gutter, Ctrl+S).
 */
function bindEditorEvents() {
  const textarea = document.getElementById('fe-code-textarea');
  const gutter = document.getElementById('fe-line-gutter');
  if (!textarea) return;

  textarea.addEventListener('input', () => {
    const doc = getActiveDoc();
    if (!doc) return;
    doc.content = textarea.value;
    doc.isDirty = (doc.content !== doc.initialContent);
    updateGutter();
    updateCursorAndStats();
    updateActiveTabDirtyIndicator();
  });

  textarea.addEventListener('scroll', () => {
    if (gutter) gutter.scrollTop = textarea.scrollTop;
  });

  textarea.addEventListener('keyup', updateCursorAndStats);
  textarea.addEventListener('click', updateCursorAndStats);

  textarea.addEventListener('keydown', (e) => {
    // Поддержка сохранения по Ctrl+S / Cmd+S
    if ((e.ctrlKey || e.metaKey) && (e.key === 's' || e.key === 'S')) {
      e.preventDefault();
      saveActiveDocument();
      return;
    }

    // Поддержка отступа Tab (2 пробела)
    if (e.key === 'Tab') {
      e.preventDefault();
      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;
      const val = textarea.value;
      textarea.value = val.substring(0, start) + '  ' + val.substring(end);
      textarea.selectionStart = textarea.selectionEnd = start + 2;
      textarea.dispatchEvent(new Event('input'));
    }
  });
}

/**
 * Открывает файл в центральном окне Studio Code в виде вкладки.
 * @param {string} relPath - Относительный путь к файлу
 * @param {string} [wsId] - ID рабочей области
 * @param {boolean} [switchSubtab=true] - Переключить ли субвкладку на panel-file-editor
 */
export async function openDocumentInTab(relPath, wsId, switchSubtab = true) {
  if (!relPath) return;
  const currentWs = wsId || getActiveWorkspaceId();
  const docKey = makeDocKey(currentWs, relPath);

  // Переключаем интерфейс на суб-панель редактора
  if (switchSubtab) {
    switchToEditorSubtab();
  }

  // Если файл уже открыт во вкладках — просто активируем её
  if (openDocuments.has(docKey)) {
    activeDocKey = docKey;
    renderTabsBar();
    renderActiveDocument();
    return;
  }

  const fileName = relPath.split('/').pop().split('\\').pop();
  const ext = (fileName.split('.').pop() || '').toLowerCase();
  const isVideo = VIDEO_EXTENSIONS.has(ext);
  const isAudio = AUDIO_EXTENSIONS.has(ext);
  const isImage = IMAGE_EXTENSIONS.has(ext);
  const isMedia = isVideo || isAudio || isImage;
  const mediaType = isVideo ? 'video' : (isAudio ? 'audio' : (isImage ? 'image' : null));
  const rawUrl = `/api/v1/workspaces/${encodeURIComponent(currentWs)}/file-raw?rel_path=${encodeURIComponent(relPath)}`;

  let isBinary = isMedia;
  let initialContent = '';

  // Для не-медиа файлов загружаем текстовое содержимое через API
  if (!isMedia) {
    try {
      const url = `/api/v1/workspaces/${encodeURIComponent(currentWs)}/file-content?rel_path=${encodeURIComponent(relPath)}`;
      const res = await fetch(url);
      if (!res.ok) {
        throw new Error(`Ошибка HTTP ${res.status}`);
      }
      const data = await res.json();
      isBinary = Boolean(data.is_binary);
      initialContent = isBinary ? '' : (data.content ?? '');
    } catch (err) {
      console.warn(`[FileEditor] Не удалось загрузить содержимое ${relPath}:`, err);
      notifyToast(`Не удалось прочитать файл: ${err.message}`, 'danger');
      return;
    }
  }

  const docState = {
    wsId: currentWs,
    relPath,
    fileName,
    ext,
    isMedia,
    mediaType,
    rawUrl,
    isBinary,
    content: initialContent,
    initialContent,
    isDirty: false,
    viewMode: 'code',
    cursorLine: 1,
    cursorCol: 1,
  };

  openDocuments.set(docKey, docState);
  activeDocKey = docKey;

  renderTabsBar();
  renderActiveDocument();
}

/**
 * Переключает навигацию рабочей области на суб-панель редактора.
 */
function switchToEditorSubtab() {
  if (typeof window.switchWorkspaceSubTab === 'function') {
    window.switchWorkspaceSubTab('panel-file-editor');
    return;
  }
  const btn = document.getElementById('subtab-ws-file-editor-btn');
  if (btn) btn.click();
}

/**
 * Возвращает состояние активного документа.
 */
function getActiveDoc() {
  if (!activeDocKey) return null;
  return openDocuments.get(activeDocKey) || null;
}

/**
 * Отрисовывает полосу открытых вкладок.
 */
function renderTabsBar() {
  const bar = document.getElementById('fe-open-tabs-bar');
  if (!bar) return;

  bar.innerHTML = '';
  if (openDocuments.size === 0) {
    return;
  }

  for (const [key, doc] of openDocuments.entries()) {
    const isActive = (key === activeDocKey);
    const tabEl = document.createElement('div');
    tabEl.className = `wasm-tab-item d-flex align-items-center gap-1.5 px-2.5 py-1 rounded-top small border-end border-subtle ${isActive ? 'active' : ''}`;
    tabEl.style.cursor = 'pointer';

    const iconClass = getFileIconClass(doc.fileName, doc.isMedia, doc.mediaType);
    tabEl.innerHTML = `
      <i class="bi ${iconClass}"></i>
      <span class="wasm-tab-title text-truncate" style="max-width: 140px;" title="${doc.relPath}">${doc.fileName}</span>
      <span class="wasm-tab-dirty text-warning ${doc.isDirty ? '' : 'd-none'}">●</span>
      <button type="button" class="btn-close btn-close-white wasm-tab-close p-0 ms-1" style="font-size: 0.65rem;" title="Закрыть вкладку"></button>
    `;

    // Клик по вкладке — активация
    tabEl.addEventListener('click', (e) => {
      if (e.target.closest('.wasm-tab-close')) return;
      activeDocKey = key;
      renderTabsBar();
      renderActiveDocument();
    });

    // Клик по крестику — закрытие вкладки
    tabEl.querySelector('.wasm-tab-close')?.addEventListener('click', (e) => {
      e.stopPropagation();
      closeDocument(key);
    });

    bar.appendChild(tabEl);
  }
}

/**
 * Закрывает указанную вкладку документа.
 */
function closeDocument(key) {
  const doc = openDocuments.get(key);
  if (!doc) return;

  if (doc.isDirty) {
    const ok = confirm(`Файл "${doc.fileName}" имеет несохранённые изменения. Закрыть без сохранения?`);
    if (!ok) return;
  }

  // Если закрывается активный медиафайл — останавливаем воспроизведение
  if (doc.isMedia && key === activeDocKey) {
    stopMediaPlayback();
  }

  openDocuments.delete(key);

  if (activeDocKey === key) {
    const remaining = Array.from(openDocuments.keys());
    activeDocKey = remaining.length > 0 ? remaining[remaining.length - 1] : null;
  }

  renderTabsBar();
  renderActiveDocument();
}

/**
 * Закрывает все открытые вкладки.
 */
function closeAllDocuments() {
  let hasDirty = false;
  for (const doc of openDocuments.values()) {
    if (doc.isDirty) {
      hasDirty = true;
      break;
    }
  }
  if (hasDirty) {
    const ok = confirm('Есть несохранённые файлы. Закрыть все вкладки без сохранения?');
    if (!ok) return;
  }

  stopMediaPlayback();
  openDocuments.clear();
  activeDocKey = null;

  renderTabsBar();
  renderActiveDocument();
}

/**
 * Останавливает воспроизведение встроенных плееров.
 */
function stopMediaPlayback() {
  const video = document.getElementById('fe-media-video');
  const audio = document.getElementById('fe-media-audio');
  if (video) {
    video.pause();
    video.removeAttribute('src');
    video.load();
  }
  if (audio) {
    audio.pause();
    audio.removeAttribute('src');
    audio.load();
  }
}

/**
 * Отрисовывает содержимое активного документа на центральной сцене.
 */
function renderActiveDocument() {
  const emptyState = document.getElementById('fe-empty-state');
  const binaryNotice = document.getElementById('fe-binary-notice');
  const textStage = document.getElementById('fe-text-stage');
  const mediaStage = document.getElementById('fe-media-stage');

  const fileNameEl = document.getElementById('fe-active-file-name');
  const filePathEl = document.getElementById('fe-active-file-path');
  const fileIconEl = document.getElementById('fe-active-file-icon');
  const viewModeGroup = document.getElementById('fe-view-mode-group');
  const btnSave = document.getElementById('fe-btn-save');
  const textarea = document.getElementById('fe-code-textarea');

  const video = document.getElementById('fe-media-video');
  const audioContainer = document.getElementById('fe-media-audio-container');
  const audio = document.getElementById('fe-media-audio');
  const image = document.getElementById('fe-media-image');

  // Всегда сначала приостанавливаем текущий поток медиа при смене документа
  stopMediaPlayback();

  const doc = getActiveDoc();

  // Если нет открытых вкладок
  if (!doc) {
    if (emptyState) emptyState.classList.remove('d-none');
    if (binaryNotice) binaryNotice.classList.add('d-none');
    if (textStage) textStage.classList.add('d-none');
    if (mediaStage) mediaStage.classList.add('d-none');

    if (fileNameEl) fileNameEl.textContent = 'Файл не выбран';
    if (filePathEl) filePathEl.textContent = '---';
    if (fileIconEl) fileIconEl.className = 'bi bi-file-earmark-code text-primary fs-5';
    if (viewModeGroup) viewModeGroup.classList.add('d-none');
    if (btnSave) btnSave.disabled = true;

    updateCursorAndStats();
    return;
  }

  // Скрываем заглушку "нет файлов"
  if (emptyState) emptyState.classList.add('d-none');

  // Обновляем шапку активного файла
  if (fileNameEl) fileNameEl.textContent = doc.fileName;
  if (filePathEl) filePathEl.textContent = doc.relPath;
  if (fileIconEl) {
    const iconClass = getFileIconClass(doc.fileName, doc.isMedia, doc.mediaType);
    fileIconEl.className = `bi ${iconClass} fs-5`;
  }

  // 1. СЛУЧАЙ: ВСТРОЕННЫЙ МЕДИАПЛЕЕР (Видео, Аудио, Картинки)
  if (doc.isMedia) {
    if (binaryNotice) binaryNotice.classList.add('d-none');
    if (textStage) textStage.classList.add('d-none');
    if (viewModeGroup) viewModeGroup.classList.add('d-none');
    if (btnSave) btnSave.disabled = true;

    if (mediaStage) mediaStage.classList.remove('d-none');

    if (doc.mediaType === 'video') {
      if (video) {
        video.classList.remove('d-none');
        video.src = doc.rawUrl;
      }
      if (audioContainer) audioContainer.classList.add('d-none');
      if (image) image.classList.add('d-none');
      setStatsText('Видеофайл • Встроенный видеоплеер');
    } else if (doc.mediaType === 'audio') {
      if (video) video.classList.add('d-none');
      if (audioContainer) {
        audioContainer.classList.remove('d-none');
        const titleEl = document.getElementById('fe-media-audio-title');
        if (titleEl) titleEl.textContent = doc.fileName;
      }
      if (audio) {
        audio.src = doc.rawUrl;
      }
      if (image) image.classList.add('d-none');
      setStatsText('Аудиозапись • Встроенный аудиоплеер');
    } else if (doc.mediaType === 'image') {
      if (video) video.classList.add('d-none');
      if (audioContainer) audioContainer.classList.add('d-none');
      if (image) {
        image.classList.remove('d-none');
        image.src = doc.rawUrl;
      }
      setStatsText('Изображение • Предпросмотр');
    }
    return;
  }

  // 2. СЛУЧАЙ: НЕИЗВЕСТНЫЙ БИНАРНЫЙ ФАЙЛ
  if (doc.isBinary) {
    if (mediaStage) mediaStage.classList.add('d-none');
    if (textStage) textStage.classList.add('d-none');
    if (binaryNotice) binaryNotice.classList.remove('d-none');
    if (viewModeGroup) viewModeGroup.classList.add('d-none');
    if (btnSave) btnSave.disabled = true;
    setStatsText('Бинарный файл');
    return;
  }

  // 3. СЛУЧАЙ: ТЕКСТОВЫЙ / CODE / MARKDOWN ФАЙЛ
  if (mediaStage) mediaStage.classList.add('d-none');
  if (binaryNotice) binaryNotice.classList.add('d-none');
  if (textStage) textStage.classList.remove('d-none');
  if (btnSave) btnSave.disabled = false;

  // Для файлов Markdown показываем переключатель "Редактор / Предпросмотр"
  const isMd = doc.ext === 'md' || doc.ext === 'markdown';
  if (viewModeGroup) {
    if (isMd) {
      viewModeGroup.classList.remove('d-none');
    } else {
      viewModeGroup.classList.add('d-none');
    }
  }

  if (textarea) {
    textarea.value = doc.content ?? '';
  }

  updateGutter();
  updateCursorAndStats();
  applyViewMode(doc.viewMode || 'code');
}

function setStatsText(txt) {
  const statsEl = document.getElementById('fe-editor-stats');
  if (statsEl) statsEl.textContent = txt;
}

/**
 * Переключает режим отображения Редактор / Предпросмотр.
 */
function switchActiveViewMode(mode) {
  const doc = getActiveDoc();
  if (!doc) return;
  doc.viewMode = mode;
  applyViewMode(mode);
}

function applyViewMode(mode) {
  const btnCode = document.getElementById('fe-tab-mode-code');
  const btnPrev = document.getElementById('fe-tab-mode-preview');
  const textarea = document.getElementById('fe-code-textarea');
  const gutter = document.getElementById('fe-line-gutter');
  const preview = document.getElementById('fe-markdown-preview');

  if (mode === 'preview') {
    if (btnCode) btnCode.classList.remove('active');
    if (btnPrev) btnPrev.classList.add('active');
    if (textarea) textarea.classList.add('d-none');
    if (gutter) gutter.classList.add('d-none');
    if (preview) {
      preview.classList.remove('d-none');
      renderMarkdownPreview();
    }
  } else {
    if (btnCode) btnCode.classList.add('active');
    if (btnPrev) btnPrev.classList.remove('active');
    if (textarea) textarea.classList.remove('d-none');
    if (gutter) gutter.classList.remove('d-none');
    if (preview) preview.classList.add('d-none');
  }
}

/**
 * Рендерит предпросмотр Markdown с помощью window.marked (если доступен).
 */
function renderMarkdownPreview() {
  const doc = getActiveDoc();
  const preview = document.getElementById('fe-markdown-preview');
  if (!doc || !preview) return;

  const raw = doc.content || '';
  if (typeof window.marked === 'function') {
    preview.innerHTML = window.marked(raw);
  } else if (typeof window.marked?.parse === 'function') {
    preview.innerHTML = window.marked.parse(raw);
  } else {
    preview.textContent = raw;
  }
}

/**
 * Обновляет нумерацию строк слева от редактора.
 */
function updateGutter() {
  const textarea = document.getElementById('fe-code-textarea');
  const gutter = document.getElementById('fe-line-gutter');
  if (!textarea || !gutter) return;

  const lines = (textarea.value || '').split('\n').length;
  let numbers = '';
  for (let i = 1; i <= lines; i++) {
    numbers += i + '\n';
  }
  gutter.textContent = numbers;
}

/**
 * Обновляет позицию курсора и статистику символов/строк.
 */
function updateCursorAndStats() {
  const doc = getActiveDoc();
  const textarea = document.getElementById('fe-code-textarea');
  const cursorEl = document.getElementById('fe-editor-cursor');
  const statsEl = document.getElementById('fe-editor-stats');

  if (!doc) {
    if (cursorEl) cursorEl.textContent = 'Ln 1, Col 1';
    if (statsEl) statsEl.textContent = 'Строк: 0 | Символов: 0';
    return;
  }

  if (doc.isMedia || doc.isBinary) {
    if (cursorEl) cursorEl.textContent = '---';
    return;
  }

  if (!textarea) return;

  const val = textarea.value || '';
  const selStart = textarea.selectionStart || 0;
  const upToCursor = val.substring(0, selStart);
  const lines = upToCursor.split('\n');
  const curLine = lines.length;
  const curCol = lines[lines.length - 1].length + 1;

  if (cursorEl) cursorEl.textContent = `Ln ${curLine}, Col ${curCol}`;
  const totalLines = val.split('\n').length;
  const totalChars = val.length;
  if (statsEl) statsEl.textContent = `Строк: ${totalLines} | Символов: ${totalChars}`;
}

/**
 * Обновляет индикатор несохранённых правок (желтая точка) на активной вкладке.
 */
function updateActiveTabDirtyIndicator() {
  const doc = getActiveDoc();
  if (!doc) return;
  const bar = document.getElementById('fe-open-tabs-bar');
  if (!bar) return;
  const activeTab = bar.querySelector('.wasm-tab-item.active .wasm-tab-dirty');
  if (activeTab) {
    if (doc.isDirty) {
      activeTab.classList.remove('d-none');
    } else {
      activeTab.classList.add('d-none');
    }
  }
}

/**
 * Сохраняет активный документ через POST /api/v1/workspaces/{workspace_id}/file-content.
 */
export async function saveActiveDocument() {
  const doc = getActiveDoc();
  if (!doc || doc.isBinary || doc.isMedia) return;

  const btnSave = document.getElementById('fe-btn-save');
  const commitInput = document.getElementById('fe-commit-msg-input');
  const statusBadge = document.getElementById('fe-save-status');

  const commitMsg = commitInput?.value?.trim() || `Правка файла ${doc.fileName}`;

  try {
    if (btnSave) btnSave.disabled = true;
    if (statusBadge) {
      statusBadge.textContent = 'Сохранение...';
      statusBadge.className = 'badge bg-warning-subtle text-warning';
    }

    const res = await fetch(`/api/v1/workspaces/${encodeURIComponent(doc.wsId)}/file-content`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        rel_path: doc.relPath,
        content: doc.content,
        commit_message: commitMsg,
      }),
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Ошибка ${res.status}`);
    }

    doc.initialContent = doc.content;
    doc.isDirty = false;
    updateActiveTabDirtyIndicator();

    if (commitInput) commitInput.value = '';
    if (statusBadge) {
      statusBadge.textContent = 'Сохранено в Git';
      statusBadge.className = 'badge bg-success-subtle text-success';
      setTimeout(() => {
        statusBadge.textContent = '';
      }, 3000);
    }
    notifyToast(`Файл "${doc.fileName}" успешно сохранён`, 'success');
  } catch (err) {
    console.error('[FileEditor] Ошибка сохранения файла:', err);
    notifyToast(`Ошибка сохранения: ${err.message}`, 'danger');
    if (statusBadge) {
      statusBadge.textContent = 'Ошибка сохранения';
      statusBadge.className = 'badge bg-danger-subtle text-danger';
    }
  } finally {
    if (btnSave) btnSave.disabled = false;
  }
}

/**
 * Открывает диалог создания нового файла.
 */
function handleCreateNewFilePrompt() {
  const name = prompt('Введите имя нового файла (например, app.py или notes.md):');
  if (!name || !name.trim()) return;
  const relPath = name.trim();
  const currentWs = getActiveWorkspaceId();
  openDocumentInTab(relPath, currentWs, true);
}

/**
 * Открывает текущий файл в ассоциированном системном приложении Windows.
 */
async function handleOpenSystem() {
  const doc = getActiveDoc();
  if (!doc) return;

  try {
    const res = await fetch(`/api/v1/workspaces/${encodeURIComponent(doc.wsId)}/open-file`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rel_path: doc.relPath }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    notifyToast(`Файл ${doc.fileName} открывается в системе`, 'info');
  } catch (err) {
    notifyToast(`Не удалось открыть файл в системе: ${err.message}`, 'warning');
  }
}

// Экспорт для глобального использования из дерева файлов и контекстного меню
window.openFileInCentralEditor = openDocumentInTab;
window.openFileInWasmEditor = openDocumentInTab;

export default {
  initFileEditorTab,
  openDocumentInTab,
  saveActiveDocument,
};
