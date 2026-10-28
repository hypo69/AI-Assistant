/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - RAG Tab Orchestrator
 * =============================================================================
 * Description:
 *   Главный оркестратор вкладки tab_rag (User Space RAG).
 *   Координирует жизненный цикл, синхронизацию активной рабочей области
 *   и взаимодействие с панелью panel-rag-chunks.
 *
 * File: main.js
 * Package: apps/ai_assistant/api/webgui/tab_rag
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-23 19:20:00
 * =============================================================================
 */

import { initRagPanel, loadWorkspacesList } from './panel_rag/panel.js';
import { loadPanelData } from '../../js/panel-loader.js';

let initialized = false;

export function init() {
  if (initialized) return;
  initialized = true;

  initRagPanel();

  // Синхронизация при смене рабочей области через верхнее меню
  document.addEventListener('context:changed', (e) => {
    const wsId = e.detail?.workspace_id;
    if (wsId) {
      const select = document.getElementById('rag-workspace-select');
      if (select && select.value !== wsId) {
        select.value = wsId;
      }
      loadPanelData('panel-rag-chunks', { workspace_id: wsId, force: true });
    }
  });
}

window.initRagTab = init;

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
