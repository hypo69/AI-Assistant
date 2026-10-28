# 🖥️ WebGUI — Единая IDE-оболочка и веб-интерфейс AI Assistant (`apps/ai_assistant/api/webgui`)

**Статус:** ✅ Активно  
**Версия:** 3.6.0  
**Пакет:** `apps.ai_assistant.api.webgui`  
**Автор:** hypo69  
**Updated:** 2026-10-28 17:14:00  

---

## 📋 Обзор интерфейса и архитектурный стандарт

Веб-интерфейс (`WebGUI`) спроектирован по модульному стандарту SPA / IDE-оболочки:
- **Единая IDE-оболочка (`index.html`, `js/ide_navigation.js`, `js/ide_file_explorer.js`, `js/ide_extensions_sidebar.js`)**: боковой проводник файлов и расширений, верхнее меню с быстрым переключателем рабочих областей (`top_workspace_dropdown.js`), выдвижная нижняя панель (Bottom Drawer) и мастер создания пространства (`workspace_wizard.js`).
- **Вкладки (`tab_<tab_id>/`)**: каждая функциональная вкладка изолирована в своём каталоге `tab_<tab_id>` и содержит `README.md`, `index.html`, `main.js` и подкаталоги панелей `panel_<panel_id>/`.
- **Интерактивный гид-тур (`components/system_tour/`)**: пошаговый обзор возможностей системы (Git-версионирование, носимый режим, NLP-извлечение фактов, WikiLLM, гибридный RAG, контур верификации).
- **Умные ИИ-тултипы (`js/global-tooltips-i18n.js`)**: контекстные подсказки с кнопкой `✨ Спросить ИИ`, открывающей `AIModalDialog` с объяснением любого элемента интерфейса.
- **Локализация и RTL (`locales/ru.json`, `en.json`, `he.json`, `css/rtl.css`)**: полная поддержка русского, английского и иврита (с автоматическим переключением `dir="rtl"` и зеркалированием боковых панелей).
- **Темизация без хардкода**: все цвета и поверхности оформлены исключительно через дизайн-токены CSS (`var(--...)`) и 5 тем (`light`, `dark`, `brick`, `terminal`, `system`).

---

## 🗂️ Полный каталог вкладок интерфейса (`tab_*`)

