/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Custom Context Menu & Git Maintenance
 * =============================================================================
 * Description:
 *   Кастомное контекстное меню по правому клику мыши (ПКМ) и интеграция
 *   с интеллектуальным анализатором GitMaintenanceAnalyzer.
 *   Отображает текущий вердикт репозитория (Норма / Наблюдение / Обслуживание),
 *   позволяет запускать штатную оптимизацию git gc --auto и открывать вкладку
 *   диагностики tab_git_maintenance.
 *
 * File: context-menu.js
 * Package: apps/ai_assistant/api/webgui/js
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-26 00:55:00
 * =============================================================================
 */

let cachedDiagnosis = {
  verdict: 'NORMAL',
  verdict_title: 'Норма',
  action_type: 'none',
  recommendation: 'Ничего не делать',
  explanation: 'Репозиторий компактен и оптимален.',
  metrics: {
    loose_count: 0,
    loose_size_kib: 0,
    packs_count: 0,
    pack_size_kib: 0,
  }
};

let cachedSchedule = {
  auto_gc_enabled: true,
  gc_interval_hours: 24,
  is_running: false,
};

let menuElement = null;

/**
 * Загружает статус обслуживания и диагностику репозитория с бэкенда.
 */
export async function fetchMaintenanceStatus() {
  try {
    const [diagRes, schedRes] = await Promise.all([
      fetch('/api/v1/git/maintenance/diagnosis'),
      fetch('/api/v1/git/maintenance/status'),
    ]);

    if (diagRes.ok) {
      cachedDiagnosis = await diagRes.json();
    }
    if (schedRes.ok) {
      const sched = await schedRes.json();
      cachedSchedule.auto_gc_enabled = sched.auto_gc_enabled ?? true;
      cachedSchedule.gc_interval_hours = sched.gc_interval_hours ?? 24;
      cachedSchedule.is_running = sched.is_running ?? false;
    }
    updateMenuStatusUI();
  } catch (err) {
    console.warn('[ContextMenu] Ошибка получения статуса обслуживания Git:', err);
  }
}

/**
 * Запускает штатное обслуживание git gc --auto.
 */
