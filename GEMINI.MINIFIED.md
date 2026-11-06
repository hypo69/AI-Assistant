# GEMINI.MINIFIED.md — Инструкции для выполнения задач (AI-Assistant)

> [!IMPORTANT]
> **Назначение файла**: Этот компактный индекс предназначен для работы с проектом **AI-Assistant** (Умный помощник хранения истории файлов, управления базами знаний и персональный ассистент пользователя) через CLI и навыки агентов.

---

## 🧭 Навигация из рабочей директории (`scripts/cli/`)

При запуске из директории `scripts/cli/` корень проекта находится на два уровня выше (`../../`). Используй указанные ниже относительные пути для доступа к инструментам, навыкам и документации.

---

### 1. Универсальный CLI инструментов — `../../manage_tools.py`
Единая точка входа для запуска проектных операций:

```powershell
# Общий синтаксис
py ../../manage_tools.py <группа> <команда> [аргументы]

# Основные команды
py ../../manage_tools.py skills list                # Список доступных навыков
py ../../manage_tools.py rag build                  # Пересборка векторного индекса знаний FAISS
py ../../manage_tools.py db check-integrity         # Проверка целостности SQLite баз знаний
py ../../manage_tools.py docs generate              # Генерация документации
```

---

### 2. Навыки агента (Agent Skills) — `../../.agents/skills/`
Каждый навык находится в собственной поддиректории `../../.agents/skills/<имя_навыка>/SKILL.md` и содержит готовые скрипты в `scripts/`:

- **Веб-интерфейс и рабочие области:**
  - `workspace-url-routing` (`../../.agents/skills/workspace-url-routing/SKILL.md`) — маршрутизация рабочих пространств через URL `#tab-workspace#panel-files#workspace=<id>`.
  - `webgui-menu-maintainer` (`../../.agents/skills/webgui-menu-maintainer/SKILL.md`) — поддержание двухуровневых меню субпанелей и блоков WebGUI с тултипами и i18n.
  - `webgui-developer` (`../../.agents/skills/webgui-developer/SKILL.md`) — разработка и модификация вкладок `tab_<tab_id>` в `apps/ai_assistant/api/webgui`.
  - `ai-modal-assistant` (`../../.agents/skills/ai-modal-assistant/SKILL.md`) — интеграция универсального модального окна ИИ-ассистента (`#universal-ai-table-modal`).
- **Персональный секретарь и коммуникации:**
  - `google-mail` (`../../.agents/skills/google-mail/SKILL.md`) — чтение, поиск и отправка писем через Gmail API.
  - `google-calendar` (`../../.agents/skills/google-calendar/SKILL.md`) — расписание, события и встречи в Google Calendar.
  - `google-drive` (`../../.agents/skills/google-drive/SKILL.md`) — поиск, загрузка и организация файлов в Google Drive.
  - `google-contacts` (`../../.agents/skills/google-contacts/SKILL.md`) — поиск и синхронизация контактов Google People API.
  - `smtp-mail-agent` (`../../.agents/skills/smtp-mail-agent/SKILL.md`) — автономная отправка писем и отчетов по SMTP.
- **Документация, файлы и обслуживание:**
  - `file-saver` (`../../.agents/skills/file-saver/SKILL.md`) — безопасное сохранение файлов и проверка целостности записи.
  - `doc-generator` (`../../.agents/skills/doc-generator/SKILL.md`) — генерация и валидация проектной документации.
  - `tdd-doc-gen` (`../../.agents/skills/tdd-doc-gen/SKILL.md`) — генерация тестов и TDD-документации.
  - `pdf-exporter` (`../../.agents/skills/pdf-exporter/SKILL.md`) — экспорт кода и документации в PDF-книги.
  - `skill-factory` (`../../.agents/skills/skill-factory/SKILL.md`) — создание и упаковка новых навыков.
  - `cert-installer` (`../../.agents/skills/cert-installer/SKILL.md`) — генерация и установка локальных SSL-сертификатов.
  - `project-installer` (`../../.agents/skills/project-installer/SKILL.md`) — установка окружения и зависимостей проекта.
  - `system-updater` (`../../.agents/skills/system-updater/SKILL.md`) — резервное копирование и обновление системы.

---

### 3. Проектные инструкции и ролевые профили — `../../.ai/instructions/`
- **Главный навигатор**: `../../.ai/instructions/README.md`
- **Ролевые профили**:
  - Техник (Git, БД знаний, RAG, провайдеры ИИ): `../../.ai/instructions/roles/TECHNICIAN.md`
  - Персональный секретарь (почта, календарь, контакты, документы): `../../.ai/instructions/roles/SECRETARY.md`
  - Администратор (рабочие области, ключи, конфигурация): `../../.ai/instructions/roles/ADMINISTRATOR.md`
- **Стандарты**:
  - `../../.ai/instructions/standards/ENGINEERING.md` — инженерный стандарт кода.
  - `../../.ai/instructions/standards/WEBGUI.md` — стандарт веб-интерфейса (`apps/ai_assistant/api/webgui`).
  - `../../.ai/instructions/standards/SUBTABS_AND_BLOCKS_MENU.md` — стандарт меню субпанелей и блоков.
  - `../../.ai/instructions/standards/WORKSPACE_ROUTING.md` — маршрутизация рабочих пространств.

---

### 4. Серверы контекста (MCP) — `../../.mcp/`
- `../../.mcp/` — MCP-серверы поиска, базы знаний и браузерной автоматизации.

---

## 📌 Правила поведения модели
1. **Опирайся на навыки (`SKILL.md`)**: При получении задачи обратись к соответствующему навыку в `../../.agents/skills/<навык>/SKILL.md`.
2. **Используй CLI инструментов**: Для выполнения проектных задач вызывай `py ../../manage_tools.py <группа> <команда>`.
3. **Языковой стандарт**: Все ответы, пояснения и отчеты формируются строго на **русском языке**.
