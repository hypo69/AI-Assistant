/**

 * =============================================================================

 * Process Name: AI Assistant WebGUI - IDE File Explorer & Command Center

 * =============================================================================

 * Description:

 *   Модуль стандартного навигатора по файлам (Primary Side Bar Explorer) в стиле

 *   Visual Studio Code и верхнего выпадающего Command Center окна выбора

 *   рабочего пространства с Git.

 *

 *   Обеспечивает:

 *   - Интерактивное дерево файлов и папок рабочего пространства (VS Code Tree View)

 *   - Иконки типов файлов по расширениям (.md, .json, .py, .txt, .pdf, картинки)

 *   - Раскрытие/сворачивание папок с сохранением состояния

 *   - Клик по файлу открывает его в редакторе или Obsidian

 *   - Кнопки в шапке навигатора: новый файл, обновить, открыть в проводнике, свернуть

 *   - Верхнее окно Command Center в стиле VS Code с живым поиском и переключением пространств

 *

 * File: ide_file_explorer.js

 * Package: apps/ai_assistant/api/webgui/js

 * Author: hypo69

 * Copyright: © 2026 hypo69

 * Updated: 2026-11-06 23:14:00

 * =============================================================================

 */



import { getActiveWorkspaceId, getActiveRepoPath, setGlobalActiveRepo, fetchAvailableRepositories } from './top_workspace_dropdown.js';

import { initIdeTreeContextMenu, openEditorModal } from './ide_tree_context_menu.js?v=20261028_v2';

import { initIdeWorkspaceSearch } from './ide_workspace_search.js?v=20261030_v1';



let isSidebarCollapsed = false;

let currentFilesData = null;

let showAllFiles = false;



try {

  const saved = localStorage.getItem('ai_show_system_files') ?? localStorage.getItem('ide_show_all_files');

  if (saved !== null) {

    showAllFiles = saved === 'true';

  }

} catch (_) {}



export const expandedFolders = new Set(['', '_Topics']); // папки, раскрытые по умолчанию



/**

 * Проверяет, является ли элемент служебным/системным файлом или папкой.

 * @param {Object} item 

 * @returns {boolean}

 */

export function isSystemItem(item) {

  if (!item) return false;

  if (item.is_system === true || item.role === 'system') {

    return true;

  }

  if (typeof item.generator === 'string' && item.generator.startsWith('ai_assistant_')) {

    return true;

  }

  const name = String(item?.name || '').trim();

  const rel = String(item?.rel_path || item?.path || '').replace(/\\/g, '/');

  const parts = rel.toLowerCase().split('/');

  return (

    name.startsWith('.') ||

    name.startsWith('_') ||

    name.toLowerCase() === 'readme.md' ||

    name.toLowerCase() === 'assets' ||

    name.toLowerCase() === 'knowledge_base.md' ||

    name.toLowerCase() === '_knowledge_base.md' ||

    parts.some(p => p.startsWith('.') || p.startsWith('_') || p === 'assets' || p === '.obsidian')

  );

}



/**

 * Фильтрует список элементов в зависимости от флага показа служебных файлов.

 * @param {Array<Object>} items 

 * @param {boolean} [showAll=false] 

 * @returns {Array<Object>}

 */

export function getVisibleItems(items, showAll = false) {

  if (showAll) return items || [];

  return (items || []).filter(item => !isSystemItem(item));

}



/**

 * Устанавливает и синхронизирует состояние отображения служебных файлов.

 * @param {boolean} showAll 

 */

export function setShowAllFiles(showAll) {

  showAllFiles = Boolean(showAll);

  try {

    localStorage.setItem('ai_show_system_files', String(showAllFiles));

    localStorage.setItem('ide_show_all_files', String(showAllFiles));

  } catch (_) {}



  updateShowAllControls(showAllFiles);



  if (currentFilesData) {

    const treeContainer = document.getElementById('ide-file-tree-container');

    const targetWs = getActiveWorkspaceId() || 'default';

    if (treeContainer) {

      const visible = getVisibleItems(currentFilesData.items || [], showAllFiles);

      if (visible.length === 0) {

        treeContainer.innerHTML = `

          <div class="p-3 text-center text-muted font-size-80">

            <i class="bi bi-folder2 text-secondary fs-4 d-block mb-1"></i>

            <div>Папка пуста или файлы не найдены</div>

            <button class="btn btn-xs btn-outline-primary mt-2" id="ide-btn-show-system-now">Показать всё</button>

          </div>

        `;

        document.getElementById('ide-btn-show-system-now')?.addEventListener('click', () => setShowAllFiles(true));

      } else {

        const treeRoot = buildTreeHierarchy(visible);

        treeContainer.innerHTML = renderTreeNode(treeRoot, 0);

        bindTreeEvents(treeContainer, targetWs);

      }

    }

  }



  // Оповещаем другие компоненты WebGUI через глобальное событие

  document.dispatchEvent(new CustomEvent('ai:system-files-toggled', {

    detail: { showAll: showAllFiles }

  }));

}



