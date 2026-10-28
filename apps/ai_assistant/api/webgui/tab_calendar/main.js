/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Google Calendar Tab Controller
 * =============================================================================
 * Description:
 *   Клиентский контроллер управления событиями Google Calendar: выборка,
 *   отображение списка, фильтрация, создание новых встреч и удаление.
 *
 * File: main.js
 * Package: apps/ai_assistant/api/webgui/tab_calendar
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-27 16:30:00
 * =============================================================================
 */

(function () {
  'use strict';

  let currentDays = 7;
  let allEvents = [];

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function formatDateTime(isoStr) {
    if (!isoStr) return '';
    try {
      const d = new Date(isoStr);
      return d.toLocaleString(undefined, {
        month: 'short',
        day: 'numeric',
        weekday: 'short',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return isoStr;
    }
  }

  async function loadEvents() {
    const spinner = document.getElementById('calendar-loading-spinner');
    const emptyState = document.getElementById('calendar-empty-state');
    const listEl = document.getElementById('calendar-events-list');

    if (spinner) spinner.classList.remove('d-none');
    if (emptyState) emptyState.classList.add('d-none');
    if (listEl) listEl.innerHTML = '';

    try {
      const qInput = document.getElementById('calendar-search-input');
      const query = qInput ? qInput.value.trim() : '';

      let url = `/api/v1/calendar/events?days=${currentDays}&limit=50`;
      if (query) url += `&query=${encodeURIComponent(query)}`;

      const res = await fetch(url);
      const data = await res.json();

      if (!res.ok || data.status === 'error') {
        throw new Error(data.detail || data.error || 'Ошибка загрузки календаря');
      }

      allEvents = data.events || [];
      renderEvents(allEvents);
    } catch (err) {
      if (listEl) {
        listEl.innerHTML = `
          <div class="col-12">
            <div class="alert alert-danger py-2 small shadow-sm">
              <i class="bi bi-exclamation-triangle-fill me-1"></i> ${escapeHtml(err.message)}
            </div>
          </div>`;
      }
    } finally {
      if (spinner) spinner.classList.add('d-none');
    }
  }

  function renderEvents(events) {
    const listEl = document.getElementById('calendar-events-list');
    const emptyState = document.getElementById('calendar-empty-state');
    if (!listEl) return;

    if (!events || events.length === 0) {
      listEl.innerHTML = '';
      if (emptyState) emptyState.classList.remove('d-none');
      return;
    }

    if (emptyState) emptyState.classList.add('d-none');

    listEl.innerHTML = events.map(ev => {
      const startStr = formatDateTime(ev.start);
      const endStr = formatDateTime(ev.end);
      const attendees = (ev.attendees || []).map(a => `<span class="badge bg-secondary-subtle text-body border font-size-75 me-1">${escapeHtml(a)}</span>`).join('');
      const locBadge = ev.location ? `<div class="small text-muted mb-1"><i class="bi bi-geo-alt me-1 text-danger"></i>${escapeHtml(ev.location)}</div>` : '';
      const linkBtn = ev.html_link ? `<a href="${escapeHtml(ev.html_link)}" target="_blank" class="btn btn-sm btn-outline-primary py-0 px-2" title="Открыть в Google Calendar"><i class="bi bi-box-arrow-up-right"></i></a>` : '';

      return `
        <div class="col-12 col-md-6 col-xl-4" id="calendar-card-${escapeHtml(ev.id)}">
          <div class="card h-100 shadow-sm border hover-shadow transition-all">
            <div class="card-body d-flex flex-column p-3">
              <div class="d-flex justify-content-between align-items-start mb-2">
                <span class="badge bg-primary-subtle text-primary border border-primary-subtle py-1 px-2 font-size-80">
                  <i class="bi bi-clock me-1"></i>${escapeHtml(startStr)}
                </span>
                <div class="d-flex gap-1">
                  ${linkBtn}
                  <button class="btn btn-sm btn-outline-danger py-0 px-2 btn-delete-event" data-event-id="${escapeHtml(ev.id)}" title="Удалить событие">
                    <i class="bi bi-trash3"></i>
                  </button>
                </div>
              </div>
              <h6 class="fw-bold mb-1 text-truncate" title="${escapeHtml(ev.summary)}">${escapeHtml(ev.summary)}</h6>
              ${locBadge}
              ${ev.description ? `<p class="small text-muted mb-2 text-truncate-2">${escapeHtml(ev.description)}</p>` : ''}
              <div class="mt-auto pt-2 border-top">
                ${attendees ? `<div class="d-flex flex-wrap align-items-center">${attendees}</div>` : '<span class="small text-muted">Без участников</span>'}
              </div>
            </div>
          </div>
        </div>
      `;
    }).join('');

    // Навешивание обработчиков удаления
    listEl.querySelectorAll('.btn-delete-event').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const id = btn.getAttribute('data-event-id');
        if (!confirm('Вы уверены, что хотите удалить это событие из Google Календаря?')) return;
        try {
          btn.disabled = true;
          const res = await fetch(`/api/v1/calendar/events/${id}`, { method: 'DELETE' });
          if (res.ok) {
            const card = document.getElementById(`calendar-card-${id}`);
            if (card) card.remove();
          } else {
            alert('Не удалось удалить событие');
          }
        } catch (err) {
          alert('Ошибка при удалении: ' + err.message);
        }
      });
    });
  }

  function setupEventHandlers() {
    const btnRefresh = document.getElementById('btn-calendar-refresh');
    if (btnRefresh) btnRefresh.addEventListener('click', loadEvents);

    const qInput = document.getElementById('calendar-search-input');
    if (qInput) {
      qInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') loadEvents();
      });
    }

    const btnClear = document.getElementById('btn-calendar-search-clear');
    if (btnClear && qInput) {
      btnClear.addEventListener('click', () => {
        qInput.value = '';
        loadEvents();
      });
    }

    // Радиокнопки дней
    document.querySelectorAll('input[name="calendar-days"]').forEach(radio => {
      radio.addEventListener('change', (e) => {
        currentDays = parseInt(e.target.value, 10) || 7;
        loadEvents();
      });
    });

    // Открытие модалки создания
    const btnCreate = document.getElementById('btn-calendar-create');
    const modalEl = document.getElementById('modal-calendar-create');
    if (btnCreate && modalEl) {
      btnCreate.addEventListener('click', () => {
        const form = document.getElementById('form-calendar-create');
        if (form) form.reset();
        const errBox = document.getElementById('cal-create-error');
        if (errBox) errBox.classList.add('d-none');

        // Установка времени по умолчанию (через 1 час)
        const now = new Date();
        now.setHours(now.getHours() + 1, 0, 0, 0);
        const end = new Date(now.getTime() + 60 * 60 * 1000);

        const formatIsoInput = (d) => {
          const tzOffset = d.getTimezoneOffset() * 60000;
          return new Date(d.getTime() - tzOffset).toISOString().slice(0, 16);
        };

        const startInput = document.getElementById('cal-create-start');
        const endInput = document.getElementById('cal-create-end');
        if (startInput) startInput.value = formatIsoInput(now);
        if (endInput) endInput.value = formatIsoInput(end);

        const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.show();
      });
    }

    // Сохранение нового события
    const btnSave = document.getElementById('btn-calendar-save-event');
    if (btnSave) {
      btnSave.addEventListener('click', async () => {
        const summary = document.getElementById('cal-create-summary')?.value.trim();
        const start = document.getElementById('cal-create-start')?.value;
        const end = document.getElementById('cal-create-end')?.value;
        const loc = document.getElementById('cal-create-location')?.value.trim();
        const attendeesRaw = document.getElementById('cal-create-attendees')?.value.trim();
        const desc = document.getElementById('cal-create-desc')?.value.trim();
        const errBox = document.getElementById('cal-create-error');

        if (!summary || !start || !end) {
          if (errBox) {
            errBox.textContent = 'Пожалуйста, заполните тему и время события';
            errBox.classList.remove('d-none');
          }
          return;
        }

        const attendees = attendeesRaw ? attendeesRaw.split(',').map(s => s.trim()).filter(Boolean) : [];

        try {
          btnSave.disabled = true;
          const res = await fetch('/api/v1/calendar/events', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              summary,
              start_time: new Date(start).toISOString(),
              end_time: new Date(end).toISOString(),
              location: loc,
              attendees,
              description: desc,
            }),
          });
          const data = await res.json();
          if (!res.ok || data.status === 'error') {
            throw new Error(data.detail || data.error || 'Ошибка при создании события');
          }

          const modal = bootstrap.Modal.getInstance(modalEl);
          if (modal) modal.hide();
          loadEvents();
        } catch (err) {
          if (errBox) {
            errBox.textContent = err.message;
            errBox.classList.remove('d-none');
          }
        } finally {
          btnSave.disabled = false;
        }
      });
    }
  }

  window.initCalendarTab = function () {
    setupEventHandlers();
    loadEvents();
  };

  window.deactivateCalendarTab = function () {
    allEvents = [];
  };
})();
