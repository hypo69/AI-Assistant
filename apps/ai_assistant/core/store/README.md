# 🗄️ Пакет репозиториев SQLite (`apps/ai_assistant/core/store`)

**Статус:** ✅ Активно  
**Версия:** 1.2.0  
**Пакет:** `apps.ai_assistant.core.store`  
**Автор:** hypo69  
**Updated:** 2026-10-26 00:26:00  

---

## 📋 Назначение

Модульная декомпозиция реляционного хранилища `KnowledgeStore` (режим `WAL`) по группам таблиц согласно стандарту `GEMINI.md`:
- [`schema.py`](schema.py) — декларативное описание таблиц и составных индексов SQLite (`KNOWLEDGE_STORE_DDL`), включая таблицу `app_settings` и поля `host_name` / `qualified_path` в `documents`.
- [`workspace_repo.py`](workspace_repo.py) — [`WorkspaceRepoMixin`](workspace_repo.py): управление таблицами `workspaces`, `workspace_sources` и `app_settings`.
- [`document_fact_repo.py`](document_fact_repo.py) — [`DocumentFactRepoMixin`](document_fact_repo.py): управление таблицами `documents` (с сохранением имени компьютера `host_name` и полного пути `qualified_path` вида `\\<HOST>\<PATH>`), `document_versions`, `document_chunks`, `entities`, `facts`, `fact_sources`, `language_analysis`.
- [`telemetry_repo.py`](telemetry_repo.py) — [`TelemetryRepoMixin`](telemetry_repo.py): управление таблицами `query_history`, `model_usage`, `embedding_registry`, `analysis_runs` и сбор метрик.