/**

 * Обновляет состояние переключателя и кнопки в тулбаре навигатора.

 * @param {boolean} showAll 

 */

export function updateShowAllControls(showAll) {
  const btnToggle = document.getElementById('ide-btn-toggle-show-all');
  const icon = btnToggle?.querySelector('i');

  if (btnToggle) {
    if (showAll) {
      btnToggle.classList.add('active', 'text-warning');
      if (icon) icon.className = 'bi bi-eye-slash';
      btnToggle.title = window.i18n?.t ? window.i18n.t('workspace.hideSystemFiles', 'Скрыть служебные') : 'Скрыть служебные';
    } else {
      btnToggle.classList.remove('active', 'text-warning');
      if (icon) icon.className = 'bi bi-eye';
      btnToggle.title = window.i18n?.t ? window.i18n.t('workspace.showAllFiles', 'Показать всё') : 'Показать всё';
    }
  }
}



export function getCurrentFilesData() {

  return currentFilesData;

}



export function setCurrentFilesData(data) {

  currentFilesData = data;

}



/**

 * Возвращает подходящую иконку Bootstrap Icons и цвет для типа файла.

 * @param {string} fileName 

 * @param {boolean} isDir 

 * @returns {{icon: string, colorClass: string}}

 */

export function getFileIconData(fileName, isDir) {

  if (isDir) {

    return { icon: 'bi-folder-fill', colorClass: 'text-warning' };

  }

  const ext = (fileName.split('.').pop() || '').toLowerCase();

  switch (ext) {

    case 'md':

      return { icon: 'bi-markdown-fill', colorClass: 'text-info' };

    case 'json':

      return { icon: 'bi-braces', colorClass: 'text-warning' };

    case 'py':

      return { icon: 'bi-filetype-py', colorClass: 'text-primary' };

    case 'txt':

    case 'log':

      return { icon: 'bi-file-text', colorClass: 'text-secondary' };

    case 'png':

    case 'jpg':

    case 'jpeg':

    case 'svg':

    case 'webp':

    case 'gif':

      return { icon: 'bi-file-earmark-image', colorClass: 'text-success' };

    case 'pdf':

      return { icon: 'bi-file-earmark-pdf', colorClass: 'text-danger' };

    case 'csv':

    case 'xlsx':

    case 'xls':

      return { icon: 'bi-file-earmark-spreadsheet', colorClass: 'text-success' };

    case 'yaml':

    case 'yml':

      return { icon: 'bi-file-earmark-code', colorClass: 'text-danger' };

    case 'gitignore':

      return { icon: 'bi-git', colorClass: 'text-danger' };

    default:

      return { icon: 'bi-file-earmark', colorClass: 'text-muted' };

  }

}



/**

 * Преобразует плоский список элементов в иерархическое дерево папок и файлов.

 * @param {Array<Object>} items 

 * @returns {Object} Корневой узел дерева

 */

export function buildTreeHierarchy(items) {

  const root = { name: '', path: '', isDir: true, children: {}, files: [] };



  (items || []).forEach((item) => {

    const rawRel = (item.rel_path || item.name || '').replace(/\\/g, '/').replace(/^\/+/, '');

    if (!rawRel) return;



    const parts = rawRel.split('/');

    let current = root;



    for (let i = 0; i < parts.length - 1; i++) {

      const folderName = parts[i];

      if (!current.children[folderName]) {

        current.children[folderName] = {

          name: folderName,

          path: parts.slice(0, i + 1).join('/'),

          isDir: true,

          children: {},

          files: [],

        };

      }

      current = current.children[folderName];

    }



    const leafName = parts[parts.length - 1];

    if (item.is_dir) {

      if (!current.children[leafName]) {

        current.children[leafName] = {

          name: leafName,

          path: rawRel,

          isDir: true,

          children: {},

          files: [],

          item,

        };

      } else {

        current.children[leafName].item = item;

      }

    } else {

      current.files.push({ ...item, name: leafName, path: rawRel });

    }

  });



  return root;

}



