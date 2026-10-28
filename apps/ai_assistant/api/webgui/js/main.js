/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Main Orchestrator Script
 * =============================================================================
 * Description:
 *   Главный клиентский скрипт-оркестратор веб-интерфейса AI Assistant
 *   (Умное версионирование и верификация).
 *   Обеспечивает переключение вкладок, управление темами (светлая/тёмная/кирпичная/терминал),
 *   многоязычность i18n, кеширование и связь с 2-step верификацией.
 *
 * File: main.js
 * Package: apps/ai_assistant/api/webgui/js
 * Author: hypo69
 * Updated: 2026-10-28 20:03:00
 * =============================================================================
 */

import { initI18n, switchLang, applyTranslations } from './i18n.js';
import { initTheme } from './theme.js';
import { initUserSettings } from './userSettings.js';
import { initCacheUI } from './cache-ui.js';
import { switchTab, loadTab, setupTabClicks } from './tab-core.js';
import { initTopWorkspaceDropdown, updateTopWorkspaceDropdown } from './top_workspace_dropdown.js';
import { initCustomContextMenu } from './context-menu.js';
import {
  initDrawerWorkspaces,
  fetchAndRenderDrawerWorkspaces,
  highlightActiveDrawerWorkspace,
  switchToWorkspace,
  findWorkspaceMatch,
} from './drawer_workspaces.js';
import { initIdeNavigation } from './ide_navigation.js';
import { initIdeFileExplorer } from './ide_file_explorer.js?v=20261027_v1';
import './api-cache.js';

// Глобальный экспорт для вызова из разметки и дочерних вкладок
window.switchTab = switchTab;
window.switchToTab = switchTab;
window.applyTranslations = applyTranslations;
window.switchLang = switchLang;
window.switchLocale = switchLang;

// Карта соответствия вкладок: id -> [htmlUrl, jsUrl]
const TABS = {
  'workspace':        ['/html/tab_workspace/index.html',        '/html/tab_workspace/main.js'],
  'create-workspace': ['/html/tab_create_workspace/index.html', '/html/tab_create_workspace/main.js'],
  'timeline':         ['/html/tab_timeline/index.html',         '/html/tab_timeline/main.js'],
  'commits':          ['/html/tab_commits/index.html',          '/html/tab_commits/main.js'],
  'diff':             ['/html/tab_diff/index.html',             '/html/tab_diff/main.js'],
  'wikillm':          ['/html/tab_wikillm/index.html',          '/html/tab_wikillm/main.js'],
  'graph':            ['/html/tab_graph/index.html',            '/html/tab_graph/main.js'],
  'rag':              ['/html/tab_rag/index.html',              '/html/tab_rag/main.js'],
  'verification':     ['/html/tab_verification/index.html',     '/html/tab_verification/main.js'],
  'status':           ['/html/tab_status/index.html',           '/html/tab_status/main.js'],
  'theme-editor':     ['/html/tab_theme_editor/index.html',     '/html/tab_theme_editor/main.js'],
  'models':           ['/html/tab_models/index.html',           '/html/tab_models/main.js'],
  'git-maintenance':  ['/html/tab_git_maintenance/index.html',  '/html/tab_git_maintenance/main.js'],
  'gmail':            ['/html/tab_gmail/index.html',            '/html/tab_gmail/main.js'],
  'calendar':         ['/html/tab_calendar/index.html',         '/html/tab_calendar/main.js'],
  'drive':            ['/html/tab_drive/index.html',            '/html/tab_drive/main.js'],
  'contacts':         ['/html/tab_contacts/index.html',         '/html/tab_contacts/main.js'],
  'plugins':          ['/html/tab_plugins/index.html',          '/html/tab_plugins/main.js'],
  'file-editor':      ['/html/tab_file_editor/index.html',      '/html/tab_file_editor/main.js'],
};

const loaded = new Set();

async function lazyLoad(tabName) {
  if (loaded.has(tabName) || !TABS[tabName]) return;
  loaded.add(tabName);
  const v = Date.now();
  const [html, js] = TABS[tabName];
  await loadTab(tabName, `${html}?v=${v}`, `${js}?v=${v}`);
  applyTranslations();
}

