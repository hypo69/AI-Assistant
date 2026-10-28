/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Google Contacts Tab Controller
 * =============================================================================
 * Description:
 *   Клиентский контроллер управления контактами и телефонной книгой:
 *   поиск, фильтрация, карточки контактов, добавление и удаление.
 *
 * File: main.js
 * Package: apps/ai_assistant/api/webgui/tab_contacts
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-27 16:30:00
 * =============================================================================
 */

(function () {
  'use strict';

  let allContacts = [];

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function getInitials(name) {
    if (!name) return '?';
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) {
      return (parts[0][0] + parts[1][0]).toUpperCase();
    }
    return name.slice(0, 2).toUpperCase();
  }

  async function loadContacts() {
    const spinner = document.getElementById('contacts-loading-spinner');
    const emptyState = document.getElementById('contacts-empty-state');
    const listEl = document.getElementById('contacts-cards-list');
    const counterEl = document.getElementById('contacts-counter');

    if (spinner) spinner.classList.remove('d-none');
    if (emptyState) emptyState.classList.add('d-none');
    if (listEl) listEl.innerHTML = '';

    try {
      const qInput = document.getElementById('contacts-search-input');
      const query = qInput ? qInput.value.trim() : '';

      let url = `/api/v1/contacts?limit=60`;
      if (query) url += `&query=${encodeURIComponent(query)}`;

      const res = await fetch(url);
      const data = await res.json();

      if (!res.ok || data.status === 'error') {
        throw new Error(data.detail || data.error || 'Ошибка загрузки контактов');
      }

      allContacts = data.contacts || [];
      if (counterEl) counterEl.textContent = `Всего контактов: ${allContacts.length}`;
      renderContacts(allContacts);
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

  function renderContacts(contacts) {
    const listEl = document.getElementById('contacts-cards-list');
    const emptyState = document.getElementById('contacts-empty-state');
    if (!listEl) return;

    if (!contacts || contacts.length === 0) {
      listEl.innerHTML = '';
      if (emptyState) emptyState.classList.remove('d-none');
      return;
    }

    if (emptyState) emptyState.classList.add('d-none');

    listEl.innerHTML = contacts.map(c => {
      const initials = getInitials(c.display_name);
      const phones = (c.phones || []).map(p => `
        <div class="small mb-1">
          <i class="bi bi-telephone text-primary me-1"></i>
          <a href="tel:${escapeHtml(p.value)}" class="text-decoration-none fw-semibold">${escapeHtml(p.value)}</a>
          <span class="font-size-75 text-muted ms-1">(${escapeHtml(p.type)})</span>
        </div>
      `).join('');

      const emails = (c.emails || []).map(e => `
        <div class="small text-truncate mb-1">
          <i class="bi bi-envelope text-secondary me-1"></i>
          <a href="mailto:${escapeHtml(e.value)}" class="text-decoration-none">${escapeHtml(e.value)}</a>
        </div>
      `).join('');

      const org = (c.organizations && c.organizations[0]) ? `
        <div class="small text-muted mb-2 text-truncate">
          <i class="bi bi-building me-1"></i> ${escapeHtml(c.organizations[0].name || '')} ${c.organizations[0].title ? '· ' + escapeHtml(c.organizations[0].title) : ''}
        </div>
      ` : '';

      return `
        <div class="col-12 col-md-6 col-xl-4" id="contact-card-${escapeHtml(encodeURIComponent(c.resource_name))}">
          <div class="card h-100 shadow-sm border hover-shadow transition-all">
            <div class="card-body p-3 d-flex flex-column">
              <div class="d-flex align-items-center justify-content-between mb-3">
                <div class="d-flex align-items-center gap-2">
                  <div class="rounded-circle bg-primary text-white d-flex align-items-center justify-content-center fw-bold shadow-sm" style="width: 42px; height: 42px; font-size: 14px;">
                    ${escapeHtml(initials)}
                  </div>
                  <div>
                    <h6 class="fw-bold mb-0 text-truncate" title="${escapeHtml(c.display_name)}">${escapeHtml(c.display_name)}</h6>
                    <span class="font-size-75 text-muted font-monospace">${escapeHtml(c.resource_name || '')}</span>
                  </div>
                </div>
                <button class="btn btn-sm btn-outline-danger py-0 px-2 btn-delete-contact" data-resource="${escapeHtml(c.resource_name)}" title="Удалить контакт">
                  <i class="bi bi-trash3"></i>
                </button>
              </div>

              ${org}
              <div class="mb-2">
                ${phones || '<div class="small text-muted mb-1">Нет номеров телефона</div>'}
                ${emails}
              </div>

              ${c.notes ? `<div class="mt-auto pt-2 border-top small text-muted text-truncate-2">${escapeHtml(c.notes)}</div>` : ''}
            </div>
          </div>
        </div>
      `;
    }).join('');

    listEl.querySelectorAll('.btn-delete-contact').forEach(btn => {
      btn.addEventListener('click', async () => {
        const resName = btn.getAttribute('data-resource');
        if (!confirm('Вы действительно хотите удалить этот контакт из телефонной книги Google?')) return;
        try {
          btn.disabled = true;
          const res = await fetch(`/api/v1/contacts/${encodeURIComponent(resName)}`, { method: 'DELETE' });
          if (res.ok) {
            const card = document.getElementById(`contact-card-${encodeURIComponent(resName)}`);
            if (card) card.remove();
          } else {
            alert('Не удалось удалить контакт');
          }
        } catch (err) {
          alert('Ошибка при удалении контакта: ' + err.message);
        }
      });
    });
  }

  function setupEventHandlers() {
    const btnRefresh = document.getElementById('btn-contacts-refresh');
    if (btnRefresh) btnRefresh.addEventListener('click', loadContacts);

    const qInput = document.getElementById('contacts-search-input');
    if (qInput) {
      qInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') loadContacts();
      });
    }

    const btnClear = document.getElementById('btn-contacts-search-clear');
    if (btnClear && qInput) {
      btnClear.addEventListener('click', () => {
        qInput.value = '';
        loadContacts();
      });
    }

    // Открытие модалки создания
    const btnCreate = document.getElementById('btn-contacts-create');
    const modalEl = document.getElementById('modal-contacts-create');
    if (btnCreate && modalEl) {
      btnCreate.addEventListener('click', () => {
        const form = document.getElementById('form-contacts-create');
        if (form) form.reset();
        const errBox = document.getElementById('contacts-create-error');
        if (errBox) errBox.classList.add('d-none');
        const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.show();
      });
    }

    // Сохранение контакта
    const btnSave = document.getElementById('btn-contacts-save');
    if (btnSave) {
      btnSave.addEventListener('click', async () => {
        const givenName = document.getElementById('cnt-create-given-name')?.value.trim();
        const familyName = document.getElementById('cnt-create-family-name')?.value.trim();
        const phone = document.getElementById('cnt-create-phone')?.value.trim();
        const email = document.getElementById('cnt-create-email')?.value.trim();
        const org = document.getElementById('cnt-create-org')?.value.trim();
        const title = document.getElementById('cnt-create-title')?.value.trim();
        const notes = document.getElementById('cnt-create-notes')?.value.trim();
        const errBox = document.getElementById('contacts-create-error');

        if (!givenName) {
          if (errBox) {
            errBox.textContent = 'Пожалуйста, укажите имя контакта';
            errBox.classList.remove('d-none');
          }
          return;
        }

        try {
          btnSave.disabled = true;
          const res = await fetch('/api/v1/contacts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              given_name: givenName,
              family_name: familyName,
              phone: phone || null,
              email: email || null,
              organization: org || null,
              title: title || null,
              notes: notes || null,
            }),
          });
          const data = await res.json();
          if (!res.ok || data.status === 'error') {
            throw new Error(data.detail || data.error || 'Ошибка при сохранении контакта');
          }

          const modal = bootstrap.Modal.getInstance(modalEl);
          if (modal) modal.hide();
          loadContacts();
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

  window.initContactsTab = function () {
    setupEventHandlers();
    loadContacts();
  };

  window.deactivateContactsTab = function () {
    allContacts = [];
  };
})();
