/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - IDE Extensions Sidebar & Marketplace
 * =============================================================================
 * Description:
 *   Модуль боковой панели расширений в стиле Visual Studio Code (Extensions View).
 *   Обеспечивает визуализацию маркетплейса стандартных плагинов, быстрый поиск,
 *   установку в один клик, управление активностью и удаление расширений.
 *
 * File: ide_extensions_sidebar.js
 * Package: apps/ai_assistant/api/webgui/js
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-25 22:30:00
 * =============================================================================
 */

let marketplacePlugins = [];
let installedPlugins = [];
let extSearchQuery = '';

/**
 * Переключает активное представление боковой панели (Explorer или Extensions).
 * @param {'explorer' | 'extensions'} viewName 
 */
export function switchSidebarView(viewName) {
  const explorerView = document.getElementById('ide-sidebar-view-explorer');
  const extensionsView = document.getElementById('ide-sidebar-view-extensions');
  const sidebar = document.getElementById('ide-file-navigator');

  if (sidebar && sidebar.classList.contains('collapsed')) {
    sidebar.classList.remove('collapsed');
    document.body.classList.remove('ide-sidebar-collapsed');
  }

  if (viewName === 'extensions') {
    if (explorerView) explorerView.classList.add('d-none');
    if (extensionsView) {
      extensionsView.classList.remove('d-none');
      loadExtensionsSidebar();
    }
  } else {
    if (extensionsView) extensionsView.classList.add('d-none');
    if (explorerView) explorerView.classList.remove('d-none');
  }
}
window.switchSidebarView = switchSidebarView;

/**
 * Загружает данные маркетплейса и установленных расширений с сервера.
 */
export async function loadExtensionsSidebar() {
  const container = document.getElementById('ide-ext-list-container');
  if (!container) return;

  try {
    const [mRes, iRes] = await Promise.all([
      fetch('/api/v1/plugins/marketplace'),
      fetch('/api/v1/plugins?lang=ru')
    ]);

    if (mRes.ok) {
      marketplacePlugins = await mRes.json();
    }
    if (iRes.ok) {
      installedPlugins = await iRes.json();
    }

    renderExtensionsSidebar();
  } catch (err) {
    console.error('[ide_extensions_sidebar] Ошибка загрузки расширений:', err);
    if (container) {
      container.innerHTML = `
        <div class="text-center py-4 text-danger small">
          <i class="bi bi-exclamation-triangle mb-1 fs-5 d-block"></i>
          <span>Не удалось загрузить каталог</span>
          <button class="btn btn-xs btn-outline-primary d-block mx-auto mt-2" id="ide-btn-retry-ext">Повторить</button>
        </div>
      `;
      document.getElementById('ide-btn-retry-ext')?.addEventListener('click', loadExtensionsSidebar);
    }
  }
}

/**
 * Отрисовывает списки расширений в боковой панели.
 */
function renderExtensionsSidebar() {
  const container = document.getElementById('ide-ext-list-container');
  if (!container) return;

  const q = extSearchQuery.trim().toLowerCase();

  // Фильтрация установленных плагинов
  const filteredInstalled = installedPlugins.filter(p => {
    if (!q) return true;
    return (p.name || '').toLowerCase().includes(q) ||
           (p.title || '').toLowerCase().includes(q) ||
           (p.description || '').toLowerCase().includes(q);
  });

  // Фильтрация маркетплейса (показываем те, что еще не установлены или все при поиске)
  const installedIds = new Set(installedPlugins.map(p => (p.name || '').toLowerCase()));
  const filteredMarketplace = marketplacePlugins.filter(p => {
    if (installedIds.has((p.id || '').toLowerCase())) return false;
    if (!q) return true;
    return (p.id || '').toLowerCase().includes(q) ||
           (p.title || '').toLowerCase().includes(q) ||
           (p.description || '').toLowerCase().includes(q) ||
           (p.category || '').toLowerCase().includes(q);
  });

  let html = '';

  // Секция 1: Установленные расширения
  html += `
    <div class="ide-ext-section-header">
      <div class="d-flex align-items-center gap-1">
        <i class="bi bi-check2-circle text-success"></i>
        <span>Установленные (${filteredInstalled.length})</span>
      </div>
    </div>
  `;

  if (filteredInstalled.length === 0) {
    html += `<div class="text-muted small px-2 py-1 font-size-75">Нет установленных расширений</div>`;
  } else {
    filteredInstalled.forEach(plugin => {
      const isEnabled = plugin.enabled !== false;
      const scope = plugin.scope || 'user';
      const isUserScope = scope === 'user';
      html += `
        <div class="ide-ext-card" data-plugin-name="${plugin.name}">
          <div class="ide-ext-card-icon">${plugin.icon || '🧩'}</div>
          <div class="ide-ext-card-body">
            <div class="ide-ext-card-title" title="${plugin.title || plugin.name}">
              ${plugin.title || plugin.name}
            </div>
            <div class="ide-ext-card-desc" title="${plugin.description || ''}">
              ${plugin.description || 'Модуль расширения IDE'}
            </div>
            <div class="ide-ext-card-meta">
              <span>v${plugin.version || '1.0.0'}</span>
              <div class="d-flex align-items-center gap-1">
                <button class="btn btn-link p-0 text-secondary ide-ext-btn-toggle" data-plugin="${plugin.name}" data-enabled="${isEnabled}" title="${isEnabled ? 'Отключить' : 'Включить'}">
                  <i class="bi ${isEnabled ? 'bi-toggle-on text-success fs-6' : 'bi-toggle-off text-muted fs-6'}"></i>
                </button>
                ${isUserScope ? `
                  <button class="btn btn-link p-0 text-danger ide-ext-btn-uninstall" data-plugin="${plugin.name}" title="Удалить плагин">
                    <i class="bi bi-trash"></i>
                  </button>
                ` : ''}
              </div>
            </div>
          </div>
        </div>
      `;
    });
  }

  // Секция 2: Маркетплейс стандартных плагинов
  html += `
    <div class="ide-ext-section-header mt-2">
      <div class="d-flex align-items-center gap-1">
        <i class="bi bi-shop text-primary"></i>
        <span>Каталог: Marketplace (${filteredMarketplace.length})</span>
      </div>
    </div>
  `;

  if (filteredMarketplace.length === 0) {
    html += `<div class="text-muted small px-2 py-1 font-size-75">Все стандартные плагины уже установлены</div>`;
  } else {
    filteredMarketplace.forEach(item => {
      html += `
        <div class="ide-ext-card" data-marketplace-id="${item.id}">
          <div class="ide-ext-card-icon">${item.icon || '🧩'}</div>
          <div class="ide-ext-card-body">
            <div class="ide-ext-card-title" title="${item.title}">
              ${item.title}
            </div>
            <div class="ide-ext-card-desc" title="${item.description}">
              ${item.description}
            </div>
            <div class="ide-ext-card-meta">
              <span class="d-flex align-items-center gap-1 text-warning">
                <i class="bi bi-star-fill"></i> ${item.rating || '4.9'}
                <span class="text-muted ms-1">${item.downloads || '10k'}</span>
              </span>
              <button class="btn btn-primary btn-sm ide-ext-btn-install" data-install-id="${item.id}">
                <i class="bi bi-cloud-arrow-down me-1"></i>Установить
              </button>
            </div>
          </div>
        </div>
      `;
    });
  }

  container.innerHTML = html;
  bindExtensionsEvents();
}