export async function switchMainTab(tabId) {
  if (!tabId) return;

  const rawName = tabId.startsWith('tab-') ? tabId.slice(4) : tabId;
  const normId = tabId.startsWith('tab-') ? tabId : `tab-${tabId}`;

  // Мгновенное переключение активного класса
  switchTab(normId);

  // Lazy-load ресурсов вкладки при первом открытии
  if (!loaded.has(rawName) && TABS[rawName]) {
    await lazyLoad(rawName).catch(err => console.warn(`[Main] Ошибка lazyLoad для ${rawName}:`, err));
  }
}
window.switchTab = switchMainTab;
window.switchToTab = switchMainTab;

// Обработка 2-Step аннотации факта
function setupAnnotationModal() {
  const submitBtn = document.getElementById('btn-submit-annotation');
  if (!submitBtn) return;

  submitBtn.addEventListener('click', async () => {
    const src = document.getElementById('modal-source-id')?.value.trim();
    const tgt = document.getElementById('modal-target-id')?.value.trim();
    const rel = document.getElementById('modal-relation-type')?.value;
    const desc = document.getElementById('modal-summary-desc')?.value.trim();
    const statusBox = document.getElementById('modal-validation-preview');

    if (!src || !tgt) {
      alert('Заполните Источник (Source ID) и Цель (Target ID)');
      return;
    }

    if (statusBox) {
      statusBox.innerHTML = '<div class="spinner-border spinner-border-sm text-primary me-2"></div> Валидация контуром безопасности...';
    }

    try {
      const res = await fetch('/api/v1/annotate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_id: src,
          target_id: tgt,
          relation_type: rel,
          summary: desc,
          confidence: 1.0,
          provenance: 'user_webgui'
        })
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || `HTTP ${res.status}`);
      }

      const result = await res.json();
      if (statusBox) {
        statusBox.innerHTML = `<span class="text-success fw-semibold">✅ Успешно верифицировано и сохранено в темпоральный граф!</span>`;
      }

      setTimeout(() => {
        const modalEl = document.getElementById('annotateModal');
        if (modalEl && window.bootstrap) {
          const m = bootstrap.Modal.getInstance(modalEl);
          if (m) m.hide();
        }
        if (typeof window.loadPanelData === 'function') {
          window.loadPanelData('panel-knowledge-links', { force: true });
          window.loadPanelData('panel-wikillm-entities', { force: true });
        }
      }, 900);
    } catch (err) {
      if (statusBox) {
        statusBox.innerHTML = `<span class="text-danger fw-semibold">❌ Отклонено верификатором: ${err.message}</span>`;
      }
    }
  });
}

async function initTopGmailBadge() {
  try {
    const res = await fetch('/api/v1/gmail/labels');
    if (!res.ok) return;
    const data = await res.json();
    const inbox = (data.labels || []).find(l => l.id === 'INBOX');
    const topBadge = document.getElementById('top-nav-gmail-badge');
    if (topBadge && inbox) {
      const count = inbox.messages_unread || 0;
      topBadge.textContent = count;
      if (count > 0) topBadge.classList.remove('d-none');
    }
  } catch (_) {}
}

