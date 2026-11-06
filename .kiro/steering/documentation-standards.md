---
name: Documentation Standards
description: Стандарты документирования, формат docstring и TDD для AI-Assistant
inclusion: auto
---

# 📚 Стандарты документирования и TDD

Этот файл синхронизирован с `.ai/instructions/standards/DOCUMENTATION.md`, `.ai/instructions/standards/FILE_HEADERS.md` и `.ai/instructions/workflows/TDD.md`.

## Три уровня документации (строго на русском языке)

| Уровень | Тип | Где | Требование |
|---|---|---|---|
| **1** | Шапка файла и Docstring (`hypo69 docblock`) | В каждом файле, классе и функции | Обязательно (`Args`, `Returns`, `Exceptions`, `Examples`) |
| **2** | Комментарии в коде | Над нетривиальными блоками | Объясняют «почему», а не «что» |
| **3** | `README.md` | В каждой директории модуля | Назначение, архитектура, примеры использования |

## Обязательные правила

- При любом изменении кода обновлять `Updated: YYYY-MM-DD HH:MM:SS` в шапке файла.
- В поле `Project:` шапки файла указывать `ai-assistant`.
- Все изменения бизнес-логики в `apps/ai_assistant/core/` и `src/` сопровождаются тестами в `apps/ai_assistant/tests/` или `tests/`.

---

**Updated:** 2026-11-01 17:34:00
