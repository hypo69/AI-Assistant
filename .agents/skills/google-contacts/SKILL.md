---
name: google-contacts
description: Google Contacts (People API) skill for searching, viewing, creating, updating, and exporting contacts, phone numbers, and address books.
description_i18n:
  en: Google Contacts (People API) skill for searching, viewing, creating, updating, and exporting contacts, phone numbers, and address books.
  ru: Навык работы с Google Контактами (People API) для поиска, просмотра, создания, обновления и экспорта телефонной книги и контактных данных.
---

# 👥 Навык: Google Contacts (People API v1)

## 📌 Назначение и концепция

Навык `google-contacts` предназначен для работы с телефонной книгой и списком контактов Google через Google People API v1:
- Поиск контактов по имени, фамилии, компании, номеру телефона или email-адресу.
- Получение подробной карточки контакта (телефоны, email, организации, заметки).
- Добавление новых контактов в адресную книгу.
- Удаление устаревших или ошибочных контактов по идентификатору `resourceName`.

Интеграция опирается на авторизованный Google OAuth токен (`src/ai/google_accounts_state.py`).

---

## 🎯 Триггеры активации

Активируйте этот навык, если в запросе пользователя требуется:
1. Найти контакт человека («Какой номер телефона у Иванова?», «Найди email бухгалтера»).
2. Просмотреть адресную книгу или список контактов.
3. Сохранить новый контакт («Добавь в контакты Сергея, телефон +79991234567»).
4. Отредактировать или удалить контакт из адресной книги.

---

## 🚀 Протокол выполнения

### 1. Поиск контакта
```bash
# Найти контакт по имени или номеру телефона:
python .agents/skills/google-contacts/scripts/list_contacts.py -q "Иван" --json

# Получить первые 20 контактов из адресной книги:
python .agents/skills/google-contacts/scripts/list_contacts.py -n 20 --json
```

### 2. Создание нового контакта
```bash
python .agents/skills/google-contacts/scripts/create_contact.py \
  -n "Алексей" \
  --family-name "Петров" \
  -p "+79990001122" \
  -e "alex@example.com" \
  --org "Tech Corp" \
  --title "Архитектор" \
  --notes "Контакт из проекта AI Assistant" \
  --json
```

### 3. Удаление контакта
```bash
python .agents/skills/google-contacts/scripts/delete_contact.py \
  -r "people/c1234567890123456789" \
  --json
```

---

## 🛠️ Состав скриптов (`scripts/`)

- **`contacts_client.py`**: Ядро `GoogleContactsClient` (работа с `people.connections.list`, `searchContacts`, `createContact`, `deleteContact`).
- **`list_contacts.py`**: CLI поиск и выборка контактов телефонной книги.
- **`create_contact.py`**: CLI создание карточки контакта с телефонами, адресами и заметками.
- **`delete_contact.py`**: CLI удаление контакта по `resourceName`.

---

## 🔒 Безопасность

- Использует область видимости (scope) `https://www.googleapis.com/auth/contacts`.
- Токены хранятся строго в `src/secrets/google_oauth_tokens/`.
