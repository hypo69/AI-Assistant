/**
 * =============================================================================
 * Process Name: Common WebGUI - Universal Rust+Wasm File Editor Orchestrator
 * =============================================================================
 * Description:
 *   Главный клиентский оркестратор вкладки универсального редактора файлов
 *   (apps/common/webgui/tab_file_editor).
 *   Координирует WebAssembly-ядро, вкладки открытых файлов, дерево файлов
 *   рабочего пространства, переключение режимов VS Code (Code, Markdown Split,
 *   CSV/TSV Grid, Jupyter .ipynb, Media/SVG/PDF Studio, Hex Editor + Data
 *   Inspector), форматирование, Unified Diff и сохранение с коммитом в Git.
 *
 * File: main.js
 * Project: ai-windows-admin
 * Package: apps/common/webgui/tab_file_editor
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-28 17:10:00
 * =============================================================================
 */

import {
  initWasmEngine,
  base64ToUint8Array,
  uint8ArrayToBase64,
  analyzeBufferWithWasm,
} from './wasm_bridge.js';
import {
  updateLineGutter,
  getCursorPosition,
  renderOutlinePanel,
  renderMarkdownSplitPreview,
  runSearchReplace,
} from './panel_code_editor.js';
import {
  renderHexEditorPage,
  renderTabularGrid,
  renderNotebookEditor,
  renderMediaStudio,
  updateDataInspectorUI,
} from './panel_specialized_editors.js';

let isInitialized = false;
let workspaceFilesCache = [];
const openDocuments = new Map(); // key: `${wsId}:${relPath}` -> docState
let activeDocKey = null;

function notifyToast(msg, type = 'info') {
  if (typeof window.showToast === 'function') window.showToast(msg, type);
  else if (typeof window.showNotificationToast === 'function') window.showNotificationToast(msg, type);
}

function getCurrentWorkspaceId() {
  if (typeof window.getActiveWorkspaceId === 'function') {
    const ws = window.getActiveWorkspaceId();
    if (ws) return ws;
  }
  try {
    return localStorage.getItem('ai_assistant_active_workspace') || 'demo';
  } catch (_) {
    return 'demo';
  }
}

function getActiveDoc() {
  return activeDocKey ? openDocuments.get(activeDocKey) || null : null;
}

/**
 * Загружает список файлов текущего рабочего пространства в левую боковую панель.
 * @param {string|null} [wsId=null]
 */