/**

 * Отрисовывает узел дерева файлов и папок в стиле Visual Studio Code.

 * @param {Object} node 

 * @param {number} depth 

 * @returns {string} HTML разметка

 */

export function renderTreeNode(node, depth = 0) {

  let html = '';

  const indentPx = depth * 14;

  const isRtl = typeof document !== 'undefined' && document.documentElement.getAttribute('dir') === 'rtl';

  const closedChevron = isRtl ? 'bi-chevron-left' : 'bi-chevron-right';



  // 1. Папки (отсортированы по имени)

  const sortedFolders = Object.keys(node.children).sort((a, b) => a.localeCompare(b));

  for (const fName of sortedFolders) {

    const folder = node.children[fName];

    const isExpanded = expandedFolders.has(folder.path);

    const chevronIcon = isExpanded ? 'bi-chevron-down' : closedChevron;

    const isExternalDir = Boolean(folder.item?.is_external || folder.item?.source_mode === 'linked');

    const folderIcon = isExternalDir

      ? (isExpanded ? 'bi-folder2-open' : 'bi-folder-symlink-fill')

      : (isExpanded ? 'bi-folder2-open' : 'bi-folder-fill');

    const folderColor = isExternalDir ? 'text-info' : 'text-warning';

    const extBadge = isExternalDir

      ? `<span class="badge bg-info-subtle text-info border font-size-75 ms-auto py-0 px-1" title="Внешняя присоединенная директория: ${folder.item?.qualified_path || folder.item?.local_path || ''}"><i class="bi bi-link-45deg"></i></span>`

      : '';



    html += `

      <div class="ide-tree-item ide-tree-folder ${isExternalDir ? 'ide-tree-external-item' : ''}" data-folder-path="${folder.path}" style="padding-inline-start: ${indentPx + 8}px; padding-left: ${indentPx + 8}px;">

        <span class="ide-tree-chevron"><i class="bi ${chevronIcon}"></i></span>

        <i class="bi ${folderIcon} ide-tree-icon ${folderColor}"></i>

        <span class="ide-tree-label text-truncate">${folder.name}</span>

        ${extBadge}

      </div>

      <div class="ide-tree-subgroup ${isExpanded ? '' : 'd-none'}" id="folder-group-${folder.path.replace(/[^a-zA-Z0-9_-]/g, '_')}">

        ${renderTreeNode(folder, depth + 1)}

      </div>

    `;

  }



  // 2. Файлы (отсортированы по имени)

  const sortedFiles = [...node.files].sort((a, b) => a.name.localeCompare(b.name));

  for (const file of sortedFiles) {

    const iconData = getFileIconData(file.name, false);

    const isExternal = Boolean(file.is_external || file.source_mode === 'linked');

    const extBadge = isExternal

      ? `<span class="badge bg-info-subtle text-info border font-size-75 py-0 px-1" title="Присоединенный внешний файл: ${file.qualified_path || file.local_path || file.path}"><i class="bi bi-link-45deg"></i></span>`

      : '';

    const gitTag = file.tracked_by_git ? '<span class="ide-git-tag text-success" title="Отслеживается Git">●</span>' : '';



    html += `

      <div class="ide-tree-item ide-tree-file ${isExternal ? 'ide-tree-external-item' : ''}" data-rel-path="${file.path}" data-name="${file.name}" style="padding-inline-start: ${indentPx + 22}px; padding-left: ${indentPx + 22}px;" title="${file.path} (${file.size_formatted || ''})${isExternal ? ' [Внешний файл]' : ''}">

        <i class="bi ${iconData.icon} ide-tree-icon ${iconData.colorClass}"></i>

        <span class="ide-tree-label text-truncate">${file.name}</span>

        <span class="ide-tree-meta ms-auto d-flex align-items-center gap-1">${extBadge}${gitTag}</span>

      </div>

    `;

  }



  if (depth > 0 && sortedFolders.length === 0 && sortedFiles.length === 0) {
    const emptyText = (typeof window !== 'undefined' && window.i18n && typeof window.i18n.t === 'function')
      ? window.i18n.t('ide.emptyFolder', 'Папка пуста')
      : 'Папка пуста';
    return `
      <div class="ide-tree-item ide-tree-empty-notice text-muted" style="padding-inline-start: ${indentPx + 22}px; padding-left: ${indentPx + 22}px; font-size: 0.75rem; font-style: italic;">
        <i class="bi bi-dash me-1"></i><span data-i18n="ide.emptyFolder">${emptyText}</span>
      </div>
    `;
  }

  return html;

}



