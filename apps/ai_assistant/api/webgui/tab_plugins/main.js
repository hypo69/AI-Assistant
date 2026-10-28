/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Plugins Tab & Marketplace Controller
 * =============================================================================
 * Description:
 *   Клиентский модуль управления вкладкой модульных плагинов и маркетплейса IDE.
 *   Обеспечивает загрузку каталога, установку стандартных плагинов в стиле VS Code,
 *   переключение флагов активности, вызов действий (Actions) и удаление плагинов.
 *
 * File: main.js
 * Package: apps/ai_assistant/api/webgui/tab_plugins
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-25 22:30:00
 * =============================================================================
 */

let allPlugins = [];
let marketplacePlugins = [];
let currentScopeFilter = 'all';
let currentSearchQuery = '';
let currentMarketplaceQuery = '';
let activeConfigPlugin = null;

function notify(message, type = 'info') {
  if (typeof window.showToast === 'function') {
    window.showToast(message, type);
  } else {
    console.log(`[Plugins] [${type}] ${message}`);
  }
}

/**
 * Инициализирует вкладку плагинов и маркетплейса.
 */
export async function initPluginsTab() {
  setupFilterHandlers();
  setupSearchHandlers();
  setupMarketplaceSearchHandlers();
  setupReloadHandler();
  setupConfigModalHandlers();
  await Promise.all([
    loadPluginsCatalog(),
    loadMarketplaceCatalog(),
  ]);
}
window.initPluginsTab = initPluginsTab;

/**
 * Загружает список установленных плагинов с сервера.
 */
async function loadPluginsCatalog() {
  const grid = document.getElementById('plugins-cards-grid');
  if (!grid) return;

  grid.innerHTML = `
    <div class="col-12 text-center py-5 text-secondary">
      <div class="spinner-border spinner-border-sm text-primary mb-2" role="status"></div>
      <div class="small">Загрузка каталога плагинов...</div>
    </div>
  `;

  try {
    const res = await fetch('/api/v1/plugins?lang=ru');
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    allPlugins = await res.json();
    renderPlugins();
  } catch (err) {
    console.error('[PluginsTab] Ошибка загрузки плагинов:', err);
    grid.innerHTML = `
      <div class="col-12">
        <div class="alert alert-danger py-3 px-3 d-flex align-items-center justify-content-between flex-wrap gap-2">
          <div class="d-flex align-items-center gap-2">
            <i class="bi bi-exclamation-triangle-fill fs-5"></i>
            <span>Не удалось загрузить плагины: ${err.message}</span>
          </div>
          <button class="btn btn-sm btn-outline-danger" id="btn-retry-plugins-load">
            <i class="bi bi-arrow-clockwise me-1"></i>Повторить
          </button>
        </div>
      </div>
    `;
    document.getElementById('btn-retry-plugins-load')?.addEventListener('click', loadPluginsCatalog);
  }
}

/**
 * Загружает каталог стандартных расширений из маркетплейса.
 */
async function loadMarketplaceCatalog() {
  const grid = document.getElementById('marketplace-cards-grid');
  const badge = document.getElementById('marketplace-available-badge');
  if (!grid) return;

  try {
    const res = await fetch('/api/v1/plugins/marketplace');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    marketplacePlugins = await res.json();
    if (badge) {
      const uninstalledCount = marketplacePlugins.filter(p => !p.installed).length;
      badge.textContent = uninstalledCount;
    }
    renderMarketplace();
  } catch (err) {
    console.error('[PluginsTab] Ошибка загрузки маркетплейса:', err);
    grid.innerHTML = `
      <div class="col-12 text-center py-4 text-danger small">
        <i class="bi bi-exclamation-triangle fs-4 mb-2 d-block"></i>
        <span>Не удалось загрузить маркетплейс расширений</span>
      </div>
    `;
  }
}

/**
 * Отрисовывает карточки плагинов с учетом активных фильтров.
 */
