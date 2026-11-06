/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Document Categorizer Controller
 * =============================================================================
 * Description:
 *   Клиентский контроллер управления умной категоризацией документов:
 *   статус сканирования, карточки категорий, интерактивная очередь вопросов
 *   Human-in-the-Loop, семантический RAG-поиск и таблица документов.
 *
 * File: main.js
 * Package: apps/ai_assistant/api/webgui/tab_doc_categorizer
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-03 11:46:00
 * =============================================================================
 */

import { registerTabPoller, unregisterTabPoller, isTabActive } from '../js/tab-core.js';

(function () {
  'use strict';

  let currentCategoryFilter = '';
  let currentStatusFilter = '';
  let searchQuery = '';
  let pollerId = null;

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function formatBytes(bytes) {
    if (!bytes || isNaN(bytes)) return '-';
    const num = parseInt(bytes, 10);
    if (num < 1024) return num + ' B';
    if (num < 1024 * 1024) return (num / 1024).toFixed(1) + ' KB';
    return (num / (1024 * 1024)).toFixed(1) + ' MB';
  }

  function formatDate(isoStr) {
    if (!isoStr) return '-';
    try {
      const d = new Date(isoStr);
      return d.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return isoStr;
    }
  }

  async function fetchStatus() {
    try {
      const res = await fetch('/api/v1/documents/status');
      if (!res.ok) return;
      const data = await res.json();
      renderStatus(data);
    } catch (err) {
      console.warn('[DocCategorizer] Ошибка опроса статуса:', err);
    }
  }

  function renderStatus(data) {
    const totalEl = document.getElementById('doc-stat-total-val');
    const classEl = document.getElementById('doc-stat-classified-val');
    const uncertEl = document.getElementById('doc-stat-uncertain-val');
    const uncertBadge = document.getElementById('doc-cat-uncertain-badge');
    const progressAlert = document.getElementById('doc-scan-progress-alert');
    const scanBadge = document.getElementById('doc-scan-count-badge');
    const scanFile = document.getElementById('doc-scan-current-file');

    if (totalEl) totalEl.textContent = data.total_documents || 0;
    if (classEl) classEl.textContent = data.classified_count || 0;
    if (uncertEl) uncertEl.textContent = data.uncertain_count || 0;

    if (uncertBadge) {
      const uCount = data.uncertain_count || 0;
      if (uCount > 0) {
        uncertBadge.textContent = uCount;
        uncertBadge.classList.remove('d-none');
      } else {
        uncertBadge.classList.add('d-none');
      }
    }

    if (progressAlert) {
      if (data.is_scanning) {
        progressAlert.classList.remove('d-none');
        progressAlert.classList.add('d-flex');
        if (scanBadge) scanBadge.textContent = `${data.scan_stats?.processed || 0} обработано`;
        if (scanFile) scanFile.textContent = data.scan_stats?.current_file || '';
      } else {
        progressAlert.classList.add('d-none');
        progressAlert.classList.remove('d-flex');
      }
    }

    renderCategoryChips(data.categories || {}, data.default_categories || {});
  }

  function renderCategoryChips(counts, defaultCategories) {
    const container = document.getElementById('doc-categories-chips');
    if (!container) return;

    let html = `
      <div class="col-6 col-sm-4 col-md-3 col-xl-2">
        <div class="card p-2 text-center cursor-pointer border ${currentCategoryFilter === '' ? 'border-primary bg-primary-subtle' : 'bg-body'}" data-category="">
          <div class="fw-semibold small">Все категории</div>
          <div class="small text-muted font-monospace">${Object.values(counts).reduce((a, b) => a + b, 0)}</div>
        </div>
      </div>
    `;

    for (const [key, meta] of Object.entries(defaultCategories)) {
      const cnt = counts[key] || 0;
      const isSelected = currentCategoryFilter === key;
      html += `
        <div class="col-6 col-sm-4 col-md-3 col-xl-2">
          <div class="card p-2 text-center cursor-pointer border ${isSelected ? 'border-primary bg-primary-subtle' : 'bg-body'}" data-category="${key}">
            <div class="d-flex align-items-center justify-content-center gap-1.5 fw-semibold small">
              <i class="bi ${meta.icon} text-${meta.color}"></i>
              <span class="text-truncate">${escapeHtml(meta.title)}</span>
            </div>
            <div class="small text-muted font-monospace">${cnt}</div>
          </div>
        </div>
      `;
    }

    container.innerHTML = html;

    container.querySelectorAll('[data-category]').forEach(card => {
      card.addEventListener('click', () => {
        currentCategoryFilter = card.getAttribute('data-category');
        renderCategoryChips(counts, defaultCategories);
        loadDocumentsList();
      });
    });
  }

  async function loadDocumentsList() {
    const tbody = document.getElementById('doc-items-tbody');
    if (!tbody) return;

    try {
      const params = new URLSearchParams();
      if (currentCategoryFilter) params.append('category', currentCategoryFilter);
      if (currentStatusFilter) params.append('status', currentStatusFilter);
      if (searchQuery) params.append('query', searchQuery);
      params.append('limit', '50');

      const res = await fetch(`/api/v1/documents/items?${params.toString()}`);
      if (!res.ok) return;
      const data = await res.json();

      if (!data.items || data.items.length === 0) {
        tbody.innerHTML = `
          <tr>
            <td class="text-center py-4 text-muted" colspan="5">
              <i class="bi bi-inbox fs-2 d-block mb-1"></i>
              Документы не найдены
            </td>
          </tr>
        `;
        return;
      }

      tbody.innerHTML = data.items.map(doc => {
        const confPct = Math.round((doc.confidence || 0) * 100);
        const statusBadge = doc.status === 'classified'
          ? `<span class="badge bg-success-subtle text-success border border-success-subtle">Готов (${confPct}%)</span>`
          : `<span class="badge bg-warning-subtle text-warning border border-warning-subtle">Вопрос (${confPct}%)</span>`;

        return `
          <tr>
            <td>
              <div class="d-flex align-items-center gap-2">
                <i class="bi bi-file-earmark-text text-primary fs-5"></i>
                <div class="text-truncate">
                  <div class="fw-semibold text-truncate" title="${escapeHtml(doc.file_name)}">${escapeHtml(doc.file_name)}</div>
                  <div class="small text-muted text-truncate font-monospace" title="${escapeHtml(doc.file_path)}">${escapeHtml(doc.file_path)}</div>
                </div>
              </div>
            </td>
            <td><span class="badge bg-body-secondary text-body border">${escapeHtml(doc.category || 'Не определено')}</span></td>
            <td>${statusBadge}</td>
            <td class="font-monospace small">${formatBytes(doc.file_size)}</td>
            <td class="text-muted small">${formatDate(doc.modified_at)}</td>
          </tr>
        `;
      }).join('');

    } catch (err) {
      console.warn('[DocCategorizer] Ошибка загрузки документов:', err);
    }
  }

  async function loadUncertainQueue() {
    const container = document.getElementById('doc-uncertain-cards-container');
    const badge = document.getElementById('doc-uncertain-queue-count');
    if (!container) return;

    try {
      const res = await fetch('/api/v1/documents/uncertain?limit=20');
      if (!res.ok) return;
      const items = await res.json();

      if (badge) badge.textContent = `${items.length} ожидают`;

      if (!items || items.length === 0) {
        container.innerHTML = `
          <div class="text-center py-5 text-muted">
            <i class="bi bi-check2-all fs-1 text-success d-block mb-2"></i>
            <div class="fw-semibold">Все документы успешно категоризированы!</div>
            <div class="small text-muted">Спорных файлов, требующих уточнения, сейчас нет.</div>
          </div>
        `;
        return;
      }

      container.innerHTML = items.map(doc => {
        const confPct = Math.round((doc.confidence || 0) * 100);
        const dirName = doc.file_path.split(/[\\/]/).slice(-2, -1)[0] || '';

        return `
          <div class="card border mb-3 shadow-xs" data-doc-id="${doc.id}">
            <div class="card-body p-3">
              <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-2">
                <div class="d-flex align-items-center gap-2">
                  <span class="fs-4">❓</span>
                  <div>
                    <div class="fw-bold text-body">${escapeHtml(doc.file_name)}</div>
                    <div class="small text-muted font-monospace text-truncate max-width-600">${escapeHtml(doc.file_path)}</div>
                  </div>
                </div>
                <div class="d-flex align-items-center gap-2">
                  <span class="badge bg-warning-subtle text-warning border border-warning-subtle">Уверенность: ${confPct}%</span>
                </div>
              </div>

              <div class="bg-body-tertiary p-2 rounded small text-muted font-monospace mb-3 border">
                ${escapeHtml(doc.content_preview || 'Нет доступного текстового фрагмента')}
              </div>

              <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 pt-2 border-top">
                <div class="d-flex flex-wrap align-items-center gap-1.5">
                  <span class="small text-muted me-1">Выберите категорию:</span>
                  <button class="btn btn-sm btn-outline-primary btn-resolve" data-cat="finance">Финансы</button>
                  <button class="btn btn-sm btn-outline-info btn-resolve" data-cat="legal">Договоры</button>
                  <button class="btn btn-sm btn-outline-success btn-resolve" data-cat="personal">Личные</button>
                  <button class="btn btn-sm btn-outline-warning btn-resolve" data-cat="work">Работа</button>
                  <button class="btn btn-sm btn-outline-secondary btn-resolve" data-cat="archive">Архив</button>
                </div>
                <div class="form-check form-switch small">
                  <input class="form-check-input rule-toggle" type="checkbox" id="rule-${doc.id}" checked>
                  <label class="form-check-label text-muted" for="rule-${doc.id}">
                    Обучить: применять к папке "${escapeHtml(dirName)}"
                  </label>
                </div>
              </div>
            </div>
          </div>
        `;
      }).join('');

      container.querySelectorAll('.card[data-doc-id]').forEach(card => {
        const docId = card.getAttribute('data-doc-id');
        const dirToggle = card.querySelector('.rule-toggle');
        const pathText = card.querySelector('.font-monospace')?.textContent || '';
        const dirName = pathText.split(/[\\/]/).slice(-2, -1)[0] || '';

        card.querySelectorAll('.btn-resolve').forEach(btn => {
          btn.addEventListener('click', async () => {
            const cat = btn.getAttribute('data-cat');
            const shouldRule = dirToggle?.checked && dirName;
            await resolveDoc(docId, cat, shouldRule, dirName);
            card.remove();
            fetchStatus();
            loadDocumentsList();
          });
        });
      });

    } catch (err) {
      console.warn('[DocCategorizer] Ошибка загрузки очереди:', err);
    }
  }

  async function resolveDoc(docId, category, createRule, pattern) {
    try {
      await fetch('/api/v1/documents/resolve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          doc_id: docId,
          category: category,
          create_rule: Boolean(createRule),
          rule_pattern: pattern || null
        })
      });
    } catch (err) {
      console.warn('[DocCategorizer] Ошибка подтверждения категории:', err);
    }
  }

  async function executeRagSearch() {
    const input = document.getElementById('doc-rag-query-input');
    const resultsCard = document.getElementById('doc-rag-results-card');
    const hitsContainer = document.getElementById('doc-rag-hits-container');
    const badge = document.getElementById('doc-rag-hits-count');
    if (!input || !resultsCard || !hitsContainer) return;

    const query = input.value.trim();
    if (!query) return;

    try {
      const res = await fetch('/api/v1/documents/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: query, limit: 15 })
      });
      if (!res.ok) return;
      const data = await res.json();

      resultsCard.classList.remove('d-none');
      if (badge) badge.textContent = `${data.total || 0} источников найдено`;

      if (!data.hits || data.hits.length === 0) {
        hitsContainer.innerHTML = '<div class="text-muted small py-3 text-center">Ничего не найдено по вашему запросу.</div>';
        return;
      }

      hitsContainer.innerHTML = data.hits.map(hit => `
        <div class="p-2.5 rounded border bg-body-tertiary">
          <div class="d-flex align-items-center justify-content-between gap-2 mb-1">
            <div class="fw-semibold small d-flex align-items-center gap-1.5">
              <i class="bi bi-file-earmark-text text-primary"></i>
              <span>${escapeHtml(hit.file_name)}</span>
            </div>
            <span class="badge bg-secondary-subtle text-body border">${escapeHtml(hit.category || 'Без категории')}</span>
          </div>
          <div class="small font-monospace text-muted text-truncate mb-2">${escapeHtml(hit.file_path)}</div>
          <div class="p-2 bg-body rounded border small font-size-88">
            ${hit.match_snippet ? hit.match_snippet : escapeHtml(hit.content_preview)}
          </div>
        </div>
      `).join('');

    } catch (err) {
      console.warn('[DocCategorizer] Ошибка RAG-поиска:', err);
    }
  }

  function setupEventHandlers() {
    const btnAutoScan = document.getElementById('btn-doc-scan-auto');
    const btnCustomScan = document.getElementById('btn-doc-scan-folder');
    const btnRefresh = document.getElementById('btn-doc-refresh');
    const btnStartCustom = document.getElementById('btn-start-custom-scan');
    const tableFilter = document.getElementById('doc-table-filter-input');
    const statusFilter = document.getElementById('doc-filter-status-select');
    const btnRagSearch = document.getElementById('btn-doc-rag-search');
    const ragInput = document.getElementById('doc-rag-query-input');

    if (btnAutoScan) {
      btnAutoScan.addEventListener('click', async () => {
        await fetch('/api/v1/documents/scan', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ mode: 'auto' })
        });
        fetchStatus();
      });
    }

    if (btnCustomScan) {
      btnCustomScan.addEventListener('click', () => {
        const modalEl = document.getElementById('modal-doc-custom-scan');
        if (modalEl && window.bootstrap) {
          const m = new window.bootstrap.Modal(modalEl);
          m.show();
        }
      });
    }

    if (btnStartCustom) {
      btnStartCustom.addEventListener('click', async () => {
        const pathInput = document.getElementById('input-custom-scan-path');
        const customPath = pathInput ? pathInput.value.trim() : '';
        if (!customPath) return;

        await fetch('/api/v1/documents/scan', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ mode: 'explicit', custom_path: customPath })
        });

        const modalEl = document.getElementById('modal-doc-custom-scan');
        if (modalEl && window.bootstrap) {
          const m = window.bootstrap.Modal.getInstance(modalEl);
          if (m) m.hide();
        }
        fetchStatus();
      });
    }

    if (btnRefresh) {
      btnRefresh.addEventListener('click', () => {
        fetchStatus();
        loadDocumentsList();
        loadUncertainQueue();
      });
    }

    if (tableFilter) {
      tableFilter.addEventListener('input', (e) => {
        searchQuery = e.target.value.trim();
        loadDocumentsList();
      });
    }

    if (statusFilter) {
      statusFilter.addEventListener('change', (e) => {
        currentStatusFilter = e.target.value;
        loadDocumentsList();
      });
    }

    if (btnRagSearch) {
      btnRagSearch.addEventListener('click', executeRagSearch);
    }

    if (ragInput) {
      ragInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') executeRagSearch();
      });
    }

    // Слушатели смены суб-вкладок
    const subtabUncertain = document.getElementById('btn-subtab-uncertain');
    if (subtabUncertain) {
      subtabUncertain.addEventListener('shown.bs.tab', loadUncertainQueue);
    }
  }

  window.initDocCategorizerTab = function () {
    setupEventHandlers();
    fetchStatus();
    loadDocumentsList();

    // Регистрация поллера активной вкладки
    pollerId = registerTabPoller('tab-doc-categorizer', async () => {
      await fetchStatus();
    }, 4000, { immediate: true });
  };

  window.deactivateDocCategorizerTab = function () {
    if (pollerId) {
      unregisterTabPoller(pollerId);
      pollerId = null;
    }
  };
})();

