/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Tab Workspace Virtual & Physical File Tree Panel
 * =============================================================================
 * Description:
 *   Отдельная панель виртуального семантического дерева и физической иерархии
 *   файлов рабочей области и внешних источников (panel-tree) на #tab-workspace.
 *   Строит виртуальные категории на основе оценки содержимого всех отслеживаемых
 *   Git файлов (включая файлы вне рабочей директории) и позволяет запускать
 *   ревизию (переоценку содержимого и логики построения категорий моделью ИИ).
 *
 * File: panel.js
 * Package: apps/ai_assistant/api/webgui/tab_workspace/panel_tree
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-28 18:49:00
 * =============================================================================
 */

import { registerPanelRenderer } from '../../js/panel-loader.js';
import { fetchJson } from '../common/ui_utils.js';
import { getCurrentWorkspaceId } from '../panel_workspace_select/panel.js';

let treeItemsCache = [];
let treeMetaCache = {};
let taxonomyMetaCache = {};
let selectedRelPath = '';
let treeViewMode = 'virtual'; // 'virtual' (по содержимому) | 'physical' (по папкам)
const collapsedFolders = new Set();

/**
 * Экранирует спецсимволы HTML.
 * @param {string} str - Исходная строка
 * @returns {string}
 */
function escapeHtml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/**
 * Подбирает иконку Bootstrap Icons по типу узла (виртуальная категория, папка или файл).
 * @param {Object} node - Узел дерева
 * @param {boolean} isExpanded - Раскрыта ли категория/папка
 * @returns {string} HTML иконки
 */
function getNodeIconHtml(node, isExpanded = true) {
  if (node.isDir) {
    if (node.isVirtualCategory) {
      return isExpanded
        ? '<i class="bi bi-Collection-fill bi-folder2-open text-info"></i>'
        : '<i class="bi bi-folder-fill text-info"></i>';
    }
    return isExpanded
      ? '<i class="bi bi-folder2-open text-warning"></i>'
      : '<i class="bi bi-folder-fill text-warning"></i>';
  }
  const ext = (node.extension || '').toLowerCase();
  if (ext === '.pdf') return '<i class="bi bi-file-earmark-pdf text-danger"></i>';
  if (['.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif', '.tiff'].includes(ext)) {
    return '<i class="bi bi-file-earmark-image text-info"></i>';
  }
  if (['.wav', '.mp3', '.ogg', '.m4a', '.flac', '.aac'].includes(ext)) {
    return '<i class="bi bi-file-earmark-music text-primary"></i>';
  }
  if (['.xls', '.xlsx', '.csv'].includes(ext)) {
    return '<i class="bi bi-file-earmark-spreadsheet text-success"></i>';
  }
  if (ext === '.md') return '<i class="bi bi-markdown text-primary"></i>';
  if (['.py', '.js', '.ts', '.json', '.html', '.css'].includes(ext)) {
    return '<i class="bi bi-file-earmark-code text-info"></i>';
  }
  return '<i class="bi bi-file-earmark-text text-secondary"></i>';
}

function t(key, fallback = '') {
  if (typeof window !== 'undefined' && window.i18n && typeof window.i18n.t === 'function') {
    return window.i18n.t(key, fallback);
  }
  return fallback;
}

/**
 * Формирует бейдж статуса Git для элемента дерева.
 * @param {Object} item - Элемент директории
 * @returns {string} HTML бейджа
 */
