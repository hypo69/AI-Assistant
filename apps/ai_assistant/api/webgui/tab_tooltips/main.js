/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Tooltips & i18n Editor Controller
 * =============================================================================
 * Description:
 *   Контроллер вкладки редактора всплывающих подсказок. Обеспечивает отображение
 *   каталога подсказок, фильтрацию, редактирование переводов на 4 языка (RU, EN,
 *   HE, UK), одноразовый перевод, предпросмотр и персистентное сохранение.
 *
 * File: main.js
 * Package: apps/ai_assistant/api/webgui/tab_tooltips
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-07 00:33:00
 * =============================================================================
 */

(function () {
  'use strict';

  let tooltipsData = [];
  let currentEditingItem = null;
  let previewLang = 'ru';

  const elements = {
    counterBadge: document.getElementById('tooltips-counter-badge'),
    statTotal: document.getElementById('tooltips-stat-total'),
    statComplete: document.getElementById('tooltips-stat-complete'),
    statMissing: document.getElementById('tooltips-stat-missing'),
    refreshBtn: document.getElementById('btn-tooltips-refresh'),
    searchInput: document.getElementById('tooltips-search-input'),
    filterCategory: document.getElementById('tooltips-filter-category'),
    filterStatus: document.getElementById('tooltips-filter-status'),
    tbody: document.getElementById('tooltips-tbody'),
    kbTbody: document.getElementById('tooltips-kb-tbody'),
    subtabsNav: document.getElementById('tooltips-subtabs-nav'),

    // Редактор
    fieldKey: document.getElementById('editor-field-key'),
    fieldIcon: document.getElementById('editor-field-icon'),
    fieldCategory: document.getElementById('editor-field-category'),
    titleRu: document.getElementById('editor-title-ru'),
    summaryRu: document.getElementById('editor-summary-ru'),
    titleEn: document.getElementById('editor-title-en'),
    summaryEn: document.getElementById('editor-summary-en'),
    titleHe: document.getElementById('editor-title-he'),
    summaryHe: document.getElementById('editor-summary-he'),
    titleUk: document.getElementById('editor-title-uk'),
    summaryUk: document.getElementById('editor-summary-uk'),
    btnSave: document.getElementById('btn-editor-save'),
    btnAutoTranslate: document.getElementById('btn-editor-auto-translate'),

    // Live Preview
    previewIcon: document.getElementById('preview-icon'),
    previewTitle: document.getElementById('preview-title'),
    previewBadge: document.getElementById('preview-badge'),
    previewBody: document.getElementById('preview-body'),
    previewLangSwitch: document.getElementById('preview-lang-switch')
  };

  /**
   * Загружает каталог подсказок с бэкенда.
   */
  async function loadTooltips() {
    try {
      if (elements.tbody) {
        elements.tbody.innerHTML = '<tr><td colspan="7" class="text-center py-4 text-muted">Загрузка подсказок...</td></tr>';
      }

      const res = await fetch('/api/v1/tooltips');
      if (!res.ok) throw new Error(`HTTP error ${res.status}`);
      const data = await res.json();

      tooltipsData = data.tooltips || [];
      const stats = data.stats || {};

      if (elements.counterBadge) elements.counterBadge.textContent = String(stats.total || tooltipsData.length);
      if (elements.statTotal) elements.statTotal.textContent = String(stats.total || tooltipsData.length);
      if (elements.statComplete) elements.statComplete.textContent = String(stats.complete || 0);
      if (elements.statMissing) elements.statMissing.textContent = String(stats.partial || 0);

      populateCategoriesFilter();
      renderCatalogTable();
      renderKbTable();

      // Если есть выбранная подсказка, обновляем ее
      if (currentEditingItem) {
        const updated = tooltipsData.find((x) => x.key === currentEditingItem.key);
        if (updated) openEditor(updated);
      } else if (tooltipsData.length > 0) {
        // По умолчанию открываем первую
        openEditor(tooltipsData[0]);
      }
    } catch (e) {
      console.error('[TooltipsTab] Ошибка загрузки данных:', e);
      if (elements.tbody) {
        elements.tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-danger">Ошибка загрузки: ${e.message}</td></tr>`;
      }
    }
  }

  /**
   * Заполняет выпадающий список категорий.
   */
  function populateCategoriesFilter() {
    if (!elements.filterCategory) return;
    const curVal = elements.filterCategory.value;
    const cats = new Set();
    tooltipsData.forEach((item) => {
      if (item.category) cats.add(item.category);
    });

    elements.filterCategory.innerHTML = '<option value="all">Все категории</option>';
    Array.from(cats).sort().forEach((cat) => {
      const opt = document.createElement('option');
      opt.value = cat;
      opt.textContent = cat;
      elements.filterCategory.appendChild(opt);
    });

    if (curVal && Array.from(cats).includes(curVal)) {
      elements.filterCategory.value = curVal;
    }
  }

  /**
   * Отрисовывает таблицу каталога с учетом поиска и фильтров.
   */
  function renderCatalogTable() {
    if (!elements.tbody) return;

    const query = (elements.searchInput ? elements.searchInput.value : '').toLowerCase().trim();
    const cat = elements.filterCategory ? elements.filterCategory.value : 'all';
    const statusFilter = elements.filterStatus ? elements.filterStatus.value : 'all';

    const filtered = tooltipsData.filter((item) => {
      if (cat !== 'all' && item.category !== cat) return false;
      if (statusFilter !== 'all' && item.status !== statusFilter) return false;

      if (!query) return true;
      const tRu = (item.titles.ru || '').toLowerCase();
      const tEn = (item.titles.en || '').toLowerCase();
      const sRu = (item.summaries.ru || '').toLowerCase();
      const key = item.key.toLowerCase();
      return key.includes(query) || tRu.includes(query) || tEn.includes(query) || sRu.includes(query);
    });

    if (filtered.length === 0) {
      elements.tbody.innerHTML = '<tr><td colspan="7" class="text-center py-4 text-muted">Ничего не найдено</td></tr>';
      return;
    }

    elements.tbody.innerHTML = filtered.map((item, idx) => {
      const titleRu = item.titles.ru || '<span class="text-danger small">—</span>';
      const titleEn = item.titles.en || '<span class="text-danger small">—</span>';
      const hasRu = Boolean(item.titles.ru);
      const hasEn = Boolean(item.titles.en);
      const hasHe = Boolean(item.titles.he);
      const hasUk = Boolean(item.titles.uk);

      const badgeRu = hasRu ? '<span class="badge bg-success-subtle text-success border me-0.5">RU</span>' : '<span class="badge bg-danger-subtle text-danger border me-0.5">RU</span>';
      const badgeEn = hasEn ? '<span class="badge bg-success-subtle text-success border me-0.5">EN</span>' : '<span class="badge bg-danger-subtle text-danger border me-0.5">EN</span>';
      const badgeHe = hasHe ? '<span class="badge bg-success-subtle text-success border me-0.5">HE</span>' : '<span class="badge bg-secondary-subtle text-secondary border me-0.5">HE</span>';
      const badgeUk = hasUk ? '<span class="badge bg-success-subtle text-success border">UK</span>' : '<span class="badge bg-secondary-subtle text-secondary border">UK</span>';

      return `
        <tr>
          <td class="text-center text-muted small">${idx + 1}</td>
          <td>
            <div class="d-flex align-items-center gap-1.5">
              <span>${item.icon || '💡'}</span>
              <span class="font-monospace small text-primary fw-semibold">${escapeHtml(item.key)}</span>
            </div>
          </td>
          <td><div class="small fw-semibold text-truncate" style="max-width: 240px;">${titleRu}</div></td>
          <td><div class="small text-truncate text-secondary" style="max-width: 240px;">${titleEn}</div></td>
          <td class="text-center">${badgeRu}${badgeEn}${badgeHe}${badgeUk}</td>
          <td><span class="badge bg-body-secondary text-body border small">${escapeHtml(item.category || 'Навигация')}</span></td>
          <td class="text-center">
            <button class="btn btn-xs btn-outline-primary btn-edit-item" data-key="${escapeHtml(item.key)}" title="Редактировать подсказку">
              <i class="bi bi-pencil"></i>
            </button>
          </td>
        </tr>
      `;
    }).join('');

    // Навешиваем слушатели на кнопки редактирования
    elements.tbody.querySelectorAll('.btn-edit-item').forEach((btn) => {
      btn.addEventListener('click', () => {
        const k = btn.getAttribute('data-key');
        const item = tooltipsData.find((x) => x.key === k);
        if (item) {
          openEditor(item);
          switchToSubtab('panel-editor');
        }
      });
    });
  }

  /**
   * Отрисовывает таблицу базы знаний WikiLLM.
   */
  function renderKbTable() {
    if (!elements.kbTbody) return;
    const kbItems = tooltipsData.filter((x) => x.source === 'kb');

    if (kbItems.length === 0) {
      elements.kbTbody.innerHTML = '<tr><td colspan="6" class="text-center py-4 text-muted">Термины базы знаний отсутствуют</td></tr>';
      return;
    }

    elements.kbTbody.innerHTML = kbItems.map((item, idx) => {
      return `
        <tr>
          <td class="text-center text-muted small">${idx + 1}</td>
          <td class="font-monospace small text-primary fw-semibold">${escapeHtml(item.key)}</td>
          <td class="small fw-semibold">${escapeHtml(item.titles.ru || item.key)}</td>
          <td class="small text-secondary">${escapeHtml(item.summaries.ru || '—')}</td>
          <td><span class="badge bg-body-secondary text-body border small">${escapeHtml(item.category || 'WikiLLM')}</span></td>
          <td class="text-center">
            <button class="btn btn-xs btn-outline-primary btn-edit-item" data-key="${escapeHtml(item.key)}" title="Редактировать">
              <i class="bi bi-pencil"></i>
            </button>
          </td>
        </tr>
      `;
    }).join('');

    elements.kbTbody.querySelectorAll('.btn-edit-item').forEach((btn) => {
      btn.addEventListener('click', () => {
        const k = btn.getAttribute('data-key');
        const item = tooltipsData.find((x) => x.key === k);
        if (item) {
          openEditor(item);
          switchToSubtab('panel-editor');
        }
      });
    });
  }

  /**
   * Открывает подсказку в форме редактирования.
   */
  function openEditor(item) {
    if (!item) return;
    currentEditingItem = item;

    if (elements.fieldKey) elements.fieldKey.value = item.key;
    if (elements.fieldIcon) elements.fieldIcon.value = item.icon || '💡';
    if (elements.fieldCategory) elements.fieldCategory.value = item.category || 'Навигация';

    if (elements.titleRu) elements.titleRu.value = item.titles.ru || '';
    if (elements.summaryRu) elements.summaryRu.value = item.summaries.ru || '';

    if (elements.titleEn) elements.titleEn.value = item.titles.en || '';
    if (elements.summaryEn) elements.summaryEn.value = item.summaries.en || '';

    if (elements.titleHe) elements.titleHe.value = item.titles.he || '';
    if (elements.summaryHe) elements.summaryHe.value = item.summaries.he || '';

    if (elements.titleUk) elements.titleUk.value = item.titles.uk || '';
    if (elements.summaryUk) elements.summaryUk.value = item.summaries.uk || '';

    updateLivePreview();
  }

  /**
   * Обновляет карточку Live Preview в реальном времени.
   */
  function updateLivePreview() {
    const icon = elements.fieldIcon ? elements.fieldIcon.value : '💡';
    const category = elements.fieldCategory ? elements.fieldCategory.value : 'WikiLLM';

    let title = '';
    let summary = '';

    if (previewLang === 'en') {
      title = (elements.titleEn && elements.titleEn.value) || (elements.titleRu && elements.titleRu.value) || 'Tooltip Title';
      summary = (elements.summaryEn && elements.summaryEn.value) || (elements.summaryRu && elements.summaryRu.value) || 'Description in English';
    } else if (previewLang === 'he') {
      title = (elements.titleHe && elements.titleHe.value) || (elements.titleRu && elements.titleRu.value) || 'כותרת רמז';
      summary = (elements.summaryHe && elements.summaryHe.value) || (elements.summaryRu && elements.summaryRu.value) || 'תיאור בעברית';
    } else if (previewLang === 'uk') {
      title = (elements.titleUk && elements.titleUk.value) || (elements.titleRu && elements.titleRu.value) || 'Заголовок підказки';
      summary = (elements.summaryUk && elements.summaryUk.value) || (elements.summaryRu && elements.summaryRu.value) || 'Опис українською мовою';
    } else {
      title = (elements.titleRu && elements.titleRu.value) || 'Заголовок подсказки';
      summary = (elements.summaryRu && elements.summaryRu.value) || 'Готовое контекстное пояснение на русском языке.';
    }

    if (elements.previewIcon) elements.previewIcon.textContent = icon;
    if (elements.previewTitle) elements.previewTitle.textContent = title;
    if (elements.previewBadge) elements.previewBadge.textContent = category;
    if (elements.previewBody) elements.previewBody.textContent = summary;
  }

  /**
   * Сохраняет изменения текущей подсказки на сервер.
   */
  async function saveCurrentTooltip() {
    if (!currentEditingItem) return;
    const key = currentEditingItem.key;

    const payload = {
      category: elements.fieldCategory ? elements.fieldCategory.value.trim() : 'Навигация',
      icon: elements.fieldIcon ? elements.fieldIcon.value.trim() : '💡',
      titles: {
        ru: elements.titleRu ? elements.titleRu.value.trim() : '',
        en: elements.titleEn ? elements.titleEn.value.trim() : '',
        he: elements.titleHe ? elements.titleHe.value.trim() : '',
        uk: elements.titleUk ? elements.titleUk.value.trim() : ''
      },
      summaries: {
        ru: elements.summaryRu ? elements.summaryRu.value.trim() : '',
        en: elements.summaryEn ? elements.summaryEn.value.trim() : '',
        he: elements.summaryHe ? elements.summaryHe.value.trim() : '',
        uk: elements.summaryUk ? elements.summaryUk.value.trim() : ''
      }
    };

    try {
      if (elements.btnSave) elements.btnSave.disabled = true;

      const res = await fetch(`/api/v1/tooltips/${encodeURIComponent(key)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!res.ok) throw new Error(`HTTP error ${res.status}`);

      if (window.showToast) {
        window.showToast('Подсказка успешно сохранена!', 'success');
      }

      await loadTooltips();
    } catch (e) {
      console.error('[TooltipsTab] Ошибка сохранения:', e);
      if (window.showToast) {
        window.showToast(`Ошибка сохранения: ${e.message}`, 'danger');
      }
    } finally {
      if (elements.btnSave) elements.btnSave.disabled = false;
    }
  }

  /**
   * Одноразовый автоперевод с RU на EN, HE, UK.
   */
  async function autoTranslateCurrent() {
    const srcTitle = elements.titleRu ? elements.titleRu.value.trim() : '';
    const srcSummary = elements.summaryRu ? elements.summaryRu.value.trim() : '';

    if (!srcTitle && !srcSummary) {
      if (window.showToast) window.showToast('Заполните заголовок или описание на русском языке!', 'warning');
      return;
    }

    try {
      if (elements.btnAutoTranslate) elements.btnAutoTranslate.disabled = true;

      if (srcTitle) {
        const resTitle = await fetch('/api/v1/tooltips/translate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: srcTitle, source_lang: 'ru', target_langs: ['en', 'he', 'uk'] })
        });
        if (resTitle.ok) {
          const dataT = await resTitle.json();
          const trs = dataT.translations || {};
          if (elements.titleEn && trs.en && !elements.titleEn.value) elements.titleEn.value = trs.en;
          if (elements.titleHe && trs.he && !elements.titleHe.value) elements.titleHe.value = trs.he;
          if (elements.titleUk && trs.uk && !elements.titleUk.value) elements.titleUk.value = trs.uk;
        }
      }

      if (srcSummary) {
        const resSum = await fetch('/api/v1/tooltips/translate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: srcSummary, source_lang: 'ru', target_langs: ['en', 'he', 'uk'] })
        });
        if (resSum.ok) {
          const dataS = await resSum.json();
          const trsS = dataS.translations || {};
          if (elements.summaryEn && trsS.en && !elements.summaryEn.value) elements.summaryEn.value = trsS.en;
          if (elements.summaryHe && trsS.he && !elements.summaryHe.value) elements.summaryHe.value = trsS.he;
          if (elements.summaryUk && trsS.uk && !elements.summaryUk.value) elements.summaryUk.value = trsS.uk;
        }
      }

      updateLivePreview();
      if (window.showToast) window.showToast('Одноразовый перевод успешно выполнен!', 'success');
    } catch (e) {
      console.error('[TooltipsTab] Ошибка автоперевода:', e);
    } finally {
      if (elements.btnAutoTranslate) elements.btnAutoTranslate.disabled = false;
    }
  }

  /**
   * Переключает субпанель с синхронизацией URL.
   */
  function switchToSubtab(panelId) {
    if (!elements.subtabsNav) return;
    const btn = elements.subtabsNav.querySelector(`[data-panel-id="${panelId}"]`);
    if (btn) {
      if (window.bootstrap && window.bootstrap.Tab) {
        const tab = new window.bootstrap.Tab(btn);
        tab.show();
      } else {
        btn.click();
      }
    }
    // Обновляем хэш URL
    try {
      const curHash = window.location.hash || '';
      const baseTab = curHash.split('#')[1] || 'tab-tooltips';
      history.replaceState(null, '', `#${baseTab}#${panelId}`);
    } catch (_) {}
  }

  function escapeHtml(str) {
    return String(str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function initEvents() {
    if (elements.refreshBtn) {
      elements.refreshBtn.addEventListener('click', loadTooltips);
    }

    if (elements.searchInput) {
      elements.searchInput.addEventListener('input', renderCatalogTable);
    }

    if (elements.filterCategory) {
      elements.filterCategory.addEventListener('change', renderCatalogTable);
    }

    if (elements.filterStatus) {
      elements.filterStatus.addEventListener('change', renderCatalogTable);
    }

    if (elements.btnSave) {
      elements.btnSave.addEventListener('click', saveCurrentTooltip);
    }

    if (elements.btnAutoTranslate) {
      elements.btnAutoTranslate.addEventListener('click', autoTranslateCurrent);
    }

    // Слушатели для живого обновления предпросмотра
    [
      elements.fieldIcon, elements.fieldCategory,
      elements.titleRu, elements.summaryRu,
      elements.titleEn, elements.summaryEn,
      elements.titleHe, elements.summaryHe,
      elements.titleUk, elements.summaryUk
    ].forEach((input) => {
      if (input) input.addEventListener('input', updateLivePreview);
    });

    // Переключатель языка предпросмотра
    if (elements.previewLangSwitch) {
      elements.previewLangSwitch.querySelectorAll('.btn-preview-lang').forEach((btn) => {
        btn.addEventListener('click', () => {
          elements.previewLangSwitch.querySelectorAll('.btn-preview-lang').forEach((b) => b.classList.remove('active'));
          btn.classList.add('active');
          previewLang = btn.getAttribute('data-lang') || 'ru';
          updateLivePreview();
        });
      });
    }

    // Обработка переключения субвкладок
    if (elements.subtabsNav) {
      elements.subtabsNav.querySelectorAll('button[data-panel-id]').forEach((btn) => {
        btn.addEventListener('shown.bs.tab', (e) => {
          const panelId = btn.getAttribute('data-panel-id');
          try {
            history.replaceState(null, '', `#tab-tooltips#${panelId}`);
          } catch (_) {}
        });
      });
    }
  }

  // Инициализация при монтировании вкладки
  initEvents();
  loadTooltips();

  // Маршрутизация из URL хэша
  try {
    const hash = window.location.hash || '';
    if (hash.includes('#panel-')) {
      const match = hash.match(/#(panel-[a-zA-Z0-9_\-]+)/);
      if (match && match[1]) {
        switchToSubtab(match[1]);
      }
    }
  } catch (_) {}
})();