/**

 * Загружает содержимое директории активного рабочего пространства и рендерит дерево файлов.

 * @param {string|null} [wsId=null] 

 */

export async function refreshFileTree(wsId = null) {

  const targetWs = wsId || getActiveWorkspaceId() || 'default';

  const treeContainer = document.getElementById('ide-file-tree-container');

  const titleNameEl = document.getElementById('ide-explorer-ws-title');

  const branchBadge = document.getElementById('ide-explorer-ws-branch');

  const summaryBadge = document.getElementById('ide-explorer-summary-badge');



  if (titleNameEl) titleNameEl.textContent = targetWs;



  if (treeContainer) {

    treeContainer.innerHTML = `

      <div class="p-3 text-center text-muted font-size-80">

        <div class="spinner-border spinner-border-sm text-primary mb-1" role="status"></div>

        <div>Загрузка файлов ${targetWs}...</div>

      </div>

    `;

  }



  try {

    const res = await fetch(`/api/v1/workspaces/${encodeURIComponent(targetWs)}/directory-contents`);

    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const data = await res.json();

    currentFilesData = data;



    if (branchBadge) branchBadge.textContent = data.branch || 'master';

    const allItems = data.items || [];

    const visibleItems = getVisibleItems(allItems, showAllFiles);



    if (summaryBadge) {

      const extCount = (allItems || []).filter(i => !i.is_dir && (i.is_external || i.source_mode === 'linked')).length;

      const totalCount = data.total_files || (allItems || []).filter(i => !i.is_dir).length;

      const visibleCount = (visibleItems || []).filter(i => !i.is_dir).length;

      const hiddenCount = totalCount - visibleCount;

      if (!showAllFiles && hiddenCount > 0) {

        summaryBadge.textContent = `${visibleCount} файлов (скрыто: ${hiddenCount})`;

      } else if (extCount > 0) {

        summaryBadge.textContent = `${totalCount} файлов (${extCount} внешн.)`;

      } else {

        summaryBadge.textContent = `${totalCount} файлов`;

      }

    }



    if (treeContainer) {

      if (visibleItems.length === 0) {

        treeContainer.innerHTML = `

          <div class="p-3 text-center text-muted font-size-80">

            <i class="bi bi-folder2 text-secondary fs-4 d-block mb-1"></i>

            <div>Папка пуста или файлы не найдены</div>

            <button class="btn btn-xs btn-outline-primary mt-2" id="ide-btn-add-first-file">+ Добавить файл</button>

          </div>

        `;

        document.getElementById('ide-btn-add-first-file')?.addEventListener('click', promptCreateFile);

        return;

      }



      const treeRoot = buildTreeHierarchy(visibleItems);

      treeContainer.innerHTML = renderTreeNode(treeRoot, 0);



      // Привязка интерактивных событий дерева файлов и папок
      bindTreeEvents(treeContainer, targetWs);

    }

  } catch (err) {

    console.warn('[IDE File Explorer] Ошибка загрузки файлов:', err);

    if (treeContainer) {

      treeContainer.innerHTML = `

        <div class="p-3 text-danger font-size-80">

          <i class="bi bi-exclamation-triangle me-1"></i> Не удалось прочесть файлы: ${err.message}

        </div>

      `;

    }

  }

}



/**
 * Переключает раскрытие/сворачивание папки в дереве проводника.
 * @param {HTMLElement} folderEl
 * @param {boolean|null} [forceState=null]
 */