function renderPlugins() {
  const grid = document.getElementById('plugins-cards-grid');
  const countBadge = document.getElementById('plugins-total-count-badge');
  if (!grid) return;

  let filtered = allPlugins.filter(p => {
    if (currentScopeFilter !== 'all') {
      const scope = (p.scope || 'user').toLowerCase();
      if (scope !== currentScopeFilter) return false;
    }
    if (currentSearchQuery) {
      const q = currentSearchQuery.toLowerCase();
      const matchName = (p.name || '').toLowerCase().includes(q);
      const matchTitle = (p.title || '').toLowerCase().includes(q);
      const matchDesc = (p.description || '').toLowerCase().includes(q);
      return matchName || matchTitle || matchDesc;
    }
    return true;
  });

  if (countBadge) {
    countBadge.textContent = `${allPlugins.length} ${allPlugins.length === 1 ? 'плагин' : 'плагинов'}`;
  }

  if (filtered.length === 0) {
    grid.innerHTML = `
      <div class="col-12 text-center py-5 text-secondary">
        <div class="fs-1 mb-2">🔍</div>
        <h6>Плагины не найдены</h6>
        <p class="small text-muted mb-0">Попробуйте изменить параметры поиска или фильтра по области видимости.</p>
      </div>
    `;
    return;
  }

  grid.innerHTML = filtered.map(p => renderPluginCard(p)).join('');
  attachCardEventListeners();
}

/**
 * Отрисовывает HTML для отдельной карточки плагина.
 */
