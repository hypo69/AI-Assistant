/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Chat Tab Controller
 * =============================================================================
 * Description:
 *   Клиентский контроллер отдельной функциональной вкладки диалога с ИИ
 *   (tab-chat, #tab-chat). Обеспечивает интеллектуальный диалог с контекстом
 *   активной рабочей области через API /api/v1/ask, потоковую разметку
 *   Markdown, отображение подтвержденных цитат источников и синхронизацию
 *   смены рабочей области.
 *
 * File: main.js
 * Package: apps/ai_assistant/api/webgui/tab_chat
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-11 20:54:00
 * =============================================================================
 */

import { isTabActive } from '../js/tab-core.js';
import { getActiveWorkspaceId } from '../js/top_workspace_dropdown.js';

let isSending = false;
let isInitialized = false;

/**
 * Возвращает текущий активный язык интерфейса с fallback на 'ru'.
 * @returns {string} Код языка (ru, en, he, uk)
 */
export function getCurrentLanguage() {
  if (typeof window !== 'undefined' && window.i18n && window.i18n.lang) {
    return window.i18n.lang;
  }
  if (typeof document !== 'undefined' && document.documentElement.lang) {
    return document.documentElement.lang;
  }
  return 'ru';
}

/**
 * Загружает и отрисовывает динамические чипы вопросов по содержимому активной рабочей области.
 * @param {string} [wsId] - Идентификатор рабочей области
 */
export async function loadDynamicQuickPrompts(wsId) {
  const container = document.getElementById('chat-quick-prompts');
  if (!container) return;

  const targetWs = wsId || resolveCurrentWorkspaceId();
  if (!targetWs) return;

  const lang = getCurrentLanguage();
  try {
    const res = await fetchJson(`/api/v1/workspaces/${encodeURIComponent(targetWs)}/suggested-questions?language=${encodeURIComponent(lang)}&limit=3`);
    if (res && res.status === 'ok' && Array.isArray(res.prompts) && res.prompts.length > 0) {
      container.innerHTML = '';
      res.prompts.forEach((item, idx) => {
        const btn = document.createElement('button');
        btn.className = 'btn btn-sm btn-outline-secondary rounded-pill py-1 px-3 chat-prompt-chip d-inline-flex align-items-center gap-1.5';
        btn.type = 'button';
        btn.id = `chat-prompt-chip-${idx + 1}`;

        const icon = document.createElement('i');
        icon.className = `bi ${item.icon || 'bi-lightbulb'} me-1`;
        if (item.type === 'git_file' || item.type === 'history') {
          icon.classList.add('text-danger');
        } else if (item.type === 'document' || item.type === 'structure') {
          icon.classList.add('text-info');
        } else {
          icon.classList.add('text-warning');
        }

        const span = document.createElement('span');
        span.id = `chat-prompt-span-${idx + 1}`;
        span.textContent = item.text;

        btn.appendChild(icon);
        btn.appendChild(span);

        btn.addEventListener('click', () => {
          const inputEl = document.getElementById('ws-chat-input');
          if (inputEl) {
            inputEl.value = item.text;
            inputEl.focus();
          }
        });

        container.appendChild(btn);
      });
    }
  } catch (err) {
    console.debug('[ChatTab] Сбой загрузки контекстных подсказок:', err);
  }
}

/**
 * Локализует строку через глобальный менеджер i18n с резервным значением.
 * @param {string} key - Ключ локализации
 * @param {string} [fallback=''] - Значение по умолчанию
 * @returns {string} Локализованная строка
 */
function t(key, fallback = '') {
  if (typeof window !== 'undefined') {
    if (window.i18n && typeof window.i18n.t === 'function') {
      const val = window.i18n.t(key, fallback);
      if (val && val !== key) return val;
    }
    if (window.i18next && typeof window.i18next.t === 'function') {
      const val = window.i18next.t(key);
      if (val && val !== key) return val;
    }
  }
  return fallback;
}

/**
 * Выполняет сетевой JSON-запрос с обработкой ошибок.
 * @param {string} url - URL эндпоинта
 * @param {RequestInit} [options={}] - Опции запроса fetch
 * @returns {Promise<any>} Распарсенный ответ
 */
async function fetchJson(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok) {
    let errDetail = `${res.status} ${res.statusText}`;
    try {
      const data = await res.json();
      if (data && (data.detail || data.error)) {
        errDetail = data.detail || data.error;
      }
    } catch (_) {}
    throw new Error(errDetail);
  }
  return res.json();
}

/**
 * Экранирует HTML-спецсимволы для безопасного отображения пользовательского ввода.
 * @param {string} str - Исходный текст
 * @returns {string} Экранированный текст
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
 * Рендерит текст сообщения в безопасный HTML с поддержкой Markdown.
 * @param {string} text - Исходный текст ответа
 * @returns {string} HTML-разметка
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
 * Извлекает активный идентификатор рабочей области с каскадным fallback.
 * @returns {string|null} Идентификатор рабочей области
 */