function getGitBadgeHtml(item) {
  if (!item || item.is_dir) return '';
  const code = String(item.git_code || '');
  const status = String(item.git_status || t('workspace.treeGitTracked', 'Отслеживается'));

  if (code.includes('R') || item.moved_from) {
    const title = item.moved_from ? `${t('workspace.treeMovedFromLabel', 'Перенесён без потери связей из')}: ${item.moved_from}` : status;
    return `<span class="badge bg-info-subtle text-info border border-info-subtle font-monospace" title="${escapeHtml(title)}">${t('workspace.treeGitMoved', 'R100 Перемещён')}</span>`;
  }
  if (code.includes('M')) {
    return `<span class="badge bg-warning-subtle text-warning border border-warning-subtle" title="${escapeHtml(status)}">${t('workspace.treeGitModified', 'Изменён')}</span>`;
  }
  if (code.includes('D')) {
    return `<span class="badge bg-danger-subtle text-danger border border-danger-subtle" title="${escapeHtml(status)}">${t('workspace.treeGitDeleted', 'Удалён')}</span>`;
  }
  if (code === 'L') {
    return `<span class="badge bg-primary-subtle text-primary border border-primary-subtle" title="${escapeHtml(status)}">${t('workspace.treeGitExternal', 'Вне рабочей папки (Git)')}</span>`;
  }
  if (item.tracked_by_git) {
    return `<span class="badge bg-success-subtle text-success border border-success-subtle" title="${escapeHtml(status)}">${t('workspace.treeGitOk', 'Git OK')}</span>`;
  }
  return `<span class="badge bg-secondary-subtle text-secondary border" title="${escapeHtml(status)}">${escapeHtml(code || '??')}</span>`;
}

/**
 * Строит иерархическое дерево из списка элементов в виртуальном (по содержимому) или физическом режиме.
 * @param {Array<Object>} items - Список файлов и папок рабочей области
 * @param {'virtual'|'physical'} [mode='virtual'] - Режим построения иерархии
 * @returns {Object} Корневой узел дерева
 */
export function buildHierarchyTree(items, mode = 'virtual') {
  const root = {
    name: '/',
    relPath: '',
    isDir: true,
    isVirtualCategory: mode === 'virtual',
    childrenMap: new Map(),
    children: [],
    item: null,
  };

  for (const rawItem of items || []) {
    if (mode === 'virtual' && rawItem.is_dir) {
      // В виртуальном режиме иерархия строится строго по виртуальным категориям содержимого файлов
      continue;
    }

    const rawTreePath = mode === 'virtual'
      ? (rawItem.virtual_path || `${rawItem.virtual_category || 'Общая база знаний / Документы'}/${rawItem.name || rawItem.rel_path}`)
      : (rawItem.rel_path || rawItem.name || '');

    const normPath = String(rawTreePath)
      .replace(/\\/g, '/')
      .replace(/^\/+|\/+$/g, '');
    if (!normPath) continue;

    const parts = normPath.split('/').map((p) => p.trim()).filter(Boolean);
    let current = root;
    let accumPath = '';

    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      accumPath = accumPath ? `${accumPath}/${part}` : part;
      const isLast = i === parts.length - 1;
      const isDirNode = isLast ? Boolean(rawItem.is_dir) : true;

      if (!current.childrenMap.has(part)) {
        const newNode = {
          name: part,
          relPath: isLast && !isDirNode ? String(rawItem.rel_path || accumPath).replace(/\\/g, '/') : accumPath,
          treeNodeKey: accumPath,
          isDir: isDirNode,
          isVirtualCategory: isDirNode && mode === 'virtual',
          extension: isDirNode ? 'dir' : (rawItem.extension || ''),
          childrenMap: new Map(),
          children: [],
          item: isLast ? rawItem : null,
        };
        current.childrenMap.set(part, newNode);
        current.children.push(newNode);
      } else if (isLast) {
        const existing = current.childrenMap.get(part);
        existing.item = rawItem;
        existing.isDir = Boolean(rawItem.is_dir);
        if (!existing.isDir) {
          existing.relPath = String(rawItem.rel_path || accumPath).replace(/\\/g, '/');
          existing.extension = rawItem.extension || '';
        }
      }
      current = current.childrenMap.get(part);
    }
  }

  const sortRec = (node) => {
    node.children.sort((a, b) => {
      if (a.isDir !== b.isDir) return a.isDir ? -1 : 1;
      return a.name.localeCompare(b.name, 'ru');
    });
    for (const child of node.children) {
      if (child.isDir) sortRec(child);
    }
  };
  sortRec(root);
  return root;
}

/**
 * Подсчитывает общее количество файлов внутри узла-категории.
 * @param {Object} node - Узел дерева
 * @returns {number}
 */
function countLeafFiles(node) {
  if (!node.isDir) return 1;
  return (node.children || []).reduce((acc, child) => acc + countLeafFiles(child), 0);
}