export async function loadEditorWorkspaceFiles(wsId = null) {
  const targetWs = wsId || getCurrentWorkspaceId();
  const listEl = document.getElementById('fe-workspace-file-list');
  if (!listEl) return;

  try {
    const res = await fetch(`/api/v1/workspaces/${encodeURIComponent(targetWs)}/directory-contents`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    workspaceFilesCache = (data.items || []).filter((item) => !item.is_dir);
    renderWorkspaceFileList(
      document.getElementById('fe-file-filter-input')?.value || '',
      targetWs
    );

    // Если еще не открыт ни один файл — открываем первый доступный
    if (!activeDocKey && workspaceFilesCache.length > 0) {
      const first = workspaceFilesCache[0];
      await openFileInWasmEditor(first.rel_path || first.name, targetWs, false);
    }
  } catch (err) {
    listEl.innerHTML = `<div class="p-2 small text-muted">Нет доступных файлов (${err.message})</div>`;
  }
}

function renderWorkspaceFileList(filterStr = '', wsId = null) {
  const listEl = document.getElementById('fe-workspace-file-list');
  if (!listEl) return;
  const targetWs = wsId || getCurrentWorkspaceId();
  const q = (filterStr || '').trim().toLowerCase();

  const filtered = workspaceFilesCache.filter((f) => {
    const rel = (f.rel_path || f.name || '').toLowerCase();
    return !q || rel.includes(q);
  });

  if (filtered.length === 0) {
    listEl.innerHTML = `<div class="p-2 small text-muted">Файлы не найдены</div>`;
    return;
  }

  const curDoc = getActiveDoc();
  listEl.innerHTML = filtered
    .map((f) => {
      const rel = f.rel_path || f.name;
      const isAct = curDoc && curDoc.relPath === rel && curDoc.wsId === targetWs;
      return `
        <div class="wasm-editor-file-item ${isAct ? 'active' : ''}" data-fe-rel="${rel}" title="${rel}">
          <i class="bi bi-file-earmark-code text-primary"></i>
          <span class="text-truncate">${rel}</span>
        </div>
      `;
    })
    .join('');

  listEl.querySelectorAll('[data-fe-rel]').forEach((item) => {
    item.addEventListener('click', () => {
      const rel = item.getAttribute('data-fe-rel');
      if (rel) openFileInWasmEditor(rel, targetWs, false);
    });
  });
}

/**
 * Открывает файл в универсальном Wasm-редакторе (и при необходимости переключает вкладку WebGUI).
 * @param {string} relPath
 * @param {string|null} [wsId=null]
 * @param {boolean} [switchMainWebguiTab=true]
 */
export async function openFileInWasmEditor(relPath, wsId = null, switchMainWebguiTab = true) {
  if (!relPath) return;
  const targetWs = wsId || getCurrentWorkspaceId();

  if (switchMainWebguiTab && typeof window.switchTab === 'function') {
    await window.switchTab('tab-file-editor');
  }

  const key = `${targetWs}:${relPath}`;
  if (openDocuments.has(key)) {
    activeDocKey = key;
    syncUIWithActiveDocument();
    return;
  }

  try {
    const url = `/api/v1/file-editor/read?workspace_id=${encodeURIComponent(targetWs)}&rel_path=${encodeURIComponent(relPath)}`;
    const res = await fetch(url);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);

    const bytes = data.base64_content
      ? base64ToUint8Array(data.base64_content)
      : new TextEncoder().encode(data.content || '');
    const wasmStats = analyzeBufferWithWasm(bytes);
    const ext = (data.descriptor?.extension || relPath.split('.').pop() || '').toLowerCase();
    const defaultMode = mapDescriptorModeToStage(data.descriptor?.default_mode || 'code');

    const docState = {
      key,
      wsId: targetWs,
      relPath: data.rel_path || relPath,
      fileName: data.file_name || relPath.split('/').pop(),
      ext,
      descriptor: data.descriptor || {},
      isBinary: Boolean(data.is_binary),
      content: data.content ?? '',
      base64Content: data.base64_content || '',
      bytes,
      hexPatches: new Map(),
      hexPage: 0,
      selectedOffset: 0,
      lineEnding: data.line_ending || 'LF',
      mode: defaultMode,
      dirty: false,
      wasmStats,
      rotation: 0,
      flipH: false,
      flipV: false,
    };

    openDocuments.set(key, docState);
    activeDocKey = key;
    syncUIWithActiveDocument();
  } catch (err) {
    notifyToast(`Ошибка открытия файла: ${err.message}`, 'danger');
  }
}

function mapDescriptorModeToStage(rawMode) {
  if (['image', 'vector_svg', 'pdf', 'media'].includes(rawMode)) return 'media_studio';
  if (['code', 'markdown', 'tabular', 'notebook', 'hex'].includes(rawMode)) return rawMode;
  return 'code';
}

/**
 * Полностью синхронизирует интерфейс редактора с текущим активным документом.
 */
function syncUIWithActiveDocument() {
  renderOpenTabsBar();
  renderWorkspaceFileList(document.getElementById('fe-file-filter-input')?.value || '');

  const doc = getActiveDoc();
  const textarea = document.getElementById('fe-code-textarea');
  const gutter = document.getElementById('fe-line-gutter');
  const outlineEl = document.getElementById('fe-outline-list');
  const lineEndingSel = document.getElementById('fe-line-ending-select');

  if (!doc) {
    if (textarea) textarea.value = '';
    updateLineGutter(textarea, gutter);
    return;
  }

  if (lineEndingSel) lineEndingSel.value = doc.lineEnding || 'LF';
  if (textarea && !doc.isBinary) {
    textarea.value = doc.content || '';
    updateLineGutter(textarea, gutter);
  }

  renderOutlinePanel(doc.content || '', doc.ext, outlineEl, textarea);
  updateDataInspectorUI(doc.bytes, doc.selectedOffset || 0);
  switchEditorStageMode(doc.mode);
  updateStatusBar(doc);
}

