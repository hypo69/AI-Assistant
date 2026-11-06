# 📜 CODE_STANDARD.md — Стандарт оформления и написания кода (v2.3)

**Updated:** 2026-11-01 17:30:00

## 1. Основные стандарты
* **Python**: Python 3.12+, Pydantic v2, `from __future__ import annotations`.
* **Frontend**: Чистый Vanilla JS ES6+ без внешних тяжелых фреймворков.
* **Именование**:
  * Модули и папки вкладок: `snake_case` с префиксом `tab_` для вкладок WebGUI (например, `tab_workspace`, `tab_commits`, `tab_git_maintenance`, `ai_modal_dialog`).
  * CSS классы: `kebab-case` (`.ui-card`, `.ui-badge`, `.ai-modal-overlay`).
  * JS классы/модули: `PascalCase` (`AIModalDialog`, `I18nManager`, `ThemeManager`).

## 2. Надёжность и асинхронность
* Блокирующие файловые операции, вызовы Git и конвертеров документов в асинхронных роутерах оборачиваются в `asyncio.to_thread()`.
* Все fetch-запросы на фронтенде снабжаются `AbortController` для моментальной отмены при переключении вкладки или рабочего пространства.
* Валидация параметров выполняется по принципу Fail-Fast без использования `None` в качестве значений по умолчанию.