export function toggleFolder(folderEl, forceState = null) {
  if (!folderEl) return;
  const fPath = folderEl.dataset.folderPath;
  if (fPath === undefined) return;

  const subgroup = folderEl.nextElementSibling;
  const isCurrentlyExpanded = expandedFolders.has(fPath);
  const nextExpanded = forceState !== null ? Boolean(forceState) : !isCurrentlyExpanded;

  if (nextExpanded) {
    expandedFolders.add(fPath);
  } else {
    expandedFolders.delete(fPath);
  }

  if (subgroup && subgroup.classList.contains('ide-tree-subgroup')) {
    if (nextExpanded) {
      subgroup.classList.remove('d-none');
    } else {
      subgroup.classList.add('d-none');
    }
  }

  // Обновляем иконку стрелки (chevron)
  const isRtl = typeof document !== 'undefined' && document.documentElement.getAttribute('dir') === 'rtl';
  const closedChevron = isRtl ? 'bi-chevron-left' : 'bi-chevron-right';
  const chevronIcon = folderEl.querySelector('.ide-tree-chevron i');
  if (chevronIcon) {
    chevronIcon.className = i ;
  }

  // Обновляем иконку папки
  const folderIcon = folderEl.querySelector('.ide-tree-icon');
  if (folderIcon) {
    const isExternalDir = folderEl.classList.contains('ide-tree-external-item');
    const folderColor = isExternalDir ? 'text-info' : 'text-warning';
    const iconName = isExternalDir
      ? (nextExpanded ? 'bi-folder2-open' : 'bi-folder-symlink-fill')
      : (nextExpanded ? 'bi-folder2-open' : 'bi-folder-fill');
    folderIcon.className = i  ide-tree-icon ;
  }

  // Подсвечиваем активный элемент
  const treeContainer = document.getElementById('ide-file-tree-container');
  if (treeContainer) {
    treeContainer.querySelectorAll('.ide-tree-item').forEach((el) => el.classList.remove('active'));
  }
  folderEl.classList.add('active');

  // Если открыта вкладка Дерево файлов (tab_file_tree), синхронизируем переход
  if (typeof window !== 'undefined' && typeof window.browseDirectoryInTree === 'function' && typeof window.isTabActive === 'function' && window.isTabActive('file-tree')) {
    window.browseDirectoryInTree(fPath);
  }
}

/**
 * Обрабатывает клик по файлу: подсветка и открытие в редакторе.
 * @param {HTMLElement} fileEl
 * @param {string|null} [wsId=null]
 */
export async function handleFileClick(fileEl, wsId = null) {
  if (!fileEl) return;
  const targetWs = wsId || getActiveWorkspaceId() || 'default';
  const treeContainer = document.getElementById('ide-file-tree-container');
  if (treeContainer) {
    treeContainer.querySelectorAll('.ide-tree-item').forEach((f) => f.classList.remove('active'));
  }
  fileEl.classList.add('active');

  const relPath = fileEl.dataset.relPath;
  if (!relPath) return;

  // Гарантированно открываем файл в центральном редакторе Studio Code (#tab-workspace#panel-file-editor)
  if (typeof window.switchTab === 'function' && typeof window.isTabActive === 'function' && !window.isTabActive('tab-workspace')) {
    await window.switchTab('tab-workspace');
  }
  if (typeof window.switchWorkspaceSubTab === 'function') {
    window.switchWorkspaceSubTab('panel-file-editor', true);
  }

  // Ожидаем готовности универсального Wasm-редактора
  for (let i = 0; i < 25; i++) {
    if (typeof window.openFileInWasmEditor === 'function') break;
    await new Promise((r) => setTimeout(r, 60));
  }

  if (typeof window.openFileInWasmEditor === 'function') {
    await window.openFileInWasmEditor(relPath, targetWs, true);
    return;
  }

  const ext = (relPath.split('.').pop() || '').toLowerCase();
  const isEditableText = [
    'txt', 'md', 'markdown', 'log', 'json', 'py', 'js', 'html', 'css',
    'yaml', 'yml', 'ini', 'cfg', 'toml', 'csv', 'sh', 'bat', 'ps1', 'xml'
  ].includes(ext);

  if (isEditableText) {
    const fileName = fileEl.dataset.name || relPath.split('/').pop() || relPath;
    openEditorModal({ isDir: false, relPath, name: fileName }, targetWs);
  } else {
    try {
      await fetch(/api/v1/workspaces//open-file, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rel_path: relPath }),
      });
    } catch (_) {}
  }
}

