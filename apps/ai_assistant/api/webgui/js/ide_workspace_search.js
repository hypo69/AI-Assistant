/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - IDE Workspace Search (Quick Open)
 * =============================================================================
 * Description:
 *   Модуль поиска по активной рабочей области в стиле VS Code Command Center (Quick Open).
 *   Обеспечивает:
 *   - Интерактивное окно поиска по файлам и папкам текущей рабочей области
 *   - Живую фильтрацию с подсветкой совпадений и ранжированием
 *   - Клавиатурную навигацию (Стрелки Вверх/Вниз, Enter для открытия, Esc для отмены)
 *   - Глобальный хоткей Ctrl+P / Cmd+P
 *   - Открытие текстовых файлов во встроенном модальном редакторе или в WASM-редакторе
 *
 * File: ide_workspace_search.js
 * Package: apps/ai_assistant/api/webgui/js
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-07 00:00:00
 * =============================================================================
 */

import { getActiveWorkspaceId } from './top_workspace_dropdown.js';
import { openEditorModal } from './ide_tree_context_menu.js?v=20261028_v2';
import {
  getFileIconData,
  expandedFolders,
  buildTreeHierarchy,
  renderTreeNode,
  bindTreeEvents,
  getCurrentFilesData,
  setCurrentFilesData,
} from './ide_file_explorer.js?v=20261106_v2';

/**
 * Инициализирует окно поиска по рабочей области в стиле VS Code Command Center (Quick Open).
 */