/**
 * Рекурсивно рендерит HTML-разметку узлов дерева.
 * @param {Array<Object>} nodes - Узлы текущего уровня
 * @param {number} depth - Глубина вложенности
 * @returns {string} HTML
 */
function renderTreeNodesHtml(nodes, depth = 0) {
  if (!nodes || nodes.length === 0) return '';

  return nodes.map((node) => {
    const folderKey = node.treeNodeKey || node.relPath;
    const isCollapsed = node.isDir && collapsedFolders.has(folderKey);
    const isSelected = !node.isDir && selectedRelPath === node.relPath;
    const indentClass = depth > 0 ? `ps-${Math.min(depth * 3, 5)}` : '';
    const activeClass = isSelected
      ? 'bg-primary-subtle border-primary-subtle fw-semibold'
      : (node.isVirtualCategory ? 'bg-body-tertiary border-secondary-subtle fw-semibold' : 'bg-body border-transparent');

    const chevronHtml = node.isDir
      ? `<button class="btn btn-sm p-0 border-0 text-secondary ws-tree-toggle-btn" data-folder-path="${escapeHtml(folderKey)}" type="button" title="Свернуть/развернуть категорию">
           <i class="bi ${isCollapsed ? 'bi-chevron-right' : 'bi-chevron-down'} small"></i>
         </button>`
      : '<span class="d-inline-block" style="width: 16px;"></span>';

    const iconHtml = getNodeIconHtml(node, !isCollapsed);
    const itemMeta = node.item || {};
    const leafCount = node.isDir ? countLeafFiles(node) : 0;
    const sizeText = node.isDir
      ? `<span class="badge bg-secondary-subtle text-secondary border">${leafCount} ф.</span>`
      : `<span class="text-secondary small font-monospace">${escapeHtml(itemMeta.size_formatted || '')}</span>`;

    const badgeHtml = getGitBadgeHtml(itemMeta);
    const categoryBadge = node.isVirtualCategory && depth === 0
      ? '<span class="badge bg-info-subtle text-info border">Категория</span>'
      : '';

    const tagsHtml = (!node.isDir && Array.isArray(itemMeta.semantic_tags) && itemMeta.semantic_tags.length > 0)
      ? itemMeta.semantic_tags.slice(0, 2).map((t) => `<span class="badge bg-body-secondary text-secondary border">${escapeHtml(t)}</span>`).join('')
      : '';

    const childrenHtml = (node.isDir && !isCollapsed && node.children.length > 0)
      ? `<div class="ws-tree-children border-start border-secondary-subtle ms-3 ps-2 mt-1">${renderTreeNodesHtml(node.children, depth + 1)}</div>`
      : '';

    return `
      <div class="ws-tree-node-wrap mb-1" data-rel-path="${escapeHtml(node.relPath)}">
        <div class="d-flex align-items-center justify-content-between gap-2 py-1 px-2 rounded border ${activeClass} ${indentClass} ws-tree-row"
             data-rel-path="${escapeHtml(node.relPath)}"
             data-folder-key="${escapeHtml(folderKey)}"
             data-is-dir="${node.isDir ? '1' : '0'}"
             role="button">
          <div class="d-flex align-items-center gap-1.5 text-truncate">
            ${chevronHtml}
            ${iconHtml}
            <span class="small text-truncate" title="${escapeHtml(itemMeta.semantic_summary || node.relPath)}">${escapeHtml(node.name)}</span>
          </div>
          <div class="d-flex align-items-center gap-1 flex-shrink-0">
            ${categoryBadge}
            ${tagsHtml}
            ${badgeHtml}
            ${sizeText}
          </div>
        </div>
        ${childrenHtml}
      </div>
    `;
  }).join('');
}

/**
 * Отображает подробную информацию о выбранном файле (включая виртуальную категорию, обоснование и физический путь).
 * @param {string} relPath - Относительный путь к выбранному узлу
 */
