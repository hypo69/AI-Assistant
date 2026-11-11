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



 * Updated: 2026-11-10 20:30:00



 * =============================================================================



 */



import { getActiveWorkspaceId } from './top_workspace_dropdown.js';



import { refreshFileTree } from './ide_file_explorer.js?v=20261106_v2';



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



    <div class="custom-context-menu-header" id="cm-tree-target-header" data-i18n="ide.contextMenu.targetHeader">Проводник</div>



    <div class="custom-context-menu-item" data-tree-action="summary" id="cm-tree-item-summary" title="Кратко о файле (аналитическая сводка)" data-i18n-title="ide.contextMenu.summaryTitle">



      <span class="custom-context-menu-icon"><i class="bi bi-info-circle text-info"></i></span>



      <span class="custom-context-menu-label" data-i18n="ide.contextMenu.summary">Кратко о файле</span>



    </div>



    <div class="custom-context-menu-item" data-tree-action="wasm-editor" id="cm-tree-item-wasm-editor" title="Открыть в универсальном редакторе Rust + WebAssembly (все типы файлов VS Code)" data-i18n-title="ide.contextMenu.wasmEditorTitle">



      <span class="custom-context-menu-icon"><i class="bi bi-code-square text-warning"></i></span>



      <span class="custom-context-menu-label" data-i18n="ide.contextMenu.wasmEditor">Редактор (Rust + Wasm)</span>



      <span class="badge bg-warning-subtle text-warning custom-context-menu-badge">Wasm</span>



    </div>



    <div class="custom-context-menu-item" data-tree-action="add" id="cm-tree-item-add" title="Создать новый файл или папку в этой директории" data-i18n-title="ide.contextMenu.createNewTitle">



      <span class="custom-context-menu-icon"><i class="bi bi-plus-circle text-success"></i></span>



      <span class="custom-context-menu-label" data-i18n="ide.contextMenu.createNew">Создать новый...</span>



      <span class="text-muted font-size-80" data-i18n="ide.contextMenu.fileFolder">Файл/Папка</span>



    </div>



    <div class="custom-context-menu-item" data-tree-action="edit" id="cm-tree-item-edit" title="Редактировать текстовый файл в модальном окне" data-i18n-title="ide.contextMenu.quickEditorTitle">



      <span class="custom-context-menu-icon"><i class="bi bi-pencil text-primary"></i></span>



      <span class="custom-context-menu-label" data-i18n="ide.contextMenu.quickEditor">Быстрый редактор</span>



    </div>



    <div class="custom-context-menu-item" data-tree-action="versions" id="cm-tree-item-versions" title="Посмотреть историю версий Git" data-i18n-title="ide.contextMenu.versionsTitle">



      <span class="custom-context-menu-icon"><i class="bi bi-clock-history text-info"></i></span>



      <span class="custom-context-menu-label" data-i18n="ide.contextMenu.versions">Версии</span>



      <span class="badge bg-secondary-subtle text-secondary custom-context-menu-badge">Git</span>



    </div>



    <div class="custom-context-menu-divider"></div>



    <div class="custom-context-menu-item text-danger" data-tree-action="delete" id="cm-tree-item-delete" title="Удалить файл или папку" data-i18n-title="ide.contextMenu.deleteTitle">



      <span class="custom-context-menu-icon"><i class="bi bi-trash text-danger"></i></span>



      <span class="custom-context-menu-label text-danger" data-i18n="common.delete">Удалить</span>



      <span class="text-muted font-size-80">Del</span>



    </div>



  `;



  document.body.appendChild(menu);



  menuElement = menu;



  if (window.i18n && typeof window.i18n.applyTranslations === 'function') {



    window.i18n.applyTranslations(menuElement);



  }



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



    case 'summary':



      if (currentTarget.isDir) {



        showToast(window.i18n?.t('ide.contextMenu.filesOnlyToast', 'ℹ️ Действие доступно только для файлов'), 'secondary');



        return;



      }



      openFileSummary(currentTarget, wsId);



      break;



    case 'add':



      openCreateModal(currentTarget);



      break;



    case 'edit':

    case 'wasm-editor':

      if (currentTarget.isDir) {

        showToast(window.i18n?.t('ide.contextMenu.filesOnlyToast', 'ℹ️ Действие доступно только для файлов'), 'secondary');

        return;

      }

      // Открываем файл в центральном окне редактора с вкладками (#tab-workspace#panel-file-editor)

      if (typeof window.openFileInWasmEditor === 'function') {

        await window.openFileInWasmEditor(currentTarget.relPath, wsId, true);

      } else {

        openEditorModal(currentTarget, wsId);

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




/**
 * Обрабатывает запрос на переименование файла или каталога через POST /api/v1/workspaces/{id}/items/move.
 */
async function handleRenameItemPrompt(target, wsId) {
  const currentName = target.name || target.relPath.split('/').pop();
  const newName = prompt(`Переименовать "${currentName}" в:`, currentName);
  if (!newName || !newName.trim() || newName.trim() === currentName) return;

  const parts = target.relPath.split('/');
  parts.pop();
  parts.push(newName.trim());
  const newRelPath = parts.join('/');

  try {
    const res = await fetch(`/api/v1/workspaces/${encodeURIComponent(wsId)}/items/move`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        old_rel_path: target.relPath,
        new_rel_path: newRelPath,
        commit_message: `Переименование ${target.relPath} -> ${newRelPath}`,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    showToast(`Переименовано в "${newName.trim()}"`, 'success');
    if (typeof refreshFileTree === 'function') {
      await refreshFileTree(wsId);
    }
  } catch (err) {
    showToast(`Ошибка переименования: ${err.message}`, 'danger');
  }
}

function openCreateModal(target, initialType = 'file') {



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



    const rootLabel = window.i18n?.t('ide.rootFolder', '/ (корень)');



    parentPathEl.textContent = parentFolder ? `/${parentFolder}/` : rootLabel;



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



      alert(window.i18n?.t('ide.specifyNameAlert', 'Пожалуйста, укажите имя создаваемого объекта.'));



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



 * Открывает краткую аналитическую сводку по файлу (в AIModalDialog или уведомлением).



 * @param {{isDir: boolean, relPath: string, name: string}} target 



 * @param {string} wsId 



 */



export async function openFileSummary(target, wsId) {



  try {



    const res = await fetch(`/api/v1/file-tree/summary?workspace_id=${encodeURIComponent(wsId)}&rel_path=${encodeURIComponent(target.relPath)}`);



    if (!res.ok) throw new Error(`HTTP ${res.status}`);



    const data = await res.json();



    if (window.AIModalDialog && typeof window.AIModalDialog.show === 'function') {



      window.AIModalDialog.show({



        title: data.name,



        subtitle: `${data.language_id} • ${data.size_formatted} • ${data.lines_count !== null ? data.lines_count + ' строк' : 'Бинарный'}`,



        panelId: 'panel-file-tree',



        tableType: 'file_summary',



        metadata: {



          'Путь': data.rel_path,



          'Размер': data.size_formatted,



          'Строк': data.lines_count !== null ? String(data.lines_count) : 'Бинарный',



          'Язык': data.language_id,



          'Суть': data.summary,



        },



        raw_data: data.preview || data.summary,



      });



    } else {



      showToast(`📄 ${data.name}: ${data.summary}`, 'info');



    }



  } catch (err) {



    showToast(`Ошибка сводки: ${err.message}`, 'danger');



  }



}

/**
 * Определяет вероятный тип (расширение) файла по содержимому и имени, если у файла нет расширения.
 * @param {string} content
 * @param {string} fileName
 * @returns {string|null}
 */
export function detectFileTypeFromContent(content, fileName = '') {
  const name = (fileName || '').split('/').pop().split('\\').pop().toLowerCase();
  if (['license', 'licence', 'readme', 'changelog', 'gemini'].includes(name)) return 'md';
  if (name === 'dockerfile') return 'dockerfile';
  if (name === 'makefile') return 'makefile';
  if (['.gitignore', '.gitattributes', '.editorconfig'].includes(name)) return 'txt';
  if (name === '.env') return 'ini';

  if (!content || typeof content !== 'string') return null;
  const text = content.slice(0, 8192).trim();
  if (!text) return null;

  // 1. Shebang (#!/...)
  if (text.startsWith('#!')) {
    const firstLine = text.split('\n')[0].toLowerCase();
    if (firstLine.includes('python')) return 'py';
    if (firstLine.includes('bash') || firstLine.includes('zsh') || firstLine.includes('/sh')) return 'sh';
    if (firstLine.includes('node')) return 'js';
    if (firstLine.includes('perl')) return 'pl';
    if (firstLine.includes('php')) return 'php';
    if (firstLine.includes('ruby')) return 'rb';
  }

  // 2. HTML, XML, SVG
  if (/^<!doctype\s+html/i.test(text) || /^<html[\s>]/i.test(text)) return 'html';
  if (text.startsWith('<?xml')) {
    return text.toLowerCase().includes('<svg') ? 'svg' : 'xml';
  }
  if (/^<svg[\s>]/i.test(text)) return 'svg';

  // 3. JSON
  if ((text.startsWith('{') && text.endsWith('}')) || (text.startsWith('[') && text.endsWith(']'))) {
    try {
      JSON.parse(text);
      return 'json';
    } catch (_) {}
  }

  // 4. Markdown Frontmatter (YAML --- ... ---)
  if (/^---\r?\n[\s\S]*?\r?\n---\r?\n?/.test(text)) {
    return 'md';
  }

  // 5. Markdown заголовки, Obsidian Wikilinks, списки задач, цитаты/callouts
  if (
    /^#{1,6}\s+.+/m.test(text) ||
    /\[\[.+?\]\]/.test(text) ||
    /^>\s*\[!/m.test(text) ||
    /^\s*[-*+]\s+\[[ x]\]/im.test(text)
  ) {
    return 'md';
  }

  // 6. CSV / TSV разделители
  const lines = text.split(/\r?\n/).filter(l => l.trim().length > 0).slice(0, 10);
  if (lines.length >= 2) {
    const commaCounts = lines.map(l => l.split(',').length);
    if (commaCounts[0] >= 2 && commaCounts.every(c => c === commaCounts[0])) return 'csv';
    const tabCounts = lines.map(l => l.split('\t').length);
    if (tabCounts[0] >= 2 && tabCounts.every(c => c === tabCounts[0])) return 'tsv';
  }

  return null;
}

/**
 * Выполняет предобработку Markdown перед рендерингом:
 * - Форматирует YAML Frontmatter (Obsidian Metadata) в аккуратную карточку
 * - Преобразует ссылки Obsidian [[Target|Title]] и [[Target]] в интерактивные бейджи
 * - Защищает строки перед '---' от ошибочного превращения в Setext-заголовки h2
 * - Предотвращает склеивание элементов списков со следующим текстом при отсутствии пустой строки
 * @param {string} src
 * @returns {{frontmatterHtml: string, cleanMarkdown: string}}
 */
export function preprocessMarkdownContent(src) {
  if (!src) return { frontmatterHtml: '', cleanMarkdown: '' };
  let text = String(src);

  const escapeHtml = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const escapeAttr = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

  // 1. Извлекаем YAML Frontmatter в начале документа (Obsidian Metadata)
  let frontmatterHtml = '';
  const fmMatch = text.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?/);
  if (fmMatch) {
    const fmRaw = fmMatch[1];
    text = text.slice(fmMatch[0].length);

    const lines = fmRaw.split(/\r?\n/);
    const rows = [];
    let currentKey = '';
    let currentList = [];

    const flushList = () => {
      if (currentKey && currentList.length > 0) {
        const badges = currentList.map(item => `<span class="badge bg-secondary-subtle text-secondary me-1 mb-1 font-monospace">${escapeHtml(item)}</span>`).join('');
        rows.push(`<tr><th class="text-muted small py-1 px-2" style="width: 140px;">${escapeHtml(currentKey)}</th><td class="py-1 px-2">${badges}</td></tr>`);
        currentKey = '';
        currentList = [];
      }
    };

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      if (trimmed.startsWith('- ')) {
        const val = trimmed.slice(2).trim().replace(/^["']/, '').replace(/["']$/, '').trim();
        currentList.push(val);
      } else {
        flushList();
        const colonIdx = trimmed.indexOf(':');
        if (colonIdx > 0) {
          const k = trimmed.slice(0, colonIdx).trim();
          const v = trimmed.slice(colonIdx + 1).trim().replace(/^["']/, '').replace(/["']$/, '').trim();
          if (v) {
            rows.push(`<tr><th class="text-muted small py-1 px-2" style="width: 140px;">${escapeHtml(k)}</th><td class="py-1 px-2 font-monospace small" dir="auto">${escapeHtml(v)}</td></tr>`);
          } else {
            currentKey = k;
          }
        }
      }
    }
    flushList();

    if (rows.length > 0) {
      frontmatterHtml = `
        <details class="card mb-3 border border-subtle shadow-xs" open>
          <summary class="card-header py-1.5 px-3 bg-body-tertiary small text-muted fw-semibold user-select-none cursor-pointer d-flex align-items-center gap-1.5">
            <i class="bi bi-file-earmark-code text-primary"></i>
            <span>YAML Frontmatter (Obsidian Metadata)</span>
          </summary>
          <div class="card-body p-0 table-responsive">
            <table class="table table-sm table-striped mb-0 small">
              <tbody>${rows.join('')}</tbody>
            </table>
          </div>
        </details>
      `;
    }
  }

  // 2. Обработка Obsidian Wikilinks: [[Target|Title]] и [[Target]]
  text = text.replace(/\[\[([^|\]\n]+)\|([^\]\n]+)\]\]/g, (_, target, title) => {
    const tClean = target.trim();
    const lClean = title.trim();
    return `<a href="#" class="obsidian-wikilink badge bg-primary-subtle text-primary border border-primary-subtle text-decoration-none px-1.5 py-0.5 rounded me-1 align-baseline" data-target="${escapeAttr(tClean)}" title="Obsidian ссылка: ${escapeAttr(tClean)}"><i class="bi bi-link-45deg me-0.5"></i>${escapeHtml(lClean)}</a>`;
  });
  text = text.replace(/\[\[([^\]\n]+)\]\]/g, (_, target) => {
    const tClean = target.trim();
    return `<a href="#" class="obsidian-wikilink badge bg-primary-subtle text-primary border border-primary-subtle text-decoration-none px-1.5 py-0.5 rounded me-1 align-baseline" data-target="${escapeAttr(tClean)}" title="Obsidian ссылка: ${escapeAttr(tClean)}"><i class="bi bi-link-45deg me-0.5"></i>${escapeHtml(tClean)}</a>`;
  });

  // 3. Защита от превращения строки перед --- в Setext Header <h2>
  text = text.replace(/([^\r\n]+)\r?\n---(?:\r?\n|$)/g, '$1\n\n---\n');

  // 4. Защита от слипания списков с последующим текстом
  text = text.replace(/(^[\t ]*[-*+][\t ][^\r\n]+)\r?\n(?!\r?\n|[\t ]*[-*+][\t ]|[\t ]*\d+\.[\t ])([^\r\n]+)/gm, '$1\n\n$2');

  return { frontmatterHtml, cleanMarkdown: text };
}

/**
 * Автономный парсер Markdown (CommonMark + GFM) для модального редактора.
 * @param {string} src
 * @returns {string}
 */
export function parseMarkdownToHtmlFallback(src) {
  if (!src) return '';

  const { frontmatterHtml, cleanMarkdown } = preprocessMarkdownContent(src);

  if (typeof window !== 'undefined') {
    if (typeof window.marked?.parse === 'function') {
      try {
        if (typeof window.marked.setOptions === 'function' && !window._markedConfigured) {
          window.marked.setOptions({ breaks: true, gfm: true });
          window._markedConfigured = true;
        }
        return frontmatterHtml + window.marked.parse(cleanMarkdown);
      } catch (_) {}
    }
  }

  const escapeHtml = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const codeBlocks = [];
  let text = cleanMarkdown.replace(/```([a-zA-Z0-9_\-#+.]*)\r?\n([\s\S]*?)```/g, (_, lang, code) => {
    const idx = codeBlocks.length;
    const safeLang = escapeHtml(lang.trim() || 'text');
    const safeCode = escapeHtml(code);
    codeBlocks.push(`
      <div class="card my-2 border border-subtle shadow-xs">
        <div class="card-header py-1 px-2.5 bg-body-tertiary d-flex align-items-center justify-content-between font-monospace small text-muted">
          <span>${safeLang}</span>
        </div>
        <pre class="p-2.5 m-0 overflow-auto bg-body font-monospace small" style="line-height: 1.45;"><code>${safeCode}</code></pre>
      </div>
    `);
    return `@@CODE_BLOCK_${idx}@@`;
  });
  text = escapeHtml(text);
  text = text.replace(/((?:^\|.+?\|(?:\r?\n|$))+)/gm, (tableText) => {
    const lines = tableText.trim().split(/\r?\n/).filter(Boolean);
    if (lines.length < 2) return tableText;
    if (!/^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$/.test(lines[1])) return tableText;
    const parseRow = (line) => line.replace(/^\||\|$/g, '').split('|').map((c) => c.trim());
    const headerCells = parseRow(lines[0]);
    const bodyRows = lines.slice(2).map(parseRow);
    const thead = `<tr>${headerCells.map((c) => `<th class="bg-body-tertiary px-2.5 py-1.5">${c}</th>`).join('')}</tr>`;
    const tbody = bodyRows.map((r) => `<tr>${r.map((c) => `<td class="px-2.5 py-1.5">${c}</td>`).join('')}</tr>`).join('');
    return `<div class="table-responsive my-2"><table class="table table-sm table-bordered table-hover mb-0"><thead>${thead}</thead><tbody>${tbody}</tbody></table></div>`;
  });
  text = text.replace(/^######\s+(.+)$/gm, '<h6 class="mt-3 mb-1.5 fw-bold" dir="auto">$1</h6>');
  text = text.replace(/^#####\s+(.+)$/gm, '<h5 class="mt-3 mb-1.5 fw-bold" dir="auto">$1</h5>');
  text = text.replace(/^####\s+(.+)$/gm, '<h4 class="mt-3.5 mb-2 fw-bold" dir="auto">$1</h4>');
  text = text.replace(/^###\s+(.+)$/gm, '<h3 class="mt-3.5 mb-2 fw-bold" dir="auto">$1</h3>');
  text = text.replace(/^##\s+(.+)$/gm, '<h2 class="mt-4 mb-2 fw-bold border-bottom pb-1 border-subtle" dir="auto">$1</h2>');
  text = text.replace(/^#\s+(.+)$/gm, '<h1 class="mt-4 mb-2.5 fw-bold border-bottom pb-2 border-subtle" dir="auto">$1</h1>');
  text = text.replace(/^(?:---|\*\*\*|___)\s*$/gm, '<hr class="my-3 border-subtle" />');
  text = text.replace(/^\s*[-*+]\s+\[x\]\s+(.+)$/gim, '<div class="form-check my-1"><input class="form-check-input" type="checkbox" checked disabled><label class="form-check-label text-decoration-line-through text-muted small">$1</label></div>');
  text = text.replace(/^\s*[-*+]\s+\[\s\]\s+(.+)$/gim, '<div class="form-check my-1"><input class="form-check-input" type="checkbox" disabled><label class="form-check-label small">$1</label></div>');
  text = text.replace(/(?:^\s*[-*+]\s+(?:(?!<div class="form-check").)*$(?:\r?\n)?)+/gm, (listBlock) => {
    const items = listBlock.trim().split(/\r?\n/).map((line) => line.replace(/^\s*[-*+]\s+/, '').trim()).filter(Boolean).map((it) => `<li dir="auto">${it}</li>`).join('');
    return `<ul class="my-1.5 ps-3">${items}</ul>`;
  });
  text = text.replace(/(?:^\s*\d+\.\s+.+$(?:\r?\n)?)+/gm, (listBlock) => {
    const items = listBlock.trim().split(/\r?\n/).map((line) => line.replace(/^\s*\d+\.\s+/, '').trim()).filter(Boolean).map((it) => `<li dir="auto">${it}</li>`).join('');
    return `<ol class="my-1.5 ps-3">${items}</ol>`;
  });
  text = text.replace(/`([^`\n]+)`/g, '<code class="px-1 py-0.5 rounded bg-body-secondary text-body font-monospace font-size-85">$1</code>');
  text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  text = text.replace(/__(.+?)__/g, '<strong>$1</strong>');
  text = text.replace(/\*([^\s*][^*]*?)\*/g, '<em>$1</em>');
  text = text.replace(/_([^\s_][^_]*?)_/g, '<em>$1</em>');
  text = text.replace(/~~(.+?)~~/g, '<del>$1</del>');
  text = text.replace(/!\[(.*?)\]\((.+?)\)/g, '<img src="$2" alt="$1" class="img-fluid rounded border border-subtle my-2 shadow-xs" style="max-height: 480px; object-fit: contain;" />');
  text = text.replace(/\[(.*?)\]\((.+?)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" class="text-primary text-decoration-underline">$1</a>');
  text = text.split(/\r?\n\r?\n/).map((block) => {
    const trimmed = block.trim();
    if (!trimmed) return '';
    if (/^<(?:h[1-6]|div|table|ul|ol|blockquote|hr|pre)/.test(trimmed)) return trimmed;
    return `<p class="mb-2 leading-relaxed" dir="auto">${trimmed.replace(/\r?\n/g, '<br />')}</p>`;
  }).join('\n');
  text = text.replace(/@@CODE_BLOCK_(\d+)@@/g, (_, idx) => codeBlocks[parseInt(idx, 10)] || '');
  return frontmatterHtml + text;
}

if (typeof window !== 'undefined') {
  window.parseMarkdownToHtml = parseMarkdownToHtmlFallback;
}

/**
 * Открывает модальное окно текстового редактора файла (встроенный редактор для txt, md и других форматов).
 * @param {{isDir: boolean, relPath: string, name: string}} target 
 * @param {string} wsId 
 */
export async function openEditorModal(target, wsId) {

  // Перенаправляем открытие в центральное окно редактора Studio Code с вкладками

  if (typeof window.openFileInWasmEditor === 'function' && target && target.relPath && !target.driveFileId) {

    await window.openFileInWasmEditor(target.relPath, wsId, true);

    return;

  }



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
  const btnSplit = document.getElementById('ide-editor-tab-split');
  const btnPreview = document.getElementById('ide-editor-tab-preview');
  const mdPreview = document.getElementById('ide-editor-markdown-preview');
  const isDrive = Boolean(target.driveFileId || target.source === 'drive' || wsId === 'gdrive');
  const driveFileId = target.driveFileId || target.id;
  const fileName = target.name || target.relPath || 'file';
  let ext = (fileName.includes('.') ? fileName.split('.').pop() : '').toLowerCase();
  let isMarkdown = ['md', 'markdown', 'mdown', 'mkd'].includes(ext);

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

  // Режим просмотра: для Markdown по умолчанию открываем раздельный вид (Вид/Редактор)
  let currentModalMode = isMarkdown ? 'split' : 'code';

  const renderModalPreview = () => {
    if (!mdPreview) return;
    const raw = textarea?.value || '';
    if (typeof window.marked !== 'undefined' && typeof window.marked.parse === 'function') {
      try {
        mdPreview.innerHTML = window.marked.parse(raw);
        return;
      } catch (err) {
        console.warn('[IDE Modal Editor] marked parse error:', err);
      }
    }
    if (typeof window.parseMarkdownToHtml === 'function') {
      mdPreview.innerHTML = window.parseMarkdownToHtml(raw);
      return;
    }
    mdPreview.innerHTML = parseMarkdownToHtmlFallback(raw);
  };

  const applyModalMode = (mode) => {
    currentModalMode = mode;
    btnCode?.classList.toggle('active', mode === 'code');
    btnSplit?.classList.toggle('active', mode === 'split');
    btnPreview?.classList.toggle('active', mode === 'preview');

    if (mode === 'split') {
      if (textarea) {
        textarea.classList.remove('d-none');
        textarea.style.display = 'block';
        textarea.style.flex = '1 1 50%';
        textarea.style.width = '50%';
        textarea.style.maxWidth = '50%';
        textarea.style.minWidth = '0';
      }
      if (mdPreview) {
        mdPreview.classList.remove('d-none');
        mdPreview.style.display = 'block';
        mdPreview.style.flex = '1 1 50%';
        mdPreview.style.width = '50%';
        mdPreview.style.maxWidth = '50%';
        mdPreview.style.minWidth = '0';
        renderModalPreview();
      }
    } else if (mode === 'preview') {
      if (textarea) {
        textarea.classList.add('d-none');
        textarea.style.display = 'none';
      }
      if (mdPreview) {
        mdPreview.classList.remove('d-none');
        mdPreview.style.display = 'block';
        mdPreview.style.flex = '1 1 100%';
        mdPreview.style.width = '100%';
        mdPreview.style.maxWidth = '100%';
        mdPreview.style.minWidth = '0';
        renderModalPreview();
      }
    } else {
      // mode === 'code'
      if (mdPreview) {
        mdPreview.classList.add('d-none');
        mdPreview.style.display = 'none';
      }
      if (textarea) {
        textarea.classList.remove('d-none');
        textarea.style.display = 'block';
        textarea.style.flex = '1 1 100%';
        textarea.style.width = '100%';
        textarea.style.maxWidth = '100%';
        textarea.style.minWidth = '0';
        textarea.focus();
      }
    }
  };

  if (viewModeGroup) {
    if (isMarkdown) {
      viewModeGroup.classList.remove('d-none');
    } else {
      viewModeGroup.classList.add('d-none');
    }
  }

  applyModalMode(currentModalMode);



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

        // Если у файла нет расширения — определяем тип по бэкенду или по содержимому
        if (!ext || ext === fileName.toLowerCase()) {
          const detected = (data && data.detected_type) || detectFileTypeFromContent(data.content, fileName);
          if (detected) {
            ext = detected;
            if (['md', 'markdown', 'mdown', 'mkd'].includes(ext)) {
              isMarkdown = true;
              if (viewModeGroup) viewModeGroup.classList.remove('d-none');
              applyModalMode('split');
            }
          }
        }

        setTimeout(() => textarea.focus(), 250);
        if (isMarkdown && (currentModalMode === 'split' || currentModalMode === 'preview')) {
          renderModalPreview();
        }
      }

      if (saveBtn) saveBtn.disabled = false;

      const updateStats = () => {
        const val = textarea?.value || '';
        const lines = val.split('\n').length;
        const linesWord = window.i18n?.t('ide.linesWord', 'Строк');
        const charsWord = window.i18n?.t('ide.charsWord', 'Символов');
        if (statsEl) statsEl.textContent = `${linesWord}: ${lines} | ${charsWord}: ${val.length}`;
      };

      updateStats();

      textarea?.addEventListener('input', () => {
        updateStats();
        if (currentModalMode === 'split' || currentModalMode === 'preview') {
          renderModalPreview();
        }
      });
    }
  } catch (err) {
    if (textarea) textarea.value = `Ошибка загрузки файла: ${err.message}`;
    showToast(`❌ Ошибка открытия: ${err.message}`, 'danger');
  }

  // Переключение режимов: Редактор / Вид/Редактор (Split) / Вид
  if (btnCode) btnCode.onclick = () => applyModalMode('code');
  if (btnSplit) btnSplit.onclick = () => applyModalMode('split');
  if (btnPreview) btnPreview.onclick = () => applyModalMode('preview');



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
window.detectFileTypeFromContent = detectFileTypeFromContent;



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



  // Редактирование и сводка доступны только для файлов



  const summaryItem = document.getElementById('cm-tree-item-summary');



  const wasmEditorItem = document.getElementById('cm-tree-item-wasm-editor');



  if (summaryItem) {



    if (currentTarget.isDir) {



      summaryItem.classList.add('disabled');



      summaryItem.title = 'Сводка доступна только для файлов';



    } else {



      summaryItem.classList.remove('disabled');



      summaryItem.title = 'Кратко о файле (аналитическая сводка)';



    }



  }



  if (wasmEditorItem) {



    if (currentTarget.isDir) {



      wasmEditorItem.classList.add('disabled');



      wasmEditorItem.title = 'Редактор доступен только для файлов';



    } else {



      wasmEditorItem.classList.remove('disabled');



      wasmEditorItem.title = 'Открыть в универсальном редакторе Rust + WebAssembly';



    }



  }



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



