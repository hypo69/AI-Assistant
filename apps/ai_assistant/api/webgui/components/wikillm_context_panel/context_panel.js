// =============================================================================
// Process Name: AI-Windows-Admin Apps AI_Assistant - WikiLLM Context Panel Component
// Updated: 2026-10-15 09:10:00
// =============================================================================

/**
 * Отрисовывает архитектурные сущности WikiLLM.
 * @param {HTMLElement} container - Элемент контейнера сущностей.
 * @param {Array} entities - Список сущностей.
 */
export function renderWikiEntities(container, entities) {
    if (!entities || entities.length === 0) {
        container.innerHTML = '<div class="empty-state">Связанные статьи и сущности WikiLLM не найдены.</div>';
        return;
    }

    container.innerHTML = '';
    entities.forEach(ent => {
        const item = document.createElement('div');
        item.className = 'timeline-item';
        item.innerHTML = `
            <div class="timeline-content">
                <div class="timeline-header">
                    <span class="commit-hash">${escapeHtml(ent.canonical_key || ent.entity_id || '')}</span>
                    <span class="commit-time">${escapeHtml(ent.entity_type || ent.type || 'Концепт')}</span>
                </div>
                <div class="commit-message"><strong>${escapeHtml(ent.name || ent.canonical_key)}</strong></div>
                <div class="commit-meta">${escapeHtml(ent.summary || 'Описание отсутствует')}</div>
            </div>
        `;
        container.appendChild(item);
    });
}

/**
 * Отрисовывает темпоральные связи EvidenceLink.
 * @param {HTMLElement} container - Элемент контейнера связей.
 * @param {Array} links - Массив объектов связей.
 * @param {Function} onSupersede - Колбэк для инвалидации связи.
 */
export function renderEvidenceLinks(container, links, onSupersede) {
    if (!links || links.length === 0) {
        container.innerHTML = '<div class="empty-state">Темпоральные связи графа отсутствуют.</div>';
        return;
    }

    container.innerHTML = '';
    links.forEach(l => {
        const item = document.createElement('div');
        item.className = 'timeline-item';
        const isSuperseded = l.status === 'SUPERSEDED' || Boolean(l.valid_to);
        const badgeClass = isSuperseded ? 'evidence-badge superseded' : 'evidence-badge active';
        const badgeLabel = isSuperseded ? 'SUPERSEDED' : 'ACTIVE';

        item.innerHTML = `
            <div class="timeline-content">
                <div class="timeline-header">
                    <span class="${badgeClass}">${badgeLabel}</span>
                    <span class="commit-time">${escapeHtml(l.relation_type)}</span>
                </div>
                <div class="commit-message">
                    <code>${escapeHtml(l.source_id)}</code> ➔ <code>${escapeHtml(l.target_id)}</code>
                </div>
                <div class="commit-meta">
                    <span>Окно: [${escapeHtml(l.valid_from)} ... ${l.valid_to ? escapeHtml(l.valid_to) : '∞'}]</span>
                    <span>Достоверность: ${(l.confidence * 100).toFixed(0)}%</span>
                </div>
                ${!isSuperseded ? `<button class="btn btn-sm btn-outline btn-supersede" style="margin-top: 8px;">Инвалидировать</button>` : ''}
            </div>
        `;

        const btnSupersede = item.querySelector('.btn-supersede');
        if (btnSupersede && typeof onSupersede === 'function') {
            btnSupersede.addEventListener('click', (e) => {
                e.stopPropagation();
                onSupersede(l);
            });
        }

        container.appendChild(item);
    });
}

function escapeHtml(text) {
    if (!text) return '';
    return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
