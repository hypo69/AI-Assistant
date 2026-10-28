/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Verification Tab Orchestrator
 * =============================================================================
 * Description:
 *   Главный оркестратор вкладки tab_verification.
 *   Координирует жизненный цикл и панель panel_verification.
 *
 * File: main.js
 * Package: apps/ai_assistant/api/webgui/tab_verification
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-17 00:49:00
 * =============================================================================
 */

import { initVerificationPanel } from './panel_verification/panel.js';

export function init() {
  initVerificationPanel();
}

window.initVerificationTab = init;

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
