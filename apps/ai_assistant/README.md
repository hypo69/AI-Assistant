# 🧠 AI Assistant — Мультиязычная система извлечения знаний и умной истории версий (Git + WikiLLM + RAG + FAISS + SQLite + Gemini)

**Статус:** ✅ Активно  
**Версия:** 2.5.0  
**Автор:** hypo69  
**Пакет:** `apps.ai_assistant`  
**Updated:** 2026-10-26 00:26:00  

---

## 📋 Обзор

Модуль **AI Assistant** реализует мультиязычную систему хранения истории файлов, извлечения структурированных знаний и интеллектуального поиска фактов на базе **Git + WikiLLM + Gemini (`src/ai`) + RAG + FAISS + SQLite** в соответствии с [`TECHNICAL_SPECIFICATION.md`](TECHNICAL_SPECIFICATION.md).

### Как работает система:
1. **Выбор рабочей области (`Workspace`)**: для каждой рабочей области автоматически создаётся и отслеживается собственный изолированный Git-репозиторий (`.git`) и конфигурация `.workspace/config.json`.
2. **Слежение за файлами на диске без копирования по умолчанию (`copy_to_workspace = False`)**:
   - Когда вы указываете путь к файлу или папке на диске (без явного включения флажка копирования), Git начинает следить за ними **на месте (in-place)**, не копируя и не перемещая оригиналы в папку рабочей области.
   - Текстовые слепки файлов фиксируются в `.extracted_snapshots/*.snapshot`, а метаданные — в `.tracked_sources.json`, что обеспечивает полноценную историю коммитов и `git diff`.
   - При явном включении переключателя `Копировать файлы в директорию рабочей области` (`copy_to_workspace = True`) или при прямой загрузке через форму выбора файлов оригиналы физически копируются в каталог рабочей области.
3. **Носимый режим на USB-флешке и привязка к имени компьютера (`\\<HOST_NAME>\<PATH>`)**:
   - Приложение рассчитано на перенос и запуск с внешнего USB-носителя (флешки) на разных компьютерах.
   - Для всех внешних файлов и папок, находящихся вне директории рабочей области, система автоматически определяет имя компьютера (`COMPUTERNAME` / `platform.node()`) и сохраняет:
     - `host_name` — нормализованное имя компьютера (например, `OFFICE-PC`, `HOME-LAPTOP`);
     - `qualified_path` — полный путь, включающий имя компьютера в формате `\\<HOST_NAME>\<Диск>:\<Путь>` (например, `\\OFFICE-PC\C:\Docs\architecture.md`);
     - `file_path` / `source_path` — локальный путь на этом компьютере.
   - При подключении флешки к другому компьютеру (`current_host != host_name`) внешние файлы с других ПК получают статус `На другом ПК (<HOST_NAME>)` (`other_host`), не помечаются как удалённые, а их ранее извлечённые факты, векторы FAISS и текстовые слепки `.extracted_snapshots/` остаются полностью доступными для поиска, чтения и ответов на вопросы.
   - Если на двух разных компьютерах отслеживаются одноимённые файлы (например, `C:\Work\notes.txt` на `OFFICE-PC` и `C:\Work\notes.txt` на `HOME-LAPTOP`), они автоматически разделяются по префиксу имени ПК и не перезаписывают друг друга.
4. **Универсальная конвертация и пропуск через анализ**: содержимое любых форматов автоматически конвертируется:
   - **PDF**: извлечение текста страниц через `src.utils.pdf` (`pypdf`) или мультимодальную модель Gemini;
   - **Excel (.xlsx, .xls)**: разбор листов и преобразование таблиц в Markdown через `src.utils.convertors.excel` (`openpyxl`);
   - **Аудио (.wav, .mp3, .ogg, .m4a, .flac)**: транскрибация речи в текст через Google Gemini API (`src.utils.convertors.audio`) с ротацией ключей из `src/secrets/gemini_keys.json`;
   - **Google Таблицы (Google Sheets)**: чтение таблиц через Google Sheets API v4 (токены из `src/secrets`) и публичный веб-экспорт (`src.utils.convertors.google_sheet`);
   - **Word DOCX & CSV**: структурированное извлечение параграфов и таблиц.
   Извлечённый текст проходит мультиязычный синтаксический разбор с разрешением кореференции местоимений (`он/она/они/у него/у неё`, `הוא/היא/לו/לה`, `he/she/they`), извлечение фактов (`action`, `possession`) в SQLite, векторизацию в **FAISS** и связывание в темпоральном графе **WikiLLM**.