/**
 * Переключает активную сцену редактора (`code`, `markdown`, `tabular`, `notebook`, `media_studio`, `hex`, `diff`).
 * @param {string} mode
 */
export function switchEditorStageMode(mode) {
  const doc = getActiveDoc();
  if (doc && mode !== 'diff') doc.mode = mode;

  // Подсветка пилюль режимов
  document.querySelectorAll('#fe-mode-pills [data-editor-mode]').forEach((btn) => {
    btn.classList.toggle('active', btn.getAttribute('data-editor-mode') === mode);
  });

  const modeBadge = document.getElementById('wasm-active-mode-badge');
  if (modeBadge) modeBadge.textContent = mode.toUpperCase();

  const stages = {
    code: document.getElementById('fe-stage-code'),
    markdown: document.getElementById('fe-stage-code'),
    tabular: document.getElementById('fe-stage-tabular'),
    notebook: document.getElementById('fe-stage-notebook'),
    media_studio: document.getElementById('fe-stage-media'),
    hex: document.getElementById('fe-stage-hex'),
    diff: document.getElementById('fe-stage-diff'),
  };

  Object.values(stages).forEach((el) => {
    if (!el) return;
    el.classList.add('d-none');
    el.classList.remove('d-flex');
  });

  const targetStage = stages[mode] || stages.code;
  if (targetStage) {
    targetStage.classList.remove('d-none');
    if (targetStage.id !== 'fe-stage-code') targetStage.classList.add('d-flex');
  }

  const mdSplit = document.getElementById('fe-markdown-split-preview');
  if (mdSplit) {
    if (mode === 'markdown') {
      mdSplit.classList.remove('d-none');
      renderMarkdownSplitPreview(doc?.content || '', mdSplit);
    } else {
      mdSplit.classList.add('d-none');
    }
  }

  if (!doc) return;

  if (mode === 'tabular') {
    renderTabularGrid(doc, (newCsv) => updateActiveDocText(newCsv));
  } else if (mode === 'notebook') {
    renderNotebookEditor(doc, (newJson) => updateActiveDocText(newJson));
  } else if (mode === 'media_studio') {
    renderMediaStudio(doc, (newB64) => {
      doc.base64Content = newB64;
      doc.bytes = base64ToUint8Array(newB64);
      doc.dirty = true;
      renderOpenTabsBar();
    });
  } else if (mode === 'hex') {
    const hexContainer = document.getElementById('fe-hex-grid-container');
    renderHexEditorPage(doc, hexContainer, (offset, newVal) => {
      doc.bytes[offset] = newVal;
      doc.hexPatches.set(offset, newVal);
      doc.dirty = true;
      doc.wasmStats = analyzeBufferWithWasm(doc.bytes);
      renderHexEditorPage(doc, hexContainer, () => {});
      renderOpenTabsBar();
      updateStatusBar(doc);
    });
  }
}

function updateActiveDocText(newText) {
  const doc = getActiveDoc();
  if (!doc) return;
  doc.content = newText;
  doc.bytes = new TextEncoder().encode(newText);
  doc.dirty = true;
  doc.wasmStats = analyzeBufferWithWasm(doc.bytes);
  const textarea = document.getElementById('fe-code-textarea');
  if (textarea && textarea.value !== newText) textarea.value = newText;
  renderOpenTabsBar();
  updateStatusBar(doc);
}

