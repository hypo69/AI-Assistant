/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - WikiLLM Panel
 * =============================================================================
 * Description:
 *   Изолированная панель базы знаний WikiLLM (panel-wikillm-entities).
 *   Отображает архитектурные сущности, типы связей (modifies, fixes, documents),
 *   степень доверия и провенанс.
 *
 * File: panel.js
 * Package: apps/ai_assistant/api/webgui/tab_wikillm/panel_wikillm
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-17 00:50:00
 * =============================================================================
 */

import { registerPanelRenderer, loadPanelData } from '../../js/panel-loader.js';

export function renderWikiLLMPanel(result, panelEl) {
  const tbody = document.getElementById('wikillm-table-body');
  const countBadge = document.getElementById('wikillm-count-badge');
  if (!tbody) return;

  const data = result?.data || [];
  if (countBadge) countBadge.textContent = `${data.length} связей`;

  if (data.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" class="text-center py-3 text-muted">Связи WikiLLM отсутствуют. Используйте 2-Step Аннотацию для создания.</td></tr>`;
    return;
  }

  tbody.innerHTML = data.map(item => {
    const src = `${item.source_type || ''}:${item.source_id || ''}`;
    const rel = item.relation_type || 'relates';
    const tgt = `${item.target_type || ''}:${item.target_id || ''}`;
    const conf = typeof item.confidence === 'number' ? (item.confidence * 100).toFixed(0) + '%' : '100%';
    const prov = `${item.provenance || 'auto'} • ${(item.created_at || '').slice(0, 19).replace('T', ' ')}`;

    return `
      <tr>
        <td><span class="badge bg-secondary-subtle text-secondary border font-monospace">${src}</span></td>
        <td><span class="badge bg-info-subtle text-info border">${rel}</span></td>
        <td><span class="fw-medium">${tgt}</span></td>
        <td><span class="badge bg-success-subtle text-success border">${conf}</span></td>
        <td class="small text-muted">${prov}</td>
      </tr>
    `;
  }).join('');
}

export function initWikiLLMPanel() {
  registerPanelRenderer('panel-wikillm-entities', renderWikiLLMPanel);

  document.getElementById('wikillm-refresh-btn')?.addEventListener('click', () => {
    loadPanelData('panel-wikillm-entities', { force: true });
  });

  loadPanelData('panel-wikillm-entities');
}
