---
name: google-calendar
description: Google Calendar skill for listing events, scheduling meetings, querying agendas, creating, updating, and deleting events via Google Calendar API.
description_i18n:
  en: Google Calendar skill for listing events, scheduling meetings, querying agendas, creating, updating, and deleting events via Google Calendar API.
  ru: Навык работы с Google Календарем для просмотра расписания, планирования встреч, создания, обновления и удаления событий через Google Calendar API.
---

# 📅 Навык: Google Calendar (Calendar API v3)

## 📌 Назначение и концепция

Навык `google-calendar` наделяет агентов ИИ способностью управлять календарями Google пользователя:
- Просматривать предстоящее расписание и встречи на заданное количество дней вперед.
- Находить события по ключевым словам или фильтровать по временным диапазонам.
- Создавать новые встречи, задачи и напоминания с указанием участников, местоположения и описания.
- Удалять отмененные события по идентификатору.

Интеграция работает через `src/ai/google_accounts_state.py` с использованием авторизованного профиля Google OAuth 2.0.

---

## 🎯 Триггеры активации

Активируйте навык, если в запросе пользователя требуется:
1. Посмотреть расписание («Какие у меня планы на завтра?», «Покажи встречи на этой неделе»).
2. Запланировать событие или встречу («Создай встречу с коллегой во вторник в 15:00»).
3. Найти информацию о событии («Когда созвон по проекту X?»).
4. Отменить или удалить мероприятие из календаря.

---

## 🚀 Протокол выполнения

### 1. Просмотр расписания
```bash
# Получить события на ближайшие 7 дней в формате JSON:
python .agents/skills/google-calendar/scripts/list_events.py -d 7 --json

# Поиск конкретного события по ключевому слову:
python .agents/skills/google-calendar/scripts/list_events.py -q "Синхронизация" --json
```

### 2. Создание события
```bash
# Встреча с точным временем начала и конца:
python .agents/skills/google-calendar/scripts/create_event.py \
  -s "Встреча по архитектуре проекта" \
  --start "2026-10-28T11:00:00+02:00" \
  --end "2026-10-28T12:00:00+02:00" \
  --desc "Обсуждение новых навыков Google Workspace" \
  --location "Google Meet" \
  -a "partner@example.com" \
  --json

# Событие на весь день:
python .agents/skills/google-calendar/scripts/create_event.py \
  -s "Релиз версии 4.0" \
  --start "2026-11-01" \
  --end "2026-11-01" \
  --json
```

### 3. Удаление события
```bash
python .agents/skills/google-calendar/scripts/delete_event.py -i "<EVENT_ID>" --json
```

---

## 🛠️ Состав скриптов (`scripts/`)

- **`calendar_client.py`**: Ядро `GoogleCalendarClient` (вызовы `googleapiclient.discovery.build('calendar', 'v3')`).
- **`list_events.py`**: CLI просмотр и фильтрация событий календаря.
- **`create_event.py`**: CLI добавление мероприятий с участниками и гео/онлайн ссылками.
- **`delete_event.py`**: CLI удаление событий по ID.

---

## 🔒 Безопасность

- Использует область видимости (scope) `https://www.googleapis.com/auth/calendar`.
- Токены хранятся в `src/secrets/google_oauth_tokens/`.
