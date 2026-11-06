/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Smart Tasks & Workflows Controller
 * =============================================================================
 * Description:
 *   Контроллер вкладки умных задач и поручений. Обеспечивает интерактивную
 *   ИИ-декомпозицию звонков, управление кейсами сделок, координацию участников,
 *   связку с календарем и двухстороннее переключение субпанелей.
 *
 * File: main.js
 * Package: apps/ai_assistant/api/webgui/tab_tasks
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-06 23:30:00
 * =============================================================================
 */

let currentCases = [];
let selectedCaseId = null;
let currentPreviewPlan = null;
let isInitialized = false;

const COW_DEMO_TEXT = `Дядя Моше позвонил и попросил срочно заняться вопросом:
"Я договорился со Шмуликом о покупке у него коровы для нашего хозяйства.
Нужно подготовить полный пакет документации на передачу права собственности,
договориться с нашим ветеринаром д-ром Левиным о выездном осмотре коровы прямо
в загоне у Шмулика, а также согласовать приезд страхового агента из 'АгроСтрах'
для оценки и оформления страховки до того, как мы переведем деньги."`;

/**
 * Инициализирует вкладку задач.
 */
export async function initTasksTab() {
  if (isInitialized) {
    await loadCases();
    return;
  }
  isInitialized = true;

  setupSubtabsNavigation();
  setupTasksHashRouting();
  setupEventListeners();
  await loadCases();

  // Регистрация поллера активной вкладки
  if (window.registerTabPoller) {
    window.registerTabPoller('tasks', async () => {
      await loadCases(true);
    }, 15000);
  }
}

/**
 * Деактивация вкладки при переключении.
 */
export function deactivateTasksTab() {
  // Освобождение ресурсов при необходимости
}

/**
 * Настройка переключения субпанелей (Уровень 1).
 */
function setupSubtabsNavigation() {
  const nav = document.getElementById('tasks-subtabs-nav');
  if (!nav) return;

  nav.addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-panel-id]');
    if (!btn) return;

    const panelId = btn.getAttribute('data-panel-id');
    switchSubpane(panelId);
  });
}

/**
 * Переключает субпанель по её panelId.
 */
function switchSubpane(panelId, updateHash = true) {
  // Активируем кнопку в меню
  const navBtns = document.querySelectorAll('#tasks-subtabs-nav button[data-panel-id]');
  navBtns.forEach(b => {
    if (b.getAttribute('data-panel-id') === panelId) {
      b.classList.add('active');
    } else {
      b.classList.remove('active');
    }
  });

  // Переключаем видимость контейнеров
  const paneSuffix = panelId.replace('panel-', '');
  const panes = document.querySelectorAll('.tasks-subpane');
  panes.forEach(p => {
    if (p.id === `tasks-subpane-${paneSuffix}`) {
      p.classList.remove('d-none');
      p.classList.add('active');
    } else {
      p.classList.add('d-none');
      p.classList.remove('active');
    }
  });

  if (updateHash && window.history?.replaceState) {
    window.history.replaceState(null, null, `#tab-tasks#${panelId}`);
  }
}

/**
 * Синхронизирует выбранную субпанель с URL-хэшем.
 */