5. **Ответы на вопросы (QA Engine)**: гибридный поиск (SQLite факты + FAISS + лексический TF + темпоральный граф WikiLLM) и точный грамматический ответ с указанием первоисточника (включая потоковый режим SSE `/api/v1/ask/stream`).

---

## 🎯 Примеры поддерживаемых сценариев

### Русский язык (`mama.txt`: `Мама мыла раму.`)
- `Что мыла мама?` → **`Раму.`** (`object`, винительный падеж `accs`)
- `Кто мыл раму?` → **`Мама.`** (`subject`, именительный падеж `nomn`)
- `Кем была вымыта рама?` → **`Мамой.`** (`subject` при пассивном залоге, творительный падеж `inst`)

### Иврит — конструкция обладания (`farm.txt`: `לדוד משה היתה חווה`)
- `מה היה לדוד משה?` → **`חווה`** (`possessed`)
- `למי הייתה חווה?` → **`לדוד משה`** (`possessor` с предлогом `ל־`)
- `למי הייתה החווה?` → **`לדוד משה`** (`possessor` при определённом артикле `ה־`)
- `האם לדוד משה הייתה חווה?` → **`כן`** (`yes_no`)
- `מה היה הקשר בין דוד משה לחווה?` → **`לדוד משה הייתה חווה`** (`relation_query`)

### Иврит — активное действие (`frame_he.txt`: `אמא רחצה את המסגרת`)
- `מי רחצה את המסגרת?` → **`אמא`** (`subject`)
- `מה רחצה אמא?` → **`המסגרת`** (`object`)

---

## 🛠 Компоненты модуля

| Компонент | Файл | Назначение |
|---|---|---|
| **Универсальный экстрактор контента** | `core/content_extractor.py` | Автоматическое определение типа и конвертация PDF, Excel, Audio, DOCX, CSV, Google Sheets в текст. |
| **Конвертер Excel** | `src/utils/convertors/excel.py` | Преобразование книг и листов .xlsx/.xls в словари и таблицы Markdown. |
| **Транскрибатор Аудио** | `src/utils/convertors/audio.py` | Высокоточная транскрибация речи в текст через Gemini API и fallback TTS. |
| **Ридер Google Sheets** | `src/utils/convertors/google_sheet.py` | Чтение Google Таблиц по ID/URL через Google Sheets API v4 и веб-экспорт CSV. |
| **Мультиязычные анализаторы** | `core/nlp_analyzers.py` | Протокол `LanguageAnalyzer`, `RussianAnalyzer`, `HebrewAnalyzer`, `EnglishAnalyzer`. |
| **Файловый реестр и привязка к ПК** | `core/workspace_registry.py` | Реестр `.workspace/config.json`, определение имени ПК (`get_current_host_name`) и формирование полных путей `\\<HOST_NAME>\<PATH>` для носимого USB-режима. |
| **Трекер файлов и директорий Git** | `core/workspace_items_tracker.py` | Добавление файлов и папок в Git-слежение (по умолчанию без копирования `copy_to_workspace=False`, либо с копированием `True`), просмотр содержимого и открытие в системном редакторе. |
| **Гибридный движок RAG FAISS** | `core/rag_faiss_engine.py` | Семантический + лексический поиск чанков на базе детерминированного векторного индекса `TextRAG` (FAISS 256D) и TF-скоринга. |
| **SQLite Хранилище знаний** | `core/knowledge_store.py` | Реляционное хранилище `KnowledgeStore` в режиме WAL (таблицы `documents` с `host_name` и `qualified_path`, `facts`, `entities` и др.). |
| **Менеджер рабочих областей** | `core/workspace_manager.py` | Связывание внешних источников с привязкой к имени ПК, изолированные Git-репозитории, инкрементальная детекция изменений и синхронизация без перемещения файлов. |
| **Движок вопросов и ответов** | `core/qa_engine.py` | Вопросно-ответная система по фактам, FAISS и WikiLLM с автоматической записью проверенных ответов в Obsidian Vault. |
| **Построитель компактного Obsidian Vault** | `core/obsidian_vault.py` | Автоматическое («на лету») и целенаправленное обогащение `.md` документов блоками YAML frontmatter, списками фактов и `[[wikilinks]]`, генерация `_Knowledge_Base.md` и тематических конспектов `_Topics/<Тема>.md` внутри папки рабочей области (`workspaces/<id>/`). |
| **Dual-Engine Adapter API** | `core/engine_adapter.py` | Единый контракт управления графическими движками оболочки: **Electron** (основной: Chromium + Node.js + IPC мост) и **WebView2** (встроенный Windows-хост). |
| **Оболочка Electron** | `electron/` | Самостоятельное Electron-приложение (`main.js`, `preload.js`, `package.json`) с прямым доступом к файловой системе Obsidian Vault и протоколу `obsidian://`. |
| **REST API Знаний и Obsidian** | `api/routers/router_knowledge.py`, `api/routers/router_obsidian.py` | Эндпоинты управления рабочими областями, источниками, импорта, QA, сборки Obsidian Vault и статуса движка. |
| **WebGUI Вкладка** | `api/webgui/tab_workspace/` | 3-шаговый интерфейс: Рабочая область, Obsidian Vault и Файлы → Документы и Факты → Вопрос-ответ. |

