/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - User Space RAG Panel
 * =============================================================================
 * Description:
 *   Изолированная панель RAG и семантического поиска (panel-rag-chunks).
 *   Отображает индексированные чанки документов рабочей области пользователя,
 *   управляет 5-этапным поиском (/api/v1/query) и синтезом ответов по базе знаний.
 *
 * File: panel.js
 * Package: apps/ai_assistant/api/webgui/tab_rag/panel_rag
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-23 19:20:00
 * =============================================================================
 */

import { registerPanelRenderer, loadPanelData } from '../../js/panel-loader.js';

let currentWorkspaceId = 'default';

/**
 * Отрисовывает таблицу индексированных чанков рабочей области.
 * @param {object} result - Ответ API со списком чанков
 * @param {HTMLElement} panelEl - Элемент контейнера панели
 */
export function renderRagChunksPanel(result, panelEl) {
  const tbody = document.getElementById('rag-chunks-table-body');
  const countBadge = document.getElementById('rag-chunks-count-badge');
  if (!tbody) return;

  const data = result?.data || [];
  if (countBadge) countBadge.textContent = `${data.length} чанков`;

  if (data.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="6" class="text-center py-4 text-muted">
          <div><i class="bi bi-info-circle me-1"></i>В базе знаний текущей рабочей области нет проиндексированных фрагментов.</div>
          <div class="small mt-1">Добавьте документы или файлы во вкладке «Рабочие пространства» для автоматической индексации.</div>
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = data.map((item) => {
    const cid = (item.chunk_id || '').slice(0, 8);
    const doc = item.document_id || item.file_path || '---';
    const sIdx = item.sentence_index !== undefined ? item.sentence_index : '—';
    const lang = item.language || 'ru';
    const sha = (item.sha256 || '---').slice(0, 10);
    const text = item.content_preview || item.text || '';

    return `
      <tr>
        <td><span class="badge bg-secondary-subtle text-secondary border font-monospace">${cid}</span></td>
        <td class="text-truncate" style="max-width: 180px;" title="${doc}">
          <i class="bi bi-file-text me-1 text-primary"></i>${doc}
        </td>
        <td><span class="badge bg-light text-dark border">#${sIdx}</span></td>
        <td><span class="badge bg-info-subtle text-info border">${lang.toUpperCase()}</span></td>
        <td><span class="font-monospace text-muted small">${sha}</span></td>
        <td class="text-muted text-truncate" style="max-width: 380px;" title="${text}">${text}</td>
      </tr>
    `;
  }).join('');
}

/**
 * Загружает список доступных рабочих пространств в селектор вкладки.
 */
export async function loadWorkspacesList() {
  const select = document.getElementById('rag-workspace-select');
  if (!select) return;

  try {
    const [wsRes, activeRes] = await Promise.all([
      fetch('/api/v1/workspaces').then((r) => (r.ok ? r.json() : { workspaces: [] })),
      fetch('/api/v1/workspaces/active').then((r) => (r.ok ? r.json() : {})),
    ]);

    const workspaces = wsRes.workspaces || [];
    const activeWs = activeRes.workspace_id || (typeof window.getActiveWorkspaceId === 'function' ? window.getActiveWorkspaceId() : '') || 'default';

    if (workspaces.length > 0) {
      select.innerHTML = workspaces
        .map(
          (w) => `
        <option value="${w.workspace_id}" ${w.workspace_id === activeWs ? 'selected' : ''}>
          ${w.name || w.workspace_id} (${w.workspace_id})
        </option>
      `
        )
        .join('');
    } else {
      select.innerHTML = `<option value="default" selected>default</option>`;
    }

    currentWorkspaceId = select.value || activeWs || 'default';
  } catch (err) {
    console.warn('[RAG Tab] Ошибка загрузки списка рабочих областей:', err);
  }
}

/**
 * Выполняет 5-этапный гибридный поиск по пользовательскому пространству.
 * @param {string} query - Вопрос или поисковый запрос
 */
export async function executeHybridSearch(query) {
  const card = document.getElementById('rag-results-card');
  const answerEl = document.getElementById('rag-answer-text');
  const factContainer = document.getElementById('rag-matched-fact-container');
  const factText = document.getElementById('rag-matched-fact-text');
  const evidenceList = document.getElementById('rag-evidence-list');
  const faissContainer = document.getElementById('rag-faiss-container');
  const faissList = document.getElementById('rag-faiss-hits-list');
  const quickBox = document.getElementById('rag-quick-questions');
  const statusText = document.getElementById('rag-search-status-text');
  const countBadge = document.getElementById('rag-results-count-badge');
  const latencyBadge = document.getElementById('rag-latency-badge');
  const select = document.getElementById('rag-workspace-select');

  const wsId = select?.value || currentWorkspaceId || 'default';

  if (!card || !answerEl) return;
  card.classList.remove('d-none');
  answerEl.innerHTML = '<div class="spinner-border spinner-border-sm text-primary me-2"></div> Выполняется 5-этапный поиск в базе знаний (NLP + SQLite + FAISS + LLM)...';
  if (factContainer) factContainer.classList.add('d-none');
  if (evidenceList) evidenceList.innerHTML = '';
  if (faissContainer) faissContainer.classList.add('d-none');
  if (quickBox) quickBox.innerHTML = '';
  if (statusText) {
    statusText.textContent = 'Обработка RAG-конвейера...';
    statusText.className = 'badge bg-warning-subtle text-warning border';
  }

  try {
    const res = await fetch('/api/v1/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: query, workspace_id: wsId, top_k: 5 }),
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    // 1. Синтезированный ответ
    answerEl.textContent = data.explanation || data.answer || 'Ответ сформирован на основе базы знаний.';
    if (statusText) {
      statusText.textContent = 'Готово';
      statusText.className = 'badge bg-success-subtle text-success border';
    }

    // 2. Время выполнения
    const latency = data.processing?.latency_ms !== undefined ? `${data.processing.latency_ms} ms` : '—';
    if (latencyBadge) latencyBadge.textContent = latency;

    // 3. Структурированный факт
    if (data.matched_fact && factContainer && factText) {
      factContainer.classList.remove('d-none');
      const mf = data.matched_fact;
      const subj = mf.subject?.text || mf.owner?.text || '—';
      const pred = mf.predicate?.verb_form || mf.predicate?.lemma || mf.relation || '—';
      const obj = mf.object?.text || mf.possessed_entity?.text || '—';
      factText.innerHTML = `<strong>Субъект:</strong> [${subj}] &nbsp;→&nbsp; <strong>Действие/Отношение:</strong> [${pred}] &nbsp;→&nbsp; <strong>Объект:</strong> [${obj}]`;
    }

    // 4. Доказательная база первоисточников
    const sources = data.sources || data.evidence || [];
    if (countBadge) countBadge.textContent = `${sources.length} источников`;

    if (evidenceList) {
      if (sources.length === 0) {
        evidenceList.innerHTML = '<div class="small text-muted">Прямые цитаты документов не найдены.</div>';
      } else {
        evidenceList.innerHTML = sources
          .map(
            (s) => `
          <div class="p-2 rounded bg-body-tertiary border d-flex flex-column gap-1 small">
            <div class="d-flex align-items-center justify-content-between">
              <div>
                <span class="badge bg-secondary-subtle text-secondary border font-monospace me-1">
                  <i class="bi bi-file-earmark-text me-1"></i>${s.document_id || 'Документ'}
                </span>
                ${s.sentence_index !== undefined ? `<span class="badge bg-light text-dark border me-1">Предл. #${s.sentence_index}</span>` : ''}
              </div>
              ${s.score !== undefined ? `<span class="badge bg-primary-subtle text-primary border">Релевантность: ${s.score}</span>` : ''}
            </div>
            ${s.quote ? `<div class="text-secondary fst-italic ps-2 border-start border-2 border-primary">«${s.quote}»</div>` : ''}
          </div>
        `
          )
          .join('');
      }
    }

    // 5. Векторные совпадения FAISS
    const faissHits = data.faiss_hits || [];
    if (faissHits.length > 0 && faissContainer && faissList) {
      faissContainer.classList.remove('d-none');
      faissList.innerHTML = faissHits
        .map(
          (h) => `
        <div class="p-2 rounded bg-light border small text-truncate">
          <span class="badge bg-success-subtle text-success border me-2">FAISS Hit</span>
          <span class="text-secondary">${h.text || h.content || JSON.stringify(h)}</span>
        </div>
      `
        )
        .join('');
    }

    // 6. Быстрые вопросы
    if (quickBox && Array.isArray(data.suggested_quick_questions)) {
      quickBox.innerHTML = data.suggested_quick_questions
        .map(
          (q) => `
        <button class="btn btn-sm btn-outline-secondary py-1 px-2 rag-quick-q-btn" data-q="${q}">
          <i class="bi bi-arrow-right-short me-1"></i>${q}
        </button>
      `
        )
        .join('');

      quickBox.querySelectorAll('.rag-quick-q-btn').forEach((btn) => {
        btn.addEventListener('click', (e) => {
          const q = e.currentTarget.getAttribute('data-q');
          const input = document.getElementById('rag-search-input');
          if (input) input.value = q;
          executeHybridSearch(q);
        });
      });
    }
  } catch (err) {
    answerEl.textContent = `Ошибка RAG-поиска: ${err.message}`;
    if (statusText) {
      statusText.textContent = 'Ошибка';
      statusText.className = 'badge bg-danger-subtle text-danger border';
    }
  }
}

/**
 * Инициализирует панель RAG и регистрирует обработчики событий.
 */
export function initRagPanel() {
  registerPanelRenderer('panel-rag-chunks', renderRagChunksPanel);

  // Загружаем список рабочих областей
  loadWorkspacesList();

  const select = document.getElementById('rag-workspace-select');
  select?.addEventListener('change', (e) => {
    currentWorkspaceId = e.target.value;
    loadPanelData('panel-rag-chunks', { workspace_id: currentWorkspaceId, force: true });
  });

  document.getElementById('rag-refresh-btn')?.addEventListener('click', () => {
    loadWorkspacesList().then(() => {
      loadPanelData('panel-rag-chunks', { workspace_id: currentWorkspaceId, force: true });
    });
  });

  document.getElementById('rag-execute-search-btn')?.addEventListener('click', () => {
    const q = document.getElementById('rag-search-input')?.value.trim();
    if (q) executeHybridSearch(q);
  });

  document.getElementById('rag-search-input')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      const q = e.target.value.trim();
      if (q) executeHybridSearch(q);
    }
  });

  loadPanelData('panel-rag-chunks', { workspace_id: currentWorkspaceId });
}