function renderOpenTabsBar() {
  const bar = document.getElementById('fe-open-tabs-bar');
  if (!bar) return;
  if (openDocuments.size === 0) {
    bar.innerHTML = `<span class="small text-muted px-2">Нет открытых вкладок</span>`;
    return;
  }

  bar.innerHTML = Array.from(openDocuments.values())
    .map((d) => {
      const isAct = d.key === activeDocKey;
      const icon = d.descriptor?.icon_class || 'bi-file-earmark-code';
      return `
        <div class="wasm-open-file-tab ${isAct ? 'active' : ''}" data-open-tab-key="${d.key}">
          <i class="bi ${icon} text-primary"></i>
          <span>${d.fileName}</span>
          ${d.dirty ? '<span class="text-warning fw-bold" title="Несохраненные изменения">●</span>' : ''}
          <button type="button" class="wasm-open-file-tab-close" data-close-tab-key="${d.key}" title="Закрыть вкладку">&times;</button>
        </div>
      `;
    })
    .join('');

  bar.querySelectorAll('[data-open-tab-key]').forEach((tabEl) => {
    tabEl.addEventListener('click', (e) => {
      if (e.target.closest('[data-close-tab-key]')) return;
      activeDocKey = tabEl.getAttribute('data-open-tab-key');
      syncUIWithActiveDocument();
    });
  });

  bar.querySelectorAll('[data-close-tab-key]').forEach((closeBtn) => {
    closeBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      const k = closeBtn.getAttribute('data-close-tab-key');
      openDocuments.delete(k);
      if (activeDocKey === k) {
        const keys = Array.from(openDocuments.keys());
        activeDocKey = keys.length > 0 ? keys[keys.length - 1] : null;
      }
      syncUIWithActiveDocument();
    });
  });
}

function updateStatusBar(doc) {
  const setTxt = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  };
  const textarea = document.getElementById('fe-code-textarea');
  const pos = getCursorPosition(textarea);
  setTxt('fe-status-cursor', `Ln ${pos.line}, Col ${pos.col}`);
  setTxt('fe-status-lines', `${doc?.wasmStats?.linesCount || 1} lines`);
  setTxt('fe-status-size', `${doc?.bytes?.length || 0} B`);
  setTxt('fe-status-hash', `FNV1a: ${doc?.wasmStats?.hashHex || '00000000'}`);
  setTxt('fe-status-wasm-timing', `⚡ Wasm: ${doc?.wasmStats?.durationMs || '0.0'} ms`);
  setTxt('fe-status-lang', doc?.descriptor?.display_name || 'Plain Text');
}

async function saveActiveDocument() {
  const doc = getActiveDoc();
  if (!doc) return;

  const commitMsg = document.getElementById('fe-commit-msg-input')?.value || '';
  const lineEnding = document.getElementById('fe-line-ending-select')?.value || 'LF';

  const payload = {
    workspace_id: doc.wsId,
    rel_path: doc.relPath,
    line_ending: lineEnding,
    commit_to_git: true,
    commit_message: commitMsg || null,
  };

  if (doc.hexPatches && doc.hexPatches.size > 0 && doc.isBinary) {
    payload.hex_patches = Array.from(doc.hexPatches.entries()).map(([offset, value]) => ({ offset, value }));
  } else if (doc.isBinary) {
    payload.base64_content = doc.base64Content || uint8ArrayToBase64(doc.bytes);
  } else {
    payload.content = doc.content;
  }

  try {
    const res = await fetch('/api/v1/file-editor/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);

    doc.dirty = false;
    doc.hexPatches.clear();
    renderOpenTabsBar();
    notifyToast(`Файл "${doc.relPath}" сохранён (${data.size} B, FNV1a: ${data.fnv1a_hash})`, 'success');
  } catch (err) {
    notifyToast(`Ошибка сохранения: ${err.message}`, 'danger');
  }
}

async function formatActiveDocument() {
  const doc = getActiveDoc();
  if (!doc || doc.isBinary) return;

  try {
    const res = await fetch('/api/v1/file-editor/format', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        content: doc.content,
        extension: doc.ext,
        language_id: doc.descriptor?.language_id || 'plaintext',
        indent_size: 2,
      }),
    });
    const data = await res.json();
    if (!data.valid && data.diagnostics?.length) {
      notifyToast(data.diagnostics.join('; '), 'warning');
      return;
    }
    updateActiveDocText(data.formatted);
    syncUIWithActiveDocument();
    notifyToast('Документ отформатирован и проверен', 'info');
  } catch (err) {
    notifyToast(`Ошибка форматирования: ${err.message}`, 'danger');
  }
}