function renderPluginCard(p) {
  const isEnabled = p.enabled !== false;
  const scope = (p.scope || 'user').toLowerCase();
  let scopeBadgeClass = 'bg-secondary-subtle text-secondary';
  let scopeLabel = 'Пользовательский';

  if (scope === 'system') {
    scopeBadgeClass = 'bg-danger-subtle text-danger';
    scopeLabel = 'Системный';
  } else if (scope === 'developer') {
    scopeBadgeClass = 'bg-info-subtle text-info';
    scopeLabel = 'Для разработчиков';
  }

  const actions = Array.isArray(p.actions) ? p.actions : [];
  const tools = Array.isArray(p.tools) ? p.tools : [];
  const fields = Array.isArray(p.fields) ? p.fields : [];
  const hasConfig = fields.length > 0 || (p.config && Object.keys(p.config).length > 0);

  return `
    <div class="col-md-6 col-xl-4">
      <div class="card shadow-sm border h-100 plugin-card d-flex flex-column ${!isEnabled ? 'opacity-75' : ''}" data-plugin-name="${p.name}">
        <!-- Шапка карточки -->
        <div class="card-header bg-transparent border-bottom p-3 d-flex align-items-center justify-content-between gap-2">
          <div class="d-flex align-items-center gap-2 overflow-hidden">
            <span class="fs-4 flex-shrink-0">${p.icon || '🧩'}</span>
            <div class="text-truncate">
              <h6 class="mb-0 fw-bold text-truncate" title="${p.title || p.name}">${p.title || p.name}</h6>
              <div class="d-flex align-items-center gap-1.5 mt-0.5">
                <span class="badge ${scopeBadgeClass} border font-size-75 py-0.5 px-1.5">${scopeLabel}</span>
                <span class="badge bg-body-tertiary text-secondary border font-monospace font-size-75 py-0.5 px-1.5">v${p.version || '1.0.0'}</span>
              </div>
            </div>
          </div>
          <div class="form-check form-switch mb-0 flex-shrink-0" title="${isEnabled ? 'Отключить плагин' : 'Включить плагин'}">
            <input class="form-check-input plugin-toggle-switch cursor-pointer" type="checkbox" role="switch" data-plugin-name="${p.name}" ${isEnabled ? 'checked' : ''} />
          </div>
        </div>

        <!-- Тело карточки -->
        <div class="card-body p-3 d-flex flex-column gap-2 flex-grow-1">
          <p class="small text-secondary mb-1 flex-grow-1" style="min-height: 40px;">
            ${p.description || 'Описание отсутствует.'}
          </p>

          ${tools.length > 0 ? `
            <div class="mb-1">
              <div class="small fw-semibold text-secondary mb-1 font-size-75">
                <i class="bi bi-tools me-1"></i>Функции ИИ (${tools.length}):
              </div>
              <div class="d-flex flex-wrap gap-1">
                ${tools.slice(0, 4).map(t => {
                  const fname = t.function?.name || t.name || 'tool';
                  return `<span class="badge bg-body-secondary text-primary font-monospace font-size-75 border">${fname}</span>`;
                }).join('')}
                ${tools.length > 4 ? `<span class="badge bg-body-secondary text-secondary font-size-75">+${tools.length - 4}</span>` : ''}
              </div>
            </div>
          ` : ''}

          ${actions.length > 0 ? `
            <div class="d-flex flex-wrap gap-1.5 pt-2 border-top mt-auto">
              ${actions.map(act => `
                <button type="button" class="btn btn-sm btn-outline-primary plugin-action-btn d-flex align-items-center gap-1 py-1 px-2 font-size-80" data-plugin-name="${p.name}" data-action-id="${act.id}" title="${act.description || act.label}">
                  <i class="bi bi-play-circle"></i>
                  <span>${act.label || act.id}</span>
                </button>
              `).join('')}
            </div>
          ` : ''}
        </div>

        <!-- Подвал карточки с настройками и удалением -->
        <div class="card-footer bg-transparent border-top p-2 d-flex align-items-center justify-content-between gap-2">
          <span class="small text-secondary font-monospace font-size-75">
            <i class="bi bi-folder2 text-secondary me-1"></i>${p.name}
          </span>
          <div class="d-flex align-items-center gap-1.5">
            ${hasConfig ? `
              <button type="button" class="btn btn-sm btn-outline-secondary btn-plugin-settings py-0.5 px-2 font-size-80 d-flex align-items-center gap-1" data-plugin-name="${p.name}" title="Открыть параметры конфигурации">
                <i class="bi bi-sliders"></i>
                <span>Настройки</span>
              </button>
            ` : ''}
            ${scope === 'user' ? `
              <button type="button" class="btn btn-sm btn-outline-danger btn-plugin-delete py-0.5 px-2 font-size-80 d-flex align-items-center gap-1" data-plugin-name="${p.name}" title="Удалить пользовательский плагин">
                <i class="bi bi-trash"></i>
                <span>Удалить</span>
              </button>
            ` : ''}
          </div>
        </div>
      </div>
    </div>
  `;
}

/**
 * Отрисовывает витрину стандартных расширений маркетплейса в стиле VS Code.
 */