async function renderSelectedNodeInspector(relPath) {
  const emptyBox = document.getElementById('ws-tree-inspector-empty');
  const detailsBox = document.getElementById('ws-tree-inspector-details');
  if (!emptyBox || !detailsBox) return;

  const found = treeItemsCache.find((i) => String(i.rel_path).replace(/\\/g, '/') === relPath);
  if (!found) {
    emptyBox.classList.remove('d-none');
    detailsBox.classList.add('d-none');
    return;
  }

  emptyBox.classList.add('d-none');
  detailsBox.classList.remove('d-none');

  const nameEl = document.getElementById('ws-tree-insp-name');
  const vcatEl = document.getElementById('ws-tree-insp-vcat');
  const rationaleEl = document.getElementById('ws-tree-insp-rationale');
  const tagsEl = document.getElementById('ws-tree-insp-tags');
  const relEl = document.getElementById('ws-tree-insp-relpath');
  const qualEl = document.getElementById('ws-tree-insp-qualpath');
  const gitEl = document.getElementById('ws-tree-insp-gitstatus');
  const hashEl = document.getElementById('ws-tree-insp-hash');
  const movedRow = document.getElementById('ws-tree-insp-moved-row');
  const movedEl = document.getElementById('ws-tree-insp-moved-from');
  const moveInput = document.getElementById('ws-tree-move-target-input');
  const previewEl = document.getElementById('ws-tree-file-preview');

  if (nameEl) nameEl.textContent = found.name || relPath;
  if (vcatEl) {
    const conf = found.confidence ? ` (${Math.round(found.confidence * 100)}%)` : '';
    vcatEl.textContent = `${found.virtual_category || 'Общая база знаний'}${conf}`;
  }
  if (rationaleEl) {
    rationaleEl.textContent = found.classification_rationale || found.semantic_summary || t('workspace.treeDefaultRationale', 'Категория назначена на основе оценки содержимого файла.');
  }
  if (tagsEl) {
    const tags = Array.isArray(found.semantic_tags) ? found.semantic_tags : [];
    tagsEl.innerHTML = tags.map((tTag) => `<span class="badge bg-secondary-subtle text-secondary border me-1">${escapeHtml(tTag)}</span>`).join('');
  }
  if (relEl) relEl.textContent = found.rel_path || relPath;
  if (qualEl) {
    const locType = found.source_mode === 'linked' ? t('workspace.treeExternalSourcePrefix', '[Внешний источник вне рабочей папки] ') : t('workspace.treeWorkspaceDirPrefix', '[Рабочая директория] ');
    qualEl.textContent = locType + (found.qualified_path || found.local_path || found.rel_path || '---');
  }
  if (gitEl) {
    let statusText = found.git_status;
    if (found.source_mode === 'linked' || found.git_code === 'L') {
      statusText = t('workspace.treeGitTrackedOnDisk', 'Отслеживается (на диске)');
    } else if (!statusText || statusText === 'Отслеживается') {
      statusText = t('workspace.treeGitTracked', 'Отслеживается');
    }
    gitEl.textContent = `${statusText} ${found.git_code ? `(${found.git_code})` : ''}`;
  }
  if (hashEl) hashEl.textContent = found.content_hash ? `${found.content_hash.slice(0, 16)}…` : t('workspace.treeHashComputing', 'вычисляется при индексации');

  if (movedRow && movedEl) {
    if (found.moved_from) {
      movedRow.classList.remove('d-none');
      movedEl.textContent = found.moved_from;
    } else {
      movedRow.classList.add('d-none');
      movedEl.textContent = '';
    }
  }

  if (moveInput) {
    moveInput.value = found.rel_path || relPath;
  }

  if (previewEl) {
    if (found.is_dir) {
      previewEl.textContent = t('workspace.treeSelectedDirectory', 'Выбрана директория.');
    } else if (found.source_mode === 'local') {
      previewEl.textContent = t('workspace.treeLoadingPreview', 'Загрузка предпросмотра файла...');
      try {
        const wsId = getCurrentWorkspaceId() || 'default';
        const res = await fetchJson(`/api/v1/workspaces/${encodeURIComponent(wsId)}/file-content?rel_path=${encodeURIComponent(found.rel_path)}`);
        previewEl.textContent = res.content || t('workspace.treeEmptyFile', '(Файл пуст)');
      } catch (err) {
        previewEl.textContent = found.semantic_summary || `(${t('workspace.treePreviewUnavailable', 'Предпросмотр недоступен')}: ${err.message})`;
      }
    } else {
      const extNote = t('workspace.treeExternalTrackedNote', '[Внешний файл отслеживается Git без копирования в рабочую директорию: {path}]')
        .replace('{path}', found.qualified_path || found.rel_path);
      previewEl.textContent = `${found.semantic_summary || ''}\n\n${extNote}`;
    }
  }
}

