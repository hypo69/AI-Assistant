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
 * Updated: 2026-10-28 19:00:00
 * =============================================================================
 */

import { getActiveWorkspaceId, getActiveRepoPath, setGlobalActiveRepo, fetchAvailableRepositories } from './top_workspace_dropdown.js';
import { initIdeTreeContextMenu, openEditorModal } from './ide_tree_context_menu.js?v=20261028_v2';

let isSidebarCollapsed = false;
let currentFilesData = null;
const expandedFolders = new Set(['', '_Topics']); // папки, раскрытые по умолчанию

/**
 * Возвращает подходящую иконку Bootstrap Icons и цвет для типа файла.
 * @param {string} fileName 
 * @param {boolean} isDir 
 * @returns {{icon: string, colorClass: string}}
 */
function getFileIconData(fileName, isDir) {
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
function buildTreeHierarchy(items) {
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
function renderTreeNode(node, depth = 0) {
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
    const folderIcon = isExpanded ? 'bi-folder2-open' : 'bi-folder-fill';

    html += `
      <div class="ide-tree-item ide-tree-folder" data-folder-path="${folder.path}" style="padding-inline-start: ${indentPx + 8}px; padding-left: ${indentPx + 8}px;">
        <span class="ide-tree-chevron"><i class="bi ${chevronIcon}"></i></span>
        <i class="bi ${folderIcon} ide-tree-icon text-warning"></i>
        <span class="ide-tree-label text-truncate">${folder.name}</span>
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
    const gitTag = file.tracked_by_git ? '<span class="ide-git-tag text-success" title="Отслеживается Git">●</span>' : '';

    html += `
      <div class="ide-tree-item ide-tree-file" data-rel-path="${file.path}" data-name="${file.name}" style="padding-inline-start: ${indentPx + 22}px; padding-left: ${indentPx + 22}px;" title="${file.path} (${file.size_formatted || ''})">
        <i class="bi ${iconData.icon} ide-tree-icon ${iconData.colorClass}"></i>
        <span class="ide-tree-label text-truncate">${file.name}</span>
        <span class="ide-tree-meta ms-auto">${gitTag}</span>
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
    if (summaryBadge) {
      summaryBadge.textContent = `${data.total_files || 0} файлов`;
    }

    if (treeContainer) {
      const items = data.items || [];
      if (items.length === 0) {
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

      const treeRoot = buildTreeHierarchy(items);
      treeContainer.innerHTML = renderTreeNode(treeRoot, 0);

      // Привязка кликов по папкам (раскрытие/сворачивание)
      treeContainer.querySelectorAll('.ide-tree-folder').forEach((folderEl) => {
        folderEl.addEventListener('click', (e) => {
          e.stopPropagation();
          const fPath = folderEl.dataset.folderPath;
          if (expandedFolders.has(fPath)) {
            expandedFolders.delete(fPath);
          } else {
            expandedFolders.add(fPath);
          }
          // Перерисовываем для быстрого отклика
          if (currentFilesData) {
            const root = buildTreeHierarchy(currentFilesData.items || []);
            treeContainer.innerHTML = renderTreeNode(root, 0);
            bindTreeEvents(treeContainer, targetWs);
          }
        });
      });

      // Привязка кликов по файлам (выбор и открытие)
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
 * Навешивает обработчики кликов на элементы дерева файлов.
 * Для текстовых файлов (.txt, .md и др.) открывает встроенный веб-редактор.
 * @param {HTMLElement} container 
 * @param {string} wsId 
 */
function bindTreeEvents(container, wsId) {
  container.querySelectorAll('.ide-tree-file').forEach((fileEl) => {
    fileEl.addEventListener('click', async (e) => {
      e.stopPropagation();
      container.querySelectorAll('.ide-tree-file').forEach((f) => f.classList.remove('active'));
      fileEl.classList.add('active');

      const relPath = fileEl.dataset.relPath;
      if (!relPath) return;

      // Если активна вкладка универсального редактора Rust + Wasm — открываем любой тип файла прямо в ней
      if (typeof window.isTabActive === 'function' && window.isTabActive('tab-file-editor') && typeof window.openFileInWasmEditor === 'function') {
        await window.openFileInWasmEditor(relPath, wsId, false);
        return;
      }

      const ext = (relPath.split('.').pop() || '').toLowerCase();
      const isEditableText = [
        'txt', 'md', 'markdown', 'log', 'json', 'py', 'js', 'html', 'css',
        'yaml', 'yml', 'ini', 'cfg', 'toml', 'csv', 'sh', 'bat', 'ps1', 'xml'
      ].includes(ext);

      if (isEditableText) {
        // Для txt, md и текстовых форматов открываем встроенный веб-редактор
        const fileName = fileEl.dataset.name || relPath.split('/').pop() || relPath;
        openEditorModal({ isDir: false, relPath, name: fileName }, wsId);
      } else {
        // Для нетекстовых/бинарных файлов открываем в системе через open-file
        try {
          await fetch(`/api/v1/workspaces/${encodeURIComponent(wsId)}/open-file`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ rel_path: relPath }),
          });
        } catch (_) {}
      }
    });
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
  if (!sidebar) return;

  if (forceState !== null) {
    isSidebarCollapsed = !forceState;
  } else {
    isSidebarCollapsed = !isSidebarCollapsed;
  }

  if (isSidebarCollapsed) {
    sidebar.classList.add('collapsed');
    if (mainViewport) mainViewport.classList.add('sidebar-collapsed');
  } else {
    sidebar.classList.remove('collapsed');
    if (mainViewport) mainViewport.classList.remove('sidebar-collapsed');
    refreshFileTree();
  }
}

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
  document.addEventListener('workspace:changed', (e) => {
    const wsId = e.detail?.workspaceId;
    if (wsId) {
      updateCommandCenterDisplay(wsId);
      refreshFileTree(wsId);
    }
  });
}

/**
 * Инициализирует весь комплекс стандартного IDE-интерфейса: навигатор файлов и Command Center.
 */
export function initIdeFileExplorer() {
  const explorerSidebar = document.getElementById('ide-file-navigator');
  if (!explorerSidebar) return;

  // 1. Привязка кнопки сворачивания навигатора
  document.getElementById('ide-btn-collapse-explorer')?.addEventListener('click', () => {
    toggleFileExplorerSidebar(false);
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
      await fetch(`/api/v1/workspaces/${encodeURIComponent(wsId)}/open-folder`);
    } catch (_) {}
  });

  // 5. Переключение сайдбара по клику на иконку Explorer в Activity Bar
  document.getElementById('ide-nav-workspace')?.addEventListener('click', () => {
    // В VS Code: если сайдбар закрыт — открыть, если открыт — свернуть
    toggleFileExplorerSidebar();
  });

  // 6. Первая загрузка дерева файлов
  refreshFileTree();

  // 7. Инициализация раскрывающегося окна Command Center
  initIdeWorkspacePicker();

  // 8. Инициализация контекстного меню по ПКМ для дерева файлов
  initIdeTreeContextMenu();

  // 9. Перерисовка дерева файлов при переключении языка (RTL <-> LTR)
  window.addEventListener('languageChanged', () => {
    refreshFileTree();
  });
}
