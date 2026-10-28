/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Status Tab Orchestrator
 * =============================================================================
 * Description:
 *   Главный оркестратор вкладки tab_status.
 *   Координирует жизненный цикл и панель panel_status.
 *
 * File: main.js
 * Package: apps/ai_assistant/api/webgui/tab_status
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-17 00:49:00
 * =============================================================================
 */

import { initStatusPanel } from './panel_status/panel.js';

export function init() {
  initStatusPanel();
}

window.initStatusTab = init;

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
