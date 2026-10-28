/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - WikiLLM Tab Orchestrator
 * =============================================================================
 * Description:
 *   Главный оркестратор вкладки tab_wikillm.
 *   Координирует жизненный цикл и панель panel_wikillm.
 *
 * File: main.js
 * Package: apps/ai_assistant/api/webgui/tab_wikillm
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-17 00:50:00
 * =============================================================================
 */

import { initWikiLLMPanel } from './panel_wikillm/panel.js';

export function init() {
  initWikiLLMPanel();
}

window.initWikiLLMTab = init;

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