async function init() {
  // 1. Инициализация темы (light, dark, brick, terminal, system)
  initTheme();

  // 2. Инициализация i18n с авто-определением языка и URL параметров (?lang=ru, ?locale=ru-RU)
  await initI18n();

  // 3. Настройки пользователя и кеш
  await initUserSettings();
  initCacheUI();

  // 4. Привязка кликов по кнопкам меню/вкладок
  setupTabClicks();

  // 5. Настройка модального окна 2-Step аннотации
  setupAnnotationModal();

  // 5.1 Инициализация выпадающего списка рабочих пространств на верхней панели
  await initTopWorkspaceDropdown();

  // 5.2 Инициализация кастомного контекстного меню (ПКМ) и Git GC
  await initCustomContextMenu();

  // 5.3 Инициализация бокового меню рабочих областей
  await initDrawerWorkspaces();

  // 5.4 Синхронизация бейджа непрочитанных писем Gmail в верхней панели
  initTopGmailBadge();

  // 5.5 Инициализация вертикальной панели навигации в стиле стандартных IDE (Activity Bar)
  initIdeNavigation();
  // 5.6 Инициализация стандартного навигатора по файлам и Command Center
  initIdeFileExplorer();

  // Вспомогательный канонический парсер URL стандарта workspace-url-routing
  const parseWorkspaceUrlComponents = (rawHash) => {
    const clean = (rawHash || '').replace(/^#/, '');
    const parts = clean.split('#');
    const tabId = parts[0] || 'tab-workspace';
    let panelId = null;
    let wsId = null;

    for (let i = 1; i < parts.length; i++) {
      const part = parts[i];
      if (part.startsWith('workspace=')) {
        try {
          wsId = decodeURIComponent(part.slice(10));
        } catch (_) {
          wsId = part.slice(10);
        }
      } else if (part.startsWith('panel-') || part.startsWith('step')) {
        panelId = part;
      } else if (!wsId && !part.includes('=')) {
        try {
          wsId = decodeURIComponent(part);
        } catch (_) {
          wsId = part;
        }
      }
    }

    return {
      tabId,
      panelId: panelId || (wsId ? 'panel-files' : null),
      workspaceId: wsId ? wsId.trim().normalize('NFC') : null,
    };
  };

  // 6. Определение активного пространства из конфига и URL стандартов workspace-url-routing
  const parsedUrl = parseWorkspaceUrlComponents(typeof location !== 'undefined' ? location.hash : '');
  let initialTabId = parsedUrl.tabId || 'tab-workspace';
  let targetWsId = parsedUrl.workspaceId;
  const targetPanelId = parsedUrl.panelId || 'panel-files';

  // 6.1 Если в URL рабочее пространство не указано — читаем последнее открытое из конфига на сервере
  if (!targetWsId) {
    try {
      const activeRes = await fetch('/api/v1/workspaces/active');
      if (activeRes.ok) {
        const activeData = await activeRes.json();
        if (activeData && activeData.workspace_id) {
          targetWsId = activeData.workspace_id;
        }
      }
    } catch (err) {
      console.warn('[Main] Ошибка получения активного рабочего пространства из конфига:', err);
    }
  }

  // 6.2 Если в конфиге нет последнего открытого пространства — сразу открываем мастер создания нового пространства
  if (!targetWsId) {
    initialTabId = 'tab-create-workspace';
    targetWsId = null;
    if (typeof history !== 'undefined' && history.replaceState) {
      history.replaceState(null, null, '#tab-create-workspace');
    }
  }

  const rawTabName = initialTabId.startsWith('tab-') ? initialTabId.slice(4) : initialTabId;

  // 7. Загрузка исключительно целевой активной вкладки
  await lazyLoad(rawTabName);
  applyTranslations();
  await switchMainTab(initialTabId);

  // 8. Если определен идентификатор рабочего пространства
  if (targetWsId) {
    if (typeof window.switchWorkspaceSubTab === 'function') {
      window.switchWorkspaceSubTab(targetPanelId, false);
    }
    await updateTopWorkspaceDropdown(targetWsId);
    highlightActiveDrawerWorkspace(targetWsId);
  }

  // 9. Реакция на изменение URL хэша пользователем или историей браузера
  window.addEventListener('hashchange', async () => {
    const parsed = parseWorkspaceUrlComponents(typeof location !== 'undefined' ? location.hash : '');
    const curTab = parsed.tabId;
    if (curTab) {
      await switchMainTab(curTab);
    }
    if (curTab === 'tab-workspace' || curTab === 'workspace') {
      if (parsed.workspaceId) {
        if (typeof window.selectWorkspaceInTab === 'function') {
          await window.selectWorkspaceInTab(parsed.workspaceId);
        }
        if (typeof window.switchWorkspaceSubTab === 'function' && parsed.panelId) {
          window.switchWorkspaceSubTab(parsed.panelId, false);
        }
        await updateTopWorkspaceDropdown(parsed.workspaceId);
        highlightActiveDrawerWorkspace(parsed.workspaceId);
      }
    }
  });
  // 10. Навигация на главную страницу при клике по брендингу (#app-brand-link)
  const brandLink = document.getElementById('app-brand-link');
  if (brandLink) {
    brandLink.addEventListener('click', (e) => {
      if (e.ctrlKey || e.metaKey || e.shiftKey || e.button !== 0) return;
      e.preventDefault();
      if (typeof location !== 'undefined' && location.hash) {
        history.pushState(null, '', location.pathname);
      }
      switchMainTab('tab-workspace');
    });
  }
}

document.readyState === 'loading'
  ? document.addEventListener('DOMContentLoaded', init)
  : init();
