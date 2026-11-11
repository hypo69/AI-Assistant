---
name: webgui-developer
description: Архитектурный стандарт, шаблоны и пошаговые протоколы для разработки, модификации и отладки веб-интерфейсов, вкладок (tab_<tab_id>) и интеграции с AIModalDialog и tab-core в AI-Assistant.
description_i18n:
  en: Architectural standards, templates, and step-by-step protocols for developing, modifying, and debugging WebGUI tabs (tab_<tab_id>) with AIModalDialog and tab-core integration in AI-Assistant.
  ru: Архитектурный стандарт, шаблоны и пошаговые протоколы для разработки, модификации и отладки веб-интерфейсов, вкладок (tab_<tab_id>) и интеграции с AIModalDialog и tab-core в AI-Assistant.
---

# 🌐 Навык: Разработчик WebGUI (WebGUI Developer)

**Updated:** 2026-11-11 21:25:00

Этот навык предназначен для проектирования, создания, модификации и поддержки вкладок (`tab_<tab_id>`) и веб-интерфейса в проекте **AI-Assistant** (`apps/ai_assistant/api/webgui/` и `apps/common/webgui/`).

---

## 🎯 Когда активировать этот навык

- Разработка новой функциональной вкладки (`tab_<tab_id>`) в `apps/ai_assistant/api/webgui/` или `apps/common/webgui/`.
- Модификация или рефакторинг существующих вкладок (`tab_workspace`, `tab_commits`, `tab_diff`, `tab_timeline`, `tab_graph`, `tab_rag`, `tab_verification`, `tab_git_maintenance`, `tab_doc_categorizer`, `tab_gmail`, `tab_calendar`, `tab_drive`, `tab_contacts`, `tab_models`, `tab_plugins`, `tab_chat`, `tab_theme_editor`, `tab_file_editor`, `tab_file_tree`, `tab_obsidian`).
- Интеграция списков и таблиц с универсальным модальным окном ИИ-ассистента (`window.AIModalDialog.show`).
- Настройка двухуровневых меню субпанелей и блоков (`menu_config.json`, `SUBTABS_AND_BLOCKS_MENU.md`).
- Аудит верстки на соответствие темам оформления, размеру модальных окон (`90vw × 90vh`) и правилам RTL.

---

## 🏗️ Архитектурная карта WebGUI

```text
apps/ai_assistant/api/webgui/
├── index.html                   # Главная оболочка (Top Navbar, IDE Activity Bar, Offcanvas, Modals)
├── css/
│   ├── main.css                 # Главная таблица стилей (@import компонентов и rtl.css)
│   ├── components.css           # Компоненты и единый размер модальных окон 90vw × 90vh
│   ├── rtl.css                  # Правила двунаправленного интерфейса RTL/LTR и полей ввода (§ 8.1)
│   ├── themes.css               # Палитры тем оформления
│   └── variables.css            # Базовые CSS-переменные
├── js/
│   ├── main.js                  # Главный оркестратор и реестр ленивой загрузки вкладок (TABS)
│   ├── tab-core.js              # Ядро переключения вкладок, синхронизации URL hash и поллинга
│   ├── panel-loader.js          # Загрузчик субпанелей внутри составных вкладок
│   ├── menu_dnd.js              # Drag & Drop кнопок меню (menu_config.json)
│   ├── i18n.js & global-i18n.js # Локализация (ru, en, he, uk) и переключение dir="rtl"/"ltr"
│   └── theme.js & theme-engine.js # Движок тем оформления
├── locales/                     # Словари локализации: ru.json, en.json, he.json, uk.json
├── ai_modal_dialog/             # Универсальное модальное окно ИИ-анализа и WikiLLM
└── tab_<tab_id>/                # Изолированный модуль вкладки
    ├── index.html               # Чистая разметка (БЕЗ тегов <script>)
    ├── main.js                  # Контроллер: window.init<Name>Tab, window.deactivate<Name>Tab
    ├── menu_config.json         # Конфигурация меню субпанелей и блоков (опционально)
    └── README.md                # Документация модуля на русском языке
```

---

## 🚀 Пошаговый протокол: Создание или изменение вкладки

1. **Каталог вкладки `apps/ai_assistant/api/webgui/tab_<tab_id>/`**:
   - Создайте `index.html` (чистая разметка строго с плейсхолдерами `{{key}}`, атрибутами `data-i18n*` и уникальным `id` на каждом переводимом элементе), `main.js` (с экспортом `window.init<PascalName>Tab`) и `README.md` на русском языке.
   - Если во вкладке есть субпанели и подменю блоков — добавьте `menu_config.json` согласно стандарту `.ai/instructions/standards/SUBTABS_AND_BLOCKS_MENU.md`.
2. **Регистрация в `apps/ai_assistant/api/webgui/js/main.js`**:
   - Добавьте запись в словарь `TABS`:
     ```javascript
     'my-feature': ['/html/tab_my_feature/index.html?v=YYYYMMDD_v1', '/html/tab_my_feature/main.js?v=YYYYMMDD_v1'],
     ```
3. **Навигация в `apps/ai_assistant/api/webgui/index.html`**:
   - Добавьте кнопку с атрибутом `data-tab="tab-my-feature"`, `id`, `data-i18n`, `data-i18n-title` и `title="{{...}}"`.
