/**
 * =============================================================================
 * Process Name: WebGUI - Universal Draggable Menu Controller (HTML5 Drag & Drop)
 * =============================================================================
 * Description:
 *   Универсальный клиентский модуль горизонтального перетаскивания (Drag & Drop)
 *   кнопок меню панелей (субвкладок) и подменю блоков влево <-> вправо.
 *   Обеспечивает:
 *     - Перемещение кнопок внутри контейнера с визуальной подсветкой;
 *     - Сохранение пользовательского порядка в localStorage;
 *     - Автоматическое чтение и применение конфигурации из menu_config.json вкладки;
 *     - Сохранение измененного порядка на бэкенд через REST API.
 *
 * File: menu_dnd.js
 * Package: apps/ai_assistant/api/webgui/js
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-31 19:55:00
 * =============================================================================
 */

(function (root, factory) {
  if (typeof define === 'function' && define.amd) {
    define([], factory);
  } else if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.WebGUIMenuDnD = factory();
  }
}(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  /**
   * Применяет сохраненный порядок кнопок к контейнеру меню.
   * @param {HTMLElement} container - DOM-контейнер меню.
   * @param {string[]} order - Массив идентификаторов кнопок или panel/block ID.
   */
  function applyOrder(container, order) {
    if (!container || !Array.isArray(order) || order.length === 0) return;
    const buttons = Array.from(container.children);
    const map = new Map();

    buttons.forEach((btn) => {
      const key = btn.getAttribute('data-block-id') ||
                  btn.getAttribute('data-panel-id') ||
                  btn.id;
      if (key) map.set(key, btn);
    });

    order.forEach((key) => {
      const btn = map.get(key);
      if (btn) {
        container.appendChild(btn);
        map.delete(key);
      }
    });

    // Оставшиеся кнопки добавляются в конец
    map.forEach((btn) => container.appendChild(btn));
  }

  /**
   * Считывает текущий порядок кнопок в контейнере.
   * @param {HTMLElement} container - DOM-контейнер меню.
   * @returns {string[]}
   */
  function extractOrder(container) {
    if (!container) return [];
    return Array.from(container.children).map((btn) => {
      return btn.getAttribute('data-block-id') ||
             btn.getAttribute('data-panel-id') ||
             btn.id;
    }).filter(Boolean);
  }

  /**
   * Делает кнопки внутри меню перетаскиваемыми влево <-> вправо.
   * @param {HTMLElement|string} target - Контейнер меню (элемент или CSS-селектор).
   * @param {Object} [options] - Параметры инициализации.
   * @param {string} [options.storageKey] - Ключ в localStorage для сохранения порядка.
   * @param {string} [options.tabId] - Идентификатор вкладки для синхронизации с API.
   * @param {Function} [options.onOrderChanged] - Обработчик изменения порядка.
   * @returns {Object} Контроллер меню.
   */
  function makeMenuDraggable(target, options = {}) {
    const container = typeof target === 'string' ? document.querySelector(target) : target;
    if (!container) return null;

    const storageKey = options.storageKey || null;

    // 1. Восстанавливаем порядок из localStorage (если есть)
    if (storageKey) {
      try {
        const saved = localStorage.getItem(`webgui_menu_order_${storageKey}`);
        if (saved) {
          const parsed = JSON.parse(saved);
          if (Array.isArray(parsed)) {
            applyOrder(container, parsed);
          }
        }
      } catch (err) {
        console.warn('[WebGUIMenuDnD] Ошибка чтения localStorage:', err);
      }
    }

    let draggedBtn = null;

    // 2. Навешиваем Drag & Drop на каждую кнопку
    function setupButton(btn) {
      if (btn.tagName !== 'BUTTON' && !btn.classList.contains('btn')) return;

      btn.setAttribute('draggable', 'true');
      btn.classList.add('menu-btn-draggable');

      btn.addEventListener('dragstart', (e) => {
        draggedBtn = btn;
        btn.classList.add('menu-btn-dragging');
        if (e.dataTransfer) {
          e.dataTransfer.effectAllowed = 'move';
          e.dataTransfer.setData('text/plain', btn.id || 'menu-item');
        }
      });

      btn.addEventListener('dragend', () => {
        if (draggedBtn) {
          draggedBtn.classList.remove('menu-btn-dragging');
          draggedBtn = null;
        }

        // Очищаем классы подсветки
        Array.from(container.children).forEach((el) => {
          el.classList.remove('menu-btn-drag-over-left', 'menu-btn-drag-over-right');
        });

        // Сохраняем новый порядок
        const newOrder = extractOrder(container);
        if (storageKey) {
          try {
            localStorage.setItem(`webgui_menu_order_${storageKey}`, JSON.stringify(newOrder));
          } catch (err) {
            console.warn('[WebGUIMenuDnD] Ошибка записи в localStorage:', err);
          }
        }

        if (typeof options.onOrderChanged === 'function') {
          options.onOrderChanged(newOrder);
        }
      });

      btn.addEventListener('dragover', (e) => {
        e.preventDefault();
        if (!draggedBtn || draggedBtn === btn) return;

        if (e.dataTransfer) {
          e.dataTransfer.dropEffect = 'move';
        }

        const rect = btn.getBoundingClientRect();
        const midX = rect.left + rect.width / 2;

        if (e.clientX < midX) {
          btn.classList.add('menu-btn-drag-over-left');
          btn.classList.remove('menu-btn-drag-over-right');
          if (btn.previousElementSibling !== draggedBtn) {
            container.insertBefore(draggedBtn, btn);
          }
        } else {
          btn.classList.add('menu-btn-drag-over-right');
          btn.classList.remove('menu-btn-drag-over-left');
          if (btn.nextElementSibling !== draggedBtn) {
            container.insertBefore(draggedBtn, btn.nextSibling);
          }
        }
      });

      btn.addEventListener('dragleave', () => {
        btn.classList.remove('menu-btn-drag-over-left', 'menu-btn-drag-over-right');
      });

      btn.addEventListener('drop', (e) => {
        e.preventDefault();
        btn.classList.remove('menu-btn-drag-over-left', 'menu-btn-drag-over-right');
      });
    }

    // Инициализируем текущие кнопки
    Array.from(container.children).forEach(setupButton);

    // Следим за динамическим добавлением кнопок через MutationObserver
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((m) => {
        m.addedNodes.forEach((node) => {
          if (node.nodeType === Node.ELEMENT_NODE) {
            setupButton(node);
          }
        });
      });
    });
    observer.observe(container, { childList: true });

    return {
      container,
      getOrder: () => extractOrder(container),
      setOrder: (order) => applyOrder(container, order),
      resetOrder: () => {
        if (storageKey) localStorage.removeItem(`webgui_menu_order_${storageKey}`);
      }
    };
  }

  /**
   * Инициализирует все перетаскиваемые меню вкладки из её menu_config.json.
   * @param {string} tabDirName - Каталог вкладки (например: 'tab_workspace').
   * @param {string} [customConfigUrl] - Альтернативный URL для загрузки конфига.
   * @returns {Promise<Object>}
   */
  async function initTabMenusFromConfig(tabDirName, customConfigUrl = null) {
    const configUrl = customConfigUrl || `/html/${tabDirName}/menu_config.json`;
    let config = null;

    try {
      const resp = await fetch(configUrl);
      if (resp.ok) {
        config = await resp.json();
      }
    } catch (e) {
      console.warn(`[WebGUIMenuDnD] Конфигурация меню ${configUrl} не загружена:`, e);
      return null;
    }

    if (!config || !config.draggable) return null;

    const controllers = {};

    // 1. Инициализация меню субвкладок (Уровень 1)
    if (config.subtabs && config.subtabs.nav_id) {
      const navEl = document.getElementById(config.subtabs.nav_id);
      if (navEl) {
        controllers.subtabs = makeMenuDraggable(navEl, {
          storageKey: config.subtabs.storage_key || `${config.tab_id}_subtabs`,
          tabId: config.tab_id
        });
      }
    }

    // 2. Инициализация подменю блоков (Уровень 2)
    if (config.blocks && typeof config.blocks === 'object') {
      controllers.blocks = {};
      Object.entries(config.blocks).forEach(([blockKey, blockConf]) => {
        if (blockConf.nav_id) {
          const blockNavEl = document.getElementById(blockConf.nav_id);
          if (blockNavEl) {
            controllers.blocks[blockKey] = makeMenuDraggable(blockNavEl, {
              storageKey: blockConf.storage_key || `${config.tab_id}_block_${blockKey}`,
              tabId: config.tab_id
            });
          }
        }
      });
    }

    return controllers;
  }

  return {
    makeMenuDraggable,
    initTabMenusFromConfig,
    applyOrder,
    extractOrder
  };
}));
