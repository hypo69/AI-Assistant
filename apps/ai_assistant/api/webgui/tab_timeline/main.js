/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Timeline Tab Orchestrator
 * =============================================================================
 * Description:
 *   Главный оркестратор вкладки tab_timeline.
 *   Координирует жизненный цикл и панель panel_timeline.
 *
 * File: main.js
 * Package: apps/ai_assistant/api/webgui/tab_timeline
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-17 00:46:00
 * =============================================================================
 */

import { initTimelinePanel } from './panel_timeline/panel.js';

export function init() {
  initTimelinePanel();
}

window.initTimelineTab = init;

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