function renderMarketplace() {
  const grid = document.getElementById('marketplace-cards-grid');
  if (!grid) return;

  const q = currentMarketplaceQuery.trim().toLowerCase();
  const installedNames = new Set(allPlugins.map(p => (p.name || '').toLowerCase()));

  const filtered = marketplacePlugins.filter(item => {
    if (!q) return true;
    return (item.id || '').toLowerCase().includes(q) ||
           (item.title || '').toLowerCase().includes(q) ||
           (item.description || '').toLowerCase().includes(q) ||
           (item.category || '').toLowerCase().includes(q);
  });

  if (filtered.length === 0) {
    grid.innerHTML = `
      <div class="col-12 text-center py-5 text-secondary">
        <div class="fs-1 mb-2">🛍️</div>
        <h6>Плагины не найдены в каталоге</h6>
        <p class="small text-muted mb-0">Попробуйте ввести другой поисковый запрос.</p>
      </div>
    `;
    return;
  }

  grid.innerHTML = filtered.map(item => {
    const isInstalled = installedNames.has((item.id || '').toLowerCase()) || item.installed;
    return `
      <div class="col-md-6 col-xl-4">
        <div class="card shadow-sm border h-100 d-flex flex-column">
          <div class="card-header bg-transparent border-bottom p-3 d-flex align-items-start justify-content-between gap-2">
            <div class="d-flex align-items-start gap-2.5 overflow-hidden">
              <span class="fs-3 flex-shrink-0 p-1.5 rounded bg-body-tertiary">${item.icon || '🧩'}</span>
              <div class="text-truncate">
                <h6 class="mb-0 fw-bold text-truncate" title="${item.title}">${item.title}</h6>
                <div class="small text-muted mb-1 font-monospace font-size-75">${item.id}</div>
                <div class="d-flex align-items-center gap-1.5 flex-wrap">
                  <span class="badge bg-secondary-subtle text-secondary border font-size-75">${item.category}</span>
                  <span class="badge bg-body-tertiary text-secondary border font-size-75">v${item.version}</span>
                </div>
              </div>
            </div>
          </div>

          <div class="card-body p-3 d-flex flex-column justify-content-between flex-grow-1">
            <p class="small text-secondary mb-3">${item.description}</p>
            <div class="d-flex align-items-center justify-content-between text-muted small pt-2 border-top">
              <span class="d-flex align-items-center gap-1 text-warning">
                <i class="bi bi-star-fill"></i> ${item.rating || '4.9'}
                <span class="text-secondary ms-1">(${item.downloads || '10k'} скачиваний)</span>
              </span>
              <span class="small font-monospace">${item.author || 'AI Team'}</span>
            </div>
          </div>

          <div class="card-footer bg-transparent border-top p-2 d-flex align-items-center justify-content-between">
            <span class="badge ${isInstalled ? 'bg-success-subtle text-success border-success' : 'bg-body-secondary text-secondary'} border px-2 py-1 font-size-80">
              <i class="bi ${isInstalled ? 'bi-check2-circle me-1' : 'bi-circle me-1'}"></i>
              ${isInstalled ? 'Установлен' : 'Доступен'}
            </span>
            ${isInstalled ? `
              <button type="button" class="btn btn-sm btn-outline-secondary py-1 px-3 d-flex align-items-center gap-1.5" disabled>
                <i class="bi bi-check-lg"></i>
                <span>Установлено</span>
              </button>
            ` : `
              <button type="button" class="btn btn-sm btn-primary btn-marketplace-install py-1 px-3 d-flex align-items-center gap-1.5 shadow-sm" data-plugin-id="${item.id}">
                <i class="bi bi-cloud-arrow-down"></i>
                <span>Установить в IDE</span>
              </button>
            `}
          </div>
        </div>
      </div>
    `;
  }).join('');

  attachMarketplaceEventListeners();
}

/**
 * Обработчики событий маркетплейса (кнопка установки).
 */
function attachMarketplaceEventListeners() {
  document.querySelectorAll('.btn-marketplace-install').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      const pluginId = e.currentTarget.getAttribute('data-plugin-id');
      if (!pluginId) return;

      const origHtml = btn.innerHTML;
      btn.disabled = true;
      btn.innerHTML = `<span class="spinner-border spinner-border-sm me-1" role="status"></span>Установка...`;

      try {
        const res = await fetch('/api/v1/plugins/install', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ plugin_id: pluginId }),
        });
        const data = await res.json();
        if (res.ok) {
          notify(`Плагин '${data.title || pluginId}' успешно установлен!`, 'success');
          await Promise.all([
            loadPluginsCatalog(),
            loadMarketplaceCatalog(),
          ]);
          if (typeof window.loadExtensionsSidebar === 'function') {
            window.loadExtensionsSidebar();
          }
        } else {
          throw new Error(data.detail || 'Ошибка установки');
        }
      } catch (err) {
        btn.disabled = false;
        btn.innerHTML = origHtml;
        notify(`Ошибка установки плагина: ${err.message}`, 'error');
      }
    });
  });
}

