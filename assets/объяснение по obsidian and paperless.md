Ran search Obsidian/Paperless code · Exited with code 1
Ran search Obsidian/Paperless files
Analyzed obsidian_vault.py:L1-120
Analyzed paperless_sync.py:L1-98
Ran search DB usage in workspace

Let me check the schema tables and Paperless details.

Ran schema and Paperless details · Exited with code 1
Ran graph storage lookup

Отвечаю по коду проекта: [obsidian_vault.py](file:///c:/Users/onela/AppData/Local/AI-Assistant/apps/ai_assistant/core/obsidian_vault.py), [paperless_sync.py](file:///c:/Users/onela/AppData/Local/AI-Assistant/apps/ai_assistant/core/paperless_sync.py), [paperless_connector.py](file:///c:/Users/onela/AppData/Local/AI-Assistant/apps/ai_assistant/core/paperless_connector.py) и [workspace_manager.py](file:///c:/Users/onela/AppData/Local/AI-Assistant/apps/ai_assistant/core/workspace_manager.py).

## 1. Что даёт Obsidian

Obsidian не хранит данные сам. Он показывает знания, которые ИИ извлёк из документов, в виде заметок, которые удобно читать человеку. Класс [`ObsidianVaultBuilder`](file:///c:/Users/onela/AppData/Local/AI-Assistant/apps/ai_assistant/core/obsidian_vault.py) создаёт хранилище Obsidian прямо в папке рабочего пространства:

- **Документы дополняются знаниями.** В каждый `.md` файл добавляются:
  - шапка с метаданными (YAML frontmatter);
  - список извлечённых фактов;
  - ссылки на сущности в формате `[[wikilinks]]`.

  Связи между людьми, предметами и документами видны в графе Obsidian без отдельного интерфейса.
- **Общий индекс.** Файл `_Knowledge_Base.md` — одна сводка по всей рабочей области вместо десятков мелких файлов.
- **Конспекты по темам.** В папке `_Topics/<Тема>.md` собираются знания по заданному запросу.
- **Ничего не теряется.** Всё хранится в обычных Markdown-файлах: их можно открыть без нашего приложения, вести в Git и править вручную. Функция [`strip_obsidian_enrichment`](file:///c:/Users/onela/AppData/Local/AI-Assistant/apps/ai_assistant/core/obsidian_vault.py#L57-L87) при повторном чтении убирает добавленные блоки, поэтому исходный текст не засоряется.

## 2. Что даёт Paperless-ngx

Paperless — это внешняя система управления документами (DMS). Она хранит **исходные документы и распознанный (OCR) текст**:

- **Текст не дублируется.** В нашей базе `knowledge_store.db` лежат только факты, связи и ссылка `paperless_id`. Сам текст при необходимости запрашивается через [`PaperlessTextResolver`](file:///c:/Users/onela/AppData/Local/AI-Assistant/apps/ai_assistant/core/paperless_sync.py#L34-L58), который кэширует последние запрошенные документы (до 64 штук).
- **Готовое распознавание текста.** Сканы, PDF и фото Paperless распознаёт сам, без нашего кода.
- **Рабочие области через теги.** Каждой рабочей области соответствует тег Paperless. Функция [`sync_workspace_from_paperless`](file:///c:/Users/onela/AppData/Local/AI-Assistant/apps/ai_assistant/core/paperless_sync.py#L61-L98) загружает все документы с этим тегом.
- **Сбой Paperless не ломает ассистента.** Если Paperless недоступен, вместо текста возвращается пустая строка, а `paperless_bootstrap` при старте пытается поднять его через Docker Compose. Запуск ассистента при этом не блокируется.

**Коротко:** Paperless хранит исходники, наша SQLite-база хранит знания, Obsidian их показывает.

## 3. Какие базы создаются для каждого рабочего пространства

Всё хранится в `workspaces/<id>/.workspace/`:

| Хранилище | Путь | Что внутри |
|---|---|---|
| **SQLite `knowledge_store.db`** — одна база на рабочую область | `.workspace/knowledge_store.db` | Таблицы из [schema.py](file:///c:/Users/onela/AppData/Local/AI-Assistant/apps/ai_assistant/core/store/schema.py): `documents` (с полем `paperless_id`), `document_versions`, `document_chunks`, `entities`, `facts`, `fact_relations`, `fact_sources`, `language_analysis`, `embedding_registry`, `query_history`, `analysis_runs`, `model_usage`, `app_settings` |
| **Граф связей по времени** (`TemporalCodeGraph`) | тот же `knowledge_store.db` | Таблица `temporal_evidence_links` — связи между фактами и их источниками с привязкой ко времени |
| **Векторный индекс FAISS** | `.workspace/faiss_indices/ws_<id>.faiss` и `.json` | Векторы фрагментов текста для поиска по смыслу (RAG) |
| **Конфигурация** (это не база) | `.workspace/config.json` | Настройки и запись в реестре рабочих областей |

Кроме баз, в каждой рабочей области создаются:
- **Git-репозиторий** — история версий документов;
- **Obsidian Vault** — `_Knowledge_Base.md`, `_Topics/`, `_notes/`.

> [!NOTE]
> Индекс FAISS можно в любой момент полностью пересобрать из данных SQLite (`rebuild_faiss_index`). Поэтому главная база — `knowledge_store.db`, а FAISS — производный индекс, его можно не хранить в Git.