export function initIdeWorkspaceSearch() {
  const searchInput = document.getElementById('ide-workspace-search-input');
  const searchWrapper = document.getElementById('ide-search-box-wrapper');
  const dropdownEl = document.getElementById('ide-search-results-dropdown');
  const listEl = document.getElementById('ide-search-results-list');
  const clearBtn = document.getElementById('ide-search-clear-btn');
  const countEl = document.getElementById('ide-search-results-count');

  if (!searchInput || !dropdownEl || !listEl) return;

  let activeIndex = -1;
  let currentSearchResults = [];

  const getTranslation = (key, fallback) => {
    if (typeof window.i18next?.t === 'function') {
      const res = window.i18next.t(key);
      if (res && res !== key) return res;
    }
    return fallback;
  };

  const closeDropdown = () => {
    dropdownEl.classList.add('d-none');
    activeIndex = -1;
    listEl.querySelectorAll('.ide-search-item').forEach((el) => el.classList.remove('active'));
  };

  const openDropdown = () => {
    dropdownEl.classList.remove('d-none');
  };

  const escapeHtml = (str) => {
    return String(str || '').replace(/[&<>"']/g, (m) => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;',
    }[m]));
  };

  const highlightMatch = (text, query) => {
    if (!query) return escapeHtml(text);
    const escapedText = escapeHtml(text);
    const escapedQuery = escapeHtml(query);
    const regex = new RegExp(`(${escapedQuery.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
    return escapedText.replace(regex, '<span class="ide-search-item-match text-primary">$1</span>');
  };

  const renderSearchResults = (items, query) => {
    currentSearchResults = items;
    activeIndex = items.length > 0 ? 0 : -1;

    if (countEl) {
      const title = getTranslation('ui.ide.searchResults', 'Результаты поиска');
      countEl.textContent = `${title} (${items.length})`;
    }

    if (items.length === 0) {
      const noFoundText = getTranslation('ui.ide.noWorkspaceFilesFound', 'Файлы не найдены');
      listEl.innerHTML = `
        <div class="p-3 text-center text-muted font-size-80">
          <i class="bi bi-search text-secondary d-block fs-5 mb-1"></i>
          <div>${noFoundText}${query ? ` «${escapeHtml(query)}»` : ''}</div>
        </div>
      `;
      return;
    }

    listEl.innerHTML = items.map((item, idx) => {
      const iconData = getFileIconData(item.name, item.is_dir);
      const isDir = Boolean(item.is_dir);
      const relPath = item.rel_path || item.name;
      const sizeStr = item.size_formatted || (item.size_bytes ? `${Math.round(item.size_bytes / 1024)} KB` : '');
      const gitTag = item.tracked_by_git
        ? '<span class="badge bg-success-subtle text-success border border-success-subtle font-size-75 py-0 px-1">Git</span>'
        : '';
      const activeClass = idx === 0 ? 'active' : '';

      return `
        <button class="ide-search-item ${activeClass}" data-index="${idx}" data-rel-path="${escapeHtml(relPath)}" data-is-dir="${isDir}" type="button">
          <i class="bi ${iconData.icon} ${iconData.colorClass} fs-6 flex-shrink-0"></i>
          <div class="text-truncate flex-grow-1 text-start">
            <div class="fw-semibold text-truncate font-size-85">${highlightMatch(item.name, query)}</div>
            <div class="text-muted font-size-75 font-monospace text-truncate">${highlightMatch(relPath, query)}</div>
          </div>
          <div class="d-flex align-items-center gap-1.5 flex-shrink-0 ms-2 font-size-75 text-muted">
            ${gitTag}
            ${sizeStr ? `<span>${sizeStr}</span>` : ''}
          </div>
        </button>
      `;
    }).join('');

    // Привязка кликов к результатам
    listEl.querySelectorAll('.ide-search-item').forEach((btnEl) => {
      btnEl.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        const idx = parseInt(btnEl.dataset.index, 10);
        selectResult(idx);
      });
      btnEl.addEventListener('mouseenter', () => {
        const idx = parseInt(btnEl.dataset.index, 10);
        setActiveItem(idx);
      });
    });
  };

  const setActiveItem = (index) => {
    const buttons = listEl.querySelectorAll('.ide-search-item');
    if (buttons.length === 0) return;
    buttons.forEach((b) => b.classList.remove('active'));
    if (index >= 0 && index < buttons.length) {
      activeIndex = index;
      buttons[index].classList.add('active');
      buttons[index].scrollIntoView({ block: 'nearest' });
    }
  };

  const selectResult = async (index) => {
    const item = currentSearchResults[index];
    if (!item) return;

    closeDropdown();
    const wsId = getActiveWorkspaceId() || 'default';
    const relPath = item.rel_path || item.name;

    if (item.is_dir) {
      // Раскрываем директорию в проводнике
      expandedFolders.add(relPath);
      const treeContainer = document.getElementById('ide-file-tree-container');
      const curData = getCurrentFilesData();
      if (treeContainer && curData) {
        const root = buildTreeHierarchy(curData.items || []);
        treeContainer.innerHTML = renderTreeNode(root, 0);
        bindTreeEvents(treeContainer, wsId);
      }
      return;
    }

    // Если активна вкладка Rust+WASM
    if (typeof window.switchTab === 'function' && typeof window.isTabActive === 'function' && !window.isTabActive('tab-workspace') && !window.isTabActive('tab-file-editor')) {
      await window.switchTab('tab-workspace');
    }
    if (typeof window.switchWorkspaceSubTab === 'function') {
      window.switchWorkspaceSubTab('panel-file-editor', true);
    }
    if (typeof window.openFileInWasmEditor === 'function') {
      await window.openFileInWasmEditor(relPath, wsId, false);
      return;
    }
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
      openEditorModal({ isDir: false, relPath, name: item.name }, wsId);
    } else {
      try {
        await fetch(`/api/v1/workspaces/${encodeURIComponent(wsId)}/open-file`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ rel_path: relPath }),
        });
      } catch (_) {}
    }
  };

  const performSearch = async (query = '') => {
    const normQ = (query || '').trim().toLowerCase();
    if (clearBtn) {
      if (normQ) clearBtn.classList.remove('d-none');
      else clearBtn.classList.add('d-none');
    }

    const wsId = getActiveWorkspaceId() || 'default';
    let allItems = getCurrentFilesData()?.items;

    if (!allItems || allItems.length === 0) {
      try {
        const res = await fetch(`/api/v1/workspaces/${encodeURIComponent(wsId)}/directory-contents`);
        if (res.ok) {
          const data = await res.json();
          setCurrentFilesData(data);
          allItems = data.items || [];
        }
      } catch (_) {
        allItems = [];
      }
    }

    allItems = allItems || [];

    let filtered = allItems;
    if (normQ) {
      filtered = allItems.filter((it) => {
        const name = (it.name || '').toLowerCase();
        const rel = (it.rel_path || '').toLowerCase();
        return name.includes(normQ) || rel.includes(normQ);
      });

      // Ранжирование: сначала точные совпадения по имени, потом префиксы имени, затем по пути
      filtered.sort((a, b) => {
        const aName = (a.name || '').toLowerCase();
        const bName = (b.name || '').toLowerCase();
        const aExact = aName === normQ;
        const bExact = bName === normQ;
        if (aExact !== bExact) return aExact ? -1 : 1;

        const aStarts = aName.startsWith(normQ);
        const bStarts = bName.startsWith(normQ);
        if (aStarts !== bStarts) return aStarts ? -1 : 1;

        return aName.localeCompare(bName);
      });
    }

    // Ограничиваем список первыми 30 элементами
    renderSearchResults(filtered.slice(0, 30), normQ);
    openDropdown();
  };

  // События ввода
  searchInput.addEventListener('input', (e) => {
    performSearch(e.target.value);
  });

  searchInput.addEventListener('focus', () => {
    performSearch(searchInput.value);
  });

  // Навигация с клавиатуры
  searchInput.addEventListener('keydown', (e) => {
    if (dropdownEl.classList.contains('d-none')) {
      if (e.key === 'ArrowDown' || e.key === 'Enter') {
        performSearch(searchInput.value);
        e.preventDefault();
      }
      return;
    }

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      const nextIdx = activeIndex + 1 < currentSearchResults.length ? activeIndex + 1 : 0;
      setActiveItem(nextIdx);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      const prevIdx = activeIndex - 1 >= 0 ? activeIndex - 1 : currentSearchResults.length - 1;
      setActiveItem(prevIdx);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (activeIndex >= 0 && activeIndex < currentSearchResults.length) {
        selectResult(activeIndex);
      }
    } else if (e.key === 'Escape') {
      e.preventDefault();
      closeDropdown();
      searchInput.blur();
    }
  });

  // Кнопка очистки
  clearBtn?.addEventListener('click', () => {
    searchInput.value = '';
    clearBtn.classList.add('d-none');
    performSearch('');
    searchInput.focus();
  });

  // Закрытие при клике вне области
  document.addEventListener('click', (e) => {
    if (searchWrapper && !searchWrapper.contains(e.target)) {
      closeDropdown();
    }
  });

  // Глобальный хоткей Ctrl+P / Cmd+P
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && (e.key === 'p' || e.key === 'P' || e.key === 'з' || e.key === 'З')) {
      e.preventDefault();
      searchInput.focus();
      searchInput.select();
      performSearch(searchInput.value);
    }
  });

  // Обновление при смене рабочего пространства
  document.addEventListener('workspace:changed', () => {
    searchInput.value = '';
    closeDropdown();
  });
}