/**
 * Навешивает обработчики событий на элементы карточек установленных плагинов.
 */
function attachCardEventListeners() {
  // 1. Тумблер включения/выключения
  document.querySelectorAll('.plugin-toggle-switch').forEach(sw => {
    sw.addEventListener('change', async (e) => {
      const pluginName = e.target.getAttribute('data-plugin-name');
      const enabled = e.target.checked;
      await handlePluginToggle(pluginName, enabled, e.target);
    });
  });

  // 2. Кнопки действий плагина
  document.querySelectorAll('.plugin-action-btn').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      const targetBtn = e.currentTarget;
      const pluginName = targetBtn.getAttribute('data-plugin-name');
      const actionId = targetBtn.getAttribute('data-action-id');
      await handlePluginAction(pluginName, actionId, targetBtn);
    });
  });

  // 3. Кнопка настроек
  document.querySelectorAll('.btn-plugin-settings').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const pluginName = e.currentTarget.getAttribute('data-plugin-name');
      openPluginConfigModal(pluginName);
    });
  });

  // 4. Кнопка удаления пользовательского плагина
  document.querySelectorAll('.btn-plugin-delete').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      const pluginName = e.currentTarget.getAttribute('data-plugin-name');
      if (!confirm(`Вы действительно хотите удалить пользовательский плагин '${pluginName}'?`)) return;

      try {
        const res = await fetch(`/api/v1/plugins/${encodeURIComponent(pluginName)}/uninstall`, {
          method: 'POST',
        });
        const data = await res.json();
        if (res.ok) {
          notify(`Плагин '${pluginName}' успешно удален`, 'info');
          await Promise.all([
            loadPluginsCatalog(),
            loadMarketplaceCatalog(),
          ]);
          if (typeof window.loadExtensionsSidebar === 'function') {
            window.loadExtensionsSidebar();
          }
        } else {
          throw new Error(data.detail || 'Не удалось удалить плагин');
        }
      } catch (err) {
        notify(`Ошибка удаления: ${err.message}`, 'error');
      }
    });
  });
}

/**
 * Переключение статуса плагина.
 */
