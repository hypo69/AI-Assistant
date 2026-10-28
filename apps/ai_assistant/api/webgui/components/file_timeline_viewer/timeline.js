// =============================================================================
// Process Name: AI-Windows-Admin Apps AI_Assistant - File Timeline Viewer Component
// Updated: 2026-10-15 09:00:00
// =============================================================================

/**
 * Отрисовывает хронологическую шкалу контрольных точек изменений файла.
 * @param {HTMLElement} container - Элемент контейнера списка таймлайна.
 * @param {Array} checkpoints - Массив контрольных точек таймлайна.
 * @param {Function} onSelectCommit - Колбэк при клике на контрольную точку.
 */
export function renderTimeline(container, checkpoints, onSelectCommit) {
    if (!checkpoints || checkpoints.length === 0) {
        container.innerHTML = '<div class="empty-state">История изменений для указанного файла не найдена.</div>';
        return;
    }

    container.innerHTML = '';
    checkpoints.forEach((cp) => {
        const item = document.createElement('div');
        item.className = 'timeline-item';
        item.dataset.hash = cp.commit_hash;

        item.innerHTML = `
            <div class="timeline-node"></div>
            <div class="timeline-content">
                <div class="timeline-header">
                    <span class="commit-hash">${cp.commit_hash.slice(0, 8)}</span>
                    <span class="commit-time">${new Date(cp.timestamp).toLocaleString('ru-RU')}</span>
                </div>
                <div class="commit-message">${escapeHtml(cp.message)}</div>
                <div class="commit-meta">
                    <span>👤 ${escapeHtml(cp.author)}</span>
                    <span>📝 Добавлено: +${cp.insertions || 0} / Удалено: -${cp.deletions || 0}</span>
                </div>
            </div>
        `;

        item.addEventListener('click', () => {
            document.querySelectorAll('.timeline-item').forEach(el => el.classList.remove('active'));
            item.classList.add('active');
            if (typeof onSelectCommit === 'function') {
                onSelectCommit(cp);
            }
        });

        container.appendChild(item);
    });
}

function escapeHtml(text) {
    if (!text) return '';
    return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