export async function runGitGcAuto() {
  if (cachedSchedule.is_running) {
    showToast('⚠️ Оптимизация репозитория уже выполняется', 'warning');
    return;
  }

  cachedSchedule.is_running = true;
  updateMenuStatusUI();
  showToast('⏳ Выполнение штатного git gc --auto (Git проверяет условия сборки)...', 'info');

  try {
    const res = await fetch('/api/v1/git/maintenance/gc-auto', { method: 'POST' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Ошибка запуска');

    cachedSchedule.is_running = false;
    if (data.diagnosis) {
      cachedDiagnosis = data.diagnosis;
    }
    updateMenuStatusUI();

    showToast(`✅ git gc --auto завершен (${data.elapsed_sec}с): ${cachedDiagnosis.recommendation}`, 'success');
  } catch (err) {
    cachedSchedule.is_running = false;
    updateMenuStatusUI();
    showToast(`❌ Ошибка git gc --auto: ${err.message}`, 'danger');
  }
}

/**
 * Сохраняет настройки периодической фоновой проверки.
 */
export async function saveMaintenanceSchedule(options) {
  try {
    const payload = {
      auto_gc_enabled: options.auto_gc_enabled !== undefined ? options.auto_gc_enabled : cachedSchedule.auto_gc_enabled,
      gc_interval_hours: options.gc_interval_hours !== undefined ? options.gc_interval_hours : cachedSchedule.gc_interval_hours,
      aggressive: false,
      auto_prune: true,
    };

    const res = await fetch('/api/v1/git/maintenance/schedule', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (res.ok) {
      cachedSchedule.auto_gc_enabled = payload.auto_gc_enabled;
      cachedSchedule.gc_interval_hours = payload.gc_interval_hours;
      updateMenuStatusUI();
      showToast(
        payload.auto_gc_enabled
          ? `✅ Фоновый мониторинг Git включён (каждые ${payload.gc_interval_hours} ч)`
          : '⏸ Фоновый мониторинг Git отключен',
        payload.auto_gc_enabled ? 'success' : 'secondary'
      );
      return true;
    }
  } catch (err) {
    showToast(`❌ Ошибка сохранения расписания: ${err.message}`, 'danger');
  }
  return false;
}

/**
 * Обновляет визуальные индикаторы в кастомном меню ПКМ.
 */
function updateMenuStatusUI() {
  if (!menuElement) return;

  const statusBadge = menuElement.querySelector('#cm-git-status-badge');
  const verdict = cachedDiagnosis.verdict || 'NORMAL';

  if (statusBadge) {
    if (verdict === 'NORMAL') {
      statusBadge.className = 'badge bg-success-subtle text-success border border-success-subtle custom-context-menu-badge';
      statusBadge.textContent = '🟢 Норма';
    } else if (verdict === 'OBSERVATION') {
      statusBadge.className = 'badge bg-warning-subtle text-warning-emphasis border border-warning-subtle custom-context-menu-badge';
      statusBadge.textContent = '🟡 Наблюдение';
    } else {
      statusBadge.className = 'badge bg-danger-subtle text-danger border border-danger-subtle custom-context-menu-badge';
      statusBadge.textContent = '🔴 Требуется GC';
    }
  }

  const toggleIcon = menuElement.querySelector('#cm-gc-toggle-icon');
  const scheduleBadge = menuElement.querySelector('#cm-gc-schedule-badge');
  if (toggleIcon) {
    toggleIcon.className = cachedSchedule.auto_gc_enabled
      ? 'bi bi-check2-square text-success'
      : 'bi bi-square text-muted';
  }
  if (scheduleBadge) {
    scheduleBadge.textContent = cachedSchedule.auto_gc_enabled
      ? `${cachedSchedule.gc_interval_hours}ч`
      : 'Выкл';
  }

  const runIcon = menuElement.querySelector('#cm-gc-run-icon');
  if (runIcon) {
    runIcon.className = cachedSchedule.is_running
      ? 'spinner-border spinner-border-sm text-warning'
      : 'bi bi-lightning-charge-fill text-warning';
  }
}

/**
 * Показывает Toast уведомление.
 */
function showToast(message, type = 'info') {
  if (typeof window.showNotificationToast === 'function') {
    window.showNotificationToast(message, type);
    return;
  }
  const toastContainer = document.getElementById('toast-container');
  if (!toastContainer) {
    console.log(`[Toast ${type}] ${message}`);
    return;
  }
  const id = `toast-${Date.now()}`;
  const html = `
    <div id="${id}" class="toast align-items-center text-bg-${type} border-0 show mb-2" role="alert" aria-live="assertive" aria-atomic="true">
      <div class="d-flex">
        <div class="toast-body">${message}</div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
      </div>
    </div>
  `;
  toastContainer.insertAdjacentHTML('beforeend', html);
  setTimeout(() => {
    const el = document.getElementById(id);
    if (el) el.remove();
  }, 4000);
}

/**
 * Создаёт DOM-элемент контекстного меню.
 */
function ensureContextMenuDOM() {
  if (menuElement) return;

  const menu = document.createElement('div');
  menu.id = 'custom-app-context-menu';
  menu.className = 'custom-context-menu d-none';
  menu.innerHTML = `
    <div class="custom-context-menu-header">AI Assistant</div>
    <div class="custom-context-menu-item" data-action="reload">
      <span class="custom-context-menu-icon"><i class="bi bi-arrow-clockwise"></i></span>
      <span class="custom-context-menu-label">Обновить страницу</span>
      <span class="text-muted font-size-80">F5</span>
    </div>
    <div class="custom-context-menu-item" data-action="copy">
      <span class="custom-context-menu-icon"><i class="bi bi-clipboard"></i></span>
      <span class="custom-context-menu-label">Копировать</span>
      <span class="text-muted font-size-80">Ctrl+C</span>
    </div>
    <div class="custom-context-menu-divider"></div>

    <div class="custom-context-menu-header">Git Репозиторий</div>
    <div class="custom-context-menu-item" data-action="open-git-tab" title="Открыть вкладку диагностики состояния репозитория Git">
      <span class="custom-context-menu-icon"><i class="bi bi-speedometer2 text-info"></i></span>
      <span class="custom-context-menu-label">Состояние репозитория</span>
      <span class="badge bg-success-subtle text-success custom-context-menu-badge" id="cm-git-status-badge">🟢 Норма</span>
    </div>
    <div class="custom-context-menu-item" data-action="gc-auto" title="Выполнить штатную сборку Git по измеряемым порогам">
      <span class="custom-context-menu-icon"><i id="cm-gc-run-icon" class="bi bi-lightning-charge-fill text-warning"></i></span>
      <span class="custom-context-menu-label">Выполнить git gc --auto</span>
    </div>
    <div class="custom-context-menu-item" data-action="open-git-tab" title="Перейти к полной диагностике и журналу решений Git">
      <span class="custom-context-menu-icon"><i class="bi bi-tools text-primary"></i></span>
      <span class="custom-context-menu-label">Диагностика Git (GC)...</span>
    </div>
    <div class="custom-context-menu-item" data-action="toggle-monitor" title="Включить или выключить фоновый периодический мониторинг метрик">
      <span class="custom-context-menu-icon"><i id="cm-gc-toggle-icon" class="bi bi-check2-square text-success"></i></span>
      <span class="custom-context-menu-label">Фоновый мониторинг</span>
      <span class="badge bg-secondary-subtle text-muted custom-context-menu-badge" id="cm-gc-schedule-badge">24ч</span>
    </div>

    <div class="custom-context-menu-divider"></div>
    <div class="custom-context-menu-item" data-action="devtools-info">
      <span class="custom-context-menu-icon"><i class="bi bi-code-slash"></i></span>
      <span class="custom-context-menu-label">Инструменты DevTools</span>
      <span class="text-muted font-size-80">F12</span>
    </div>
  `;

  document.body.appendChild(menu);
  menuElement = menu;
}

/**
 * Скрывает контекстное меню.
 */
export function hideContextMenu() {
  if (menuElement && !menuElement.classList.contains('d-none')) {
    menuElement.classList.add('d-none');
  }
}

/**
 * Показывает контекстное меню по координатам клика.
 */
function showContextMenu(e) {
  ensureContextMenuDOM();
  e.preventDefault();

  const menuWidth = 270;
  const menuHeight = 290;
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

  updateMenuStatusUI();
}

/**
 * Обработчик клика по пунктам меню.
 */
async function handleMenuItemClick(action) {
  hideContextMenu();

  switch (action) {
    case 'reload':
      location.reload();
      break;

    case 'copy':
      try {
        const selected = window.getSelection()?.toString();
        if (selected) {
          await navigator.clipboard.writeText(selected);
          showToast('📋 Текст скопирован в буфер обмена', 'success');
        } else {
          showToast('ℹ️ Нет выделенного текста для копирования', 'secondary');
        }
      } catch (err) {
        showToast('❌ Ошибка копирования в буфер', 'warning');
      }
      break;

    case 'open-git-tab':
      if (typeof window.switchTab === 'function') {
        window.switchTab('tab-git-maintenance');
      }
      break;

    case 'gc-auto':
      await runGitGcAuto();
      break;

    case 'toggle-monitor':
      await saveMaintenanceSchedule({
        auto_gc_enabled: !cachedSchedule.auto_gc_enabled,
      });
      break;

    case 'devtools-info':
      showToast('💡 DevTools: нажмите F12 или откройте интерфейс в браузере: http://127.0.0.1:8002/', 'info');
      break;
  }
}

/**
 * Инициализирует кастомное контекстное меню и привязывает слушатели событий.
 */
export async function initCustomContextMenu() {
  ensureContextMenuDOM();

  // Первичная подгрузка состояния с бэкенда
  fetchMaintenanceStatus();

  // Перехват клика правой кнопкой мыши
  document.addEventListener('contextmenu', (e) => {
    // Если клик внутри проводника файлов IDE — обработку берёт ide_tree_context_menu.js
    if (e.target.closest('#ide-file-navigator, #ide-file-tree-container, .ide-tree-item')) {
      return;
    }
    showContextMenu(e);
  });

  // Закрытие по клику вне меню
  document.addEventListener('click', (e) => {
    if (menuElement && !menuElement.contains(e.target)) {
      hideContextMenu();
    }
  });

  // Закрытие по Esc
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      hideContextMenu();
    }
  });

  // Закрытие при скролле окна
  window.addEventListener('scroll', hideContextMenu, true);

  // Обработка кликов внутри меню
  menuElement.addEventListener('click', (e) => {
    const item = e.target.closest('.custom-context-menu-item');
    if (!item) return;
    const action = item.getAttribute('data-action');
    if (action) {
      handleMenuItemClick(action);
    }
  });
}
