/**

 * =============================================================================

 * Process Name: AI Assistant WebGUI - Gmail Tab Controller

 * =============================================================================

 * Description:

 *   Клиентский контроллер вкладки управления почтой Gmail (tab_gmail).

 *   Управляет загрузкой профиля, меток, фильтрацией писем, пагинацией,

 *   чтением и отправкой писем, групповыми операциями со сквозной поддержкой i18n.

 *

 * File: main.js

 * Package: apps/ai_assistant/api/webgui/tab_gmail

 * Author: hypo69

 * Copyright: © 2026 hypo69

 * Updated: 2026-10-27 21:26:00

 * =============================================================================

 */



let currentFolder = 'INBOX';

let currentFilter = '';

let currentSearchQuery = '';

let currentPageToken = '';

let pageTokensStack = [];

let selectedMessageIds = new Set();

let currentViewMessage = null;

let lastLoadedMessages = [];

let isInitialized = false;



const FOLDER_I18N_MAP = {

  INBOX: 'ui.gmail.txt_b24c1679',

  STARRED: 'ui.gmail.txt_017a2a2e',

  SENT: 'ui.gmail.txt_a59f0da1',

  DRAFT: 'ui.gmail.txt_25e27cb6',

  SPAM: 'ui.gmail.txt_bb3d0681',

  TRASH: 'ui.gmail.txt_b7697b96'

};



const LOCALE_MAP = { ru: 'ru-RU', en: 'en-US', he: 'he-IL', uk: 'uk-UA' };



/**

 * Получает локализованную строку по ключу i18n или fallback.

 */

function t(key, fallback = '') {

  if (typeof window !== 'undefined' && window.i18n && typeof window.i18n.t === 'function') {

    const res = window.i18n.t(key, fallback);

    return res !== key ? res : fallback;

  }

  return fallback;

}



/**

 * Получает BCP 47 код локали интерфейса.

 */

function getActiveLocale() {

  const lang = (window.i18n && window.i18n.lang) ? window.i18n.lang : 'ru';

  return LOCALE_MAP[lang] || 'ru-RU';

}



/**

 * Экранирует HTML символы в строках.

 */

