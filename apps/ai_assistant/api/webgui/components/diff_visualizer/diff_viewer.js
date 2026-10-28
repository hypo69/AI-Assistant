// =============================================================================
// Process Name: AI-Windows-Admin Apps AI_Assistant - Diff Visualizer Component
// Updated: 2026-10-15 09:05:00
// =============================================================================

/**
 * Отрисовывает подсветку diff текста с выделением добавленных, удаленных и hunk-строк.
 * @param {HTMLElement} codeElement - Элемент <pre><code> для вставки форматированного diff.
 * @param {string} diffText - Исходный текст git diff.
 */
export function renderDiff(codeElement, diffText) {
    if (!diffText || diffText.trim() === '') {
        codeElement.innerHTML = '<span class="empty-state">Изменения отсутствуют или файл не модифицирован в этой ревизии.</span>';
        return;
    }

    const lines = diffText.split('\n');
    const formattedHtml = lines.map(line => {
        const escaped = escapeHtml(line);
        if (line.startsWith('@@')) {
            return `<span class="diff-line-hunk">${escaped}</span>`;
        } else if (line.startsWith('+') && !line.startsWith('+++')) {
            return `<span class="diff-line-add">${escaped}</span>`;
        } else if (line.startsWith('-') && !line.startsWith('---')) {
            return `<span class="diff-line-del">${escaped}</span>`;
        }
        return `<span>${escaped}</span>`;
    }).join('\n');

    codeElement.innerHTML = formattedHtml;
}

function escapeHtml(text) {
    if (!text) return '';
    return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
