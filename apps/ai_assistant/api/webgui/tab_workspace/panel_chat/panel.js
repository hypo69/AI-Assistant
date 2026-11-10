/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Chat Panel
 * =============================================================================
 * Description:
 *   Клиентский модуль панели диалога с ИИ (Чат) в рамках вкладки
 *   tab-workspace (#tab-workspace#panel-chat). Ответы формируются строго по
 *   документам выбранной рабочей области через контур /api/v1/ask
 *   (без подмешивания общих знаний модели).
 *
 * File: panel.js
 * Package: apps/ai_assistant/api/webgui/tab_workspace/panel_chat
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-30 15:58:00
 * =============================================================================
 */

import { fetchJson, t } from '../common/ui_utils.js';
import { getCurrentWorkspaceId } from '../panel_workspace_select/panel.js';

let isSending = false;
let getWorkspaceIdCallback = null;



/**
 * Экранирует HTML-спецсимволы для безопасного отображения пользовательского ввода.
 * @param {string} str - Исходный текст.
 * @returns {string} Экранированный текст.
 */
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/**
 * Рендерит текст сообщения в безопасный HTML (с поддержкой Markdown при наличии marked).
 * @param {string} text - Исходный текст ответа.
 * @returns {string} HTML-разметка.
 */
function renderMessageContent(text) {
  if (typeof window !== 'undefined' && window.marked && typeof window.marked.parse === 'function') {
    try {
      return window.marked.parse(text);
    } catch (_) {}
  }
  return escapeHtml(text).replace(/\n/g, '<br/>');
}

/**
 * Прокручивает окно диалога к последнему сообщению.
 */
function scrollToBottom() {
  const windowEl = document.getElementById('ws-chat-response-window');
  if (windowEl) {
    windowEl.scrollTop = windowEl.scrollHeight;
  }
}

/**
 * Добавляет сообщение в окно диалога.
 * @param {'user' | 'assistant'} sender - Отправитель сообщения.
 * @param {string} text - Текст сообщения.
 * @param {boolean} [isPending=false] - Флаг ожидания ответа (с индикатором загрузки).
 * @returns {HTMLElement} Созданный DOM-элемент сообщения.
 */
function appendMessage(sender, text, isPending = false) {
  const container = document.getElementById('ws-chat-messages');
  const emptyState = document.getElementById('ws-chat-empty-state');
  if (emptyState) {
    emptyState.classList.add('d-none');
  }
  if (!container) return null;

  const msgDiv = document.createElement('div');
  const isUser = sender === 'user';

  msgDiv.className = isUser
    ? 'align-self-end rounded-3 px-3 py-2 shadow-sm bg-primary text-white'
    : 'align-self-start rounded-3 px-3 py-2 shadow-sm bg-body border text-body';

  msgDiv.style.maxWidth = isUser ? '80%' : '90%';
  msgDiv.style.wordBreak = 'break-word';

  if (isPending) {
    msgDiv.setAttribute('data-pending', 'true');
    msgDiv.innerHTML = `
      <div class="d-flex align-items-center gap-2 text-secondary small py-1">
        <span class="spinner-border spinner-border-sm text-primary" role="status"></span>
        <span>${t('workspace.chatAiThinking', 'ИИ формирует ответ...')}</span>
      </div>
    `;
  } else {
    msgDiv.innerHTML = renderMessageContent(text);
  }

  container.appendChild(msgDiv);
  scrollToBottom();
  return msgDiv;
}

/**
 * Очищает историю сообщений чата и возвращает стартовое состояние.
 */
export function clearChatHistory() {
  const container = document.getElementById('ws-chat-messages');
  const emptyState = document.getElementById('ws-chat-empty-state');
  const statusEl = document.getElementById('ws-chat-status');

  if (container) {
    container.innerHTML = '';
  }
  if (emptyState) {
    emptyState.classList.remove('d-none');
  }
  if (statusEl) {
    statusEl.textContent = t('workspace.chatReadyStatus', 'Готов к диалогу');
  }
}

/**
 * Извлекает активный идентификатор рабочего пространства с многоуровневым fallback.
 * @returns {string|null}
 */
export function resolveCurrentWorkspaceId() {
  // 1. Коллбек, переданный при инициализации (из main.js)
  let wsId = typeof getWorkspaceIdCallback === 'function' ? getWorkspaceIdCallback() : null;
  if (wsId) return String(wsId).trim().normalize('NFC');

  // 2. Модуль панели выбора рабочей области
  wsId = getCurrentWorkspaceId();
  if (wsId) return String(wsId).trim().normalize('NFC');

  // 3. Глобальная переменная на объекте window
  if (typeof window !== 'undefined' && window.currentWorkspaceId) {
    return String(window.currentWorkspaceId).trim().normalize('NFC');
  }

  // 4. Верхний селектор рабочего пространства
  if (typeof window !== 'undefined' && typeof window.getActiveWorkspaceId === 'function') {
    const act = window.getActiveWorkspaceId();
    if (act) return String(act).trim().normalize('NFC');
  }

  // 5. Разбор URL hash (#tab-workspace#panel-chat#workspace=<wsId>)
  if (typeof location !== 'undefined' && location.hash) {
    const match = location.hash.match(/workspace=([^&/#]+)/i);
    if (match && match[1]) {
      try {
        return decodeURIComponent(match[1]).trim().normalize('NFC');
      } catch (_) {
        return match[1].trim().normalize('NFC');
      }
    }
  }

  // 6. DOM-селектор рабочих областей #ws-selector
  if (typeof document !== 'undefined') {
    const selector = document.getElementById('ws-selector');
    if (selector && selector.value) {
      return String(selector.value).trim().normalize('NFC');
    }
  }

  // 7. Сохраненное значение в localStorage
  if (typeof localStorage !== 'undefined') {
    try {
      const stored = localStorage.getItem('ai_assistant_active_workspace');
      if (stored) return String(stored).trim().normalize('NFC');
    } catch (_) {}
  }

  return null;
}

/**
 * Отправляет пользовательское сообщение в ИИ и отображает ответ в окне диалога.
 */
export async function sendChatMessage() {
  if (isSending) return;

  const inputEl = document.getElementById('ws-chat-input');
  const sendBtn = document.getElementById('ws-chat-send-btn');
  const statusEl = document.getElementById('ws-chat-status');

  const text = inputEl ? inputEl.value.trim() : '';
  if (!text) return;

  isSending = true;
  if (inputEl) inputEl.value = '';
  if (sendBtn) sendBtn.disabled = true;
  if (statusEl) statusEl.textContent = t('workspace.chatSendingStatus', 'Отправка запроса...');

  // 1. Отображаем сообщение пользователя
  appendMessage('user', text);

  // 2. Отображаем временный блок ожидания ответа
  const pendingBubble = appendMessage('assistant', '', true);

  const wsId = resolveCurrentWorkspaceId();
  let responseText = '';
  let durationMs = 0;

  try {
    // Fail-Fast: чат работает строго в контексте выбранной рабочей области
    if (!wsId) {
      throw new Error(t('workspace.chatErrorNoWorkspace', 'Не выбрана рабочая область'));
    }

    // Ответ формируется ТОЛЬКО по документам рабочей области (контур /api/v1/ask).
    // Прямой вызов модели (/api/v1/chat/test-model) запрещён: он подмешивал общие знания из интернета.
    const askRes = await fetchJson('/api/v1/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question: text,
        workspace_id: wsId,
        mode: 'local_first',
      }),
    });

    responseText = askRes && askRes.answer ? askRes.answer : t('workspace.chatNoAnswer', 'Ответ не получен.');
    durationMs = (askRes && askRes.processing && askRes.processing.latency_ms) || 0;

    // Цитаты источников из документов рабочей области
    const docFallback = t('workspace.chatDocumentFallback', 'документ');
    const quotes = ((askRes && askRes.sources) || [])
      .filter((s) => s && s.quote)
      .map((s) => `> ${s.quote}\n>\n> — *${s.document_id || docFallback}*`);
    if (quotes.length) {
      responseText += `\n\n${quotes.join('\n\n')}`;
    }

    // Заменяем блок ожидания готовым ответом
    if (pendingBubble) {
      pendingBubble.removeAttribute('data-pending');
      pendingBubble.innerHTML = renderMessageContent(responseText);
    }
    if (statusEl) {
      const succText = t('workspace.chatSuccessStatus', 'Ответ получен');
      statusEl.textContent = durationMs > 0 ? `${succText} (${durationMs} мс)` : succText;
    }
  } catch (err) {
    if (pendingBubble) {
      pendingBubble.removeAttribute('data-pending');
      const errPrefix = t('workspace.chatErrorGeneration', 'Ошибка генерации ответа:');
      pendingBubble.innerHTML = `
        <div class="text-danger small d-flex align-items-center gap-1.5">
          <i class="bi bi-exclamation-triangle-fill"></i>
          <span>${errPrefix} ${escapeHtml(err.message || String(err))}</span>
        </div>
      `;
    }
    if (statusEl) {
      statusEl.textContent = t('workspace.chatErrorStatus', 'Ошибка генерации');
    }
  } finally {
    isSending = false;
    if (sendBtn) sendBtn.disabled = false;
    if (inputEl) inputEl.focus();
    scrollToBottom();
  }
}

/**
 * Инициализирует обработчики событий панели чата.
 * @param {Function|null} [getWorkspaceIdFn=null] - Функция получения ID активного рабочего пространства.
 */
export function initChatPanel(getWorkspaceIdFn = null) {
  if (typeof getWorkspaceIdFn === 'function') {
    getWorkspaceIdCallback = getWorkspaceIdFn;
  }

  const sendBtn = document.getElementById('ws-chat-send-btn');
  const inputEl = document.getElementById('ws-chat-input');
  const clearBtn = document.getElementById('ws-chat-clear-btn');

  if (sendBtn) {
    sendBtn.onclick = () => sendChatMessage();
  }

  if (inputEl) {
    inputEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendChatMessage();
      }
    });
  }

  if (clearBtn) {
    clearBtn.onclick = () => clearChatHistory();
  }
}