| Вкладка | Каталог вкладки | Внутренние панели | Назначение |
|---|---|---|---|
| **📂 Рабочая область & Вопросы** *(по умолчанию)* | [`tab_workspace/`](tab_workspace/README.md) | `panel_workspace_select/`<br>`panel_sources/`<br>`panel_documents/`<br>`panel_facts/`<br>`panel_qa/`<br>`panel_chat/`<br>`panel_commits/` | Главная рабочая среда: управление пространством и носимыми путями `\\<HOST>\<PATH>`, слежение Git за файлами на месте (`copy_to_workspace = false`), компактный Obsidian Vault, извлечение фактов (`action`, `possession`) с разрешением местоимений, вопросы и чат с потоковым SSE (`/api/v1/ask/stream`). |
| **➕ Создать пространство** | [`tab_create_workspace/`](tab_create_workspace/README.md) | — | Создание изолированной рабочей области с `git init`, привязкой к имени текущего ПК (`host_name`) и подключением внешних папок/файлов без копирования. |
| **🧹 Обслуживание Git** | [`tab_git_maintenance/`](tab_git_maintenance/README.md) | — | Аудит здоровья Git-репозитория, поиск крупных блобов/дубликатов, генерация `.gitignore` и очистка индекса. |
| **📜 История коммитов** | [`tab_commits/`](tab_commits/README.md) | `panel_commits/` | Просмотр истории коммитов, авторов, хэшей и затронутых файлов (`/v1/panel/panel-commits`). |
| **⚖️ Diff & Smart Blame** | [`tab_diff/`](tab_diff/README.md) | `panel_diff_stats/` | Построчное сравнение ревизий и ИИ-резюме изменений (`/v1/panel/panel-diff-stats`). |
| **⏳ Шкала времени** | [`tab_timeline/`](tab_timeline/README.md) | `panel_timeline/` | Хронологическая шкала эволюции файлов в Git (`/v1/panel/panel-timeline`). |
| **🧠 База знаний WikiLLM** | [`tab_wikillm/`](tab_wikillm/README.md) | `panel_wikillm/` | Просмотр и редактирование семантических сущностей и связей в графе WikiLLM (`/v1/panel/panel-wikillm-entities`). |
| **🕸️ Темпоральный граф** | [`tab_graph/`](tab_graph/README.md) | `panel_graph/` | Визуализация темпоральных связей (`valid_from`, `valid_to`, `superseded_by`) (`/v1/panel/panel-knowledge-links`). |
| **🔍 5-этапный поиск RAG** | [`tab_rag/`](tab_rag/README.md) | `panel_rag/` | Пользовательский и диагностический поиск по гибридному индексу FAISS 256D + TF (`/v1/panel/panel-rag-chunks`). |
| **🤖 Модели и провайдеры ИИ** | [`tab_models/`](tab_models/README.md) | `panel_models_catalog/`<br>`panel_providers_config/`<br>`panel_gemini_keys/`<br>`panel_agy_keys/`<br>`panel_google_accounts/` | Управление провайдерами `src/ai` (Gemini, AGY, Foundry, Ollama, OpenAI), пулом API-ключей и аккаунтами Google. |
| **📧 Почта Gmail** | [`tab_gmail/`](tab_gmail/README.md) | — | Интеграция с почтовым клиентом и Google OAuth для импорта писем и вложений в базу знаний. |
| **🔌 Плагины и интеграции** | [`tab_plugins/`](tab_plugins/README.md) | — | Управление системными и пользовательскими плагинами (`plugins/`), их настройками и статусом. |
| **🎨 Редактор тем** | [`tab_theme_editor/`](tab_theme_editor/README.md) | `panel_presets/`<br>`panel_tokens/`<br>`panel_preview/`<br>`panel_actions/` | Визуальная настройка CSS-переменных и палитр тем оформления в реальном времени. |
| **💻 Редактор файлов (Rust + Wasm)** | [`../../common/webgui/tab_file_editor/`](../../../common/webgui/tab_file_editor/README.md) | `panel_code_editor.js`<br>`panel_specialized_editors.js`<br>`wasm_bridge.js` | Универсальный редактор всех типов файлов VS Code (код, Markdown Split, CSV/TSV Grid, Jupyter `.ipynb`, SVG/Canvas/PDF и бинарный Hex Editor с Data Inspector) на базе `apps/common/file_editor`. |
| **✅ Контур верификации** | [`tab_verification/`](tab_verification/README.md) | `panel_verification/` | Двухэтапная проверка предложенных фактов, блокировка prompt-injection и маскирование секретов (`/v1/panel/panel-verification-pipeline`). |
| **📊 Статус системы** | [`tab_status/`](tab_status/README.md) | `panel_status/` | Диагностика состояния подсистем Git, SQLite, FAISS и языковых адаптеров (`/v1/panel/panel-system-status`). |

---

## 🧩 Общие компоненты (`components/` и `ai_modal_dialog/`)

- **[`ai_modal_dialog/`](ai_modal_dialog/README.md)** — универсальное модальное окно ИИ-ассистента (`#universal-ai-table-modal`).
- **[`components/system_tour/`](components/system_tour/README.md)** — интерактивный пошаговый тур по возможностям приложения.
- **`components/diff_visualizer/`** — компонент подсветки построчного Diff.
- **`components/file_timeline_viewer/`** — визуализатор истории версий файла.
- **`components/wikillm_context_panel/`** — боковая панель связанных сущностей WikiLLM.
