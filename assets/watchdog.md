

## 1. Настоящий `watchdog` (Git-автокоммиты и условная транскрибация медиа)

- **Служба наблюдателя** [`WorkspaceWatchdogService`](file:///c:/Users/onela/AppData/Local/AI-Assistant/apps/ai_assistant/core/workspace_watchdog.py#L148-L518) на базе `watchdog.observers.Observer`:
  - Следит за папками всех рабочих пространств и всеми привязанными локальными источниками (`auto_watch=True` на текущем хосте). При создании/удалении рабочей области или привязке/отвязке источника подписки обновляются автоматически (`refresh_watches`).
  - Использует дебаунс (`debounce_seconds`), проверку стабилизации размера файла (защита от недокопированного медиа) и подавление эхо-событий от служебных файлов `.git/`, `.workspace/`, `_Knowledge_Base.md`, `.<doc>.md`.
  - **Авто-коммиты в Git:** при изменениях в папке рабочей области и `watchdog.auto_git_commit: true` автоматически индексирует изменённые документы и собирает коммит в Git-репозитории рабочей области.
  - **Условный автозахват транскрибации:** при появлении или обновлении медиафайла транскрибация запускается **только** если в [config.json](file:///c:/Users/onela/AppData/Local/AI-Assistant/apps/ai_assistant/config.json#L13-L18) параметр `watchdog.auto_transcribe_media` равен `true`.
  - Подключён к жизненному циклу сервера в [`lifespan`](file:///c:/Users/onela/AppData/Local/AI-Assistant/apps/ai_assistant/main.py#L206-L224).

- **Извлечение звуковой дорожки из любых медиафайлов** в [`ContentExtractor`](file:///c:/Users/onela/AppData/Local/AI-Assistant/apps/ai_assistant/core/content_extractor.py#L51-L168):
  - Поддержаны аудиоформаты (`.wav`, `.mp3`, `.ogg`, `.m4a`, `.flac`, `.aac`, `.opus`, `.wma`, `.amr`, `.oga`, `.spx`) и видео-/медиаконтейнеры (`.mp4`, `.mkv`, `.avi`, `.mov`, `.webm`, `.wmv`, `.flv`, `.m4v`, `.3gp`, `.mpeg`, `.mpg`, `.ts`).
  - Методы [`has_audio_track`](file:///c:/Users/onela/AppData/Local/AI-Assistant/apps/ai_assistant/core/content_extractor.py#L102-L128) (`ffprobe`) и [`_extract_audio_track_to_temp`](file:///c:/Users/onela/AppData/Local/AI-Assistant/apps/ai_assistant/core/content_extractor.py#L130-L168) (`ffmpeg`) проверяют наличие звуковой дорожки, извлекают её во временный `.mp3`, передают в `audio2text` и удаляют временный файл; видео без звука пропускаются корректно (`source_type="media_no_audio"`).
  - Расширения синхронизированы в [`workspace_manager.py`](file:///c:/Users/onela/AppData/Local/AI-Assistant/apps/ai_assistant/core/workspace_manager.py#L70) и [`workspace_items_tracker.py`](file:///c:/Users/onela/AppData/Local/AI-Assistant/apps/ai_assistant/core/workspace_items_tracker.py#L44-L53).

## 2. Настройка-тумблер в WebGUI и API

- **API настройки:** эндпоинты [`GET /api/v1/watchdog/config`](file:///c:/Users/onela/AppData/Local/AI-Assistant/apps/ai_assistant/api/routers/router_knowledge.py#L1002-L1005) и [`POST /api/v1/watchdog/config`](file:///c:/Users/onela/AppData/Local/AI-Assistant/apps/ai_assistant/api/routers/router_knowledge.py#L1008-L1016) читают и сохраняют параметры `watchdog` в `config.json` без перезапуска сервера.
- **Тумблеры в WebGUI (синхронизированы между собой через `watchdog:configChanged`):**
  - В модальном окне настроек [index.html](file:///c:/Users/onela/AppData/Local/AI-Assistant/apps/ai_assistant/api/webgui/index.html#L741-L759) (`#user-settings-auto-transcribe-toggle`, `#user-settings-auto-git-commit-toggle`) и [userSettings.js](file:///c:/Users/onela/AppData/Local/AI-Assistant/apps/ai_assistant/api/webgui/js/userSettings.js#L172-L234).
  - В панели внешних источников рабочей области [tab_workspace/index.html](file:///c:/Users/onela/AppData/Local/AI-Assistant/apps/ai_assistant/api/webgui/tab_workspace/index.html#L481-L488) (`#ws-sources-auto-transcribe-toggle`) и [panel_sources/panel.js](file:///c:/Users/onela/AppData/Local/AI-Assistant/apps/ai_assistant/api/webgui/tab_workspace/panel_sources/panel.js#L130-L161).

## 3. Добавление фактов через чат во внутренние файлы

- **Бэкенд:**
  - [`WorkspaceManager.add_fact_from_chat`](file:///c:/Users/onela/AppData/Local/AI-Assistant/apps/ai_assistant/core/workspace_manager.py#L1625-L1767) дописывает новый факт во внутренний файл рабочей области `chat_facts.md`, коммитит изменение в Git, прогоняет NLP-анализ, обновляет SQLite (`knowledge_store.db`), FAISS, темпоральный граф и Obsidian (`chat_facts.md` + `_Knowledge_Base.md`).
  - Если фраза не подпадает под regex-шаблоны NLP, для неё гарантированно создаётся структурированный факт со статусом `validated` через [`DocumentFactRepoMixin.add_manual_fact`](file:///c:/Users/onela/AppData/Local/AI-Assistant/apps/ai_assistant/core/store/document_fact_repo.py#L630-L704), причём ранее добавленные факты в `chat_facts.md` не затираются в `stale`.
  - REST API: [`POST /api/v1/workspaces/{workspace_id}/facts`](file:///c:/Users/onela/AppData/Local/AI-Assistant/apps/ai_assistant/api/routers/router_knowledge.py#L976-L993) и [`POST /api/v1/facts/from-chat`](file:///c:/Users/onela/AppData/Local/AI-Assistant/apps/ai_assistant/api/routers/router_knowledge.py#L996-L1000).
- **WebGUI и локализация (`ru`, `en`, `he`, `uk`):**
  - В [tab_chat](file:///c:/Users/onela/AppData/Local/AI-Assistant/apps/ai_assistant/api/webgui/tab_chat/index.html#L79-L90) (`#chat-add-fact-btn`, [`addFactFromChat`](file:///c:/Users/onela/AppData/Local/AI-Assistant/apps/ai_assistant/api/webgui/tab_chat/main.js#L297-L361)) и [panel_chat](file:///c:/Users/onela/AppData/Local/AI-Assistant/apps/ai_assistant/api/webgui/tab_workspace/panel_chat/panel.js#L192-L256) (`#ws-chat-add-fact-btn`) добавлена кнопка **«Добавить факт»** и поддержка команд `/fact ...`, `/факт ...`, `fact: ...`, `факт: ...`, `עובדה: ...` в строке ввода.
  - Ключи локализации добавлены во все 4 словаря (`ru.json`, `en.json`, `he.json`, `uk.json`), обновлены версии ассетов `?v=20261111_v1`.

## Проверка

- Финальный прогон 25 тестов прошёл полностью (`25 passed in 19.45s`):
  - [test_watchdog_and_chat_facts.py](file:///c:/Users/onela/AppData/Local/AI-Assistant/apps/ai_assistant/tests/test_watchdog_and_chat_facts.py) (5/5 — с синтетическим MP4 через `ffmpeg` и моком `audio2text`, проверкой `auto_transcribe_media=false/true`, автокоммитов Git, `add_fact_from_chat` + QA, REST API и WebGUI/локалей)
  - `test_tab_chat.py` (10/10)
  - `test_workspace_chat_panel.py` (4/4)
  - `test_linked_sources_and_converters.py` (6/6)
- В смежных проверках `test_theme_tokens_integrity.py` и `test_tooltip_titles_i18n.py` все проверки по нашим новым элементам (`test_no_hardcoded_colors_in_webgui_templates`, `test_no_duplicate_ids_in_any_html_file`, `test_no_id_overlap_between_index_and_tab_workspace`, `test_all_data_i18n_title_keys_exist_in_all_locales`) пройдены; в репозитории остаются 2 не связанные с нашими правками предсуществовавшие ошибки (`test_nightview_70_matches_nightview_style_and_has_zoom_reduction` и `test_no_hardcoded_titles_without_data_i18n_title`).