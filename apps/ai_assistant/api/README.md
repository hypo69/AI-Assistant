# 🌐 API — Слой REST API и веб-интерфейса (`apps/ai_assistant/api`)

**Статус:** ✅ Активно  
**Версия:** 2.5.0  
**Пакет:** `apps.ai_assistant.api`  
**Автор:** hypo69  
**Updated:** 2026-10-26 00:27:00  

---

## 📋 Назначение

Пакет `apps.ai_assistant.api` объединяет:
1. **Маршрутизаторы FastAPI (`routers/`)** — REST API для управления рабочими областями, индивидуальными Git-репозиториями, импортом документов, таблицей фактов SQLite, векторным индексом FAISS, графом знаний WikiLLM и вопросно-ответной системой (`KnowledgeQAEngine`).
2. **Pydantic-схемы (`schemas.py`)** — типизированные контракты запросов и ответов API.
3. **Клиентский веб-интерфейс (`webgui/`)** — модульный интерфейс с поддержкой тем оформления, мультиязычности (`i18n`) и пошаговой вкладкой работы со знаниями [`tab_workspace`](webgui/tab_workspace/README.md).

---

## 📂 Структура каталога

- [`schemas.py`](schemas.py) — модели данных Pydantic для коммитов, диффов, связей графа и поисковых запросов.
- [`routers/`](routers/README.md) — модули маршрутизаторов FastAPI (`router_knowledge.py`, `router_file_history.py`, `router_git_wikillm.py`, `router_panel.py`).
- [`webgui/`](webgui/README.md) — фронтенд приложения (HTML5, CSS-переменные дизайн-системы, ES6-модули, вкладки).