export function resolveCurrentWorkspaceId() {
  // 1. Верхний селектор рабочей области
  if (typeof getActiveWorkspaceId === 'function') {
    const act = getActiveWorkspaceId();
    if (act) return String(act).trim().normalize('NFC');
  }

  // 2. Глобальная переменная на объекте window
  if (typeof window !== 'undefined' && window.currentWorkspaceId) {
    return String(window.currentWorkspaceId).trim().normalize('NFC');
  }

  // 3. Разбор URL hash (#tab-chat#workspace=<wsId> или #workspace=<wsId>)
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

  // 4. Локальное хранилище
  if (typeof localStorage !== 'undefined') {
    try {
      const stored = localStorage.getItem('ai_assistant_active_workspace');
      if (stored) return String(stored).trim().normalize('NFC');
    } catch (_) {}
  }

  return 'default';
}

/**
 * Обновляет отображение активной рабочей области в заголовке вкладки чата.
 */
export function updateWorkspaceBadge() {
  const badgeEl = document.getElementById('chat-active-ws-name');
  if (badgeEl) {
    const wsId = resolveCurrentWorkspaceId() || 'default';
    badgeEl.textContent = wsId;
  }
}

/**
 * Добавляет сообщение в окно диалога.
 * @param {'user' | 'assistant'} sender - Отправитель сообщения
 * @param {string} text - Текст сообщения
 * @param {boolean} [isPending=false] - Флаг ожидания ответа
 * @returns {HTMLElement|null} Созданный DOM-элемент сообщения
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

  msgDiv.style.maxWidth = isUser ? '80%' : '92%';
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
    loadDynamicQuickPrompts();
  }
  if (statusEl) {
    statusEl.textContent = t('workspace.chatReadyStatus', 'Готов к диалогу');
  }
}

export function extractFactCommandText(rawText) {
  const trimmed = (rawText || '').trim();
  const match = trimmed.match(/^(?:\/fact|\/факт|fact:|факт:|עובדה:)\s+(.+)$/i);
  return match ? match[1].trim() : null;
}

/**
 * Сохраняет введённое утверждение как новый факт во внутренние файлы рабочей области и базу знаний.
 * @param {string|null} [factOverride=null] - Явный текст факта (если не передан, берётся из поля ввода).
 */