/**
 * Отрисовывает виртуальное или физическое дерево файлов в контейнере #ws-tree-viewport.
 */
export function renderWorkspaceTree() {
  const viewport = document.getElementById('ws-tree-viewport');
  const countBadge = document.getElementById('ws-tree-count-badge');
  const gitBadge = document.getElementById('ws-tree-git-badge');
  const repoBadge = document.getElementById('ws-tree-repo-path-badge');
  const relocBadge = document.getElementById('ws-tree-relocation-badge');
  const revBadge = document.getElementById('ws-tree-revision-badge');
  const logicTextEl = document.getElementById('ws-tree-taxonomy-logic-text');
  const strategySelect = document.getElementById('ws-tree-revision-strategy');
  if (!viewport) return;

  const searchVal = (document.getElementById('ws-tree-search-input')?.value || '').toLowerCase().trim();
  const filteredItems = searchVal
    ? treeItemsCache.filter((item) =>
        String(item.rel_path || '').toLowerCase().includes(searchVal) ||
        String(item.name || '').toLowerCase().includes(searchVal) ||
        String(item.virtual_category || '').toLowerCase().includes(searchVal) ||
        String(item.semantic_summary || '').toLowerCase().includes(searchVal) ||
        String(item.moved_from || '').toLowerCase().includes(searchVal)
      )
    : treeItemsCache;

  const totalFiles = treeItemsCache.filter((i) => !i.is_dir).length;
  const externalCount = treeItemsCache.filter((i) => !i.is_dir && i.source_mode === 'linked').length;
  const relocatedCount = treeItemsCache.filter((i) => i.moved_from || String(i.git_code || '').includes('R')).length;

  if (countBadge) {
    countBadge.textContent = externalCount > 0
      ? `${totalFiles} файлов (${externalCount} внешних)`
      : `${totalFiles} файлов`;
  }
  if (gitBadge && treeMetaCache.git_head) {
    gitBadge.textContent = `Git ${treeMetaCache.branch || 'master'} @ ${treeMetaCache.git_head}`;
  }
  if (repoBadge && treeMetaCache.workspace_path) {
    repoBadge.textContent = treeMetaCache.workspace_path;
  }
  if (revBadge && taxonomyMetaCache.revision_num) {
    revBadge.textContent = `Ревизия #${taxonomyMetaCache.revision_num} (${taxonomyMetaCache.total_categories || 0} кат.)`;
  }
  if (logicTextEl && taxonomyMetaCache.taxonomy_logic) {
    logicTextEl.textContent = taxonomyMetaCache.taxonomy_logic;
  }
  if (strategySelect && taxonomyMetaCache.strategy && !strategySelect.dataset.userTouched) {
    strategySelect.value = taxonomyMetaCache.strategy;
  }
  if (relocBadge) {
    if (relocatedCount > 0) {
      relocBadge.classList.remove('d-none');
      relocBadge.textContent = `Перемещено без потерь (R100): ${relocatedCount}`;
    } else {
      relocBadge.classList.add('d-none');
    }
  }

  if (!filteredItems || filteredItems.length === 0) {
    viewport.innerHTML = `
      <div class="text-center text-muted py-4 small" id="ws-tree-empty-msg">
        Отслеживаемые файлы не найдены.
      </div>
    `;
    return;
  }

  const root = buildHierarchyTree(filteredItems, treeViewMode);
  viewport.innerHTML = renderTreeNodesHtml(root.children, 0);

  viewport.querySelectorAll('.ws-tree-toggle-btn').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const folderPath = btn.getAttribute('data-folder-path');
      if (!folderPath) return;
      if (collapsedFolders.has(folderPath)) {
        collapsedFolders.delete(folderPath);
      } else {
        collapsedFolders.add(folderPath);
      }
      renderWorkspaceTree();
    });
  });

  viewport.querySelectorAll('.ws-tree-row').forEach((row) => {
    row.addEventListener('click', () => {
      const isDir = row.getAttribute('data-is-dir') === '1';
      if (isDir) {
        const fk = row.getAttribute('data-folder-key') || '';
        if (fk) {
          if (collapsedFolders.has(fk)) collapsedFolders.delete(fk);
          else collapsedFolders.add(fk);
          renderWorkspaceTree();
        }
        return;
      }
      const rp = row.getAttribute('data-rel-path') || '';
      selectedRelPath = rp;
      renderWorkspaceTree();
      renderSelectedNodeInspector(rp);
    });
  });
}

