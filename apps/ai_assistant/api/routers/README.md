# 🔌 Routers — Маршрутизаторы REST API (`apps/ai_assistant/api/routers`)

**Статус:** ✅ Активно  
**Версия:** 2.5.0  
**Пакет:** `apps.ai_assistant.api.routers`  
**Автор:** hypo69  
**Updated:** 2026-10-26 00:27:00  

---

## 📋 Обзор маршрутизаторов

Все маршрутизаторы подключаются в [`apps/ai_assistant/main.py`](../../main.py) с префиксом `/api/v1`.

| Файл | Назначение | Ключевые эндпоинты |
|---|---|---|
| [`router_knowledge.py`](router_knowledge.py) | Управление рабочими областями (с индивидуальным `.git`), слежение за внешними файлами на месте (без копирования по умолчанию, с привязкой к имени ПК `\\<HOST>\<PATH>`), импорт и анализ документов, факты SQLite, вопросно-ответная система (`KnowledgeQAEngine` + SSE-стриминг), перестроение FAISS и метрики. | `GET /api/v1/workspaces`<br>`POST /api/v1/workspaces`<br>`POST /api/v1/workspaces/{id}/items`<br>`GET /api/v1/workspaces/{id}/directory-contents`<br>`POST /api/v1/workspaces/{id}/open-file`<br>`GET /api/v1/workspaces/{id}/sources`<br>`GET /api/v1/workspaces/{id}/sources/changes`<br>`POST /api/v1/workspaces/{id}/sources/sync`<br>`POST /api/v1/documents/import`<br>`GET /api/v1/facts`<br>`POST /api/v1/ask`<br>`POST /api/v1/ask/stream`<br>`POST /api/v1/query` |
| [`router_file_history.py`](router_file_history.py) | Извлечение истории коммитов Git, построение темпоральной шкалы и получение diff. | `GET /api/v1/history`<br>`GET /api/v1/timeline`<br>`GET /api/v1/diff` |
| [`router_git_wikillm.py`](router_git_wikillm.py) | Связь истории Git с базой знаний WikiLLM: двухшаговая верификация аннотаций, мягкая инвалидация связей (`supersede`) и ИИ-суммаризация диффов. | `POST /api/v1/annotate`<br>`POST /api/v1/supersede`<br>`POST /api/v1/insights`<br>`POST /api/v1/git-wikillm/query`<br>`GET /api/v1/knowledge-links` |
| [`router_panel.py`](router_panel.py) | Унифицированный шлюз данных для UI-панелей и виджетов WebGUI (объединяет темпоральный граф и документы активной рабочей области). | `GET /v1/panel/{panel_id}` |
| [`router_obsidian.py`](router_obsidian.py) | Управление компактным хранилищем Obsidian Vault внутри рабочей области и адаптерами Electron / WebView2. | `POST /api/v1/workspaces/{id}/obsidian/build`<br>`POST /api/v1/workspaces/{id}/obsidian/topic`<br>`POST /api/v1/workspaces/{id}/obsidian/open` |
| [`router_git_maintenance.py`](router_git_maintenance.py) | Аудит, обслуживание и диагностика репозиториев Git рабочих областей. | `GET /api/v1/git-maintenance/status`<br>`POST /api/v1/git-maintenance/gc` |
| [`router_plugins.py`](router_plugins.py) | Управление плагинами и конфигурацией приложения. | `GET /api/v1/plugins` |

---

## 📡 Примеры запросов к API знаний (`router_knowledge.py`)

### 1. Создание демо-рабочей области с документами `mama.txt`, `farm.txt`, `frame_he.txt`
```http
POST /api/v1/workspaces/seed-demo
Content-Type: application/json

{
  "workspace_id": "default"
}
```

### 2. Импорт или обновление документа в рабочей области (с Git-коммитом и извлечением фактов)
```http
POST /api/v1/documents/import
Content-Type: application/json

{
  "workspace_id": "default",
  "document_id": "mama.txt",
  "content": "Мама мыла раму.",
  "commit_message": "Обновление документа mama.txt"
}
```

### 3. Запрос ответа на вопрос с морфологическим согласованием
```http
POST /api/v1/ask
Content-Type: application/json

{
  "question": "Кем была вымыта рама?",
  "workspace_id": "default",
  "mode": "local_first",
  "provider": "gemini",
  "model": "gemini-3.1-flash-lite"
}
```
**Ответ:**
```json
{
  "question": "Кем была вымыта рама?",
  "answer": "Мамой.",
  "language": "ru",
  "status": "success",
  "grammatical_details": {
    "answer": "Мамой.",
    "canonical_entity": "мама",
    "surface_form": "Мама",
    "grammatical_form": "inst"
  },
  "sources": [
    {
      "document_id": "mama.txt",
      "sentence_index": 0,
      "quote": "Мама мыла раму."
    }
  ]
}
```