---

## 🔌 REST API Маршруты

- `GET /api/v1/workspaces` — Список рабочих областей и статус их Git-репозиториев.
- `POST /api/v1/workspaces` — Создание/выбор рабочей области с инициализацией `.git`.
- `POST /api/v1/workspaces/{workspace_id}/items` — Добавление файлов и папок в Git-слежение (по умолчанию `copy_to_workspace=false` — слежение на месте с сохранением `\\<HOST_NAME>\<PATH>`; при `copy_to_workspace=true` — копирование в папку рабочей области).
- `GET /api/v1/workspaces/{workspace_id}/directory-contents` — Содержимое рабочей области (локальные файлы + внешние отслеживаемые файлы с `host_name`, `qualified_path` и `is_current_host`).
- `POST /api/v1/workspaces/{workspace_id}/open-file` — Открытие локального файла, внешнего файла на текущем ПК или сохранённого слепка `.snapshot` (на другом ПК) в системном редакторе.
- `POST /api/v1/workspaces/{workspace_id}/sources` — Привязка внешнего файла, папки ПК или ссылки Google Sheets с фиксацией имени компьютера.
- `GET /api/v1/workspaces/{workspace_id}/sources` — Список связанных источников рабочей области (`host_name`, `qualified_path`, `is_current_host`).
- `GET /api/v1/workspaces/{workspace_id}/sources/changes` — Быстрая инкрементальная проверка изменённых, новых, отсутствующих и находящихся на других ПК (`other_host_files`) файлов по `mtime` и размеру.
- `DELETE /api/v1/workspaces/{workspace_id}/sources/{source_id}` — Удаление привязки источника.
- `POST /api/v1/workspaces/{workspace_id}/sources/sync` — Синхронизация и индексация связанных источников без перемещения файлов.
- `POST /api/v1/extract-preview` — Предпросмотр конвертации любого файла или Google Таблицы.
- `POST /api/v1/workspaces/seed-demo` — Автоматическое создание демо-области с эталонными примерами.
- `GET /api/v1/workspaces/{workspace_id}/documents` — Документы и история версий в выбранной рабочей области (`host_name`, `qualified_path`).
- `POST /api/v1/documents/import` — Сохранение документа, Git-коммит, NLP-извлечение фактов, обновление WikiLLM и FAISS.
- `GET /api/v1/facts` — Список извлечённых фактов (`active` / `stale`).
- `POST /api/v1/ask` — Ответ на вопрос по базе знаний (`local_only`, `local_first`, `cloud_assist`, `cloud_enrich`).
- `POST /api/v1/ask/stream` — Потоковый ответ на вопрос в формате Server-Sent Events (`text/event-stream`) с поэтапной телеметрией.
- `POST /api/v1/faiss/rebuild` — Перестроение векторного индекса FAISS для рабочей области.
- `GET /api/v1/language-modules` — Список подключённых языковых анализаторов (`ru`, `he`, `en`).
- `GET /api/v1/ai-models` — Список доступных ИИ-провайдеров и моделей из `src/ai`.
- `GET /api/v1/metrics` — Метрики производительности, статусов фактов и использования моделей.

---

## 🧪 Запуск тестов

```powershell
py -m pytest apps/ai_assistant/tests -v
```
