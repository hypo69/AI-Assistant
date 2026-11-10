# 🛠️ Навык ИИ-агента: Создатель рабочего пространства (`workspace-creator`)

**Статус:** ✅ Активно  
**Пакет:** `.agents.skills.workspace-creator`  
**Автор:** hypo69  
**Updated:** 2026-11-10 16:55:00  

---

## 📋 Описание

Навык **`workspace-creator`** предоставляет ИИ-моделям инструментарий и регламент для автономного или интерактивного развёртывания полноценных рабочих пространств на базе **любой локальной директории на диске** пользователя.

В отличие от ручного создания пустых папок, модель выполняет роль интеллектуального мастера (Wizard):
1. Проводит аудит содержимого папки без вмешательства в структуру.
2. Автоматически определяет основной язык (`ru`, `he`, `en`, `ua`) и семантическую направленность документов.
3. Инициализирует Git на месте без копирования файлов пользователя (`in-place tracking`).
4. Настраивает Obsidian Vault (`.obsidian/`, `_Knowledge_Base.md`) с теневыми конспектами под точкой (`.<doc>.md`), скрывая их от пользователя через `ServiceFileAuthenticator`.
5. Генерирует адаптивный `README.md` на языке документов.
6. Индексирует контент в SQLite и векторной базе FAISS.
7. Формирует стартовые контекстные подсказки (chips).

---

## 🚀 Использование из консоли (CLI)

```powershell
# 1. Аудит директории
py .agents/skills/workspace-creator/scripts/workspace_creator_cli.py audit "C:/Users/onela/Desktop/דוד מושה"

# 2. Создание пространства
py .agents/skills/workspace-creator/scripts/workspace_creator_cli.py create "C:/Users/onela/Desktop/דוד מושה" --id "david_moshe" --lang "he"
```

---

## 📚 Связанные модули и стандарты

- Спецификация навыка: [`SKILL.md`](SKILL.md)
- Движок создания: [`apps/ai_assistant/core/workspace_creator_engine.py`](file:///c:/Users/onela/AppData/Local/AI-Assistant/apps/ai_assistant/core/workspace_creator_engine.py)
- Классификатор файлов: [`apps/ai_assistant/core/service_file_authenticator.py`](file:///c:/Users/onela/AppData/Local/AI-Assistant/apps/ai_assistant/core/service_file_authenticator.py)
- Реестр пространств: [`apps/ai_assistant/core/workspace_registry.py`](file:///c:/Users/onela/AppData/Local/AI-Assistant/apps/ai_assistant/core/workspace_registry.py)