/**
 * Навешивает обработчики событий на кнопки карточек расширений.
 */
function bindExtensionsEvents() {
  const container = document.getElementById('ide-ext-list-container');
  if (!container) return;

  // 1. Кнопки установки из маркетплейса
  container.querySelectorAll('.ide-ext-btn-install').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const pluginId = btn.dataset.installId;
      if (!pluginId) return;

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
          if (typeof window.showToast === 'function') {
            window.showToast(`Плагин '${data.title || pluginId}' успешно установлен!`, 'success');
          }
          await loadExtensionsSidebar();
          // Если вкладка tab_plugins активна, обновим и её
          if (typeof window.initPluginsTab === 'function') {
            window.initPluginsTab();
          }
        } else {
          throw new Error(data.detail || 'Ошибка установки');
        }
      } catch (err) {
        btn.disabled = false;
        btn.innerHTML = `<i class="bi bi-cloud-arrow-down me-1"></i>Установить`;
        if (typeof window.showToast === 'function') {
          window.showToast(`Ошибка установки: ${err.message}`, 'danger');
        }
      }
    });
  });

  // 2. Кнопка переключения активности
  container.querySelectorAll('.ide-ext-btn-toggle').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const name = btn.dataset.plugin;
      const current = btn.dataset.enabled === 'true';
      const target = !current;

      try {
        const res = await fetch(`/api/v1/plugins/${name}/toggle`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ enabled: target }),
        });
        if (res.ok) {
          await loadExtensionsSidebar();
          if (typeof window.initPluginsTab === 'function') {
            window.initPluginsTab();
          }
        }
      } catch (err) {
        console.error('[ide_extensions_sidebar] Ошибка toggle:', err);
      }
    });
  });

  // 3. Кнопка удаления пользовательского плагина
  container.querySelectorAll('.ide-ext-btn-uninstall').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const name = btn.dataset.plugin;
      if (!confirm(`Вы действительно хотите удалить плагин '${name}'?`)) return;

      try {
        const res = await fetch(`/api/v1/plugins/${name}/uninstall`, {
          method: 'POST',
        });
        const data = await res.json();
        if (res.ok) {
          if (typeof window.showToast === 'function') {
            window.showToast(`Плагин '${name}' успешно удален`, 'info');
          }
          await loadExtensionsSidebar();
          if (typeof window.initPluginsTab === 'function') {
            window.initPluginsTab();
          }
        } else {
          throw new Error(data.detail || 'Не удалось удалить');
        }
      } catch (err) {
        if (typeof window.showToast === 'function') {
          window.showToast(`Ошибка удаления: ${err.message}`, 'danger');
        }
      }
    });
  });
}

/**
 * Инициализация боковой панели расширений.
 */
export function initExtensionsSidebar() {
  const searchInput = document.getElementById('ide-ext-search-input');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      extSearchQuery = e.target.value || '';
      renderExtensionsSidebar();
    });
  }

  const refreshBtn = document.getElementById('ide-btn-refresh-extensions');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', () => {
      loadExtensionsSidebar();
    });
  }

  const collapseBtn = document.getElementById('ide-btn-collapse-extensions');
  if (collapseBtn) {
    collapseBtn.addEventListener('click', () => {
      const sidebar = document.getElementById('ide-file-navigator');
      if (sidebar) {
        sidebar.classList.add('collapsed');
        document.body.classList.add('ide-sidebar-collapsed');
      }
    });
  }
}