function setupTasksHashRouting() {
  const syncFromHash = () => {
    const rawHash = window.location.hash || '';
    if (!rawHash.includes('#tab-tasks#')) return;

    const panelId = rawHash
      .replace(/^#tab-tasks#/, '')
      .split('#')[0];

    if (panelId && document.querySelector(`button[data-panel-id="${panelId}"]`)) {
      switchSubpane(panelId, false);
    }
  };

  window.addEventListener('hashchange', syncFromHash);
  syncFromHash();
}

/**
 * Привязка обработчиков событий элементов UI.
 */
function setupEventListeners() {
  // Кнопка обновления
  const refreshBtn = document.getElementById('btn-tasks-refresh');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', () => loadCases());
  }

  // Кнопка быстрого демо дяди Моше
  const demoBtn = document.getElementById('btn-tasks-load-demo');
  if (demoBtn) {
    demoBtn.addEventListener('click', async () => {
      switchSubpane('panel-intake');
      const textEl = document.getElementById('tasks-intake-text');
      if (textEl) textEl.value = COW_DEMO_TEXT;
      await runDecomposition();
    });
  }

  // Кнопка создания нового поручения
  const newBtn = document.getElementById('btn-tasks-new-intake');
  if (newBtn) {
    newBtn.addEventListener('click', () => {
      switchSubpane('panel-intake');
      const textEl = document.getElementById('tasks-intake-text');
      if (textEl) textEl.focus();
    });
  }

  // Вставка примера дяди Моше в intake
  const pasteDemoBtn = document.getElementById('btn-tasks-paste-cow-demo');
  if (pasteDemoBtn) {
    pasteDemoBtn.addEventListener('click', () => {
      const textEl = document.getElementById('tasks-intake-text');
      if (textEl) textEl.value = COW_DEMO_TEXT;
    });
  }

  // Очистка intake
  const clearIntakeBtn = document.getElementById('btn-tasks-clear-intake');
  if (clearIntakeBtn) {
    clearIntakeBtn.addEventListener('click', () => {
      const textEl = document.getElementById('tasks-intake-text');
      if (textEl) textEl.value = '';
      resetPreviewCard();
    });
  }

  // Запуск ИИ декомпозиции
  const decompBtn = document.getElementById('btn-tasks-decompose-action');
  if (decompBtn) {
    decompBtn.addEventListener('click', runDecomposition);
  }

  // Подтверждение создания дела из плана
  const confirmCreateBtn = document.getElementById('btn-tasks-confirm-create');
  if (confirmCreateBtn) {
    confirmCreateBtn.addEventListener('click', createCaseFromPlan);
  }

  // Удаление текущего дела
  const deleteBtn = document.getElementById('btn-tasks-delete-case');
  if (deleteBtn) {
    deleteBtn.addEventListener('click', deleteCurrentCase);
  }

  // Синхронизация календаря для ветеринара
  const syncVetBtn = document.getElementById('btn-tasks-sync-vet-calendar');
  if (syncVetBtn) {
    syncVetBtn.addEventListener('click', () => syncCalendar('vet'));
  }

  // Синхронизация календаря для страховщика
  const syncInsBtn = document.getElementById('btn-tasks-sync-ins-calendar');
  if (syncInsBtn) {
    syncInsBtn.addEventListener('click', () => syncCalendar('insurance'));
  }
}

/**
 * Загружает список дел с бэкенда и обновляет метрики.
 */
async function loadCases(silent = false) {
  try {
    const res = await fetch('/api/v1/tasks/cases');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    currentCases = data.cases || [];

    renderMetrics(currentCases);
    renderCasesList(currentCases);

    if (currentCases.length > 0) {
      if (!selectedCaseId || !currentCases.some(c => c.id === selectedCaseId)) {
        await selectCase(currentCases[0].id);
      } else {
        await selectCase(selectedCaseId, true);
      }
    } else {
      renderEmptyCaseDetail();
    }
  } catch (err) {
    if (!silent) {
      console.warn('[TasksTab] Ошибка загрузки списка дел:', err);
      showToast('Ошибка загрузки задач: ' + err.message, 'danger');
    }
  }
}

/**
 * Отрисовывает сводные метрики.
 */
function renderMetrics(cases) {
  const total = cases.length;
  const active = cases.filter(c => c.status === 'active').length;
  const completed = cases.filter(c => c.status === 'completed').length;
  const coord = cases.reduce((acc, c) => acc + (c.total_items > 0 ? 1 : 0), 0);

  const setVal = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.textContent = String(val);
  };

  setVal('tasks-stat-total-val', total);
  setVal('tasks-stat-active-val', active);
  setVal('tasks-stat-coord-val', coord);
  setVal('tasks-stat-completed-val', completed);
}