/**
 * Навешивает обработчики кликов на элементы дерева файлов и папок.
 * @param {HTMLElement} container 
 * @param {string|null} [wsId=null] 
 */
export function bindTreeEvents(container, wsId = null) {
  if (!container) return;
  const targetWs = wsId || getActiveWorkspaceId() || 'default';

  // 1. Привязка кликов по папкам (раскрытие/сворачивание)
  container.querySelectorAll('.ide-tree-folder').forEach((folderEl) => {
    folderEl.onclick = (e) => {
      e.stopPropagation();
      toggleFolder(folderEl);
    };
  });

  // 2. Привязка кликов по файлам (выбор и открытие)
  container.querySelectorAll('.ide-tree-file').forEach((fileEl) => {
    fileEl.onclick = async (e) => {
      e.stopPropagation();
      await handleFileClick(fileEl, targetWs);
    };
  });
}




/**

 * Диалог быстрого создания нового файла в текущем рабочем пространстве.

 */

async function promptCreateFile() {

  const wsId = getActiveWorkspaceId() || 'default';

  const fileName = prompt('Введите имя нового файла (например: Notes.md или script.py):', 'Note.md');

  if (!fileName || !fileName.trim()) return;



  try {

    const res = await fetch(`/api/v1/workspaces/${encodeURIComponent(wsId)}/items`, {

      method: 'POST',

      headers: { 'Content-Type': 'application/json' },

      body: JSON.stringify({

        items: [{ path: fileName.trim(), content: `# ${fileName.trim()}\n\nСоздано в AI Assistant IDE.\n` }],

      }),

    });

    if (res.ok) {

      if (window.showToast) window.showToast(`Файл ${fileName} создан`, 'success');

      await refreshFileTree(wsId);

      if (typeof window.switchWorkspaceSubTab === 'function') {

        window.switchWorkspaceSubTab('panel-file-editor', true);

      }

      if (typeof window.openFileInWasmEditor === 'function') {

        await window.openFileInWasmEditor(fileName.trim(), wsId, false);

      }

    }

  } catch (err) {

    alert(`Ошибка создания файла: ${err.message}`);

  }

}



/**

 * Переключает видимость навигатора по файлам (Side Bar Toggle).

 * @param {boolean|null} forceState 

 */

export function toggleFileExplorerSidebar(forceState = null) {

  const sidebar = document.getElementById('ide-file-navigator');

  const mainViewport = document.querySelector('.ide-main-viewport');

  const expandBtn = document.getElementById('ide-file-sidebar-expand-btn');

  if (!sidebar) return;



  const isCurrentlyCollapsed = sidebar.classList.contains('collapsed');

  let willCollapse;

  if (forceState !== null) {

    willCollapse = !forceState;

  } else {

    willCollapse = !isCurrentlyCollapsed;

  }



  isSidebarCollapsed = willCollapse;



  if (willCollapse) {

    sidebar.classList.add('collapsed');

    if (mainViewport) mainViewport.classList.add('sidebar-collapsed');

    if (expandBtn) expandBtn.classList.remove('d-none');

    document.body.classList.add('ide-sidebar-collapsed');

  } else {

    sidebar.classList.remove('collapsed');

    if (mainViewport) mainViewport.classList.remove('sidebar-collapsed');

    if (expandBtn) expandBtn.classList.add('d-none');

    document.body.classList.remove('ide-sidebar-collapsed');

    refreshFileTree();

  }

}

window.toggleFileExplorerSidebar = toggleFileExplorerSidebar;
window.refreshFileTree = refreshFileTree;
window.setShowAllFiles = setShowAllFiles;
window.getVisibleItems = getVisibleItems;
window.toggleFolder = toggleFolder;
window.handleFileClick = handleFileClick;



/**

 * Инициализирует верхнее окно выбора рабочего пространства в стиле VS Code Command Center.

 */

