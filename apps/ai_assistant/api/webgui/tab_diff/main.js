/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Diff Tab Orchestrator
 * =============================================================================
 * Description:
 *   Главный оркестратор вкладки tab_diff.
 *   Координирует жизненный цикл и панель panel_diff_stats.
 *
 * File: main.js
 * Package: apps/ai_assistant/api/webgui/tab_diff
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-17 00:47:00
 * =============================================================================
 */

import { initDiffStatsPanel } from './panel_diff_stats/panel.js';

export function init() {
  initDiffStatsPanel();
}

window.initDiffTab = init;

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