/**
 * Отрисовывает список дел в левой колонке.
 */
function renderCasesList(cases) {
  const container = document.getElementById('tasks-cases-list-container');
  const badge = document.getElementById('tasks-cases-badge');
  if (!container) return;

  if (badge) badge.textContent = `${cases.length} дел`;

  if (cases.length === 0) {
    container.innerHTML = `
      <div class="text-center text-muted py-5" id="tasks-empty-state">
        <i class="bi bi-inbox fs-1 opacity-50 d-block mb-2"></i>
        <span>Нет активных дел. Создайте новое или загрузите пример.</span>
      </div>
    `;
    return;
  }

  container.innerHTML = cases.map(c => {
    const isSelected = c.id === selectedCaseId;
    const activeClass = isSelected ? 'border-primary bg-primary-subtle' : 'border-light-subtle';
    const progress = c.progress_percent || 0;

    return `
      <div class="card mb-2 p-2.5 cursor-pointer shadow-sm ${activeClass} case-card-item" data-case-id="${c.id}">
        <div class="d-flex justify-content-between align-items-start mb-1">
          <div class="fw-semibold small text-truncate pe-2" title="${c.title}">${c.title}</div>
          <span class="badge ${c.status === 'completed' ? 'bg-success' : 'bg-primary'} font-monospace small">
            ${c.completed_items || 0}/${c.total_items || 0}
          </span>
        </div>
        <div class="small text-muted text-truncate mb-2">${c.description.split('\n')[0] || ''}</div>
        <div class="progress" style="height: 4px;">
          <div class="progress-bar ${progress === 100 ? 'bg-success' : 'bg-primary'}" style="width: ${progress}%"></div>
        </div>
      </div>
    `;
  }).join('');

  // Обработчик клика по карточке дела
  container.querySelectorAll('.case-card-item').forEach(el => {
    el.addEventListener('click', () => {
      const caseId = el.getAttribute('data-case-id');
      selectCase(caseId);
    });
  });
}

/**
 * Выбирает дело и отображает его детали.
 */
