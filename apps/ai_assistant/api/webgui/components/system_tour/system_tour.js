/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - System Tour Guide Controller
 * =============================================================================
 * Description:
 *   Клиентский контроллер интерактивного гид-тура по возможностям системы
 *   умного хранения документации AI Assistant.
 *   Демонстрирует ключевые архитектурные модули:
 *   1. Изолированные рабочие области с индивидуальным Git-репозиторием.
 *   2. Автоматическое извлечение фактов через многоязычные NLP-анализаторы (RU/HE/EN).
 *   3. Темпоральный граф знаний WikiLLM (valid_from, valid_to, superseded_by).
 *   4. 5-этапный гибридный конвейер поиска RAG (FAISS + лексический + грамматика).
 *   5. 2-Step контур верификации и защита от prompt-инъекций.
 *   6. Аудит изменений: шкала времени, коммиты, Diff и Smart Blame.
 *
 * File: system_tour.js
 * Package: apps/ai_assistant/api/webgui/components/system_tour
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-26 01:57:00
 * =============================================================================
 */

(function () {
  'use strict';

  const MODAL_ID = 'system-tour-modal';
  const STORAGE_KEY = 'ai_assistant_tour_seen';

  /**
   * Шаги интерактивного гид-тура по системе умного хранения документации.
   */
  const TOUR_STEPS = [
    {
      id: 'step-overview',
      stepNumber: 1,
      badge: 'Архитектура',
      badgeClass: 'bg-primary-subtle text-primary border',
      icon: 'bi-cpu-fill',
      title: 'Умное Хранилище Документации нового поколения',
      subtitle: 'Синергия версионирования Git, базы знаний KnowledgeStore, WikiLLM и FAISS RAG',
      tabTarget: 'tab-workspace',
      actionText: 'Перейти к Рабочей области',
      contentHtml: `
        <div class="tour-feature-card">
          <div class="d-flex align-items-center gap-2 mb-2">
            <span class="fs-5 text-primary"><i class="bi bi-shield-check"></i></span>
            <span class="fw-bold">Детерминированная история без галлюцинаций</span>
          </div>
          <p class="small mb-2 text-body">
            В отличие от классических баз данных, где история изменений стирается или теряется в журналах,
            наша система использует <strong>реальные локальные репозитории Git</strong>. Каждая версия документа
            фиксируется криптографическим хэшем SHA-1, автором и временной меткой.
          </p>
          <div class="tour-pipeline-flow">
            <div class="tour-pipeline-step"><i class="bi bi-folder-check text-info"></i> Документ (.md/.txt/.json)</div>
            <div class="tour-pipeline-arrow">&rarr;</div>
            <div class="tour-pipeline-step"><i class="bi bi-git text-danger"></i> Git Commit</div>
            <div class="tour-pipeline-arrow">&rarr;</div>
            <div class="tour-pipeline-step"><i class="bi bi-diagram-2 text-warning"></i> NLP Извлечение</div>
            <div class="tour-pipeline-arrow">&rarr;</div>
            <div class="tour-pipeline-step"><i class="bi bi-database text-success"></i> SQLite + FAISS</div>
            <div class="tour-pipeline-arrow">&rarr;</div>
            <div class="tour-pipeline-step"><i class="bi bi-chat-text text-primary"></i> Q&A с падежами</div>
          </div>
        </div>

        <div class="row g-2">
          <div class="col-md-4">
            <div class="p-2.5 rounded bg-body-tertiary border h-100">
              <div class="fw-semibold small text-primary mb-1"><i class="bi bi-translate me-1"></i>3 Языка из коробки</div>
              <div class="small text-muted font-size-78">Морфология русского, иврита (RTL) и английского с точным склонением ответов.</div>
            </div>
          </div>
          <div class="col-md-4">
            <div class="p-2.5 rounded bg-body-tertiary border h-100">
              <div class="fw-semibold small text-success mb-1"><i class="bi bi-clock-history me-1"></i>Темпоральный граф</div>
              <div class="small text-muted font-size-78">Автоматический учет интервалов валидности фактов (valid_from / valid_to).</div>
            </div>
          </div>
          <div class="col-md-4">
            <div class="p-2.5 rounded bg-body-tertiary border h-100">
              <div class="fw-semibold small text-warning mb-1"><i class="bi bi-search me-1"></i>5-этапный RAG</div>
              <div class="small text-muted font-size-78">Гибридный поиск: точные факты, семантические векторы и fallback на ИИ.</div>
            </div>
          </div>
        </div>
      `
    },
    {
      id: 'step-workspace',
      stepNumber: 2,
      badge: 'Шаг 1: Workspaces',
      badgeClass: 'bg-info-subtle text-info border',
      icon: 'bi-folder2-open',
      title: 'Изолированные рабочие области (Workspaces)',
      subtitle: 'Индивидуальное окружение и персональный локальный Git для каждого проекта',
      tabTarget: 'tab-workspace',
      actionText: 'Выбрать или создать Workspace',
      contentHtml: `
        <div class="tour-feature-card">
          <div class="fw-bold mb-1 text-primary d-flex align-items-center gap-1.5">
            <i class="bi bi-box-seam"></i> Полная изоляция проектов и документации
          </div>
          <p class="small mb-2 text-body">
            Каждая рабочая область хранится в директории <code>data/ai_assistant/workspaces/&lt;ws_id&gt;</code>
            и инициализируется собственным независимым репозиторием <code>.git</code>.
          </p>
          <ul class="small mb-0 text-muted ps-3">
            <li><strong>Изоляция версий:</strong> Правки в одном проекте не влияют на другие области.</li>
            <li><strong>Мгновенное переключение:</strong> Выбор из выпадающего списка синхронно обновляет дерево файлов, историю коммитов и факты.</li>
            <li><strong>Демо-примеры в 1 клик:</strong> Кнопка «Загрузить демо-примеры» сразу наполняет проект файлами с русским («Мама мыла раму») и ивритом («Ферма Давида Моше»).</li>
          </ul>
        </div>

        <div class="p-2 rounded bg-body-tertiary border small">
          <span class="text-primary fw-semibold"><i class="bi bi-lightbulb me-1"></i>Совет:</span>
          Переключитесь на вкладку «Рабочая область» и нажмите кнопку <strong>«Загрузить демо-примеры»</strong>, чтобы сразу испытать всю мощь поиска!
        </div>
      `
    },
    {
      id: 'step-nlp-facts',
      stepNumber: 3,
      badge: 'Шаг 2: Документы и Факты',
      badgeClass: 'bg-success-subtle text-success border',
      icon: 'bi-file-earmark-text',
      title: 'Умное хранение & Автоизвлечение фактов (NLP Analyzers)',
      subtitle: 'Синтаксический разбор текста, извлечение действий (actions) и отношений обладания (possession)',
      tabTarget: 'tab-workspace',
      actionText: 'Открыть Редактор документов',
      contentHtml: `
        <div class="tour-feature-card">
          <div class="fw-bold mb-1 text-success d-flex align-items-center gap-1.5">
            <i class="bi bi-magic"></i> Как работает автоматическое извлечение?
          </div>
          <p class="small mb-2 text-body">
            При сохранении любого документа через форму или API запускается конвейер синтаксических анализаторов:
          </p>
          <div class="row g-2 mb-2">
            <div class="col-md-6">
              <div class="p-2 rounded bg-body border small">
                <div class="fw-semibold text-primary">1. Факты действия (Actions)</div>
                <div class="text-muted font-size-78">Пример: «Мама мыла раму» &rarr; Субъект: <em>Мама</em>, Действие: <em>мыть</em>, Объект: <em>рама</em>.</div>
              </div>
            </div>
            <div class="col-md-6">
              <div class="p-2 rounded bg-body border small">
                <div class="fw-semibold text-success">2. Факты обладания (Possession)</div>
                <div class="text-muted font-size-78">Пример: «לדוד משה הייתה חווה» &rarr; Владелец: <em>דוד משה</em>, Ресурс: <em>חווה</em> (ферма).</div>
              </div>
            </div>
          </div>
          <p class="small mb-0 text-muted">
            Все факты автоматически записываются в SQLite (<code>KnowledgeStore</code>), привязываются к файлу и коммиту Git, а также индексируются векторными эмбеддингами в <code>FAISS</code>.
          </p>
        </div>
      `
    },
    {
      id: 'step-temporal-graph',
      stepNumber: 4,
      badge: 'Онтология & Граф',
      badgeClass: 'bg-warning-subtle text-warning border',
      icon: 'bi-diagram-3-fill',
      title: 'Темпоральный граф и онтология WikiLLM',
      subtitle: 'Динамика истины во времени: valid_from, valid_to и superseded_by',
      tabTarget: 'tab-graph',
      actionText: 'Открыть Темпоральный граф',
      contentHtml: `
        <div class="tour-feature-card">
          <div class="fw-bold mb-1 text-warning d-flex align-items-center gap-1.5">
            <i class="bi bi-clock"></i> Факты имеют свой срок жизни
          </div>
          <p class="small mb-2 text-body">
            В реальной разработке документация постоянно меняется. Наш темпоральный граф фиксирует,
            когда факт был активен, и когда он устарел:
          </p>
          <ul class="small mb-2 text-muted ps-3">
            <li><span class="badge bg-success-subtle text-success border">ACTIVE</span> Факты, действующие в текущем коммите HEAD.</li>
            <li><span class="badge bg-secondary-subtle text-secondary border">SUPERSEDED</span> Устаревшие факты (переопределенные новыми правками с указанием хэша коммита-заменителя).</li>
          </ul>
          <div class="p-2 rounded bg-body border small">
            <strong>Типы связей WikiLLM:</strong>
            <code>modifies</code> (модифицирует логику), <code>fixes</code> (исправляет сбой),
            <code>documents</code> (описывает модуль), <code>caused_by</code> (вызвано событием).
          </div>
        </div>
      `
    },
    {
      id: 'step-rag-qa',
      stepNumber: 5,
      badge: 'Шаг 3: Вопрос-Ответ',
      badgeClass: 'bg-primary-subtle text-primary border',
      icon: 'bi-search',
      title: '5-этапный поиск RAG & Умный Вопрос-Ответ',
      subtitle: 'Грамматически точные ответы на естественном языке с пониманием падежей и предлогов',
      tabTarget: 'tab-workspace',
      actionText: 'Задать вопрос в QA панели',
      contentHtml: `
        <div class="tour-feature-card">
          <div class="fw-bold mb-1 text-primary d-flex align-items-center gap-1.5">
            <i class="bi bi-chat-quote"></i> 5 фаз формирования ответа
          </div>
          <ol class="small mb-2 text-body ps-3">
            <li><strong>Морфологический анализ:</strong> Распознавание падежей («Кем?» &rarr; творительный, «Кому?» &rarr; дательный, «למי?» &rarr; предлог ל).</li>
            <li><strong>Фактологический поиск в SQLite:</strong> Мгновенное локальное сопоставление субъектов и предикатов.</li>
            <li><strong>Векторный поиск FAISS:</strong> Поиск релевантных текстовых чанков по семантической близости.</li>
            <li><strong>Темпоральная фильтрация:</strong> Исключение устаревших фактов для запрошенного коммита.</li>
            <li><strong>ИИ-резерв (src/ai):</strong> Если точного факта нет в базе, запрос перенаправляется на локальную или облачную LLM.</li>
          </ol>
          <div class="tour-code-snippet">
            <div><strong>Вопрос:</strong> Кем была вымыта рама?</div>
            <div class="text-success">&rarr; <strong>Ответ:</strong> Рама была вымыта <u>мамой</u>.</div>
            <div class="mt-1"><strong>שאלה:</strong> למי הייתה חווה?</div>
            <div class="text-success">&rarr; <strong>תשובה:</strong> החווה הייתה שייכת <u>לדוד משה</u>.</div>
          </div>
        </div>
      `
    },
    {
      id: 'step-verification-audit',
      stepNumber: 6,
      badge: 'Безопасность & Аудит',
      badgeClass: 'bg-danger-subtle text-danger border',
      icon: 'bi-shield-lock-fill',
      title: 'Контур верификации и Аудит изменений',
      subtitle: '2-Step безопасность, защита от инъекций, Шкала времени, Diff и Smart Blame',
      tabTarget: 'tab-verification',
      actionText: 'Открыть Контур верификации',
      contentHtml: `
        <div class="tour-feature-card">
          <div class="fw-bold mb-1 text-danger d-flex align-items-center gap-1.5">
            <i class="bi bi-shield-shaded"></i> Двухэтапный контур безопасности
          </div>
          <p class="small mb-2 text-body">
            Все вносимые факты и метаданные перед записью в граф знаний проходят обязательную валидацию:
          </p>
          <ul class="small mb-2 text-muted ps-3">
            <li><strong>Prompt Injection Shield:</strong> Блокировка попыток подмены системных инструкций.</li>
            <li><strong>Secrets Redaction:</strong> Автоматическое выявление и маскирование API-ключей, токенов и паролей.</li>
          </ul>
        </div>

        <div class="row g-2">
          <div class="col-md-6">
            <div class="p-2.5 rounded bg-body-tertiary border h-100">
              <div class="fw-semibold small text-info mb-1"><i class="bi bi-clock-history me-1"></i>Шкала времени</div>
              <div class="small text-muted font-size-78">Интерактивный хронологический таймлайн изменения документации по часам и дням.</div>
            </div>
          </div>
          <div class="col-md-6">
            <div class="p-2.5 rounded bg-body-tertiary border h-100">
              <div class="fw-semibold small text-warning mb-1"><i class="bi bi-file-earmark-diff me-1"></i>Diff & Smart Blame</div>
              <div class="small text-muted font-size-78">Построчное сравнение ревизий с генерацией краткого ИИ-резюме сути изменений.</div>
            </div>
          </div>
        </div>
      `
    }
  ];

  let currentStepIndex = 0;
  let modalInstance = null;

  /**
   * Создает DOM-разметку модального окна тура, если её нет на странице.
   */
  function ensureTourModalDOM() {
    let modalEl = document.getElementById(MODAL_ID);
    if (modalEl) return modalEl;

    modalEl = document.createElement('div');
    modalEl.id = MODAL_ID;
    modalEl.className = 'modal fade system-tour-modal';
    modalEl.setAttribute('tabindex', '-1');
    modalEl.setAttribute('aria-labelledby', `${MODAL_ID}-label`);
    modalEl.setAttribute('aria-hidden', 'true');

    modalEl.innerHTML = `
      <div class="modal-dialog modal-dialog-centered modal-xl system-tour-dialog">
        <div class="modal-content shadow border-secondary-subtle">
          <!-- Заголовок модального окна -->
          <div class="modal-header border-secondary-subtle d-flex align-items-center justify-content-between py-2.5 px-3">
            <div class="d-flex align-items-center gap-2">
              <div class="rounded-circle bg-primary-subtle text-primary p-2 d-flex align-items-center justify-content-center" style="width: 34px; height: 34px;">
                <i class="bi bi-compass-fill fs-6" id="tour-header-icon"></i>
              </div>
              <div>
                <h6 class="modal-title mb-0 fw-bold d-flex align-items-center gap-2" id="${MODAL_ID}-label">
                  <span>Гид-тур: Умное хранилище документации</span>
                  <span class="badge bg-primary-subtle text-primary border tour-badge-pill" id="tour-step-counter">Шаг 1 из ${TOUR_STEPS.length}</span>
                </h6>
                <div class="text-muted font-size-75" id="tour-subtitle-text">Возможности и архитектура системы</div>
              </div>
            </div>
            <button aria-label="Close" class="btn-close" data-bs-dismiss="modal" type="button"></button>
          </div>

          <!-- Тело модального окна -->
          <div class="modal-body p-3">
            <!-- Верхний прогресс-степпер -->
            <div class="tour-stepper" id="tour-stepper-bar"></div>

            <!-- Тонкий прогресс-бар -->
            <div class="tour-progress-bar-container">
              <div class="tour-progress-bar-fill" id="tour-progress-bar" style="width: 16%;"></div>
            </div>

            <!-- Контейнер текущего шага -->
            <div id="tour-step-content-container"></div>
          </div>

          <!-- Нижняя панель действий -->
          <div class="modal-footer border-secondary-subtle py-2 d-flex flex-wrap align-items-center justify-content-between gap-2">
            <div class="d-flex align-items-center gap-2">
              <button type="button" class="btn btn-outline-secondary btn-sm" id="tour-btn-prev">
                <i class="bi bi-chevron-left me-1"></i>Назад
              </button>
              <button type="button" class="btn btn-primary btn-sm" id="tour-btn-next">
                Далее<i class="bi bi-chevron-right ms-1"></i>
              </button>
            </div>

            <div class="d-flex align-items-center gap-2">
              <button type="button" class="btn btn-outline-primary btn-sm" id="tour-btn-action">
                <i class="bi bi-box-arrow-up-right me-1"></i><span id="tour-btn-action-text">Перейти к разделу</span>
              </button>
              <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">
                Завершить тур
              </button>
            </div>
          </div>
        </div>
      </div>
    `;

    document.body.appendChild(modalEl);

    // Привязка обработчиков навигации внутри модалки
    document.getElementById('tour-btn-prev')?.addEventListener('click', prevStep);
    document.getElementById('tour-btn-next')?.addEventListener('click', nextStep);
    document.getElementById('tour-btn-action')?.addEventListener('click', executeCurrentStepAction);

    // Обработка клавиш со стрелками
    modalEl.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowRight') {
        e.preventDefault();
        nextStep();
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault();
        prevStep();
      }
    });

    return modalEl;
  }

  /**
   * Отрисовывает полоску степпера с кликабельными шагами.
   */
  function renderStepper() {
    const stepperContainer = document.getElementById('tour-stepper-bar');
    if (!stepperContainer) return;

    stepperContainer.innerHTML = TOUR_STEPS.map((s, idx) => {
      let stateClass = '';
      if (idx === currentStepIndex) stateClass = 'active';
      else if (idx < currentStepIndex) stateClass = 'completed';

      return `
        <button type="button" class="tour-step-pill ${stateClass}" data-step-idx="${idx}" title="${s.title}">
          <div class="tour-step-pill-indicator">${idx < currentStepIndex ? '✓' : idx + 1}</div>
          <span class="tour-step-pill-label d-none d-sm-inline">${s.badge.replace(/^Шаг \d+:?\s*/, '')}</span>
        </button>
      `;
    }).join('');

    // Привязка клика к пилюлям
    stepperContainer.querySelectorAll('.tour-step-pill').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const targetIdx = parseInt(btn.getAttribute('data-step-idx'), 10);
        if (!isNaN(targetIdx)) {
          goToStep(targetIdx);
        }
      });
    });

    // Обновление прогресс-бара
    const progressBar = document.getElementById('tour-progress-bar');
    if (progressBar) {
      const pct = Math.round(((currentStepIndex + 1) / TOUR_STEPS.length) * 100);
      progressBar.style.width = `${pct}%`;
    }
  }

  /**
   * Отображает данные текущего шага в теле модального окна.
   */
  function renderCurrentStep() {
    const step = TOUR_STEPS[currentStepIndex];
    if (!step) return;

    // Обновление заголовков и счетчиков
    const counterEl = document.getElementById('tour-step-counter');
    if (counterEl) {
      counterEl.textContent = `Шаг ${currentStepIndex + 1} из ${TOUR_STEPS.length}`;
      counterEl.className = `badge ${step.badgeClass} tour-badge-pill`;
    }

    const subtitleEl = document.getElementById('tour-subtitle-text');
    if (subtitleEl) subtitleEl.textContent = step.subtitle;

    const contentEl = document.getElementById('tour-step-content-container');
    if (contentEl) {
      contentEl.innerHTML = `
        <div class="mb-3">
          <div class="d-flex align-items-center gap-2 mb-1">
            <span class="badge ${step.badgeClass} rounded-pill">${step.badge}</span>
            <h5 class="fw-bold mb-0 text-body d-flex align-items-center gap-2">
              <i class="bi ${step.icon} text-primary"></i>
              <span>${step.title}</span>
            </h5>
          </div>
          <div class="small text-muted mb-3">${step.subtitle}</div>
          <div>${step.contentHtml}</div>
        </div>
      `;
    }

    // Обновление состояния кнопок «Назад» / «Далее»
    const prevBtn = document.getElementById('tour-btn-prev');
    if (prevBtn) {
      prevBtn.disabled = currentStepIndex === 0;
    }

    const nextBtn = document.getElementById('tour-btn-next');
    if (nextBtn) {
      if (currentStepIndex === TOUR_STEPS.length - 1) {
        nextBtn.innerHTML = '<i class="bi bi-check2-circle me-1"></i>Завершить';
      } else {
        nextBtn.innerHTML = 'Далее<i class="bi bi-chevron-right ms-1"></i>';
      }
    }

    // Обновление кнопки целевого действия
    const actionBtn = document.getElementById('tour-btn-action');
    const actionText = document.getElementById('tour-btn-action-text');
    if (actionBtn && actionText) {
      actionText.textContent = step.actionText || 'Перейти к разделу';
      actionBtn.style.display = step.tabTarget ? 'inline-flex' : 'none';
    }

    renderStepper();
  }

  /**
   * Выполняет действие перехода к разделу текущего шага и закрывает тур.
   */
  function executeCurrentStepAction() {
    const step = TOUR_STEPS[currentStepIndex];
    if (!step || !step.tabTarget) return;

    closeTour();

    if (typeof window.switchTab === 'function') {
      window.switchTab(step.tabTarget);
    } else if (typeof window.switchToTab === 'function') {
      window.switchToTab(step.tabTarget);
    }
  }

  /**
   * Переход к следующему шагу или завершение.
   */
  function nextStep() {
    if (currentStepIndex < TOUR_STEPS.length - 1) {
      currentStepIndex++;
      renderCurrentStep();
    } else {
      closeTour();
      try {
        localStorage.setItem(STORAGE_KEY, 'true');
      } catch (_) {}
    }
  }

  /**
   * Переход к предыдущему шагу.
   */
  function prevStep() {
    if (currentStepIndex > 0) {
      currentStepIndex--;
      renderCurrentStep();
    }
  }

  /**
   * Переход к конкретному шагу по индексу.
   * @param {number} index Индекс шага (0..N-1)
   */
  function goToStep(index) {
    if (index >= 0 && index < TOUR_STEPS.length) {
      currentStepIndex = index;
      renderCurrentStep();
    }
  }

  /**
   * Открывает окно тура.
   * @param {number} [startIdx=0] Стартовый индекс шага
   */
  function showTour(startIdx = 0) {
    const modalEl = ensureTourModalDOM();
    currentStepIndex = Math.max(0, Math.min(startIdx, TOUR_STEPS.length - 1));
    renderCurrentStep();

    if (window.bootstrap && window.bootstrap.Modal) {
      modalInstance = bootstrap.Modal.getOrCreateInstance(modalEl);
      modalInstance.show();
    } else {
      modalEl.classList.add('show');
      modalEl.style.display = 'block';
    }
  }

  /**
   * Закрывает окно тура.
   */
  function closeTour() {
    const modalEl = document.getElementById(MODAL_ID);
    if (!modalEl) return;

    if (modalInstance) {
      modalInstance.hide();
    } else if (window.bootstrap && window.bootstrap.Modal) {
      const inst = bootstrap.Modal.getInstance(modalEl);
      if (inst) inst.hide();
    } else {
      modalEl.classList.remove('show');
      modalEl.style.display = 'none';
    }
  }

  /**
   * Инициализирует глобальные триггеры запуска тура.
   */
  function initTourTriggers() {
    ensureTourModalDOM();

    // 1. Кнопка в верхней навигации
    document.getElementById('btn-start-system-tour')?.addEventListener('click', () => showTour(0));

    // 3. Кнопка в боковом меню Offcanvas
    document.getElementById('drawer-btn-start-tour')?.addEventListener('click', () => {
      // Закрываем меню и открываем тур
      const drawer = document.getElementById('leftSideNavOffcanvas');
      if (drawer && window.bootstrap) {
        const offcanvas = bootstrap.Offcanvas.getInstance(drawer);
        if (offcanvas) offcanvas.hide();
      }
      setTimeout(() => showTour(0), 200);
    });

    // 4. Кнопка в модальном окне справки
    document.getElementById('help-btn-start-tour')?.addEventListener('click', () => {
      const helpModal = document.getElementById('help-modal');
      if (helpModal && window.bootstrap) {
        const modal = bootstrap.Modal.getInstance(helpModal);
        if (modal) modal.hide();
      }
      setTimeout(() => showTour(0), 200);
    });
  }

  // Экспорт в глобальное пространство
  window.SystemTour = {
    show: showTour,
    close: closeTour,
    next: nextStep,
    prev: prevStep,
    goToStep: goToStep,
    init: initTourTriggers,
    STEPS: TOUR_STEPS
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initTourTriggers);
  } else {
    initTourTriggers();
  }
})();