async function handlePluginToggle(name, enabled, switchEl) {
  try {
    const res = await fetch(`/api/v1/plugins/${encodeURIComponent(name)}/toggle`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    notify(`Плагин ${name} успешно ${enabled ? 'включен' : 'отключен'}`, 'success');

    const p = allPlugins.find(item => item.name === name);
    if (p) p.enabled = enabled;

    const card = document.querySelector(`.plugin-card[data-plugin-name="${name}"]`);
    if (card) {
      if (enabled) {
        card.classList.remove('opacity-75');
      } else {
        card.classList.add('opacity-75');
      }
    }
    if (typeof window.loadExtensionsSidebar === 'function') {
      window.loadExtensionsSidebar();
    }
  } catch (err) {
    console.error(`[Plugins] Ошибка переключения ${name}:`, err);
    notify(`Ошибка изменения статуса ${name}: ${err.message}`, 'error');
    if (switchEl) switchEl.checked = !enabled;
  }
}

/**
 * Запуск действия плагина.
 */
async function handlePluginAction(pluginName, actionId, btnEl) {
  const origHtml = btnEl.innerHTML;
  btnEl.disabled = true;
  btnEl.innerHTML = `<span class="spinner-border spinner-border-sm" role="status"></span>`;

  try {
    const res = await fetch(`/api/v1/plugins/${encodeURIComponent(pluginName)}/action/${encodeURIComponent(actionId)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ params: {} }),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `HTTP ${res.status}`);
    }
    const data = await res.json();
    notify(`Действие '${actionId}' выполнено успешно!`, 'success');
  } catch (err) {
    console.error(`[Plugins] Ошибка действия ${actionId} плагина ${pluginName}:`, err);
    notify(`Ошибка выполнения действия: ${err.message}`, 'error');
  } finally {
    btnEl.disabled = false;
    btnEl.innerHTML = origHtml;
  }
}

/**
 * Открывает модальное окно настроек плагина.
 */
async function openPluginConfigModal(pluginName) {
  const modalEl = document.getElementById('modal-plugin-config');
  if (!modalEl || !window.bootstrap) return;

  const titleName = document.getElementById('modal-config-plugin-name');
  const titleIcon = document.getElementById('modal-config-plugin-icon');
  const fieldsContainer = document.getElementById('modal-config-fields-container');

  const p = allPlugins.find(item => item.name === pluginName);
  if (titleName) titleName.textContent = pluginName;
  if (titleIcon) titleIcon.textContent = p?.icon || '⚙️';

  fieldsContainer.innerHTML = `
    <div class="text-center py-4 text-secondary">
      <div class="spinner-border spinner-border-sm text-primary mb-2" role="status"></div>
      <div class="small">Загрузка параметров...</div>
    </div>
  `;

  const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
  modal.show();

  try {
    const res = await fetch(`/api/v1/plugins/${encodeURIComponent(pluginName)}/config`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    activeConfigPlugin = { name: pluginName, ...data };
    renderConfigForm(data);
  } catch (err) {
    fieldsContainer.innerHTML = `
      <div class="alert alert-danger py-2 px-3 small">
        <i class="bi bi-exclamation-triangle-fill me-1"></i>
        <span>Не удалось загрузить параметры: ${err.message}</span>
      </div>
    `;
  }
}

/**
 * Отрисовывает динамические поля формы настроек.
 */
function renderConfigForm(data) {
  const container = document.getElementById('modal-config-fields-container');
  if (!container) return;

  const config = data.config || {};
  const fields = Array.isArray(data.fields) && data.fields.length > 0 ? data.fields : null;

  if (fields) {
    container.innerHTML = fields.map(f => {
      const val = config[f.id] !== undefined ? config[f.id] : (f.default !== undefined ? f.default : '');
      if (f.type === 'boolean') {
        return `
          <div class="form-check form-switch">
            <input class="form-check-input config-field-input" type="checkbox" id="field-${f.id}" data-field-id="${f.id}" data-field-type="boolean" ${val ? 'checked' : ''} />
            <label class="form-check-label fw-semibold" for="field-${f.id}">${f.label || f.id}</label>
            ${f.description ? `<div class="form-text small text-secondary">${f.description}</div>` : ''}
          </div>
        `;
      }
      return `
        <div>
          <label class="form-label fw-semibold small mb-1" for="field-${f.id}">${f.label || f.id}</label>
          <input type="${f.type === 'number' ? 'number' : 'text'}" class="form-control form-control-sm config-field-input" id="field-${f.id}" data-field-id="${f.id}" data-field-type="${f.type || 'text'}" value="${val}" />
          ${f.description ? `<div class="form-text small text-secondary">${f.description}</div>` : ''}
        </div>
      `;
    }).join('');
    return;
  }

  // Fallback: Редактор JSON
  const jsonStr = JSON.stringify(config, null, 2);
  container.innerHTML = `
    <div>
      <label class="form-label fw-semibold small mb-1" for="config-raw-json-editor">
        <i class="bi bi-code-square me-1"></i>Параметры (JSON):
      </label>
      <textarea class="form-control font-monospace small" id="config-raw-json-editor" rows="10">${jsonStr}</textarea>
    </div>
  `;
}

/**
 * Настройка обработчиков модального окна настроек.
 */
function setupConfigModalHandlers() {
  const saveBtn = document.getElementById('btn-save-plugin-config');
  if (!saveBtn) return;

  saveBtn.addEventListener('click', async () => {
    if (!activeConfigPlugin) return;
    const pluginName = activeConfigPlugin.name;
    let newConfig = {};

    const rawEditor = document.getElementById('config-raw-json-editor');
    if (rawEditor) {
      try {
        newConfig = JSON.parse(rawEditor.value);
      } catch (err) {
        notify(`Синтаксическая ошибка в JSON: ${err.message}`, 'error');
        return;
      }
    } else {
      newConfig = { ...(activeConfigPlugin.config || {}) };
      document.querySelectorAll('.config-field-input').forEach(input => {
        const fid = input.getAttribute('data-field-id');
        const ftype = input.getAttribute('data-field-type');
        if (ftype === 'boolean') {
          newConfig[fid] = input.checked;
        } else if (ftype === 'number') {
          newConfig[fid] = Number(input.value);
        } else {
          newConfig[fid] = input.value;
        }
      });
    }

    const origHtml = saveBtn.innerHTML;
    saveBtn.disabled = true;
    saveBtn.innerHTML = `<span class="spinner-border spinner-border-sm" role="status"></span><span>Сохранение...</span>`;

    try {
      const res = await fetch(`/api/v1/plugins/${encodeURIComponent(pluginName)}/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config: newConfig }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      notify(`Настройки ${pluginName} сохранены`, 'success');

      const modalEl = document.getElementById('modal-plugin-config');
      if (modalEl && window.bootstrap) {
        bootstrap.Modal.getInstance(modalEl)?.hide();
      }
      await loadPluginsCatalog();
    } catch (err) {
      notify(`Ошибка сохранения: ${err.message}`, 'error');
    } finally {
      saveBtn.disabled = false;
      saveBtn.innerHTML = origHtml;
    }
  });
}

