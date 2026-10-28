# ⚡ JS — Клиентские модули оркестрации IDE и WebGUI (`apps/ai_assistant/api/webgui/js`)

**Статус:** ✅ Активно  
**Версия:** 3.6.0  
**Пакет:** `apps.ai_assistant.api.webgui.js`  
**Автор:** hypo69  
**Updated:** 2026-10-26 00:35:00  

---

## 📋 Назначение

Каталог содержит ядро клиентской логики WebGUI (Vanilla JS ES6+):

| Файл | Назначение |
|---|---|
| [`main.js`](main.js) | Главный оркестратор интерфейса: карта маршрутов вкладок (`TABS`), ленивая подгрузка HTML/JS, синхронизация URL-хэша (`#tab-workspace#panel-files#workspace=<id>`) и инициализация модулей. |
| [`tab-core.js`](tab-core.js) | Механизм переключения вкладок (`switchTab`, `loadTab`) и управление жизненным циклом DOM-контейнеров. |
| [`panel-loader.js`](panel-loader.js) | Динамическая загрузка и инициализация изолированных панелей `panel_<id>/panel.js`. |
| [`ide_navigation.js`](ide_navigation.js) | Управление единой IDE-оболочкой, боковой панелью активности (Activity Bar) и выдвижной нижней панелью (Bottom Drawer). |
| [`ide_file_explorer.js`](ide_file_explorer.js) | Боковой проводник файлов активной рабочей области с быстрым открытием документов и слепков `.snapshot`. |
| [`ide_extensions_sidebar.js`](ide_extensions_sidebar.js) | Боковая панель расширений и быстрого доступа к плагинам. |
| [`top_workspace_dropdown.js`](top_workspace_dropdown.js) | Верхний выпадающий список быстрого переключения активной рабочей области. |
| [`drawer_workspaces.js`](drawer_workspaces.js) | Управление списком рабочих областей в нижней выдвижной панели (Drawer). |
| [`workspace_wizard.js`](workspace_wizard.js) | Пошаговый мастер создания рабочей области с поддержкой слежения без копирования (`copy_to_workspace = false`) и путей `\\<HOST>\<PATH>`. |
| [`wikillm_editor.js`](wikillm_editor.js) | Интерактивный редактор заметок и сущностей базы знаний WikiLLM / Obsidian Vault. |
| [`theme.js`](theme.js) и [`theme-engine.js`](theme-engine.js) | Движок цветовых тем (`light`, `dark`, `brick`, `terminal`, `system`) и динамического применения CSS-токенов. |
| [`i18n.js`](i18n.js) и [`global-i18n.js`](global-i18n.js) | Мультиязычная локализация (`ru`, `en`, `he`), автоматическое включение `dir="rtl"` для иврита и перевод динамических DOM-узлов. |
| [`global-tooltips-i18n.js`](global-tooltips-i18n.js) | Система умных всплывающих подсказок с кнопкой `✨ Спросить ИИ` и интеграцией с `AIModalDialog`. |
| [`context-menu.js`](context-menu.js) | Кастомное контекстное меню для таблиц, файлов и узлов графа. |
| [`api-cache.js`](api-cache.js), [`browser-cache.js`](browser-cache.js), [`cache-ui.js`](cache-ui.js) | Клиентское кеширование ответов API, индикация состояния кеша и инвалидация. |
| [`toast.js`](toast.js) | Неблокирующие всплывающие уведомления о событиях и ошибках. |
| [`userSettings.js`](userSettings.js) | Управление пользовательскими настройками интерфейса. |
