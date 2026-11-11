<!--
=============================================================================
Process Name: Standards - WebGUI Engineering & Architecture Rules
=============================================================================
Description:
  Инженерный стандарт и свод обязательных правил разработки веб-интерфейсов (WebGUI)
  в проекте AI-Assistant (apps/ai_assistant/api/webgui и apps/common/webgui,
  модули вкладок tab_<tab_id>).

File: WEBGUI.md
Project: ai-windows-admin
Package: .ai/instructions/standards
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-11-11 21:25:00
=============================================================================
-->

# 🌐 Стандарт разработки веб-интерфейса (WebGUI) v2.1

**Статус:** ✅ Active  
**Версия:** 2.1 (AI-Assistant WebGUI & i18n SSR Templating Edition)  
**Автор:** hypo69  
**Copyright:** © 2026 hypo69  
**Область действия:** `apps/ai_assistant/api/webgui/` и общие компоненты `apps/common/webgui/`, все вкладки `tab_<tab_id>`.

---

## 📋 Содержание
1. [RFC 2119 Ключевые требования](#1-rfc-2119-ключевые-требования)
2. [Архитектура WebGUI и Вкладок (Tabs)](#2-архитектура-webgui-и-вкладок-tabs)
3. [Навигация и контракт атрибутов](#3-навигация-и-контракт-атрибутов)
4. [Строгий стандарт шаблонизации i18n (`{{key}}` и SSR)](#4-строгий-стандарт-шаблонизации-i18n-key-и-ssr)
5. [Жизненный цикл вкладки и Active-Only Polling](#5-жизненный-цикл-вкладки-и-active-only-polling)
6. [Стандарт тем оформления, модальных окон и RTL](#6-стандарт-тем-оформления-модальных-окон-и-rtl)
7. [Универсальное модальное окно ИИ (AIModalDialog) и таблицы](#7-универсальное-модальное-окно-ии-aimodaldialog-и-таблицы)
8. [Регистрация вкладок и конфигурация меню](#8-регистрация-вкладок-и-конфигурация-меню)
9. [Версионирование и Cache-Busting](#9-версионирование-и-cache-busting)
10. [Чек-лист проверки WebGUI](#10-чек-лист-проверки-webgui)

---

## 1. RFC 2119 Ключевые требования

- **MUST (ОБЯЗАТЕЛЬНО)**:
  - Все вкладки **MUST** располагаться строго в каталогах с шаблоном названия `tab_<tab_id>/` (например: `tab_workspace`, `tab_commits`, `tab_diff`, `tab_timeline`, `tab_rag`, `tab_gmail`, `tab_chat`).
  - Файл `index.html` вкладки **MUST NOT** содержать тегов `<script>` (только чистая разметка).
  - Навигация между вкладками **MUST** осуществляться через атрибут `data-tab="tab-xxx"` и `tab-core.js`.
  - Маршрутизация рабочих областей **MUST** следовать стандарту `#tab-workspace#panel-files#workspace=<id>` ([`WORKSPACE_ROUTING.md`](WORKSPACE_ROUTING.md)).
  - Двухуровневые меню субпанелей и подменю блоков **MUST** следовать стандарту [`SUBTABS_AND_BLOCKS_MENU.md`](SUBTABS_AND_BLOCKS_MENU.md) с мгновенными статическими тултипами (без обращения к AI-модели) и локальным `menu_config.json`.
  - Любой периодический опрос API **MUST** регистрироваться через `window.registerTabPoller()`.
  - Все пользовательские строки интерфейса **MUST** быть интернационализированы в 4 словарях локализации (`locales/ru.json`, `en.json`, `he.json`, `uk.json`).
  - Все HTML-шаблоны **MUST** использовать строго плейсхолдеры `{{key}}` вместо текста по умолчанию (нулевой хардкод в разметке и атрибутах), а каждый элемент с `data-i18n*` **MUST** иметь уникальный `id` (§ 4).
  - Все модальные окна **MUST** иметь единый размер **90vw × 90vh** (§ 6.4).
  - При выборе RTL-языка все поля ввода **MUST** читаться и заполняться справа налево (§ 6.5).
  - В шапке каждого изменяемого файла **MUST** обновляться временная метка `Updated: YYYY-MM-DD HH:MM:SS`.

- **MUST NOT (КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО)**:
  - **MUST NOT** оставлять в HTML-файлах захардкоженный текст по умолчанию (русский, английский и т.д.) внутри тегов или атрибутов `placeholder`, `title`, `label`, `aria-label` — допустимы только токены `{{key}}`.
  - **MUST NOT** использовать прямые `setInterval(...)` для опроса бэкенда внутри вкладок в обход `registerTabPoller`.
  - **MUST NOT** использовать `data-bs-target`, `data-bs-toggle="tab"` или инлайн-обработчики `onclick="..."` для переключения главных вкладок.
  - **MUST NOT** хардкодить цвета, фоны, рамки и статусы (`style="color:...", style="background:..."`, HEX `#facc15`, `#12151a`, RGB/RGBA, классы `bg-black`, `bg-dark`, `text-white`). Всё оформление — ТОЛЬКО через механизм тем (`var(--...)`) и стандартные классы дизайн-системы (`ui-badge`, `ui-card` и др.).
  - **MUST NOT** задавать индивидуальные размеры отдельным модальным окнам.
  - **MUST NOT** оставлять необработанные ошибки API без информирования пользователя (`window.toast`).

---

## 2. Архитектура WebGUI и Вкладок (Tabs)

Веб-интерфейс **AI-Assistant** обслуживается через `SmartMultiDirStaticFiles`, объединяя специфичные для приложения ресурсы `apps/ai_assistant/api/webgui/` и общие переиспользуемые компоненты `apps/common/webgui/`:

```text
apps/ai_assistant/api/webgui/
├── index.html                   # Главная оболочка приложения (Top Navbar, IDE Activity Bar, Offcanvas, Modals)
├── css/
│   ├── main.css                 # Точка входа стилей (@import базовых таблиц, компонентов и rtl.css)
│   ├── components.css           # Стили компонентов и единый стандарт модальных окон (90vw × 90vh)
│   ├── rtl.css                  # Двунаправленный интерфейс RTL/LTR (иврит) и правила полей ввода (§ 8.1)
│   ├── themes.css               # Палитры тем оформления
│   └── variables.css            # Базовые CSS-переменные дизайн-системы
├── js/
│   ├── main.js                  # Главный оркестратор WebGUI и реестр ленивой загрузки вкладок (TABS)
│   ├── tab-core.js              # Ядро переключения вкладок, синхронизации URL hash и поллинга
│   ├── panel-loader.js          # Загрузчик субпанелей внутри составных вкладок
│   ├── menu_dnd.js              # Drag & Drop перетаскивание кнопок меню (menu_config.json)
│   ├── i18n.js & global-i18n.js # Интернационализация (ru, en, he, uk) и переключение dir="rtl"/"ltr"
│   ├── theme.js & theme-engine.js # Движок тем оформления
│   └── toast.js                 # Всплывающие уведомления
├── locales/                     # Словари переводов: ru.json, en.json, he.json, uk.json
├── ai_modal_dialog/             # Универсальное модальное окно ИИ-анализа и WikiLLM
└── tab_<tab_id>/                # Изолированный модуль вкладки (tab_workspace, tab_commits, tab_gmail и др.)
    ├── index.html               # Чистая разметка вкладки (без <script>)
    ├── main.js                  # Контроллер вкладки: init<Name>Tab, deactivate<Name>Tab
    ├── menu_config.json         # Конфигурация меню субпанелей и блоков (при наличии субвкладок)
    └── README.md                # Документация модуля на русском языке
```

Общие вкладки и компоненты в `apps/common/webgui/`:
- `tab_file_editor/` — встроенный редактор файлов и кода;
- `tab_file_tree/` — дерево каталогов и файлов;
- `tab_obsidian/` — просмотр и управление заметками Obsidian Vault;
- `tab_theme_editor/` — интерактивный редактор токенов тем оформления.

---

## 3. Навигация и контракт атрибутов

### 3.1 Кнопки и триггеры переключения
Переключение вкладок выполняется глобальным диспетчером `tab-core.js` и оркестратором `main.js`. Единственным разрешенным триггером переключения вкладок является атрибут `data-tab`:

```html
<!-- ✅ ПРАВИЛЬНО -->
<button type="button" class="btn btn-outline-primary" data-tab="tab-commits" data-i18n-title="navCommitsTitle" id="nav-btn-commits" title="{{navCommitsTitle}}">
  <i class="bi bi-git"></i> <span data-i18n="navCommitsLabel" id="nav-span-commits">{{navCommitsLabel}}</span>
</button>

<!-- ❌ ЗАПРЕЩЕНО -->
<button type="button" data-bs-target="#tab-commits" data-bs-toggle="tab">Коммиты</button>
<button type="button" onclick="switchTab('tab-commits')">Коммиты</button>
<a href="#tab-commits">Коммиты</a>
```

### 3.2 Контейнеры вкладок
- Панель вкладки **MUST** иметь атрибуты: `id="tab-<name>"` и класс `class="tab-pane fade"`.
- Контейнер всех панелей: `<div id="mainTabContent" class="tab-content">`.

---

## 4. Строгий стандарт шаблонизации i18n (`{{key}}` и SSR)

В проекте действует **нулевой хардкод языковых строк в HTML**. Все переводимые текстовые узлы и атрибуты разметки **MUST** оформляться через токены-плейсхолдеры `{{key}}` с серверной предподстановкой (SSR) через `apps/common/webgui/i18n_renderer.py` (`SmartMultiDirStaticFiles` и маршруты `/`, `/ai_assistant`).

### 4.1 Канонические правила разметки

| Элемент | ✅ Обязательный стандарт (`{{key}}` + `id`) | ❌ Запрещено (хардкод / ошибки) |
|---|---|---|
| Текст, заголовок, `<option>` | `<span data-i18n="ui.mod.title" id="mod-span-title">{{ui.mod.title}}</span>` | `<span data-i18n="ui.mod.title">Заголовок</span>` |
| Поле ввода (`placeholder`) | `<input data-i18n-placeholder="placeholders.mod.name" id="mod-inp-name" placeholder="{{placeholders.mod.name}}" type="text"/>` | `placeholder="Введите имя..."` |
| Тултип (`title` / `aria-label`) | `<button data-i18n-title="titles.mod.save" id="mod-btn-save" title="{{titles.mod.save}}" type="button">` | `title="Сохранить данные"` |
| Кнопка с иконкой | `<button id="mod-btn-refresh" type="button"><i class="bi bi-arrow-clockwise"></i> <span data-i18n="common.refresh" id="mod-span-refresh">{{common.refresh}}</span></button>` | `<button data-i18n="common.refresh"><i class="bi ..."></i>Обновить</button>` *(затрёт иконку!)* |
| Обязательное поле (`*`) | `<label for="x" id="mod-lbl-x"><span data-i18n="ui.mod.name" id="mod-span-name">{{ui.mod.name}}</span> <span class="text-danger" id="mod-star">*</span>:</label>` | `<label data-i18n="ui.mod.name">Имя <span class="text-danger">*</span></label>` *(затрёт `*`!)* |

### 4.2 Обязательные требования к шаблонизации i18n
1. **Уникальный `id` на каждом элементе с `data-i18n*`**: каждый тег с любым атрибутом `data-i18n`, `data-i18n-placeholder`, `data-i18n-title`, `data-i18n-label`, `data-i18n-aria-label` **MUST** иметь уникальный `id` в пределах документа и не пересекаться с `index.html`.
2. **Все 4 локали синхронны**: каждый ключ `{{key}}` **MUST** присутствовать и быть переведён во всех 4 словарях (`locales/ru.json`, `en.json`, `he.json`, `uk.json`) и в `apps/common/webgui/locales/`.
3. **SSR + клиентская синхронизация**:
   - Сервер (`i18n_renderer.py`) определяет язык по приоритету `URL query (?lang=)` → `Cookie (app_language)` → `Accept-Language` → `ru`, подставляет переводы вместо `{{key}}` (с HTML-экранированием внутри атрибутов) и выставляет `<html lang="..." dir="rtl|ltr">`.
   - Клиент (`global-i18n.js` / `js/i18n.js`) при переключении языка сохраняет `app_language` в `localStorage` и `document.cookie`, а затем динамически обновляет DOM по `data-i18n*`.
   - Если ключ забыт в словаре, на экране в режиме Fail-Fast остаётся видимым `{{missing.key}}` вместо маскировки русским текстом.
4. **Динамический HTML в JS**: в `main.js` запрещены захардкоженные языковые строки — используется хелпер `t(key, fallback)` и подписка на события `languageChanged` / `i18n:languageChanged` для перерисовки списков, бейджей и баннеров.
5. **Инструмент аудита и миграции**: перед коммитом обязательно проверяйте разметку командой:
   ```powershell
   py scripts/dev/migrate_html_i18n.py --dry-run
   pytest apps/ai_assistant/tests/test_ssr_i18n_renderer.py
   ```

---

## 5. Жизненный цикл вкладки и Active-Only Polling

### 4.1 Принцип Active-Only
Опрос бэкенда **MUST** выполняться **ТОЛЬКО** в момент, когда вкладка (и соответствующая субпанель) активна на экране и окно браузера находится в фокусе. При переключении на другую вкладку или сворачивании окна таймеры **MUST** автоматически останавливаться.

### 4.2 Соглашение об экспорте функций контроллера
В `main.js` вкладки **MUST** быть определены и экспортированы в объект `window` функции жизненного цикла:

```javascript
/**
 * Инициализация вкладки (вызывается при первом открытии и активации).
 */
export async function initCommitsTab() {
  bindEvents();
  await fetchCommitsData();

  // Регистрация опросника через tab-core
  window.registerTabPoller('tab-commits', async () => {
    await fetchCommitsData(true);
  }, 5000, { immediate: false });
}
window.initCommitsTab = initCommitsTab;

/**
 * Опциональная деактивация вкладки (вызывается при уходе с вкладки).
 */
export function deactivateCommitsTab() {
  // Освобождение локальных подписок
}
window.deactivateCommitsTab = deactivateCommitsTab;
```

---

## 6. Стандарт тем оформления, модальных окон и RTL

Интерфейс поддерживает динамическую смену тем: `Light`, `NightView`, `Dark`, `Brick`, `Terminal`.

### 6.1 Семантические классы Bootstrap 5
Разметка **MUST** использовать адаптивные классы вместо фиксированных цветов:
- Фон: `bg-body`, `bg-body-tertiary`, `bg-body-secondary`.
- Текст: `text-body`, `text-body-secondary`, `text-muted`.
- Границы: `border`, `border-subtle`, `border-primary-subtle`.

### 6.2 CSS-переменные
Для кастомных стилей **MUST** использоваться переменные активной темы:
```css
/* ✅ ПРАВИЛЬНО */
.my-card {
  background: var(--surface-1, #1e293b);
  color: var(--text-color, #f8fafc);
  border: 1px solid var(--border-color, rgba(255, 255, 255, 0.1));
}

/* ❌ ЗАПРЕЩЕНО */
.my-card {
  background-color: #12151a; /* Жесткий хардкод сломает светлую тему! */
  color: #fff;
}
```

### 6.3 Унифицированные статусные бейджи (`ui-badge`) и запрет инлайнового хардкода
Для отображения любых статусов, меток версий, категорий и метаданных **КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО** использовать инлайновые стили оформления (`style="color: #...; background: rgba(...);"`).
Используются строго семантические классы дизайн-системы, привязанные к токенам активной темы (`--status-*-*`):
- **Успех / Верифицировано:** `<span class="ui-badge ui-badge-success"><i class="bi bi-check-circle-fill me-1"></i><span data-i18n="ui.common.verified" id="badge-verified">{{ui.common.verified}}</span></span>`
- **Предупреждение / Изменено:** `<span class="ui-badge ui-badge-warning"><i class="bi bi-exclamation-triangle-fill me-1"></i><span data-i18n="ui.common.uncommitted" id="badge-warn">{{ui.common.uncommitted}}</span></span>`
- **Ошибка / Конфликт:** `<span class="ui-badge ui-badge-danger"><i class="bi bi-x-circle-fill me-1"></i><span data-i18n="ui.common.error" id="badge-err">{{ui.common.error}}</span></span>`
- **Информация / Ревизия:** `<span class="ui-badge ui-badge-info">HEAD~1</span>`
- **Нейтральные метаданные:** `<span class="ui-badge ui-badge-neutral">Markdown</span>`

### 6.4 Размер модальных окон (формальное правило)
**MUST:** ВСЕ модальные окна WebGUI имеют размер **90% от размера экрана**: ширина `90vw`, высота `90vh`, по центру.
- Единственный источник значений — CSS-переменные `--modal-size-w` / `--modal-size-h` и глобальное правило `.modal .modal-dialog` в `apps/common/webgui/css/components.css` и `apps/ai_assistant/api/webgui/css/components.css`.
- **MUST NOT:** задавать размеры отдельным окнам (`max-width`, `width`, `height`, `min-height`, `!important` на `.modal-dialog` / `.modal-content`, медиа-запросы размеров). Классы `modal-sm` / `modal-lg` / `modal-xl` на размер не влияют и не используются для его выбора.
- Содержимое окна прокручивается внутри `.modal-body`.

### 6.5 Поля ввода в RTL-языках (формальное правило)
**MUST:** если выбран RTL-язык (иврит и др.; `<html dir="rtl">` выставляется `i18n.js`), ВСЕ поля ввода (`input`, `textarea`, `select`, `contenteditable`) читаются и заполняются **справа налево** (`direction: rtl; text-align: right`).
- Единственный источник правила — секция 8.1 в `apps/ai_assistant/api/webgui/css/rtl.css`; локальные `direction` / `text-align` / `dir` на отдельных полях для этого **MUST NOT** задаются.
- Исключение: поле с явным `dir="ltr"` (пути к файлам, URL, код, хеши коммитов, команды терминала) остаётся LTR.
- Не затрагивает `checkbox`, `radio`, `range`, `color`, `file` и кнопки.

---

## 7. Универсальное модальное окно ИИ (AIModalDialog) и таблицы

Таблицы и списки сущностей проекта (отслеживаемые файлы, коммиты Git, извлеченные факты, документы рабочей области, письма, плагины) интегрируются с универсальным ИИ-ассистентом через глобальный синглтон `window.AIModalDialog`:

### 7.1 Разметка интерактивной строки таблицы
```html
<tr class="interactive-table-row" data-id="doc_42" style="cursor: pointer;">
  <td>...</td>
  <td class="text-end no-modal-trigger" onclick="event.stopPropagation();">
    <!-- Кнопки действий внутри строки не должны вызывать модалку -->
    <button type="button" class="btn btn-sm btn-outline-danger" data-i18n-title="titles.ws.untrack" id="btn-untrack-42" title="{{titles.ws.untrack}}">
      <span data-i18n="btnUntrack" id="span-untrack-42">{{btnUntrack}}</span>
    </button>
  </td>
</tr>
```

### 7.2 Вызов `window.AIModalDialog.show()`
```javascript
function openDocumentAiModal(docItem) {
  const modal = window.AIModalDialog || window.AITableModal;
  if (!modal) return;

  modal.show({
    title: docItem.title || docItem.file_name,
    subtitle: `Рабочая область: ${docItem.workspace_id} | Хост: ${docItem.host_name || 'Local'}`,
    icon: '📄',
    panelId: 'panel-files',
    tableType: 'document', // 'document' | 'commit' | 'fact' | 'email' | 'plugin' | 'generic'
    badges: [
      { text: docItem.status, class: 'ui-badge ui-badge-success' }
    ],
    metadata: [
      { label: 'Полный путь', value: docItem.qualified_path, isCode: true, fullWidth: true },
      { label: 'Последний коммит', value: docItem.last_commit_hash || '—' }
    ],
    rawTitle: 'Метаданные и извлеченные факты документа',
    rawContent: JSON.stringify(docItem, null, 2),
    autoRun: false
  });
}
```

### 7.3 Стандарт адаптивных таблиц с динамическими данными (TableTemplate & Resizer)

Все таблицы с динамическими списками (файлы рабочей области, коммиты, факты, письма, модели) **SHOULD** поддерживать адаптивную высоту и ресайзер (`window.TableTemplate` / `window.autoAdjustTableHeight`):
1. **Скроллируемый контейнер таблицы (`.table-responsive`):**
   - Уникальный идентификатор: `id="<name>-table-container"`.
   - Атрибут `data-resizable-table="true"`.
   - Фиксация заголовков: `<thead class="sticky-top">`.
2. **Нижний интерактивный ползунок-ресайзер (`.sys-table-resizer`):**
   ```html
   <div class="sys-table-resizer" id="<name>-table-resizer" data-container-id="<name>-table-container">
     <div class="sys-table-resizer-grip"></div>
   </div>
   ```

---

## 8. Регистрация вкладок и конфигурация меню

Каждая новая или измененная вкладка в `apps/ai_assistant/api/webgui/` **MUST** быть зарегистрирована в следующей цепочке:

1. **Каталог вкладки `apps/ai_assistant/api/webgui/tab_<tab_id>/`**:
   - `index.html` — разметка вкладки без `<script>` и строго с токенами `{{key}}` (§ 4);
   - `main.js` — контроллер с экспортом `window.init<Name>Tab`;
   - `menu_config.json` — декларативное описание субпанелей (`subtabs`) и блоков (`blocks`) с ключами i18n и поддержкой Drag & Drop (если внутри вкладки есть субвкладки);
   - `README.md` — документация вкладки на русском языке.

2. **Реестр ленивой загрузки `apps/ai_assistant/api/webgui/js/main.js` (`TABS`)**:
   ```javascript
   const TABS = {
     // ...
     'my-feature': ['/html/tab_my_feature/index.html?v=YYYYMMDD_v1', '/html/tab_my_feature/main.js?v=YYYYMMDD_v1'],
   };
   ```

3. **Оболочка `apps/ai_assistant/api/webgui/index.html`**:
   - Кнопка навигации в боковом меню / верхней панели / IDE Activity Bar с атрибутом `data-tab="tab-my-feature"`, `data-i18n`, `data-i18n-title`, `title="{{...}}"` и уникальным `id`.
   - Контейнер `<div id="tab-my-feature" class="tab-pane fade"></div>` внутри `#mainTabContent` (или автоматическое создание через `loadTab` в `tab-core.js`).

4. **Словари локализации `apps/ai_assistant/api/webgui/locales/{ru,en,he,uk}.json`**:
   - Добавление всех ключей подписей (`*Label`) и статических подсказок (`*Title`).

---

## 9. Версионирование и Cache-Busting

Для гарантированного обновления скриптов и стилей в браузерах пользователей все URL ресурсов **MUST** содержать параметр версии вида:
```text
?v=YYYYMMDD_vN
```
При внесении любых изменений во фронтенд номер ревизии `_vN` или дата **MUST** инкрементироваться.

---

## 10. Чек-лист проверки WebGUI

Перед сдачей задачи и коммитом проверьте:
- [ ] Все модальные окна имеют размер 90vw × 90vh без локальных переопределений (§ 6.4).
- [ ] В RTL-языках все поля ввода читаются справа налево, без локальных переопределений направления (§ 6.5).
- [ ] Вкладка изолирована строго в `tab_<tab_id>/` и содержит `index.html`, `main.js`, `README.md` (и `menu_config.json` при наличии субпанелей).
- [ ] В `index.html` вкладки отсутствуют теги `<script>`.
- [ ] **Шаблонизация i18n без хардкода (§ 4):** в HTML нет захардкоженного текста по умолчанию (используются только плейсхолдеры `{{key}}` для текста, `placeholder="{{key}}"` и `title="{{key}}"`), у всех `data-i18n*` элементов есть уникальный `id`, иконки `<i>` и `*` вынесены наружу от `span[data-i18n]`.
- [ ] Проведён аудит `py scripts/dev/migrate_html_i18n.py --dry-run` и пройдены тесты `pytest apps/ai_assistant/tests/test_ssr_i18n_renderer.py`.
- [ ] Кнопки переключения вкладок используют только `data-tab="tab-<tab_id>"`.
- [ ] Фоновый опрос зарегистрирован через `window.registerTabPoller` (без прямых вызовов `setInterval`).
- [ ] **Никакого хардкода в стилях:** Проверено полное отсутствие HEX/RGB/RGBA в атрибутах `style="..."` и CSS-селекторах. Все цвета, фоны, рамки и статусы подключены строго через механизм тем (`var(--...)` и `ui-badge-*`).
- [ ] **Полная локализация (i18n):** Все строки и статические тултипы добавлены в `ru.json`, `en.json`, `he.json`, `uk.json`.
- [ ] Вкладка зарегистрирована в `apps/ai_assistant/api/webgui/js/main.js` (`TABS`).
- [ ] В шапке всех изменяемых файлов проставлена актуальная дата `Updated: YYYY-MM-DD HH:MM:SS`.
- [ ] Все комментарии к коду и документация составлены на **русском языке**.
- [ ] Версия ассетов обновлена (`?v=YYYYMMDD_vN`).
