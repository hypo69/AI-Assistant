/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Status Panel
 * =============================================================================
 * Description:
 *   Изолированная панель статуса системы (panel-system-status).
 *   Отображает здоровье подсистем: Git, WikiLLM, темпорального графа и векторного RAG.
 *
 * File: panel.js
 * Package: apps/ai_assistant/api/webgui/tab_status/panel_status
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-17 00:48:00
 * =============================================================================
 */

import { registerPanelRenderer, loadPanelData } from '../../js/panel-loader.js';

export function renderStatusPanel(result, panelEl) {
  const tbody = document.getElementById('status-table-body');
  const summaryBadge = document.getElementById('status-summary-badge');
  if (!tbody) return;

  const data = result?.data || [];
  const allReady = data.every(d => d.is_ready);

  if (summaryBadge) {
    summaryBadge.textContent = allReady ? 'Все модули в строю (ONLINE)' : 'Обнаружены недоступные модули';
    summaryBadge.className = allReady ? 'badge bg-success-subtle text-success border' : 'badge bg-danger-subtle text-danger border';
  }

  if (data.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4" class="text-center py-3 text-muted">Сведения о статусе отсутствуют.</td></tr>`;
    return;
  }

  tbody.innerHTML = data.map(item => {
    const isReady = item.is_ready;
    const badgeClass = isReady ? 'bg-success' : 'bg-danger';
    const statusText = isReady ? 'ГОТОВ' : 'НЕ ДОСТУПЕН';
    const time = (item.last_checked_at || '').slice(0, 19).replace('T', ' ');

    return `
      <tr>
        <td class="fw-semibold">${item.module_name}</td>
        <td><span class="badge ${badgeClass}">${statusText}</span></td>
        <td class="small font-monospace text-muted">${item.details}</td>
        <td class="text-end small font-monospace text-muted">${time}</td>
      </tr>
    `;
  }).join('');
}

export function initStatusPanel() {
  registerPanelRenderer('panel-system-status', renderStatusPanel);

  document.getElementById('status-refresh-btn')?.addEventListener('click', () => {
    loadPanelData('panel-system-status', { force: true });
  });

  loadPanelData('panel-system-status');
}
