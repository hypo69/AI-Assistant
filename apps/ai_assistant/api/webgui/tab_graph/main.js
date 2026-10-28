/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Graph Tab Orchestrator
 * =============================================================================
 * Description:
 *   Главный оркестратор вкладки tab_graph.
 *   Координирует жизненный цикл и панель panel_graph.
 *
 * File: main.js
 * Package: apps/ai_assistant/api/webgui/tab_graph
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-17 00:47:00
 * =============================================================================
 */

import { initGraphPanel } from './panel_graph/panel.js';

export function init() {
  initGraphPanel();
}

window.initGraphTab = init;

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