async function selectCase(caseId, silent = false) {
  selectedCaseId = caseId;

  // Подсветка в списке
  document.querySelectorAll('.case-card-item').forEach(el => {
    if (el.getAttribute('data-case-id') === caseId) {
      el.classList.add('border-primary', 'bg-primary-subtle');
    } else {
      el.classList.remove('border-primary', 'bg-primary-subtle');
    }
  });

  try {
    const res = await fetch(`/api/v1/tasks/cases/${caseId}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const c = data.case;
    if (!c) return;

    renderCaseDetail(c);
  } catch (err) {
    if (!silent) {
      console.warn('[TasksTab] Ошибка получения деталей дела:', err);
    }
  }
}

/**
 * Отрисовывает детальную информацию о выбранном деле.
 */
function renderCaseDetail(c) {
  const titleEl = document.getElementById('tasks-detail-title');
  const descEl = document.getElementById('tasks-detail-description');
  const statusBadge = document.getElementById('tasks-detail-status-badge');
  const catBadge = document.getElementById('tasks-detail-category-badge');
  const progressBar = document.getElementById('tasks-detail-progress-bar');
  const progressText = document.getElementById('tasks-detail-progress-text');
  const actorsList = document.getElementById('tasks-detail-actors-list');
  const itemsList = document.getElementById('tasks-items-list-group');
  const subtasksCount = document.getElementById('tasks-subtasks-count');

  if (titleEl) titleEl.textContent = c.title;
  if (descEl) descEl.textContent = c.description;

  if (statusBadge) {
    statusBadge.textContent = c.status === 'completed' ? 'Завершено' : 'В работе';
    statusBadge.className = `badge ${c.status === 'completed' ? 'bg-success-subtle text-success' : 'bg-primary-subtle text-primary'} border`;
  }

  if (catBadge) {
    catBadge.textContent = c.category === 'deal' ? 'Сделка' : 'Поручение';
  }

  // Расчет прогресса
  const items = c.items || [];
  const completed = items.filter(it => it.status === 'done').length;
  const pct = items.length > 0 ? Math.round((completed / items.length) * 100) : 0;

  if (progressBar) progressBar.style.width = `${pct}%`;
  if (progressText) progressText.textContent = `${pct}% (${completed}/${items.length})`;
  if (subtasksCount) subtasksCount.textContent = `${completed}/${items.length}`;

  // Отрисовка участников
  if (actorsList) {
    const actors = c.actors || [];
    if (actors.length === 0) {
      actorsList.innerHTML = '<span class="badge bg-light text-muted border">—</span>';
    } else {
      actorsList.innerHTML = actors.map(a => `
        <span class="badge bg-secondary-subtle text-secondary border d-inline-flex align-items-center gap-1 py-1 px-2">
          <i class="bi bi-person"></i>
          <strong>${a.name}</strong>
          <span class="opacity-75 font-monospace small">(${a.title || a.role})</span>
        </span>
      `).join('');
    }
  }

  // Отрисовка подзадач чек-листа
  if (itemsList) {
    if (items.length === 0) {
      itemsList.innerHTML = '<div class="list-group-item text-muted small text-center py-3">Нет подзадач в данном деле</div>';
      return;
    }

    itemsList.innerHTML = items.map(it => {
      const isDone = it.status === 'done';
      const stageIcon = getStageIcon(it.stage);

      return `
        <div class="list-group-item d-flex align-items-start gap-2.5 py-2.5">
          <input class="form-check-input mt-1 cursor-pointer task-item-checkbox" type="checkbox"
                 data-item-id="${it.id}" ${isDone ? 'checked' : ''}>
          <div class="flex-grow-1">
            <div class="d-flex align-items-center justify-content-between">
              <span class="fw-semibold small ${isDone ? 'text-decoration-line-through text-muted' : ''}">
                ${stageIcon} ${it.title}
              </span>
              <span class="badge bg-light text-secondary border font-monospace small">${it.stage}</span>
            </div>
            <div class="small text-muted mt-0.5 ${isDone ? 'text-decoration-line-through' : ''}">
              ${it.description}
            </div>
          </div>
        </div>
      `;
    }).join('');

    // Слушатели переключения чекбоксов
    itemsList.querySelectorAll('.task-item-checkbox').forEach(cb => {
      cb.addEventListener('change', async (e) => {
        const itemId = e.target.getAttribute('data-item-id');
        const newStatus = e.target.checked ? 'done' : 'todo';
        await updateTaskItemStatus(itemId, newStatus);
      });
    });
  }
}

/**
 * Иконка для стадии задачи.
 */
function getStageIcon(stage) {
  switch (stage) {
    case 'documents': return '<i class="bi bi-file-earmark-text text-primary me-1"></i>';
    case 'vet_inspection': return '<i class="bi bi-hospital text-success me-1"></i>';
    case 'insurance': return '<i class="bi bi-shield-check text-info me-1"></i>';
    case 'closing': return '<i class="bi bi-check-circle text-warning me-1"></i>';
    default: return '<i class="bi bi-circle text-secondary me-1"></i>';
  }
}

/**
 * Обновляет статус конкретной подзадачи.
 */
async function updateTaskItemStatus(itemId, status) {
  try {
    const res = await fetch(`/api/v1/tasks/items/${itemId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status })
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    await loadCases(true);
    showToast(status === 'done' ? 'Этап завершен' : 'Этап возвращен в работу', 'info');
  } catch (err) {
    console.warn('[TasksTab] Ошибка обновления статуса этапа:', err);
    showToast('Ошибка сохранения статуса: ' + err.message, 'danger');
  }
}

/**
 * Удаляет выбранное дело.
 */