/**
 * Настройка фильтра по области видимости (Scope).
 */
function setupFilterHandlers() {
  const group = document.getElementById('plugins-scope-filter-group');
  if (!group) return;

  group.querySelectorAll('button[data-filter-scope]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      group.querySelectorAll('button[data-filter-scope]').forEach(b => {
        b.classList.remove('btn-primary', 'active');
        b.classList.add('btn-outline-secondary');
      });
      const target = e.currentTarget;
      target.classList.remove('btn-outline-secondary');
      target.classList.add('btn-primary', 'active');
      currentScopeFilter = target.getAttribute('data-filter-scope') || 'all';
      renderPlugins();
    });
  });
}

/**
 * Настройка строки поиска по установленным плагинам.
 */
function setupSearchHandlers() {
  const input = document.getElementById('plugins-search-input');
  const clearBtn = document.getElementById('btn-clear-plugin-search');
  if (!input) return;

  input.addEventListener('input', (e) => {
    currentSearchQuery = e.target.value.trim();
    if (clearBtn) {
      if (currentSearchQuery) {
        clearBtn.classList.remove('d-none');
      } else {
        clearBtn.classList.add('d-none');
      }
    }
    renderPlugins();
  });

  clearBtn?.addEventListener('click', () => {
    input.value = '';
    currentSearchQuery = '';
    clearBtn.classList.add('d-none');
    renderPlugins();
  });
}

/**
 * Настройка поиска по маркетплейсу.
 */
function setupMarketplaceSearchHandlers() {
  const input = document.getElementById('marketplace-search-input');
  if (!input) return;

  input.addEventListener('input', (e) => {
    currentMarketplaceQuery = e.target.value.trim();
    renderMarketplace();
  });
}

/**
 * Обработчик кнопки перезагрузки.
 */
function setupReloadHandler() {
  const btn = document.getElementById('btn-reload-plugins');
  if (!btn) return;

  btn.addEventListener('click', async () => {
    const origHtml = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner-border spinner-border-sm" role="status"></span><span>Перезагрузка...</span>`;
    try {
      const res = await fetch('/api/v1/plugins/reload', { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      notify('Реестр плагинов успешно перезагружен', 'success');
      await Promise.all([
        loadPluginsCatalog(),
        loadMarketplaceCatalog(),
      ]);
    } catch (err) {
      notify(`Ошибка перезагрузки: ${err.message}`, 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = origHtml;
    }
  });
}