export async function initIdeWorkspacePicker() {

  const pickerBtn = document.getElementById('ide-workspace-picker-btn');

  const modalEl = document.getElementById('ideWorkspacePickerModal');

  const listEl = document.getElementById('ide-ws-picker-list');

  const searchInput = document.getElementById('ide-ws-quick-search');

  const centerWsName = document.getElementById('ide-command-center-ws-name');

  const centerBranch = document.getElementById('ide-command-center-branch');



  const updateCommandCenterDisplay = (wsId) => {

    const activeWs = wsId || getActiveWorkspaceId() || 'default';

    if (centerWsName) centerWsName.textContent = activeWs;

  };



  updateCommandCenterDisplay();



  const renderPickerList = async (filterText = '') => {

    if (!listEl) return;

    const repos = await fetchAvailableRepositories();

    const activeWs = (getActiveWorkspaceId() || '').toLowerCase();

    const normFilter = (filterText || '').trim().toLowerCase();



    const filtered = (repos || []).filter((r) => {

      const name = (r.name || r.workspace_id || '').toLowerCase();

      const branch = (r.branch || '').toLowerCase();

      return !normFilter || name.includes(normFilter) || branch.includes(normFilter);

    });



    if (filtered.length === 0) {

      listEl.innerHTML = `<div class="p-3 text-center text-muted small">Рабочие пространства с Git не найдены</div>`;

      return;

    }



    listEl.innerHTML = filtered.map((r) => {

      const wsId = r.workspace_id || (r.id ? r.id.replace(/^ws-/, '') : '');

      const isActive = wsId.toLowerCase() === activeWs;

      const cleanName = (r.name || wsId).replace(/^Workspace:\s*/i, '');



      return `

        <button class="list-group-item list-group-item-action d-flex align-items-center justify-content-between py-2 px-3 ide-ws-picker-item ${isActive ? 'active' : ''}" data-ws-id="${wsId}" data-repo-path="${r.path}" type="button">

          <div class="d-flex align-items-center gap-2 text-truncate">

            <i class="bi bi-folder-check ${isActive ? 'text-white' : 'text-primary'} fs-5"></i>

            <div class="text-truncate text-start">

              <div class="fw-semibold text-truncate">${cleanName}</div>

              <div class="small ${isActive ? 'text-white-50' : 'text-muted'} font-size-75">

                <i class="bi bi-git me-1"></i>Ветка: ${r.branch || 'master'} · ${r.path}

              </div>

            </div>

          </div>

          ${isActive ? '<span class="badge bg-success border border-white-50 font-size-75">Активно</span>' : '<span class="badge bg-body-secondary text-secondary border font-size-75">Выбрать</span>'}

        </button>

      `;

    }).join('');



    // Привязка кликов по пунктам списка

    listEl.querySelectorAll('.ide-ws-picker-item').forEach((item) => {

      item.addEventListener('click', async () => {

        const targetWs = item.dataset.wsId;

        const targetPath = item.dataset.repoPath;

        if (!targetWs) return;



        await setGlobalActiveRepo(targetPath, targetWs);

        updateCommandCenterDisplay(targetWs);

        await refreshFileTree(targetWs);



        if (modalEl && window.bootstrap) {

          bootstrap.Modal.getInstance(modalEl)?.hide();

        }

      });

    });

  };



  if (pickerBtn && modalEl && window.bootstrap) {

    pickerBtn.addEventListener('click', () => {

      const m = bootstrap.Modal.getOrCreateInstance(modalEl);

      m.show();

      renderPickerList('');

      setTimeout(() => searchInput?.focus(), 250);

    });

  }



  if (searchInput) {

    searchInput.addEventListener('input', (e) => {

      renderPickerList(e.target.value);

    });

  }



  // Обновление при смене контекста

  document.addEventListener('workspace:items-changed', (e) => {
    const wsId = e.detail?.workspaceId || getActiveWorkspaceId();
    currentFilesData = null;
    if (wsId) {
      refreshFileTree(wsId);
    }
  });

  document.addEventListener('workspace:changed', (e) => {

    const wsId = e.detail?.workspaceId;

    currentFilesData = null;

    if (wsId) {

      updateCommandCenterDisplay(wsId);

      refreshFileTree(wsId);

    }

  });

}



/**

 * Инициализирует весь комплекс стандартного IDE-интерфейса: навигатор файлов, поиск и Command Center.

 */

