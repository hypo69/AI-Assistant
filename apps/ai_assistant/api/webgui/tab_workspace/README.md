# 📂 Вкладка `tab_workspace` — Файлы, Слежение Git на месте, Носимый режим, Умный Поиск Знаний и Чат

**Статус:** ✅ Активно  
**Пакет:** `apps/ai_assistant/api/webgui/tab_workspace`  
**Автор:** hypo69  
**Updated:** 2026-10-26 00:35:00  

---

## 📌 Назначение

Главная вкладка интерфейса `AI Assistant`, реализующая полный сценарий работы пользователя под единым горизонтальным меню переключателя панелей (`workspace-subtabs-nav`):

1. **Файлы (`panel-files`):**
   - выбор или создание рабочей области (`panel-workspace-select`) с отображением имени компьютера-владельца (`🖥️ <HOST>`) и полного квалифицированного пути `\\<HOST_NAME>\<Drive>:\<Path>`;
   - просмотр содержимого Git-репозитория;
   - **слежение Git за файлами и папками на месте без копирования (`copy_to_workspace = false` по умолчанию)** через переключатель `#ws-track-copy-checkbox` (с созданием коммитируемых `.tracked.md` манифестов и текстовых слепков `.extracted_snapshots/*.snapshot`);
   - компактный **Obsidian Vault** (`_Knowledge_Base.md`, `_Topics/<Тема>.md`);
   - привязка и инкрементальный мониторинг внешних источников (`panel-sources`, `/sources/changes`) с поддержкой переноса флешки между разными ПК (статус `other_host` — «На другом ПК (`<HOST>`)»).
2. **Шаг 2 — Документы и Git-история (`panel-documents`, `panel-facts`):**
   - создание и редактирование текстовых документов с автоматическим коммитом в Git рабочей области;
   - извлечение структурированных фактов (`action`, `possession`) с автоматическим разрешением местоимений 3-го лица (`он`, `она`, `у него`, `הוא`, `היא`, `שלו`, `he`, `she`, `his`) по предыдущему предложению;
   - перевод устаревших фактов в статус `stale` и переиндексация в SQLite + гибридный индекс FAISS (256D + TF) + WikiLLM.
3. **Шаг 3 — Умный поиск и Вопрос-Ответ (`panel-qa`):**
   - ввод вопросов на русском языке, иврите или английском языке с выбором режима (`local_only`, `local_first`, `cloud_assist`, `cloud_enrich`) и модели из `src/ai`;
   - грамматически точное склонение кратких ответов по падежам (`Мама.` / `Раму.` / `Мамой.`) и поддержка конструкций принадлежности на иврите (`לדוד משה היתה חווה`).
4. **Чат (`panel-chat`):**
   - диалоговый интерфейс с поддержкой потокового SSE-ответа (`POST /api/v1/ask/stream`) и переключения рабочих контекстов.
5. **Коммиты (`panel-commits`):**
   - история коммитов Git активного пространства с фильтрацией и переходом к построчному Diff.

---

## 🎛️ Программная навигация и URL-маршрутизация

Формат URL: `#tab-workspace#<panel_id>#workspace=<workspace_id>` (см. [`.ai/instructions/standards/WORKSPACE_ROUTING.md`](../../../../../.ai/instructions/standards/WORKSPACE_ROUTING.md)).

```javascript
// Переключение верхних суб-панелей вкладки:
window.switchWorkspaceSubTab('panel-files' | 'panel-documents' | 'panel-qa' | 'panel-chat' | 'panel-commits');

// Переключение подвкладок внутри панели «Файлы»:
window.switchFilesSubTab('dir' | 'track' | 'obsidian' | 'sources');
```

---

## 🔌 Используемые эндпоинты REST API

- `GET /api/v1/workspaces` и `POST /api/v1/workspaces` — список и создание рабочих областей (с полями `host_name`, `qualified_path`, `is_current_host`);
- `POST /api/v1/workspaces/{workspace_id}/items` — подключение файлов/папок в слежение Git (`copy_to_workspace = false` по умолчанию);
- `GET /api/v1/workspaces/{workspace_id}/sources` — список отслеживаемых источников со статусом доступности (`available`, `missing`, `other_host`) и путём `\\<HOST>\<PATH>`;
- `GET /api/v1/workspaces/{workspace_id}/sources/changes` и `POST /api/v1/workspaces/{workspace_id}/sources/rescan` — обнаружение внешних изменений на диске и переиндексация;
- `POST /api/v1/documents/import` — сохранение документа, коммит в Git и извлечение знаний;
- `GET /api/v1/facts` и `POST /api/v1/facts/{fact_id}/status` — просмотр и валидация фактов;
- `POST /api/v1/ask` и `POST /api/v1/ask/stream` — синхронный и потоковый (SSE) ответ на вопрос со ссылками на документ, предложение и хэш коммита Git.
