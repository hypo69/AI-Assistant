# 🎯 Инструкции и стандарты разработки (`.ai/instructions`)

**Статус:** ✅ Активно  
**Версия:** 3.6.0  
**Автор:** hypo69  
**Updated:** 2026-10-26 00:35:00  

---

## 📚 Быстрая навигация по существующим стандартам

| Задача | Документ |
|---|---|
| **Главный индекс правил проекта** | [`../../GEMINI.md`](../../GEMINI.md) |
| **Инженерные стандарты и архитектура кода** | [`standards/ENGINEERING.md`](standards/ENGINEERING.md) |
| **Документирование кода (`hypo69 docblock` на русском) и README** | [`standards/DOCUMENTATION.md`](standards/DOCUMENTATION.md) |
| **Повторное использование кода и аудит перед разработкой** | [`standards/REUSE.md`](standards/REUSE.md) |
| **Шапки файлов и фиксация `Updated: YYYY-MM-DD HH:MM:SS`** | [`standards/FILE_HEADERS.md`](standards/FILE_HEADERS.md) |
| **Разработка вкладок и компонентов WebGUI** | [`standards/WEBGUI.md`](standards/WEBGUI.md) |
| **Маршрутизация рабочих областей в URL (`#tab-workspace...`)** | [`standards/WORKSPACE_ROUTING.md`](standards/WORKSPACE_ROUTING.md) |
| **Разработка через тестирование (TDD)** | [`workflows/TDD.md`](workflows/TDD.md) |
| **Тестирование приложений и проверка покрытия** | [`workflows/TESTING.md`](workflows/TESTING.md) |
| **Использование универсального CLI `manage_tools.py`** | [`guides/CLI_TOOLS.md`](guides/CLI_TOOLS.md) |
| **Автоматический запуск сервисных скриптов** | [`guides/MODEL_SCRIPTS.md`](guides/MODEL_SCRIPTS.md) |
| **Ролевые профили ИИ-ассистента** | [`roles/ADMINISTRATOR.md`](roles/ADMINISTRATOR.md), [`roles/TECHNICIAN.md`](roles/TECHNICIAN.md), [`roles/SECRETARY.md`](roles/SECRETARY.md) |

---

## 📖 Структура каталога `.ai/instructions`

```text
.ai/instructions/
├── README.md                         # Навигатор по стандартам и рабочим процессам
├── standards/                        # Обязательные инженерные стандарты
│   ├── DOCUMENTATION.md              # Стандарт русскоязычной документации и docstrings
│   ├── ENGINEERING.md                # Архитектура, Python 3.12+, лимит 500 строк, логирование
│   ├── FILE_HEADERS.md               # Стандарт шапок файлов и метки Updated
│   ├── REUSE.md                      # Правила переиспользования и запрет дубликатов
│   ├── WEBGUI.md                     # Стандарт вкладок tab_*, тем и CSS-переменных
│   └── WORKSPACE_ROUTING.md          # Стандарт URL-маршрутизации рабочих областей
├── workflows/                        # Рабочие процессы разработки и проверки
│   ├── TDD.md                        # Протокол Test-Driven Development
│   └── TESTING.md                    # Регламент модульного и интеграционного тестирования
├── guides/                           # Практические руководства по утилитам
│   ├── CLI_TOOLS.md                  # Справочник команд manage_tools.py
│   └── MODEL_SCRIPTS.md              # Правила вызова скриптов моделями
└── roles/                            # Ролевые инструкции
    ├── ADMINISTRATOR.md              # Роль системного администратора
    ├── SECRETARY.md                  # Роль персонального секретаря
    └── TECHNICIAN.md                 # Роль технического специалиста
```

---

## ✅ Ключевые инварианты проекта

1. **Русский языковой стандарт:** все docstrings, комментарии, README, тестовые описания и сообщения коммитов пишутся строго на **русском языке**.
2. **Обновление метки времени:** при любом изменении файла в его шапке обновляется строка `Updated: YYYY-MM-DD HH:MM:SS`.
3. **Логирование:** вывод в консоль без записи в файл выполняется через `logger.console()`, стандартное логирование — через `logger`.
4. **Отсутствие хардкода в UI:** все цвета и стили задаются исключительно через CSS-переменные (`var(--...)`) и систему тем.
