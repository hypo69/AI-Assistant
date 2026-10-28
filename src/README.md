# ⚙️ Модуль `src` — Инфраструктурное ядро и провайдеры ИИ

**Статус:** ✅ Активно  
**Версия:** 3.6.0  
**Автор:** hypo69  
**Updated:** 2026-10-26 00:35:00  

---

## 📋 Назначение

Директория `src/` содержит общие инфраструктурные подсистемы, единый слой оркестрации языковых моделей и сервисные модули, используемые приложением [`apps/ai_assistant`](../apps/ai_assistant/README.md) и CLI [`manage_tools.py`](../manage_tools.py).

---

## 🏛️ Актуальная структура `src/`

```text
src/
├── ai/               # Единый маршрутизатор ИИ (UnifiedChatModel), агенты, RAG, WikiLLM и провайдеры
│   ├── agents/       # Специализированные ИИ-агенты (почта, документация, диагностика)
│   ├── gemini/       # Прямая интеграция с Google Gemini API и ротацией пула ключей
│   ├── orchestration/# Маршрутизация и балансировка запросов между моделями
│   ├── providers/    # Адаптеры провайдеров: agy, foundry, gemini, gemini_cli, huggingface, ollama, onnx, openai, windows_ai
│   ├── rag/          # Векторный поиск и индексация базы знаний
│   └── wikillm/      # Построение семантического графа сущностей WikiLLM
├── app/              # Фабрика FastAPI-приложения, AppState, middleware, CORS, метрики и WebSocket-хаб
├── secrets/          # Управление API-ключами, ротацией квот и конфигурацией почтовых ящиков (mailboxes.json)
├── skills/           # Обнаружение, валидация и исполнение навыков агентов (.agents/skills)
├── telemetry/        # Сбор телеметрии процесса и аппаратных метрик в SQLite
└── utils/            # Вспомогательные утилиты и конвертеры форматов (src/utils/convertors)
```

---

## 🔌 Поддерживаемые провайдеры ИИ (`src/ai`)

Все провайдеры подключены через единый контракт `UnifiedChatModel` (`ask()`, `chat()`, `stream_chat()`):

| Провайдер | Тип | Пакет | Назначение |
|---|---|---|---|
| **Google Gemini** | Облачный | [`src/ai/providers/gemini`](ai/providers/gemini/README.md) | Основной облачный генератор и семантический анализатор с поддержкой пула ключей |
| **Gemini CLI** | Локальный CLI / Облако | [`src/ai/providers/gemini_cli`](ai/providers/gemini_cli/README.md) | Выполнение запросов через локальный CLI-агент Gemini |
| **AGY (Antigravity)** | Облачный | [`src/ai/providers/agy`](ai/providers/agy/README.md) | Интеграция с провайдером Antigravity API |
| **Microsoft Foundry** | Локальный / Облако | [`src/ai/providers/foundry`](ai/providers/foundry/README.md) | Запуск локальных моделей через Foundry Local |
| **Ollama** | Локальный | [`src/ai/providers/ollama`](ai/providers/ollama/README.md) | Локальный запуск LLM (`llama3`, `qwen2.5` и др.) |
| **ONNX / DirectML** | Локальный | [`src/ai/providers/onnx`](ai/providers/onnx/README.md) | Аппаратно-ускоренный локальный вывод через ONNX Runtime |
| **Windows AI** | Локальный ОС | [`src/ai/providers/windows_ai`](ai/providers/windows_ai/README.md) | Нативные API Windows AI |
| **OpenAI-совместимые** | Облачный / Локальный | [`src/ai/providers/openai`](ai/providers/openai/README.md) | Подключение DeepSeek, LM Studio, vLLM и OpenAI API |
| **HuggingFace** | Облачный / Локальный | [`src/ai/providers/huggingface`](ai/providers/huggingface/README.md) | Модели экосистемы HuggingFace |

---

## 📐 Архитектурные принципы `src/`

1. **Явное внедрение зависимостей (Explicit DI):** сервисы передаются через `AppState` или явные конструкторы без скрытых глобальных состояний.
2. **Fail-Fast и предсказуемый откат:** при недоступности облачного провайдера система фиксирует событие через `logger` и автоматически переключается на резервный локальный контур.
3. **Разделение конфигурации и секретов:** параметры хранятся в `config.json`, а ключи и учётные данные — в `.env` и `src/secrets/`.