export async function addFactFromChat(factOverride = null) {
  if (isSending) return;

  const inputEl = document.getElementById('ws-chat-input');
  const sendBtn = document.getElementById('ws-chat-send-btn');
  const addFactBtn = document.getElementById('chat-add-fact-btn');
  const statusEl = document.getElementById('ws-chat-status');

  const rawText = factOverride !== null ? String(factOverride).trim() : (inputEl ? inputEl.value.trim() : '');
  if (!rawText) return;

  isSending = true;
  if (factOverride === null && inputEl) inputEl.value = '';
  if (sendBtn) sendBtn.disabled = true;
  if (addFactBtn) addFactBtn.disabled = true;
  if (statusEl) statusEl.textContent = t('workspace.chatAddingFactStatus', 'Сохранение факта...');

  appendMessage('user', `📌 ${rawText}`);
  const pendingBubble = appendMessage('assistant', '', true);
  const wsId = resolveCurrentWorkspaceId();

  try {
    if (!wsId) {
      throw new Error(t('workspace.chatErrorNoWorkspace', 'Не выбрана рабочая область'));
    }

    const res = await fetchJson(`/api/v1/workspaces/${encodeURIComponent(wsId)}/facts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fact_text: rawText }),
    });

    const docName = res.document_id || 'chat_facts.md';
    const commitShort = (res.commit_hash || 'HEAD').slice(0, 8);
    const savedPrefix = t('workspace.chatFactSavedMsg', 'Факт сохранён во внутренний файл и базу знаний');
    const confirmText = `✅ **${savedPrefix}:** \`${docName}\` (Git: \`${commitShort}\`, фактов в файле: **${res.facts_count || 1}**)\n\n> ${escapeHtml(res.fact_text || rawText)}`;

    if (pendingBubble) {
      pendingBubble.removeAttribute('data-pending');
      pendingBubble.innerHTML = renderMessageContent(confirmText);
    }
    if (statusEl) {
      statusEl.textContent = t('workspace.chatFactSavedStatus', 'Факт добавлен');
    }
    document.dispatchEvent(new CustomEvent('workspace:factsUpdated', { detail: { workspaceId: wsId, result: res } }));
  } catch (err) {
    if (pendingBubble) {
      pendingBubble.removeAttribute('data-pending');
      const errPrefix = t('workspace.chatFactAddError', 'Ошибка добавления факта:');
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
    if (addFactBtn) addFactBtn.disabled = false;
    if (inputEl) inputEl.focus();
    scrollToBottom();
  }
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

  const cmdFact = extractFactCommandText(text);
  if (cmdFact) {
    if (inputEl) inputEl.value = '';
    await addFactFromChat(cmdFact);
    return;
  }

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
    if (!wsId) {
      throw new Error(t('workspace.chatErrorNoWorkspace', 'Не выбрана рабочая область'));
    }

    // Ответ формируется строго по документам рабочей области через /api/v1/ask
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

    // Добавляем цитаты источников из документов рабочей области
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

      // Отображаем рекомендованные связанные вопросы (Follow-up)
      if (Array.isArray(askRes && askRes.suggested_quick_questions) && askRes.suggested_quick_questions.length > 0) {
        const followUpWrap = document.createElement('div');
        followUpWrap.className = 'mt-2 pt-2 border-top border-secondary-subtle d-flex flex-wrap gap-1.5 align-items-center';

        const label = document.createElement('span');
        label.className = 'small text-secondary me-1';
        label.textContent = t('workspace.chatFollowUpLabel', 'Связанные вопросы:');
        followUpWrap.appendChild(label);

        askRes.suggested_quick_questions.forEach((qItem) => {
          const qText = typeof qItem === 'string' ? qItem : (qItem.text || '');
          if (!qText) return;
          const qBtn = document.createElement('button');
          qBtn.className = 'btn btn-sm btn-outline-primary py-0 px-2 rounded-pill small d-inline-flex align-items-center gap-1';
          qBtn.type = 'button';
          qBtn.innerHTML = `<i class="bi bi-arrow-right-short"></i><span>${escapeHtml(qText)}</span>`;
          qBtn.onclick = () => {
            const inp = document.getElementById('ws-chat-input');
            if (inp) {
              inp.value = qText;
              inp.focus();
            }
          };
          followUpWrap.appendChild(qBtn);
        });
        pendingBubble.appendChild(followUpWrap);
      }
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
 * Инициализирует вкладку диалога с ИИ (tab-chat).
 */
/**
 * Возвращает корневой DOM-контейнер выделенной вкладки диалога с ИИ.
 * @returns {HTMLElement|null}
 */
export function getChatContainer() {
  return document.getElementById('tab-chat') || document;
}

export function initChatTab() {
  updateWorkspaceBadge();

  if (isInitialized) {
    return;
  }
  isInitialized = true;

  const container = getChatContainer();
  const sendBtn = container ? container.querySelector('#ws-chat-send-btn') : null;
  const addFactBtn = container ? container.querySelector('#chat-add-fact-btn') : null;
  const inputEl = container ? container.querySelector('#ws-chat-input') : null;
  const clearBtn = container ? container.querySelector('#ws-chat-clear-btn') : null;

  if (sendBtn) {
    sendBtn.onclick = () => sendChatMessage();
  }
  if (addFactBtn) {
    addFactBtn.onclick = () => addFactFromChat();
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

  // Обработка клика по быстрым шаблонам запросов (Prompt Chips)
  document.querySelectorAll('.chat-prompt-chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      const span = chip.querySelector('span[data-i18n]');
      const promptText = span ? span.textContent.trim() : (chip.getAttribute('data-prompt') || chip.textContent.trim());
      if (promptText && inputEl) {
        inputEl.value = promptText;
        inputEl.focus();
      }
    });
  });

  // Синхронизация при смене рабочей области через верхнее меню
  const onWorkspaceUpdate = () => {
    updateWorkspaceBadge();
    loadDynamicQuickPrompts();
  };
  document.addEventListener('context:changed', onWorkspaceUpdate);
  document.addEventListener('workspace:changed', onWorkspaceUpdate);
  document.addEventListener('repo:changed', onWorkspaceUpdate);
  window.addEventListener('i18n:languageChanged', () => loadDynamicQuickPrompts());
  window.addEventListener('languageChanged', () => loadDynamicQuickPrompts());
  loadDynamicQuickPrompts();
}

/**
 * Деактивирует вкладку чата при переключении.
 */
export function deactivateChatTab() {
  // Освобождение ресурсов при скрытии вкладки
}

// Регистрация в глобальном контексте window для оркестратора вкладок
if (typeof window !== 'undefined') {
  window.initChatTab = initChatTab;
  window.deactivateChatTab = deactivateChatTab;
  window.sendChatMessage = sendChatMessage;
  window.addFactFromChat = addFactFromChat;
  window.clearChatHistory = clearChatHistory;
  window.loadDynamicQuickPrompts = loadDynamicQuickPrompts;
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initChatTab);
} else {
  initChatTab();
}
