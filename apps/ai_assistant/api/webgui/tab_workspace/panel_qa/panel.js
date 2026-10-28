/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - QA Search Panel
 * =============================================================================
 * Description:
 *   Панель интеллектуального вопрос-ответа и фактологического поиска (Шаг 3).
 *   Связывает ввод вопроса с контуром /api/v1/ask, отображает грамматический разбор,
 *   источники из Git и подтверждённые факты.
 *
 * File: panel.js
 * Package: apps/ai_assistant/api/webgui/tab_workspace/panel_qa
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-17 00:45:00
 * =============================================================================
 */

import { fetchJson } from '../common/ui_utils.js';

let currentWsId = 'default';

export async function executeAskQuestion(questionText = null, workspaceId = null) {
  if (workspaceId) currentWsId = workspaceId;
  const input = document.getElementById('qa-question-input');
  const q = (questionText !== null ? questionText : input?.value)?.trim();
  if (!q) return;
  if (input && questionText !== null) input.value = q;

  const mode = document.getElementById('qa-mode-selector')?.value || 'local_first';
  const modelRaw = document.getElementById('qa-model-selector')?.value || 'gemini|gemini-3.1-flash-lite';
  const [provider, model] = modelRaw.split('|');

  const statusInd = document.getElementById('qa-status-indicator');
  const ansBox = document.getElementById('qa-answer-box');
  const ansMain = document.getElementById('qa-answer-main-text');
  const ansBadges = document.getElementById('qa-answer-badges');
  const grammarBox = document.getElementById('qa-grammar-breakdown');
  const sourcesBox = document.getElementById('qa-sources-list');
  const jsonViewer = document.getElementById('ws-fact-json-viewer');

  if (statusInd) statusInd.textContent = 'Анализ вопроса и поиск фактов...';
  if (ansBox) ansBox.style.display = 'block';
  if (ansMain) ansMain.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Обработка...';

  try {
    const res = await fetchJson('/api/v1/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question: q,
        workspace_id: currentWsId,
        mode: mode,
        provider: provider,
        model: model,
      }),
    });

    if (ansMain) ansMain.textContent = res.answer || 'Нет ответа';
    if (statusInd) statusInd.textContent = `Выполнено за ${res.processing?.latency_ms || 0} мс`;

    if (ansBadges) {
      const gForm = res.grammatical_details?.grammatical_form || 'base';
      const cloudUsed = res.processing?.cloud_used ? '☁️ Облако (src/ai)' : '⚡ Локальный NLP + SQLite';
      ansBadges.innerHTML = `
        <span class="badge bg-primary-subtle text-primary border">Язык: ${res.language}</span>
        <span class="badge bg-success-subtle text-success border">Форма: ${gForm}</span>
        <span class="badge bg-info-subtle text-info border">${cloudUsed}</span>
        <span class="badge bg-secondary-subtle text-secondary border">${res.processing?.latency_ms || 0} мс</span>
      `;
    }

    if (grammarBox) {
      const gd = res.grammatical_details;
      const qa = res.question_analysis;
      if (gd) {
        grammarBox.innerHTML = `
          Тип вопроса: <code>${qa?.intent || ''}</code> |
          Целевая роль: <code>${qa?.target_role || ''}</code> |
          Каноническая сущность (лемма): <strong>${gd.canonical_entity || ''}</strong> |
          Исходная словоформа в тексте: <strong>${gd.surface_form || ''}</strong> &rarr;
          Форма ответа: <strong>${res.answer}</strong>
        `;
      } else {
        grammarBox.textContent = `Тип вопроса: ${qa?.intent || 'общий'} (${res.status})`;
      }
    }

    if (sourcesBox) {
      const srcs = res.sources || [];
      if (srcs.length === 0) {
        sourcesBox.innerHTML = '<span class="text-muted">Подтверждённых источников по данному вопросу не найдено.</span>';
      } else {
        sourcesBox.innerHTML = srcs.map(s => `
          <div class="p-1.5 px-2 rounded bg-body border d-flex flex-wrap align-items-center justify-content-between gap-2">
            <div>
              <i class="bi bi-file-earmark-check text-success me-1"></i>
              <strong>${s.document_id}</strong> (предложение #${s.sentence_index})
              — <em>«${s.quote || ''}»</em>
            </div>
            <span class="badge bg-secondary-subtle text-secondary border font-monospace">
              <i class="bi bi-git me-1"></i>${(s.commit_hash || 'HEAD').slice(0, 8)}
            </span>
          </div>
        `).join('');
      }
    }

    if (jsonViewer && res.matched_fact) {
      jsonViewer.textContent = JSON.stringify(res.matched_fact, null, 2);
    }
  } catch (err) {
    if (ansMain) ansMain.textContent = `Ошибка: ${err.message}`;
    if (statusInd) statusInd.textContent = 'Ошибка';
  }
}

export function initQaPanel(getWorkspaceId) {
  document.getElementById('qa-ask-btn')?.addEventListener('click', () => {
    executeAskQuestion(null, getWorkspaceId());
  });

  document.getElementById('qa-question-input')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      executeAskQuestion(null, getWorkspaceId());
    }
  });

  document.querySelectorAll('.sample-q-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const q = btn.getAttribute('data-q');
      if (q) executeAskQuestion(q, getWorkspaceId());
    });
  });
}
