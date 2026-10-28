# 🧪 Tests — Тестовый набор приложения AI Assistant (`apps/ai_assistant/tests`)

**Статус:** ✅ Активно (26 тестовых модулей, 155/155 тестов проходят)  
**Версия:** 3.6.0  
**Пакет:** `apps.ai_assistant.tests`  
**Автор:** hypo69  
**Updated:** 2026-10-26 00:35:00  

---

## 📋 Описание всех тестовых модулей

| Файл | Покрываемые сценарии |
|---|---|
| [`test_multilingual_knowledge_qa.py`](test_multilingual_knowledge_qa.py) | Полная проверка требований [`TECHNICAL_SPECIFICATION.md`](../TECHNICAL_SPECIFICATION.md) (**Тесты A–I**):<br>• **Тест A–B (Русский язык, `mama.txt`: `Мама мыла раму.`)**: активный/пассивный залог, склонение ответов по падежам (`Раму.`, `Мама.`, `Мамой.`).<br>• **Тест C (Иврит, действие `frame_he.txt`: `אמא רחצה את המסגרת`)**: `מי רחצה את המסגרת?` → `אמא`, `מה רחצה אמא?` → `המסגרת`.<br>• **Тест I (Иврит, принадлежность `farm.txt`: `לדוד משה היתה חווה`)**: 5 типов вопросов (`מה היה לדוד משה?` → `חווה`, `למי הייתה חווה?` → `לדוד משה`, `האם לדוד משה הייתה חווה?` → `כן` и др.).<br>• **Тест D–H**: перефразирование, `insufficient_data`, `local_only`, отказ API и статус `stale` при обновлении файла в Git. |
| [`test_optimizations_and_coreference.py`](test_optimizations_and_coreference.py) | • Разрешение кореференции местоимений 3-го лица (`RU / HE / EN`: `он/она/у него`, `הוא/היא/שלו`, `he/she/his`) между предложениями.<br>• Потоковый SSE-эндпоинт `POST /api/v1/ask/stream`.<br>• Гибридный поиск `RagFaissEngine` (FAISS 256D + TF).<br>• Инкрементальный мониторинг изменений внешних источников (`/sources/changes`, `/sources/rescan`).<br>• Слежение Git без копирования по умолчанию (`copy_to_workspace = False`).<br>• **Носимый режим (USB-флешка)**: пути с именем компьютера `\\<HOST_NAME>\<PATH>`, перенос между ПК (`HOST-ALPHA` / `HOST-BETA`), статус `other_host` и чтение из `.extracted_snapshots/*.snapshot`. |
| [`test_workspace_items_tracker.py`](test_workspace_items_tracker.py) | Отслеживание файлов и папок на месте (`in_place`) и с копированием (`copied`), коммиты `.tracked.md` в Git и дедупликация источников. |
| [`test_linked_sources_and_converters.py`](test_linked_sources_and_converters.py) | Извлечение текста из внешних форматов (PDF, DOCX, Excel/CSV, изображения, аудио) и сохранение слепков в `.extracted_snapshots/`. |
| [`test_workspace_registry.py`](test_workspace_registry.py) | Реестр рабочих областей, разрешение путей, сохранение `.workspace/config.json` и квалифицированных путей `\\<HOST>\<PATH>`. |
| [`test_workspace_git_history.py`](test_workspace_git_history.py) | Инициализация Git-репозиториев рабочих областей, автоматические коммиты и чтение лога ревизий. |
| [`test_git_engine.py`](test_git_engine.py) | Тестирование `GitHistoryEngine` и жизненного цикла темпорального графа `TemporalCodeGraph`. |
| [`test_git_maintenance.py`](test_git_maintenance.py) и [`test_git_maintenance_analyzer.py`](test_git_maintenance_analyzer.py) | Диагностика состояния Git-репозитория, поиск крупных объектов/дубликатов и генерация правил `.gitignore`. |
| [`test_obsidian_electron_architecture.py`](test_obsidian_electron_architecture.py) | Компактный Obsidian Vault (`_Knowledge_Base.md`, `_Topics/`), экспорт конспектов и контракт `EngineAdapter` (`electron` / `webview2`). |
| [`test_api_routers.py`](test_api_routers.py) | Маршруты REST API истории Git (`/api/v1/history`, `/api/v1/timeline`, `/api/v1/annotate`, `/api/v1/query`). |
| [`test_panel_router.py`](test_panel_router.py) | Контракт UI-панелей `/api/v1/panel/*` и раздача статики WebGUI. |
| [`test_verification_pipeline.py`](test_verification_pipeline.py) | Двухэтапный контур верификации, защита от prompt-injection и маскирование секретов. |
| [`test_tab_rag_user_space.py`](test_tab_rag_user_space.py) | Пользовательский поиск во вкладке `tab_rag` и диагностика гибридного конвейера RAG. |
| [`test_models_tab_and_api.py`](test_models_tab_and_api.py) | Маршруты `/api/v1/models/*` и вкладка управления провайдерами ИИ и пулом ключей (`tab_models`). |
| [`test_gmail_tab_and_api.py`](test_gmail_tab_and_api.py) | Маршруты `/api/v1/gmail/*`, Google OAuth и вкладка `tab_gmail`. |
| [`test_plugins_tab_and_api.py`](test_plugins_tab_and_api.py) | Маршруты `/api/v1/plugins/*` и вкладка управления плагинами (`tab_plugins`). |
| [`test_ide_navigation.py`](test_ide_navigation.py) и [`test_workspace_subtabs.py`](test_workspace_subtabs.py) | Навигация по единой IDE-оболочке, суб-вкладки `tab_workspace` и синхронизация URL-маршрутов. |
| [`test_rtl_drawer_menu.py`](test_rtl_drawer_menu.py) и [`test_webgui_rtl_controls.py`](test_webgui_rtl_controls.py) | Корректность RTL-вёрстки для иврита (`dir="rtl"`), выдвижного меню и элементов управления. |
| [`test_webgui_i18n_ids.py`](test_webgui_i18n_ids.py) и [`test_webgui_refactoring.py`](test_webgui_refactoring.py) | Полнота ключей локализации (`ru`, `en`, `he`) и модульная целостность вкладок WebGUI. |
| [`test_ai_smart_tooltips.py`](test_ai_smart_tooltips.py) | Умные тултипы с кнопкой `✨ Спросить ИИ` и связка с `AIModalDialog`. |
| [`test_system_tour.py`](test_system_tour.py) | Интерактивный гид-тур `system_tour`. |
| [`test_theme_tokens_integrity.py`](test_theme_tokens_integrity.py) | Отсутствие хардкода цветов и полнота CSS-переменных во всех темах оформления. |
| [`test_server_port_switch.py`](test_server_port_switch.py) | Конфигурация и динамическое переключение порта сервера FastAPI. |

---

## ▶️ Запуск тестов

```powershell
py -m pytest apps/ai_assistant/tests -v
```
