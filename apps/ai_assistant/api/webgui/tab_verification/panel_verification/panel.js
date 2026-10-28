/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Verification Panel
 * =============================================================================
 * Description:
 *   Изолированная панель контура верификации (panel-verification-pipeline).
 *   Отображает аудит безопасности: фильтрация инъекций, секреты, валидация фактов.
 *
 * File: panel.js
 * Package: apps/ai_assistant/api/webgui/tab_verification/panel_verification
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-17 00:49:00
 * =============================================================================
 */

import { registerPanelRenderer, loadPanelData } from '../../js/panel-loader.js';

export function renderVerificationPanel(result, panelEl) {
  const tbody = document.getElementById('verification-table-body');
  const statusBadge = document.getElementById('verification-status-badge');
  if (!tbody) return;

  const data = result?.data || [];
  const allPass = data.every(d => d.status === 'PASS');

  if (statusBadge) {
    statusBadge.textContent = allPass ? 'Все проверки пройдены (PASS)' : 'Обнаружены предупреждения';
    statusBadge.className = allPass ? 'badge bg-success-subtle text-success border' : 'badge bg-warning-subtle text-warning border';
  }

  if (data.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4" class="text-center py-3 text-muted">Журнал проверок пуст.</td></tr>`;
    return;
  }

  tbody.innerHTML = data.map(item => {
    const isPass = item.status === 'PASS';
    const badgeClass = isPass ? 'bg-success' : 'bg-warning text-dark';
    const time = (item.timestamp || '').slice(0, 19).replace('T', ' ');

    return `
      <tr>
        <td class="font-monospace fw-medium">${item.check_name}</td>
        <td><span class="badge ${badgeClass}">${item.status}</span></td>
        <td class="small text-muted">${item.details}</td>
        <td class="text-end small font-monospace text-muted">${time}</td>
      </tr>
    `;
  }).join('');
}

export function initVerificationPanel() {
  registerPanelRenderer('panel-verification-pipeline', renderVerificationPanel);

  document.getElementById('verification-refresh-btn')?.addEventListener('click', () => {
    loadPanelData('panel-verification-pipeline', { force: true });
  });

  loadPanelData('panel-verification-pipeline');
}