/**
 * Загружает виртуальное дерево всех отслеживаемых файлов (локальных и внешних) для активной области.
 * @param {string|null} [workspaceId=null] - Идентификатор рабочей области
 * @param {boolean} [force=false] - Принудительное обновление
 */
export async function loadWorkspaceTreePanel(workspaceId = null, force = false) {
  const wsId = workspaceId || getCurrentWorkspaceId() || 'default';
  try {
    const data = await fetchJson(`/api/v1/workspaces/${encodeURIComponent(wsId)}/virtual-tree`);
    treeMetaCache = data || {};
    taxonomyMetaCache = data?.virtual_taxonomy || {};
    treeItemsCache = data?.items || [];
    renderWorkspaceTree();
    if (selectedRelPath) {
      await renderSelectedNodeInspector(selectedRelPath);
    }
    return data;
  } catch (err) {
    console.warn('[TreePanel] Ошибка загрузки виртуального дерева рабочей области:', err);
    return null;
  }
}

/**
 * Инициализирует обработчики событий панели виртуального и физического дерева файлов (panel-tree).
 * @param {Function} [onTreeChanged] - Колбэк при изменении структуры файлов
 */
export function initTreePanel(onTreeChanged) {
  registerPanelRenderer('panel-tree', (result) => {
    if (result && Array.isArray(result.data)) {
      treeItemsCache = result.data;
      renderWorkspaceTree();
    }
  });

  const btnModeVirtual = document.getElementById('btn-ws-tree-mode-virtual');
  const btnModePhysical = document.getElementById('btn-ws-tree-mode-physical');

  btnModeVirtual?.addEventListener('click', () => {
    treeViewMode = 'virtual';
    collapsedFolders.clear();
    btnModeVirtual.classList.add('active');
    btnModePhysical?.classList.remove('active');
    renderWorkspaceTree();
  });

  btnModePhysical?.addEventListener('click', () => {
    treeViewMode = 'physical';
    collapsedFolders.clear();
    btnModePhysical.classList.add('active');
    btnModeVirtual?.classList.remove('active');
    renderWorkspaceTree();
  });

  document.getElementById('ws-tree-revision-strategy')?.addEventListener('change', (e) => {
    e.target.dataset.userTouched = '1';
  });

  document.getElementById('btn-ws-tree-revise-taxonomy')?.addEventListener('click', async () => {
    const wsId = getCurrentWorkspaceId() || 'default';
    const strategy = document.getElementById('ws-tree-revision-strategy')?.value || 'semantic_domain';
    const instruction = (document.getElementById('ws-tree-revision-prompt-input')?.value || '').trim();
    const statusEl = document.getElementById('ws-tree-action-status');
    if (statusEl) {
      statusEl.textContent = 'Выполняется ревизия: переоценка содержимого всех файлов и перестройка виртуальных категорий...';
    }
    try {
      const data = await fetchJson(`/api/v1/workspaces/${encodeURIComponent(wsId)}/virtual-tree/revise`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          strategy,
          instruction,
          use_model: true,
        }),
      });
      treeMetaCache = data || {};
      taxonomyMetaCache = data?.virtual_taxonomy || {};
      treeItemsCache = data?.items || [];
      treeViewMode = 'virtual';
      collapsedFolders.clear();
      btnModeVirtual?.classList.add('active');
      btnModePhysical?.classList.remove('active');
      renderWorkspaceTree();
      if (selectedRelPath) {
        await renderSelectedNodeInspector(selectedRelPath);
      }
      if (statusEl) {
        statusEl.textContent = `Ревизия #${taxonomyMetaCache.revision_num || ''} завершена: сформировано ${taxonomyMetaCache.total_categories || 0} виртуальных категорий.`;
      }
    } catch (err) {
      if (statusEl) statusEl.textContent = `Ошибка ревизии категорий: ${err.message}`;
    }
  });

  document.getElementById('ws-tree-search-input')?.addEventListener('input', () => {
    renderWorkspaceTree();
  });

  document.getElementById('btn-ws-tree-expand-all')?.addEventListener('click', () => {
    collapsedFolders.clear();
    renderWorkspaceTree();
  });

  document.getElementById('btn-ws-tree-collapse-all')?.addEventListener('click', () => {
    const root = buildHierarchyTree(treeItemsCache, treeViewMode);
    const collectKeys = (nodes) => {
      for (const n of nodes) {
        if (n.isDir) {
          collapsedFolders.add(n.treeNodeKey || n.relPath);
          collectKeys(n.children || []);
        }
      }
    };
    collectKeys(root.children);
    renderWorkspaceTree();
  });

  document.getElementById('btn-ws-tree-refresh')?.addEventListener('click', async () => {
    await loadWorkspaceTreePanel(null, true);
  });

  document.getElementById('btn-ws-tree-sync-external')?.addEventListener('click', async () => {
    const wsId = getCurrentWorkspaceId() || 'default';
    const statusEl = document.getElementById('ws-tree-action-status');
    if (statusEl) statusEl.textContent = 'Проверка внешних источников и сверка перемещений (SHA-256 + Git R100)...';
    try {
      const report = await fetchJson(`/api/v1/workspaces/${encodeURIComponent(wsId)}/sources/sync`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ force_reanalyze: false }),
      });
      const movedList = report?.relocated_files || [];
      if (statusEl) {
        statusEl.textContent = movedList.length > 0
          ? `Синхронизировано! Перемещено без потери связей и категорий: ${movedList.map((m) => `${m.from} → ${m.to}`).join(', ')}`
          : `Синхронизация завершена (обработано файлов: ${report?.total_indexed ?? 0}).`;
      }
      await loadWorkspaceTreePanel(wsId, true);
      if (typeof onTreeChanged === 'function') await onTreeChanged();
    } catch (err) {
      if (statusEl) statusEl.textContent = `Ошибка синхронизации: ${err.message}`;
    }
  });

  document.getElementById('btn-ws-tree-move-submit')?.addEventListener('click', async () => {
    const wsId = getCurrentWorkspaceId() || 'default';
    const targetInput = document.getElementById('ws-tree-move-target-input');
    const statusEl = document.getElementById('ws-tree-action-status');
    const newRelPath = (targetInput?.value || '').trim();
    if (!selectedRelPath || !newRelPath || selectedRelPath === newRelPath) {
      if (statusEl) statusEl.textContent = 'Укажите новый относительный путь (например: archive/mama.txt).';
      return;
    }
    try {
      const res = await fetchJson(`/api/v1/workspaces/${encodeURIComponent(wsId)}/items/move`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          old_rel_path: selectedRelPath,
          new_rel_path: newRelPath,
        }),
      });
      selectedRelPath = res.new_rel_path || newRelPath;
      if (statusEl) {
        statusEl.textContent = res.message || `Файл перемещён: ${res.old_rel_path} → ${res.new_rel_path}`;
      }
      await loadWorkspaceTreePanel(wsId, true);
      if (typeof onTreeChanged === 'function') await onTreeChanged();
    } catch (err) {
      if (statusEl) statusEl.textContent = `Ошибка перемещения: ${err.message}`;
    }
  });

  document.getElementById('btn-ws-tree-open-os')?.addEventListener('click', async () => {
    if (!selectedRelPath) return;
    const wsId = getCurrentWorkspaceId() || 'default';
    try {
      await fetchJson(`/api/v1/workspaces/${encodeURIComponent(wsId)}/open-file`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rel_path: selectedRelPath }),
      });
    } catch (err) {
      const statusEl = document.getElementById('ws-tree-action-status');
      if (statusEl) statusEl.textContent = `Ошибка открытия файла: ${err.message}`;
    }
  });
}
