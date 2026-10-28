---
name: google-mail
description: Full-featured Gmail API integration skill for reading, searching, sending emails, managing drafts, labels, and attachments via authorized Google OAuth.
description_i18n:
  en: Full-featured Gmail API integration skill for reading, searching, sending emails, managing drafts, labels, and attachments via authorized Google OAuth.
  ru: Полнофункциональный навык интеграции с Gmail API для чтения, поиска, отправки электронных писем, управления черновиками, метками и вложениями через Google OAuth.
---

# ✉️ Навык: Google Mail (Gmail API)

## 📌 Назначение и концепция

Навык `google-mail` предоставляет агентам ИИ и операторам инструменты прямого взаимодействия с почтовым сервисом Gmail через официальный Google API Client.
Использует централизованную систему управления токенами `src/ai/google_accounts_state.py` и профили Google OAuth 2.0.

---

## 🎯 Триггеры активации

Активируйте этот навык, если пользователь или сценарий запрашивает:
1. Поиск или чтение входящих/отправленных сообщений в Gmail (`is:unread`, `from:someone`, `subject:...`).
2. Проверку непрочитанных писем, сводку почтового ящика, извлечение сниппетов и вложений.
3. Отправку нового электронного письма, ответа или уведомления с поддержкой HTML и файлов во вложении.
4. Управление метками (отметить как прочитанное, добавить ярлык, переместить в корзину).

---

## 🚀 Протокол выполнения

### 1. Проверка авторизации
Перед началом работы убедитесь, что Google-аккаунт настроен и имеет действующий токен:
```bash
python .agents/skills/google-mail/scripts/list_messages.py --limit 1 --json
```
Если возвращается ошибка авторизации, запустите процедуру входа через интерфейс `/auth/google` или обратитесь к модулю `src.ai.google_accounts_state`.

### 2. Поиск и выборка писем
```bash
# Получить 5 последних входящих писем
python .agents/skills/google-mail/scripts/list_messages.py -n 5 --json

# Поиск только непрочитанных писем от конкретного адресата
python .agents/skills/google-mail/scripts/list_messages.py -q "from:boss@example.com is:unread" --json
```

### 3. Чтение содержимого письма
```bash
python .agents/skills/google-mail/scripts/read_message.py -i "<MESSAGE_ID>" --json
```

### 4. Отправка сообщения
```bash
# Текстовое сообщение
python .agents/skills/google-mail/scripts/send_message.py -t "recipient@example.com" -s "Тема сообщения" -b "Текст сообщения" --json

# Письмо с HTML и вложением
python .agents/skills/google-mail/scripts/send_message.py -t "recipient@example.com" -s "Отчет" -b "См. вложение" --html "<h2>Отчет готов</h2>" -a "path/to/report.pdf" --json
```

---

## 🛠️ Состав скриптов (`scripts/`)

- **`mail_client.py`**: Базовый класс `GoogleMailClient` (обёртка над `googleapiclient.discovery.build('gmail', 'v1')`).
- **`list_messages.py`**: Поиск и постраничный вывод писем по запросам и меткам.
- **`read_message.py`**: Получение полного тела письма (plain text / HTML), заголовков и метаданных вложений.
- **`send_message.py`**: Отправка сообщений с поддержкой вложений, CC и BCC.

---

## 🔒 Безопасность и хранение секретов

- Токены доступа хранятся строго в `src/secrets/google_oauth_tokens/`.
- Файлы секретов приложения хранятся в `src/secrets/google_ouath_files/`.
- Запрещено выводить приватные ключи и access-токены в открытый лог.