function escapeHtml(str) {

  if (!str) return '';

  return String(str)

    .replace(/&/g, '&amp;')

    .replace(/</g, '&lt;')

    .replace(/>/g, '&gt;')

    .replace(/"/g, '&quot;')

    .replace(/'/g, '&#39;');

}



/**

 * Отображает всплывающее уведомление.

 */

function notify(message, type = 'info') {

  if (typeof window.showToast === 'function') {

    window.showToast(message, type);

  } else {

    console.log(`[Gmail] [${type.toUpperCase()}] ${message}`);

  }

}



/**

 * Форматирует строковую дату в локализованный вид.

 */

function formatDateString(dateStr) {

  if (!dateStr) return '';

  try {

    const d = new Date(dateStr);

    if (isNaN(d.getTime())) return dateStr.slice(0, 16);

    const isToday = d.toDateString() === new Date().toDateString();

    const loc = getActiveLocale();

    return isToday

      ? d.toLocaleTimeString(loc, { hour: '2-digit', minute: '2-digit' })

      : d.toLocaleDateString(loc, { day: '2-digit', month: '2-digit' });

  } catch {

    return dateStr;

  }

}



/**

 * Загружает сводный профиль Gmail пользователя.

 */

export async function loadProfile() {

  const emailBadge = document.getElementById('gmail-account-email');

  const statMessages = document.getElementById('gmail-stat-messages');

  const statThreads = document.getElementById('gmail-stat-threads');



  try {

    const res = await fetch('/api/v1/gmail/profile');

    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const data = await res.json();

    const loc = getActiveLocale();



    if (emailBadge) emailBadge.textContent = data.email || t('ui.gmail.not_authorized', 'Не авторизован');

    if (statMessages) statMessages.textContent = (data.messages_total || 0).toLocaleString(loc);

    if (statThreads) statThreads.textContent = (data.threads_total || 0).toLocaleString(loc);

  } catch (err) {

    console.warn('[Gmail] Ошибка получения профиля:', err);

    if (emailBadge) emailBadge.textContent = t('ui.gmail.profile_error', 'Ошибка профиля');

  }

}



/**

 * Загружает метки и счетчики непрочитанных.

 */

export async function loadLabels() {

  try {

    const res = await fetch('/api/v1/gmail/labels');

    if (!res.ok) return;

    const data = await res.json();

    const inboxLabel = (data.labels || []).find(l => l.id === 'INBOX');

    const badgeInbox = document.getElementById('badge-unread-inbox');

    const topBadge = document.getElementById('top-nav-gmail-badge');



    if (inboxLabel) {

      const unreadCount = inboxLabel.messages_unread || 0;

      if (badgeInbox) {

        badgeInbox.textContent = unreadCount;

        badgeInbox.className = unreadCount > 0

          ? 'badge bg-primary rounded-pill font-size-75'

          : 'badge bg-secondary-subtle text-secondary rounded-pill font-size-75';

      }

      if (topBadge) {

        topBadge.textContent = unreadCount;

        topBadge.classList.toggle('d-none', unreadCount === 0);

      }

    }

  } catch (err) {

    console.warn('[Gmail] Ошибка меток:', err);

  }

}



/**

 * Формирует поисковый запрос Gmail.

 */

function buildFullQuery() {

  const parts = [];

  if (currentSearchQuery.trim()) parts.push(currentSearchQuery.trim());

  if (currentFilter.trim()) parts.push(currentFilter.trim());

  return parts.join(' ');

}



/**

 * Синхронизирует заголовок папки и пагинацию с учетом языка.

 */

function updateFolderAndPaginationUI(messagesCount = 0) {

  const folderTitle = document.getElementById('gmail-current-folder-title');

  if (folderTitle) {

    const i18nKey = FOLDER_I18N_MAP[currentFolder] || 'ui.gmail.txt_b24c1679';

    folderTitle.setAttribute('data-i18n', i18nKey);

    folderTitle.textContent = t(i18nKey, currentFolder);

  }



  const pagInfo = document.getElementById('gmail-pagination-info');

  if (pagInfo) {

    pagInfo.textContent = messagesCount > 0

      ? t('ui.gmail.page_info', 'Стр. {page} ({count} писем)')

          .replace('{page}', pageTokensStack.length + 1)

          .replace('{count}', messagesCount)

      : t('ui.gmail.zero_messages', '0 писем');

  }

}



/**

 * Загружает и отрисовывает список сообщений.

 */

export async function loadMessages(resetPagination = false) {

  const tbody = document.getElementById('gmail-messages-tbody');

  const btnPrev = document.getElementById('btn-gmail-prev-page');

  const btnNext = document.getElementById('btn-gmail-next-page');



  if (resetPagination) {

    currentPageToken = '';

    pageTokensStack = [];

  }

  selectedMessageIds.clear();

  updateBatchButtonsState();



  if (tbody) {

    tbody.innerHTML = `

      <tr>

        <td colspan="5" class="text-center py-5 text-muted">

          <span class="spinner-border spinner-border-sm me-2"></span>

          <span>${escapeHtml(t('ui.gmail.loading_list', 'Загрузка списка сообщений...'))}</span>

        </td>

      </tr>

    `;

  }



  try {

    const q = buildFullQuery();

    let url = `/api/v1/gmail/messages?limit=25`;

    if (currentFolder) url += `&label=${encodeURIComponent(currentFolder)}`;

    if (q) url += `&q=${encodeURIComponent(q)}`;

    if (currentPageToken) url += `&page_token=${encodeURIComponent(currentPageToken)}`;



    const res = await fetch(url);

    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const data = await res.json();

    const messages = data.messages || [];

    lastLoadedMessages = messages;



    renderMessages(messages);



    const nextPageToken = data.next_page_token || '';

    if (btnNext) {

      btnNext.disabled = !nextPageToken;

      btnNext._nextToken = nextPageToken;

    }

    if (btnPrev) {

      btnPrev.disabled = pageTokensStack.length === 0;

    }



    updateFolderAndPaginationUI(messages.length);

  } catch (err) {

    console.warn('[Gmail] Ошибка загрузки писем:', err);

    if (tbody) {

      const errTmpl = t('ui.gmail.load_error', 'Не удалось загрузить сообщения: {error}');

      tbody.innerHTML = `

        <tr>

          <td colspan="5" class="text-center py-4 text-danger">

            <i class="bi bi-exclamation-triangle me-1"></i>

            ${escapeHtml(errTmpl.replace('{error}', err.message))}

          </td>

        </tr>

      `;

    }

  }

}



/**

 * Отрисовывает строки таблицы писем.

 */

function renderMessages(messages) {

  const tbody = document.getElementById('gmail-messages-tbody');

  if (!tbody) return;



  if (messages.length === 0) {

    tbody.innerHTML = `

      <tr>

        <td colspan="5" class="text-center py-5 text-muted">

          <i class="bi bi-inbox fs-3 d-block mb-2 text-secondary"></i>

          <span>${escapeHtml(t('ui.gmail.no_messages_in_folder', 'В этой папке нет сообщений'))}</span>

        </td>

      </tr>

    `;

    return;

  }



  const starActive = t('ui.gmail.unstar', 'Снять пометку');

  const starInactive = t('ui.gmail.star', 'Пометить');

  const unknownSender = t('ui.gmail.unknown_sender', '(Неизвестно)');

  const noSubject = t('ui.gmail.no_subject', '(Без темы)');

  const markRead = t('ui.gmail.mark_as_read', 'Отметить как прочитанное');

  const markUnread = t('ui.gmail.mark_as_unread', 'Отметить как непрочитанное');

  const trash = t('ui.gmail.to_trash', 'В корзину');



  tbody.innerHTML = messages.map(msg => {

    const sender = (msg.from || '').replace(/<.*?>/, '').trim() || msg.from || unknownSender;

    const isChecked = selectedMessageIds.has(msg.id) ? 'checked' : '';

    const rowClass = msg.is_unread ? 'table-row-unread fw-bold bg-body-tertiary' : 'table-row-read';

    const starIcon = msg.is_starred ? 'bi-star-fill text-warning' : 'bi-star text-muted';

    const starTitle = msg.is_starred ? starActive : starInactive;

    const readIcon = msg.is_unread ? 'bi-envelope-open' : 'bi-envelope';

    const readTitle = msg.is_unread ? markRead : markUnread;

    const dateFormatted = formatDateString(msg.date);



    return `

      <tr class="${rowClass}" style="cursor: pointer;" data-msg-id="${msg.id}">

        <td class="text-center py-2 px-2" style="width: 36px;">

          <input type="checkbox" class="form-check-input msg-select-chk" value="${msg.id}" ${isChecked}>

        </td>

        <td class="text-center py-2 px-1" style="width: 32px;">

          <span class="btn-star cursor-pointer" title="${escapeHtml(starTitle)}" data-starred="${!!msg.is_starred}">

            <i class="bi ${starIcon}"></i>

          </span>

        </td>

        <td class="py-2 px-2 text-truncate" style="max-width: 180px;" title="${escapeHtml(msg.from || '')}">

          ${escapeHtml(sender)}

        </td>

        <td class="py-2 px-2 text-truncate" style="max-width: 460px;">
          ${msg.semantic_score ? `<span class="badge bg-info-subtle text-info border border-info-subtle font-size-75 me-1 shadow-sm" title="${escapeHtml(msg.relevance_reason || t('ui.gmail.txt_semantic_search', 'ИИ-поиск'))}"><i class="bi bi-stars me-1"></i>${Math.round(msg.semantic_score * 100)}%</span>` : ""}<span class="text-body">${escapeHtml(msg.subject || noSubject)}</span>

          <span class="text-muted small fw-normal ms-1">— ${escapeHtml(msg.snippet || '')}</span>

        </td>

        <td class="py-2 px-2 text-end text-nowrap" style="width: 160px;">

          <span class="small text-muted font-size-80 me-2">${escapeHtml(dateFormatted)}</span>

          <button class="btn btn-xs btn-outline-secondary btn-sm p-1 me-1 btn-quick-read" title="${escapeHtml(readTitle)}" data-unread="${!!msg.is_unread}">

            <i class="bi ${readIcon}"></i>

          </button>

          <button class="btn btn-xs btn-outline-danger btn-sm p-1 btn-quick-trash" title="${escapeHtml(trash)}">

            <i class="bi bi-trash"></i>

          </button>

        </td>

      </tr>

    `;

  }).join('');



  tbody.querySelectorAll('tr[data-msg-id]').forEach(tr => {

    const id = tr.getAttribute('data-msg-id');

    tr.addEventListener('click', () => viewMessage(id));



    tr.querySelector('.msg-select-chk')?.addEventListener('click', (e) => {

      e.stopPropagation();

      if (e.target.checked) selectedMessageIds.add(id);

      else selectedMessageIds.delete(id);

      updateBatchButtonsState();

    });



    tr.querySelector('.btn-star')?.addEventListener('click', async (e) => {

      e.stopPropagation();

      const starred = e.currentTarget.getAttribute('data-starred') === 'true';

      await toggleStar(id, starred);

    });



    tr.querySelector('.btn-quick-read')?.addEventListener('click', async (e) => {

      e.stopPropagation();

      const unread = e.currentTarget.getAttribute('data-unread') === 'true';

      await toggleReadStatus(id, unread);

    });



    tr.querySelector('.btn-quick-trash')?.addEventListener('click', async (e) => {

      e.stopPropagation();

      await trashMessage(id);

    });

  });

}



/**

 * Открывает письмо и отображает его в модальном окне.

 */

export async function viewMessage(messageId) {

  const modalEl = document.getElementById('gmailMessageViewModal');

  if (!modalEl || typeof bootstrap === 'undefined') return;



  const subjectEl = document.getElementById('gmail-view-subject');

  const fromEl = document.getElementById('gmail-view-from');

  const toEl = document.getElementById('gmail-view-to');

  const dateEl = document.getElementById('gmail-view-date');

  const labelsEl = document.getElementById('gmail-view-labels');

  const bodyContent = document.getElementById('gmail-view-body-content');

  const attachContainer = document.getElementById('gmail-view-attachments-container');

  const attachList = document.getElementById('gmail-view-attachments-list');



  bodyContent.innerHTML = `

    <div class="text-center py-4 text-muted">

      <span class="spinner-border spinner-border-sm me-2"></span>

      <span>${escapeHtml(t('ui.gmail.loading_body', 'Загрузка содержимого письма...'))}</span>

    </div>

  `;

  bootstrap.Modal.getOrCreateInstance(modalEl).show();



  try {

    const res = await fetch(`/api/v1/gmail/messages/${encodeURIComponent(messageId)}`);

    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const data = await res.json();

    currentViewMessage = data;



    subjectEl.textContent = data.subject || t('ui.gmail.no_subject', '(Без темы)');

    fromEl.textContent = `${t('ui.gmail.from_prefix', 'От: ')}${data.from || '—'}`;

    toEl.textContent = data.to || '—';

    dateEl.textContent = data.date || '—';



    if (labelsEl) {

      labelsEl.innerHTML = (data.labels || []).map(lbl =>

        `<span class="badge bg-secondary-subtle text-secondary border font-size-75">${escapeHtml(lbl)}</span>`

      ).join(' ');

    }



    const attachments = data.attachments || [];

    if (attachments.length > 0) {

      attachContainer.classList.remove('d-none');

      const kbText = t('ui.gmail.kb', 'КБ');

      attachList.innerHTML = attachments.map(att => `

        <span class="badge bg-info-subtle text-info border border-info-subtle p-2 d-flex align-items-center gap-1.5">

          <i class="bi bi-file-earmark"></i>

          <span>${escapeHtml(att.filename)}</span>

          <small class="text-muted">(${(att.size / 1024).toFixed(1)} ${kbText})</small>

        </span>

      `).join(' ');

    } else {

      attachContainer.classList.add('d-none');

    }



    if (data.body_html) {

      const iframe = document.createElement('iframe');

      iframe.style.width = '100%';

      iframe.style.minHeight = '320px';

      iframe.style.border = 'none';

      iframe.sandbox = 'allow-same-origin';

      bodyContent.innerHTML = '';

      bodyContent.appendChild(iframe);

      iframe.contentWindow.document.open();

      iframe.contentWindow.document.write(data.body_html);

      iframe.contentWindow.document.close();

    } else if (data.body_plain) {

      bodyContent.innerHTML = `<pre class="p-2 font-monospace font-size-85 text-wrap mb-0">${escapeHtml(data.body_plain)}</pre>`;

    } else {

      bodyContent.innerHTML = `<div class="text-muted fst-italic">${escapeHtml(t('ui.gmail.no_body', 'Письмо не содержит текстового тела.'))}</div>`;

    }



    if (data.is_unread) {

      await fetch(`/api/v1/gmail/messages/${encodeURIComponent(messageId)}/modify`, {

        method: 'POST',

        headers: { 'Content-Type': 'application/json' },

        body: JSON.stringify({ remove_labels: ['UNREAD'] }),

      });

      loadLabels();

    }

  } catch (err) {

    console.warn('[Gmail] Ошибка открытия письма:', err);

    const errTmpl = t('ui.gmail.load_body_error', 'Не удалось загрузить тело письма: {error}');

    bodyContent.innerHTML = `<div class="alert alert-danger py-2 small">${escapeHtml(errTmpl.replace('{error}', err.message))}</div>`;

  }

}



/**

 * Изменяет метки сообщения.

 */

async function modifyLabels(messageId, payload, errorKey) {

  try {

    await fetch(`/api/v1/gmail/messages/${encodeURIComponent(messageId)}/modify`, {

      method: 'POST',

      headers: { 'Content-Type': 'application/json' },

      body: JSON.stringify(payload),

    });

    loadMessages(false);

    loadLabels();

  } catch (err) {

    const errTmpl = t(errorKey, 'Ошибка изменения меток: {error}');

    notify(errTmpl.replace('{error}', err.message), 'error');

  }

}



async function toggleStar(messageId, isStarred) {

  await modifyLabels(messageId, isStarred ? { remove_labels: ['STARRED'] } : { add_labels: ['STARRED'] }, 'ui.gmail.star_error');

}



async function toggleReadStatus(messageId, isUnread) {

  await modifyLabels(messageId, isUnread ? { remove_labels: ['UNREAD'] } : { add_labels: ['UNREAD'] }, 'ui.gmail.status_error');

}



/**

 * Перемещает письмо в корзину.

 */

async function trashMessage(messageId) {

  try {

    const res = await fetch(`/api/v1/gmail/messages/${encodeURIComponent(messageId)}/trash`, { method: 'POST' });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    notify(t('ui.gmail.trash_success', 'Письмо перемещено в корзину'), 'success');

    loadMessages(false);

    loadLabels();

  } catch (err) {

    const errTmpl = t('ui.gmail.trash_error', 'Ошибка удаления: {error}');

    notify(errTmpl.replace('{error}', err.message), 'error');

  }

}



/**

 * Обновляет активность групповых кнопок тулбара.

 */

function updateBatchButtonsState() {

  const count = selectedMessageIds.size;

  ['btn-batch-mark-read', 'btn-batch-mark-unread', 'btn-batch-trash'].forEach(id => {

    const el = document.getElementById(id);

    if (el) el.disabled = count === 0;

  });

}



/**

 * Открывает окно написания нового письма.

 */

export function openComposeModal(prefill = {}) {

  const modalEl = document.getElementById('gmailComposeModal');

  if (!modalEl || typeof bootstrap === 'undefined') return;



  const toInput = document.getElementById('gmail-compose-to');

  const subjectInput = document.getElementById('gmail-compose-subject');

  const bodyInput = document.getElementById('gmail-compose-body');

  const htmlInput = document.getElementById('gmail-compose-is-html');



  if (toInput) toInput.value = prefill.to || '';

  if (subjectInput) subjectInput.value = prefill.subject || '';

  if (bodyInput) bodyInput.value = prefill.body || '';

  if (htmlInput) htmlInput.checked = !!prefill.is_html;



  bootstrap.Modal.getOrCreateInstance(modalEl).show();

}



/**

 * Отправляет электронное письмо адресату.

 */

export async function sendEmailSubmit() {

  const toInput = document.getElementById('gmail-compose-to');

  const subjectInput = document.getElementById('gmail-compose-subject');

  const bodyInput = document.getElementById('gmail-compose-body');

  const htmlInput = document.getElementById('gmail-compose-is-html');

  const btnSend = document.getElementById('btn-gmail-send-submit');



  const to = toInput?.value.trim();

  const subject = subjectInput?.value.trim();

  const body = bodyInput?.value || '';

  const isHtml = !!htmlInput?.checked;



  if (!to || !subject) {

    notify(t('ui.gmail.fill_required', 'Заполните обязательные поля: Получатель (Кому) и Тема'), 'warning');

    return;

  }



  if (btnSend) {

    btnSend.disabled = true;

    btnSend.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span> ${escapeHtml(t('ui.gmail.sending', 'Отправка...'))}`;

  }



  try {

    const res = await fetch('/api/v1/gmail/messages/send', {

      method: 'POST',

      headers: { 'Content-Type': 'application/json' },

      body: JSON.stringify({ to, subject, body, is_html: isHtml }),

    });



    if (!res.ok) {

      const errData = await res.json().catch(() => ({}));

      throw new Error(errData.detail || `HTTP ${res.status}`);

    }



    notify(t('ui.gmail.send_success', 'Письмо успешно отправлено адресату!'), 'success');



    const modalEl = document.getElementById('gmailComposeModal');

    if (modalEl && typeof bootstrap !== 'undefined') {

      bootstrap.Modal.getInstance(modalEl)?.hide();

    }



    if (toInput) toInput.value = '';

    if (subjectInput) subjectInput.value = '';

    if (bodyInput) bodyInput.value = '';

    loadMessages(false);

  } catch (err) {

    console.error('[Gmail] Ошибка отправки:', err);

    const errTmpl = t('ui.gmail.send_error', 'Ошибка при отправке письма: {error}');

    notify(errTmpl.replace('{error}', err.message), 'error');

  } finally {

    if (btnSend) {

      btnSend.disabled = false;

      const sendText = t('ui.gmail.txt_6da0f0ae', 'Отправить');

      btnSend.innerHTML = `<i class="bi bi-send-fill"></i><span data-i18n="ui.gmail.txt_6da0f0ae" id="gmail-span-6da0f0ae">${escapeHtml(sendText)}</span>`;

    }

  }

}



/**

 * Инициализирует вкладку Gmail и обработчики событий.

 */

export function initGmailTab() {

  if (isInitialized) return;

  isInitialized = true;



  document.getElementById('btn-gmail-refresh')?.addEventListener('click', () => {

    loadProfile();

    loadLabels();

    loadMessages(true);

  });



  document.getElementById('btn-gmail-compose')?.addEventListener('click', () => openComposeModal());

  document.getElementById('btn-gmail-send-submit')?.addEventListener('click', sendEmailSubmit);



  const searchInput = document.getElementById('gmail-search-input');

  const isNaturalLanguageQuery = (q) => {
    const lower = q.toLowerCase();
    if (lower.includes(':')) return false; // операторы Gmail (from:, is:, etc.)
    const words = lower.split(/\s+/).filter(w => w.length > 0);
    if (words.length >= 3) return true;
    return words.some(w => ['найди', 'покажи', 'письма', 'сделк', 'договор', 'коров', 'зина', 'счет', 'find', 'show', 'email', 'about'].some(kw => w.includes(kw)));
  };

  async function executeSemanticSearch() {
    const q = searchInput?.value.trim();
    if (!q) {
      alert(t('ui.gmail.enter_search_query', 'Пожалуйста, введите запрос для поиска'));
      return;
    }
    const tbody = document.getElementById('gmail-messages-tbody');
    if (tbody) {
      tbody.innerHTML = `
        <tr>
          <td colspan="5" class="text-center py-5 text-info">
            <div class="spinner-border text-info spinner-border-sm me-2" role="status"></div>
            <span>${escapeHtml(t('ui.gmail.semantic_searching', 'Векторный RAG-поиск и ранжирование писем по смыслу...'))}</span>
          </td>
        </tr>`;
    }
    try {
      const res = await fetch(`/api/v1/gmail/semantic_search?q=${encodeURIComponent(q)}&limit=25`);
      const data = await res.json();
      if (!res.ok || data.status === 'error') {
        throw new Error(data.detail || data.error || t('ui.gmail.load_error', 'Ошибка поиска'));
      }
      const messages = data.messages || [];
      if (messages.length === 0 && tbody) {
        tbody.innerHTML = `
          <tr>
            <td colspan="5" class="text-center py-5 text-muted">
              <i class="bi bi-search fs-3 d-block mb-2 text-secondary"></i>
              <span>${escapeHtml(t('ui.gmail.semantic_empty', 'По семантическому запросу подходящих писем не найдено'))}</span>
            </td>
          </tr>`;
      } else {
        renderMessages(messages);
      }
      const folderTitle = document.getElementById('gmail-current-folder-title');
      if (folderTitle) {
        const titleTpl = t('ui.gmail.semantic_query_info', 'Семантический RAG поиск: «{query}»');
        folderTitle.innerHTML = `<i class="bi bi-stars text-info me-1"></i> ${escapeHtml(titleTpl.replace('{query}', q))} (${data.count || 0})`;
      }
    } catch (err) {
      if (tbody) {
        tbody.innerHTML = `<tr><td colspan="5" class="text-center py-4 text-danger">${escapeHtml(err.message)}</td></tr>`;
      }
    }
  }

  const executeSearch = () => {
    const q = searchInput?.value.trim() || '';
    currentSearchQuery = q;
    // Если запрос введен на естественном языке, автоматически задействуем семантический RAG-поиск
    if (q && isNaturalLanguageQuery(q)) {
      executeSemanticSearch();
    } else {
      loadMessages(true);
    }
  };

  document.getElementById('btn-gmail-search')?.addEventListener('click', executeSearch);
  document.getElementById('btn-gmail-semantic-search')?.addEventListener('click', executeSemanticSearch);


  searchInput?.addEventListener('keydown', (e) => { if (e.key === 'Enter') executeSearch(); });

  document.getElementById('btn-gmail-search-clear')?.addEventListener('click', () => {

    if (searchInput) searchInput.value = '';

    currentSearchQuery = '';

    loadMessages(true);

  });



  const filterBtns = document.querySelectorAll('#gmail-quick-filters button');

  filterBtns.forEach(btn => {

    btn.addEventListener('click', () => {

      filterBtns.forEach(b => b.classList.remove('active'));

      btn.classList.add('active');

      currentFilter = btn.getAttribute('data-filter') || '';

      loadMessages(true);

    });

  });



  const folderBtns = document.querySelectorAll('#gmail-folders-list button[data-folder]');

  folderBtns.forEach(btn => {

    btn.addEventListener('click', () => {

      folderBtns.forEach(b => b.classList.remove('active'));

      btn.classList.add('active');

      currentFolder = btn.getAttribute('data-folder') || 'INBOX';



      const folderTitle = document.getElementById('gmail-current-folder-title');

      if (folderTitle) {

        const i18nKey = FOLDER_I18N_MAP[currentFolder] || 'ui.gmail.txt_b24c1679';

        folderTitle.setAttribute('data-i18n', i18nKey);

        folderTitle.textContent = t(i18nKey, currentFolder);

      }

      loadMessages(true);

    });

  });



  const btnNext = document.getElementById('btn-gmail-next-page');

  btnNext?.addEventListener('click', () => {

    if (btnNext._nextToken) {

      pageTokensStack.push(currentPageToken);

      currentPageToken = btnNext._nextToken;

      loadMessages(false);

    }

  });



  const btnPrev = document.getElementById('btn-gmail-prev-page');

  btnPrev?.addEventListener('click', () => {

    if (pageTokensStack.length > 0) {

      currentPageToken = pageTokensStack.pop() || '';

      loadMessages(false);

    }

  });



  const selectAllChk = document.getElementById('gmail-select-all');

  selectAllChk?.addEventListener('change', () => {

    document.querySelectorAll('.msg-select-chk').forEach(c => {

      c.checked = selectAllChk.checked;

      if (selectAllChk.checked) selectedMessageIds.add(c.value);

      else selectedMessageIds.delete(c.value);

    });

    updateBatchButtonsState();

  });



  const executeBatch = async (payload, successNotice = null) => {

    for (const id of selectedMessageIds) {

      if (payload === 'trash') {

        await fetch(`/api/v1/gmail/messages/${encodeURIComponent(id)}/trash`, { method: 'POST' });

      } else {

        await fetch(`/api/v1/gmail/messages/${encodeURIComponent(id)}/modify`, {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify(payload),

        });

      }

    }

    if (successNotice) notify(successNotice, 'info');

    loadMessages(false);

    loadLabels();

  };



  document.getElementById('btn-batch-mark-read')?.addEventListener('click', () =>

    executeBatch({ remove_labels: ['UNREAD'] })

  );

  document.getElementById('btn-batch-mark-unread')?.addEventListener('click', () =>

    executeBatch({ add_labels: ['UNREAD'] })

  );

  document.getElementById('btn-batch-trash')?.addEventListener('click', () => {

    const tmpl = t('ui.gmail.batch_trash_count', 'Перемещено писем в корзину: {count}');

    executeBatch('trash', tmpl.replace('{count}', selectedMessageIds.size));

  });



  document.getElementById('btn-view-trash-message')?.addEventListener('click', async () => {

    if (!currentViewMessage) return;

    await trashMessage(currentViewMessage.id);

    const modalEl = document.getElementById('gmailMessageViewModal');

    if (modalEl && typeof bootstrap !== 'undefined') {

      bootstrap.Modal.getInstance(modalEl)?.hide();

    }

  });



  document.getElementById('btn-view-toggle-unread')?.addEventListener('click', async () => {

    if (!currentViewMessage) return;

    await toggleReadStatus(currentViewMessage.id, false);

    const modalEl = document.getElementById('gmailMessageViewModal');

    if (modalEl && typeof bootstrap !== 'undefined') {

      bootstrap.Modal.getInstance(modalEl)?.hide();

    }

  });



  document.getElementById('btn-view-reply')?.addEventListener('click', () => {

    if (!currentViewMessage) return;

    const modalEl = document.getElementById('gmailMessageViewModal');

    if (modalEl && typeof bootstrap !== 'undefined') {

      bootstrap.Modal.getInstance(modalEl)?.hide();

    }



    const senderEmail = (currentViewMessage.from || '').match(/<([^>]+)>/)?.[1] || currentViewMessage.from;

    const subj = currentViewMessage.subject?.startsWith('Re:')

      ? currentViewMessage.subject

      : `Re: ${currentViewMessage.subject || ''}`;

    const quoteTmpl = t('ui.gmail.quote_header', '--- Исходное сообщение от {date} ---');

    const quote = `\n\n${quoteTmpl.replace('{date}', currentViewMessage.date)}\n${currentViewMessage.body_plain || ''}`;



    openComposeModal({ to: senderEmail, subject: subj, body: quote });

  });



  window.addEventListener('i18n:languageChanged', () => {

    updateFolderAndPaginationUI(lastLoadedMessages.length);

    loadProfile();

    if (lastLoadedMessages.length > 0) {

      renderMessages(lastLoadedMessages);

    }

  });



  loadProfile();

  loadLabels();

  loadMessages(true);

}



if (document.readyState === 'loading') {

  document.addEventListener('DOMContentLoaded', initGmailTab);

} else {

  initGmailTab();

}