export function initIdeFileExplorer() {

  const explorerSidebar = document.getElementById('ide-file-navigator');

  if (!explorerSidebar) return;



  // 0. Делегированная обработка кликов по элементам дерева файлов и папок
  const treeContainer = document.getElementById('ide-file-tree-container');
  if (treeContainer && !treeContainer._delegatedBound) {
    treeContainer._delegatedBound = true;
    treeContainer.addEventListener('click', async (e) => {
      const folderEl = e.target.closest('.ide-tree-folder');
      if (folderEl) {
        e.stopPropagation();
        toggleFolder(folderEl);
        return;
      }
      const fileEl = e.target.closest('.ide-tree-file');
      if (fileEl) {
        e.stopPropagation();
        const targetWs = getActiveWorkspaceId() || 'default';
        await handleFileClick(fileEl, targetWs);
        return;
      }
    });
  }

  // 1. Привязка кнопки сворачивания навигатора

  document.getElementById('ide-btn-collapse-explorer')?.addEventListener('click', () => {

    toggleFileExplorerSidebar(false);

  });



  // 1.1. Привязка плавающей кнопки разворачивания

  document.getElementById('ide-file-sidebar-expand-btn')?.addEventListener('click', () => {

    toggleFileExplorerSidebar(true);

  });



  // 2. Кнопка обновления дерева файлов

  document.getElementById('ide-btn-refresh-explorer')?.addEventListener('click', () => {

    refreshFileTree();

  });



  // 3. Кнопка создания нового файла

  document.getElementById('ide-btn-new-file')?.addEventListener('click', promptCreateFile);



  // 4. Кнопка открытия папки в проводнике Windows

  document.getElementById('ide-btn-open-explorer-folder')?.addEventListener('click', async () => {

    const wsId = getActiveWorkspaceId() || 'default';

    try {

      await fetch(`/api/v1/workspaces/${encodeURIComponent(wsId)}/open-folder`, { method: 'POST' });

    } catch (_) {}

  });



  // 4.1. Привязка контролов скрытия/показа служебных файлов

  updateShowAllControls(showAllFiles);



  const switchShowAll = document.getElementById('ide-switch-show-all');

  if (switchShowAll && !switchShowAll._bound) {

    switchShowAll._bound = true;

    switchShowAll.addEventListener('change', (e) => {

      setShowAllFiles(e.target.checked);

    });

  }



  const btnToggleShowAll = document.getElementById('ide-btn-toggle-show-all');

  if (btnToggleShowAll && !btnToggleShowAll._bound) {

    btnToggleShowAll._bound = true;

    btnToggleShowAll.addEventListener('click', () => {

      setShowAllFiles(!showAllFiles);

    });

  }



  // Синхронизация при внешнем событии ai:system-files-toggled

  document.addEventListener('ai:system-files-toggled', (e) => {

    const nextVal = Boolean(e.detail?.showAll);

    if (nextVal !== showAllFiles) {

      showAllFiles = nextVal;

      updateShowAllControls(showAllFiles);

      if (currentFilesData) {

        const treeContainer = document.getElementById('ide-file-tree-container');

        const targetWs = getActiveWorkspaceId() || 'default';

        if (treeContainer) {

          const visible = getVisibleItems(currentFilesData.items || [], showAllFiles);

          const root = buildTreeHierarchy(visible);

          treeContainer.innerHTML = renderTreeNode(root, 0);

          bindTreeEvents(treeContainer, targetWs);

        }

      }

    }

  });



  // 5. Переключение сайдбара по клику на иконку Explorer в Activity Bar

  document.getElementById('ide-nav-workspace')?.addEventListener('click', () => {

    // В VS Code: если сайдбар закрыт — открыть, если открыт — свернуть

    toggleFileExplorerSidebar();

  });



  // 6. Первая загрузка дерева файлов

  refreshFileTree();



  // 7. Инициализация окна поиска по рабочей области (Quick Open в стиле VS Code)

  initIdeWorkspaceSearch();



  // 8. Инициализация раскрывающегося окна Command Center

  initIdeWorkspacePicker();



  // 9. Инициализация контекстного меню по ПКМ для дерева файлов

  initIdeTreeContextMenu();



  // 10. Перерисовка дерева файлов при переключении языка (RTL <-> LTR)

  window.addEventListener('languageChanged', () => {

    refreshFileTree();

  });

}

