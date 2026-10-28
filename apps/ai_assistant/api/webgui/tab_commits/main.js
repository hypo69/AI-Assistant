/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Commits Tab Orchestrator
 * =============================================================================
 * Description:
 *   Главный оркестратор вкладки tab_commits.
 *   Координирует жизненный цикл и панель panel_commits.
 *
 * File: main.js
 * Package: apps/ai_assistant/api/webgui/tab_commits
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-17 00:46:00
 * =============================================================================
 */

import { initCommitsPanel } from './panel_commits/panel.js';

export function init() {
  initCommitsPanel();
}

window.initCommitsTab = init;

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