/**
 * Автоматическая синхронизация активной панели вкладки с URL-хэшем.
 */
export function initTabUrlHashRouting() {
  const canonicalTabId = 'tab-doc_categorizer';
  const syncFromHash = () => {
    const raw = window.location.hash || '';
    if (!raw.includes(canonicalTabId)) return;
    const parts = raw.replace(/^#/, '').split('#');
    const panelPart = parts.find((p) => p.startsWith('panel-'));
    if (panelPart) {
      const btn = document.querySelector(`button[data-panel-id="${panelPart}"]`) ||
                  document.querySelector(`button[data-bs-target="#${panelPart}"]`);
      if (btn && window.bootstrap && window.bootstrap.Tab) {
        (window.bootstrap.Tab.getInstance?.(btn) || window.bootstrap.Tab.getOrCreateInstance?.(btn) || new window.bootstrap.Tab(btn)).show();
      }
    }
  };

  document.addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-panel-id], button[data-bs-toggle="pill"]');
    if (btn) {
      const panelId = btn.getAttribute('data-panel-id') || btn.getAttribute('data-bs-target')?.replace('#', '');
      const blockId = btn.getAttribute('data-block-id');
      if (panelId) {
        let hash = `#${canonicalTabId}#${panelId}`;
        if (blockId) hash += `#${blockId}`;
        history.replaceState(null, null, hash);
      }
    }
  });

  window.addEventListener('hashchange', syncFromHash);
  syncFromHash();
}

if (typeof window !== 'undefined') {
  window.initTabUrlHashRouting = initTabUrlHashRouting;
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initTabUrlHashRouting);
  } else {
    initTabUrlHashRouting();
  }
}
