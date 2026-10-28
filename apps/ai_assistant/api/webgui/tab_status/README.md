# Вкладка: Статус системы (tab_status)

Вкладка отображает диагностическую готовность подсистем (Git, WikiLLM, Temporal Graph, RAG).

## Структура
- `panel_status/`: Изолированная панель `panel-system-status`, взаимодействующая с `/v1/panel/panel-system-status`.
- `main.js`: Оркестратор вкладки.
- `index.html`: Разметка вкладки.