async function deleteCurrentCase() {
  if (!selectedCaseId) return;
  if (!confirm('Вы уверены, что хотите удалить выбранное дело и все его этапы?')) return;

  try {
    const res = await fetch(`/api/v1/tasks/cases/${selectedCaseId}`, { method: 'DELETE' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    selectedCaseId = null;
    await loadCases();
    showToast('Дело успешно удалено', 'success');
  } catch (err) {
    console.warn('[TasksTab] Ошибка удаления дела:', err);
    showToast('Ошибка удаления: ' + err.message, 'danger');
  }
}

/**
 * Очищает детали дела при пустом списке.
 */
function renderEmptyCaseDetail() {
  const titleEl = document.getElementById('tasks-detail-title');
  const descEl = document.getElementById('tasks-detail-description');
  const itemsList = document.getElementById('tasks-items-list-group');
  const actorsList = document.getElementById('tasks-detail-actors-list');

  if (titleEl) titleEl.textContent = 'Нет активных дел';
  if (descEl) descEl.textContent = 'Используйте мастер разбора разговора, чтобы создать новое дело.';
  if (itemsList) itemsList.innerHTML = '<div class="list-group-item text-muted small text-center py-3">Список задач пуст</div>';
  if (actorsList) actorsList.innerHTML = '<span class="badge bg-light text-muted border">—</span>';
}

/**
 * Выполняет ИИ декомпозицию сырого текста.
 */
async function runDecomposition() {
  const textEl = document.getElementById('tasks-intake-text');
  const sourceEl = document.getElementById('tasks-intake-source');
  const text = textEl ? textEl.value.trim() : '';
  const sourceLabel = sourceEl ? sourceEl.value : 'Телефонный разговор';

  if (!text) {
    showToast('Пожалуйста, введите текст разговора или поручения', 'warning');
    return;
  }

  const decompBtn = document.getElementById('btn-tasks-decompose-action');
  if (decompBtn) {
    decompBtn.disabled = true;
    decompBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Анализ...';
  }

  try {
    const res = await fetch('/api/v1/tasks/decompose', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, source_label: sourceLabel })
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    currentPreviewPlan = data.plan;

    renderPlanPreview(currentPreviewPlan);
    showToast('Поручение успешно декомпозировано ИИ', 'success');
  } catch (err) {
    console.warn('[TasksTab] Ошибка декомпозиции:', err);
    showToast('Ошибка декомпозиции: ' + err.message, 'danger');
  } finally {
    if (decompBtn) {
      decompBtn.disabled = false;
      decompBtn.innerHTML = '<i class="bi bi-cpu"></i> <span>Разобрать с помощью ИИ</span>';
    }
  }
}

/**
 * Отрисовывает предпросмотр сгенерированного плана.
 */
function renderPlanPreview(plan) {
  const placeholder = document.getElementById('tasks-preview-placeholder');
  const content = document.getElementById('tasks-preview-content');
  const titleEl = document.getElementById('tasks-preview-title');
  const descEl = document.getElementById('tasks-preview-desc');
  const actorsEl = document.getElementById('tasks-preview-actors');
  const stepsEl = document.getElementById('tasks-preview-steps');
  const badge = document.getElementById('tasks-preview-badge');

  if (placeholder) placeholder.classList.add('d-none');
  if (content) content.classList.remove('d-none');
  if (badge) {
    badge.textContent = 'Готово к запуску';
    badge.className = 'badge bg-success-subtle text-success border';
  }

  if (titleEl) titleEl.textContent = plan.title;
  if (descEl) descEl.textContent = plan.description;

  if (actorsEl) {
    actorsEl.innerHTML = (plan.actors || []).map(a => `
      <span class="badge bg-primary-subtle text-primary border d-inline-flex align-items-center gap-1 py-1 px-2">
        <i class="bi bi-person-fill"></i>
        <strong>${a.name}</strong>
        <span class="opacity-75 font-monospace small">(${a.title})</span>
      </span>
    `).join('');
  }

  if (stepsEl) {
    stepsEl.innerHTML = (plan.items || []).map((step, idx) => `
      <div class="list-group-item py-2 px-2.5">
        <div class="d-flex align-items-center justify-content-between mb-0.5">
          <span class="fw-semibold small text-primary">${idx + 1}. ${step.title}</span>
          <span class="badge bg-secondary-subtle text-secondary font-monospace small">${step.stage}</span>
        </div>
        <div class="small text-muted">${step.description}</div>
      </div>
    `).join('');
  }
}

/**
 * Сбрасывает карточку предпросмотра.
 */
function resetPreviewCard() {
  currentPreviewPlan = null;
  const placeholder = document.getElementById('tasks-preview-placeholder');
  const content = document.getElementById('tasks-preview-content');
  const badge = document.getElementById('tasks-preview-badge');

  if (placeholder) placeholder.classList.remove('d-none');
  if (content) content.classList.add('d-none');
  if (badge) {
    badge.textContent = 'Ожидание';
    badge.className = 'badge bg-info-subtle text-info border';
  }
}

/**
 * Создает комплексное дело на сервере на основании предпросмотра плана.
 */
async function createCaseFromPlan() {
  if (!currentPreviewPlan) {
    showToast('Сначала разберите текст поручения', 'warning');
    return;
  }

  const textEl = document.getElementById('tasks-intake-text');
  const rawTranscript = textEl ? textEl.value.trim() : '';

  try {
    const res = await fetch('/api/v1/tasks/cases', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: currentPreviewPlan.title,
        description: currentPreviewPlan.description,
        category: currentPreviewPlan.category || 'deal',
        raw_transcript: rawTranscript,
        actors: currentPreviewPlan.actors || [],
        items: currentPreviewPlan.items || []
      })
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const createdCase = data.case;

    showToast(`Дело "${createdCase.title}" успешно создано!`, 'success');
    resetPreviewCard();
    if (textEl) textEl.value = '';

    // Переключаемся на субпанель дел и выбираем созданное дело
    switchSubpane('panel-cases');
    await loadCases();
    if (createdCase && createdCase.id) {
      await selectCase(createdCase.id);
    }
  } catch (err) {
    console.warn('[TasksTab] Ошибка создания дела:', err);
    showToast('Ошибка создания дела: ' + err.message, 'danger');
  }
}