async function showActiveDocumentDiff() {
  const doc = getActiveDoc();
  if (!doc) return;
  try {
    const res = await fetch('/api/v1/file-editor/diff', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        workspace_id: doc.wsId,
        rel_path: doc.relPath,
        modified_content: doc.content || '',
      }),
    });
    const data = await res.json();
    const diffOut = document.getElementById('fe-diff-output');
    const diffBadge = document.getElementById('fe-diff-summary-badge');
    if (diffBadge) diffBadge.textContent = `+${data.added_lines || 0} / -${data.removed_lines || 0}`;
    if (diffOut) {
      diffOut.textContent = data.unified_diff || 'Изменений относительно сохранённой версии на диске нет.';
    }
    switchEditorStageMode('diff');
  } catch (err) {
    notifyToast(`Ошибка расчёта Diff: ${err.message}`, 'danger');
  }
}

function bindEvents() {
  const textarea = document.getElementById('fe-code-textarea');
  const gutter = document.getElementById('fe-line-gutter');

  textarea?.addEventListener('input', () => {
    const doc = getActiveDoc();
    if (doc) {
      doc.content = textarea.value;
      doc.bytes = new TextEncoder().encode(textarea.value);
      doc.dirty = true;
      doc.wasmStats = analyzeBufferWithWasm(doc.bytes);
      if (doc.mode === 'markdown') {
        renderMarkdownSplitPreview(doc.content, document.getElementById('fe-markdown-split-preview'));
      }
      renderOutlinePanel(doc.content, doc.ext, document.getElementById('fe-outline-list'), textarea);
      renderOpenTabsBar();
      updateStatusBar(doc);
    }
    updateLineGutter(textarea, gutter);
  });

  textarea?.addEventListener('scroll', () => {
    if (gutter) gutter.scrollTop = textarea.scrollTop;
  });

  textarea?.addEventListener('click', () => updateStatusBar(getActiveDoc()));
  textarea?.addEventListener('keyup', () => updateStatusBar(getActiveDoc()));

  textarea?.addEventListener('keydown', (e) => {
    if (e.key === 'Tab') {
      e.preventDefault();
      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;
      textarea.value = textarea.value.slice(0, start) + '  ' + textarea.value.slice(end);
      textarea.selectionStart = textarea.selectionEnd = start + 2;
      textarea.dispatchEvent(new Event('input'));
    }
  });

  // Переключение режимов редактора (Pills)
  document.querySelectorAll('#fe-mode-pills [data-editor-mode]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const mode = btn.getAttribute('data-editor-mode');
      if (mode) switchEditorStageMode(mode);
    });
  });

  document.getElementById('fe-btn-save')?.addEventListener('click', saveActiveDocument);
  document.getElementById('fe-btn-format')?.addEventListener('click', formatActiveDocument);
  document.getElementById('fe-btn-diff')?.addEventListener('click', showActiveDocumentDiff);
  document.getElementById('fe-btn-refresh-files')?.addEventListener('click', () => loadEditorWorkspaceFiles());

  document.getElementById('fe-btn-toggle-tree')?.addEventListener('click', () => {
    document.getElementById('fe-workbench')?.classList.toggle('hide-left');
  });

  document.getElementById('fe-file-filter-input')?.addEventListener('input', (e) => {
    renderWorkspaceFileList(e.target.value);
  });

  // Создание нового файла
  document.getElementById('fe-btn-new-file')?.addEventListener('click', async () => {
    const name = prompt('Введите относительный путь нового файла (например: script.py, table.csv, note.ipynb):', 'new_file.py');
    if (!name || !name.trim()) return;
    const wsId = getCurrentWorkspaceId();
    await fetch('/api/v1/file-editor/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workspace_id: wsId, rel_path: name.trim(), content: '' }),
    });
    await loadEditorWorkspaceFiles(wsId);
    await openFileInWasmEditor(name.trim(), wsId, false);
  });

  // Загрузка локального файла с диска напрямую в Wasm-память браузера
  document.getElementById('fe-local-file-input')?.addEventListener('change', async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const buf = new Uint8Array(await file.arrayBuffer());
    const stats = analyzeBufferWithWasm(buf);
    const ext = (file.name.split('.').pop() || '').toLowerCase();
    const isBin = stats.isBinary;
    const text = isBin ? '' : new TextDecoder('utf-8').decode(buf);
    const key = `local:${file.name}`;
    openDocuments.set(key, {
      key,
      wsId: getCurrentWorkspaceId(),
      relPath: file.name,
      fileName: file.name,
      ext,
      descriptor: { display_name: ext.toUpperCase(), extension: ext },
      isBinary: isBin,
      content: text,
      base64Content: uint8ArrayToBase64(buf),
      bytes: buf,
      hexPatches: new Map(),
      hexPage: 0,
      selectedOffset: 0,
      lineEnding: 'LF',
      mode: isBin ? 'hex' : 'code',
      dirty: true,
      wasmStats: stats,
    });
    activeDocKey = key;
    syncUIWithActiveDocument();
  });

  // Скачивание текущего буфера
  document.getElementById('fe-btn-download')?.addEventListener('click', () => {
    const doc = getActiveDoc();
    if (!doc) return;
    const blob = new Blob([doc.bytes], { type: doc.descriptor?.mime_type || 'application/octet-stream' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = doc.fileName || 'file.bin';
    a.click();
    URL.revokeObjectURL(a.href);
  });

  // Поиск и замена
  document.getElementById('fe-btn-toggle-search')?.addEventListener('click', () => {
    document.getElementById('fe-search-bar')?.classList.toggle('d-none');
    document.getElementById('fe-find-input')?.focus();
  });

  const execSearch = (mode) => {
    const q = document.getElementById('fe-find-input')?.value || '';
    const r = document.getElementById('fe-replace-input')?.value || '';
    const count = runSearchReplace(textarea, q, r, mode);
    const badge = document.getElementById('fe-search-matches-badge');
    if (badge) badge.textContent = `${count}`;
  };
  document.getElementById('fe-btn-find-next')?.addEventListener('click', () => execSearch('find'));
  document.getElementById('fe-btn-replace-one')?.addEventListener('click', () => execSearch('replace'));
  document.getElementById('fe-btn-replace-all')?.addEventListener('click', () => execSearch('replaceAll'));

  // Пагинация Hex-редактора
  document.getElementById('fe-hex-prev-page')?.addEventListener('click', () => {
    const doc = getActiveDoc();
    if (doc && doc.hexPage > 0) {
      doc.hexPage--;
      switchEditorStageMode('hex');
    }
  });
  document.getElementById('fe-hex-next-page')?.addEventListener('click', () => {
    const doc = getActiveDoc();
    if (doc) {
      doc.hexPage++;
      switchEditorStageMode('hex');
    }
  });

  // Кнопки CSV и Jupyter Notebook и Image Studio
  document.getElementById('fe-csv-add-row')?.addEventListener('click', () => {
    const doc = getActiveDoc();
    if (!doc) return;
    updateActiveDocText((doc.content || '').trimEnd() + '\n,\n');
    switchEditorStageMode('tabular');
  });
  document.getElementById('fe-csv-add-col')?.addEventListener('click', () => {
    const doc = getActiveDoc();
    if (!doc) return;
    const delim = doc.ext === 'tsv' ? '\t' : ',';
    const updated = (doc.content || '')
      .trimEnd()
      .split('\n')
      .map((l, idx) => l + delim + (idx === 0 ? 'NewCol' : ''))
      .join('\n');
    updateActiveDocText(updated + '\n');
    switchEditorStageMode('tabular');
  });
  document.getElementById('fe-nb-add-code')?.addEventListener('click', () => {
    const doc = getActiveDoc();
    if (!doc || !doc.notebookObj) return;
    doc.notebookObj.cells.push({ cell_type: 'code', execution_count: null, metadata: {}, outputs: [], source: ['# Новый код\n'] });
    updateActiveDocText(JSON.stringify(doc.notebookObj, null, 2) + '\n');
    switchEditorStageMode('notebook');
  });
  document.getElementById('fe-nb-add-md')?.addEventListener('click', () => {
    const doc = getActiveDoc();
    if (!doc || !doc.notebookObj) return;
    doc.notebookObj.cells.push({ cell_type: 'markdown', metadata: {}, source: ['### Заголовок заметки\n'] });
    updateActiveDocText(JSON.stringify(doc.notebookObj, null, 2) + '\n');
    switchEditorStageMode('notebook');
  });
  document.getElementById('fe-img-rotate-left')?.addEventListener('click', () => {
    const doc = getActiveDoc();
    if (doc) {
      doc.rotation = (doc.rotation || 0) - 90;
      switchEditorStageMode('media_studio');
    }
  });
  document.getElementById('fe-img-rotate-right')?.addEventListener('click', () => {
    const doc = getActiveDoc();
    if (doc) {
      doc.rotation = (doc.rotation || 0) + 90;
      switchEditorStageMode('media_studio');
    }
  });
  document.getElementById('fe-img-flip-h')?.addEventListener('click', () => {
    const doc = getActiveDoc();
    if (doc) {
      doc.flipH = !doc.flipH;
      switchEditorStageMode('media_studio');
    }
  });
  document.getElementById('fe-img-flip-v')?.addEventListener('click', () => {
    const doc = getActiveDoc();
    if (doc) {
      doc.flipV = !doc.flipV;
      switchEditorStageMode('media_studio');
    }
  });
  document.getElementById('fe-pdf-extract-md')?.addEventListener('click', () => {
    const doc = getActiveDoc();
    if (!doc) return;
    const rawStr = new TextDecoder('latin1').decode(doc.bytes || new Uint8Array(0));
    const matches = [...rawStr.matchAll(/\(([^()]{2,200})\)/g)].map((m) => m[1]);
    const extracted = `# ${doc.fileName}\n\n` + (matches.length ? matches.join('\n\n') : doc.content || '');
    doc.isBinary = false;
    updateActiveDocText(extracted);
    switchEditorStageMode('markdown');
  });

  // Горячие клавиши Ctrl+S и Ctrl+F внутри вкладки редактора
  document.addEventListener('keydown', (e) => {
    if (typeof window.isTabActive === 'function' && !window.isTabActive('tab-file-editor')) return;
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
      e.preventDefault();
      saveActiveDocument();
    } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'f') {
      e.preventDefault();
      document.getElementById('fe-search-bar')?.classList.remove('d-none');
      document.getElementById('fe-find-input')?.focus();
    }
  });

  document.addEventListener('workspace:changed', (e) => {
    loadEditorWorkspaceFiles(e.detail?.workspaceId);
  });
}

/**
 * Инициализирует вкладку универсального редактора файлов Rust + WebAssembly.
 */
export async function initFileEditorTab() {
  if (!isInitialized) {
    bindEvents();
    isInitialized = true;
  }

  await initWasmEngine();
  try {
    const res = await fetch('/api/v1/file-editor/catalog');
    if (res.ok) {
      const cat = await res.json();
      const badge = document.getElementById('fe-catalog-count-badge');
      if (badge) badge.textContent = `${cat.total_types || 85}+`;
    }
  } catch (_) {}

  await loadEditorWorkspaceFiles();
}

export function activateFileEditorTab() {
  loadEditorWorkspaceFiles();
}

export function deactivateFileEditorTab() {}

if (typeof window !== 'undefined') {
  window.initFileEditorTab = initFileEditorTab;
  window.activateFileEditorTab = activateFileEditorTab;
  window.deactivateFileEditorTab = deactivateFileEditorTab;
  window.openFileInWasmEditor = openFileInWasmEditor;
}