4. **Локализация**:
   - Добавьте все текстовые ключи (`*Label`), плейсхолдеры и статические подсказки (`*Title`) во все 4 файла `apps/ai_assistant/api/webgui/locales/{ru,en,he,uk}.json` (и `apps/common/webgui/locales/` при использовании общих компонентов).

---

## 🧩 Строгий стандарт шаблонизации i18n (`{{key}}` + SSR + уникальный `id`)

> [!IMPORTANT]
> **КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО** оставлять в `*.html` любой захардкоженный естественный текст (русский, английский и т.д.) — даже в качестве «значения по умолчанию» внутри тегов или в `placeholder` / `title` / `label` / `aria-label` / `<option>`.

1. **Единый формат плейсхолдеров в HTML (`WEBGUI.md` § 4)**:
   - **Текст, заголовки, `<option>`**: `<span data-i18n="ui.mod.title" id="mod-span-title">{{ui.mod.title}}</span>`
   - **Плейсхолдеры полей ввода**: `data-i18n-placeholder="placeholders.mod.ph" placeholder="{{placeholders.mod.ph}}"`
   - **Подсказки (`title` / `aria-label`)**: `data-i18n-title="titles.mod.tip" title="{{titles.mod.tip}}"`
   - **Кнопки с иконками**: иконка `<i>` выносится **наружу** от `<span data-i18n="..." id="...">{{...}}</span>` (иначе `innerHTML` удалит иконку!).
   - **Обязательные поля (`*`)**: маркер `<span class="text-danger">*</span>` размещается **рядом** со `<span data-i18n="..." id="...">{{...}}</span>`, а не внутри него.
2. **Уникальный `id` обязателен**: каждый элемент с любым атрибутом `data-i18n*` обязан иметь уникальный `id`.
3. **Серверная предподстановка (SSR) + клиент**:
   - Исходный HTML на диске хранит только `{{key}}`. При отдаче через `SmartMultiDirStaticFiles` или `/` сервер (`apps/common/webgui/i18n_renderer.py`) подставляет переводы из `locales/*.json` по `?lang=`, cookie `app_language` или `Accept-Language`.
   - При смене языка без перезагрузки DOM обновляется через `global-i18n.js` / `i18n.js`, а в `main.js` вкладки динамические фрагменты строятся строго через `t('ui.mod.key', ...)` с перерисовкой по событию `i18n:languageChanged`.
4. **Аудит и проверка перед сдачей**:
   ```powershell
   py scripts/dev/migrate_html_i18n.py --dry-run
   pytest apps/ai_assistant/tests/test_ssr_i18n_renderer.py
   ```

---

## ⚡ Обязательные стандарты разработки

1. **Навигация строго через `data-tab`**:
   - Используйте `<button type="button" data-tab="tab-commits" id="...">...</button>`.
2. **Поллинг строго через `window.registerTabPoller`**:
   - Прямой `setInterval` для опроса API запрещен; опрос должен автоматически останавливаться при уходе с вкладки или сворачивании окна браузера.
3. **Полный запрет хардкода в стилях и строках UI**:
   - Все цвета, фоны и рамки задаются строго через CSS-переменные тем (`var(--surface-1)`, `var(--text-color)`, `var(--border-color)`) и семантические классы (`ui-badge`, `ui-card`).
4. **Модальные окна = 90vw × 90vh (`WEBGUI.md` § 6.4)**:
   - Все модальные окна подчиняются глобальному правилу `.modal .modal-dialog` (`90vw × 90vh`). Запрещено задавать индивидуальные размеры отдельным окнам.
5. **Поля ввода в RTL (`WEBGUI.md` § 6.5)**:
   - При выборе RTL-языка (`html[dir="rtl"]`) все поля ввода (`input`, `textarea`, `select`, `contenteditable`) читаются и заполняются справа налево (секция 8.1 в `rtl.css`). Исключение — поля с явным `dir="ltr"` (пути, URL, хеши, команды).

---

## 📋 Чек-лист перед коммитом

- [ ] Каталог вкладки назван строго `tab_<tab_id>` и зарегистрирован в `apps/ai_assistant/api/webgui/js/main.js` (`TABS`).
- [ ] В `index.html` вкладки нет тегов `<script>`.
- [ ] **Шаблонизация i18n без хардкода:** в HTML нет ни одной захардкоженной языковой строки по умолчанию — везде используются токены `{{key}}` (`title="{{key}}"`, `placeholder="{{key}}"`), у всех `data-i18n*` есть уникальный `id`, иконки `<i>` и `*` вынесены из `span[data-i18n]`.
- [ ] Все строки, подсказки и динамические сообщения `main.js` переведены в `ru.json`, `en.json`, `he.json`, `uk.json`.
- [ ] Проведён аудит `py scripts/dev/migrate_html_i18n.py --dry-run` и пройдены тесты `pytest apps/ai_assistant/tests/test_ssr_i18n_renderer.py`.
- [ ] Отсутствует хардкод цветов (HEX/RGB/inline styles).
- [ ] Все модальные окна имеют размер `90vw × 90vh` без локальных переопределений.
- [ ] В RTL-режиме все поля ввода читаются справа налево.
- [ ] Обновлена версия ассетов `?v=YYYYMMDD_vN` и метка `Updated: YYYY-MM-DD HH:MM:SS` в шапке файлов.