/**
 * Синхронизирует этап визита с календарем.
 */
async function syncCalendar(role) {
  const isVet = role === 'vet';
  const summary = isVet ? 'Осмотр коровы ветеринаром (Ферма Шмулика)' : 'Осмотр коровы страховым агентом (Ферма Шмулика)';
  const dateEl = document.getElementById(isVet ? 'tasks-vet-date' : 'tasks-ins-date');
  const timeEl = document.getElementById(isVet ? 'tasks-vet-time' : 'tasks-ins-time');
  const locEl = document.getElementById(isVet ? 'tasks-vet-location' : 'tasks-ins-location');

  const dateVal = dateEl ? dateEl.value : '2026-11-05';
  const timeVal = timeEl ? timeEl.value : '10:00';
  const location = locEl ? locEl.value : 'Хозяйство Шмулика';

  try {
    const res = await fetch('/api/v1/tasks/actions/sync_calendar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        case_id: selectedCaseId || 'demo_case',
        item_id: isVet ? 'vet_step' : 'ins_step',
        summary,
        start_time: `${dateVal}T${timeVal}:00`,
        end_time: `${dateVal}T${parseInt(timeVal) + 1}:00:00`,
        location,
        attendees: []
      })
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    showToast(data.message || 'Событие добавлено в Google Calendar', 'success');
  } catch (err) {
    showToast('Ошибка синхронизации с календарем: ' + err.message, 'danger');
  }
}

/**
 * Выводит тост уведомление пользователю.
 */
function showToast(message, variant = 'info') {
  if (window.toast) {
    window.toast(message, variant);
  } else {
    console.log(`[Toast ${variant}]:`, message);
  }
}
