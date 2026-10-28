---
name: google-drive
description: Google Drive skill for searching, uploading, downloading, organizing files and folders, and managing sharing permissions via Google Drive API.
description_i18n:
  en: Google Drive skill for searching, uploading, downloading, organizing files and folders, and managing sharing permissions via Google Drive API.
  ru: Навык работы с Google Диском для поиска, загрузки, скачивания, организации файлов и папок, а также управления доступом через Google Drive API.
---

# 📁 Навык: Google Drive (Drive API v3)

## 📌 Назначение и концепция

Навык `google-drive` обеспечивает полнофункциональную работу агентов ИИ с файловым хранилищем Google Диска:
- Поиск файлов по названиям, типам (MIME), содержимому и родительским папкам.
- Загрузка локальных документов, отчетов, таблиц и архивов на Google Drive.
- Скачивание файлов с облака на локальный компьютер с автоматической конвертацией Google Docs/Sheets в форматы Office/PDF при необходимости.
- Получение ссылок для совместного доступа (`webViewLink`).

Интеграция опирается на авторизованный Google OAuth токен (`src/ai/google_accounts_state.py`).

---

## 🎯 Триггеры активации

Активируйте данный навык, если задача требует:
1. Найти файл или документ на Google Диске («Найди таблицу расходов на диске», «Покажи последние загруженные файлы»).
2. Загрузить локальный файл, созданный агентом или пользователем, в облако («Выгрузи сгенерированный PDF отчет на Google Drive»).
3. Скачать документ из облака для локальной обработки или анализа.
4. Проверить структуру папок и ссылки на документы.

---

## 🚀 Протокол выполнения

### 1. Поиск и просмотр файлов
```bash
# Получить последние 10 файлов:
python .agents/skills/google-drive/scripts/list_files.py -n 10 --json

# Поиск файлов, содержащих в названии 'audit':
python .agents/skills/google-drive/scripts/list_files.py -q "name contains 'audit'" --json

# Выборка файлов внутри конкретной папки:
python .agents/skills/google-drive/scripts/list_files.py -f "<FOLDER_ID>" --json
```

### 2. Загрузка файла в облако
```bash
# Выгрузить локальный файл в корень Диска:
python .agents/skills/google-drive/scripts/upload_file.py -f "reports/summary.pdf" --json

# Выгрузить в определенную папку с переименованием:
python .agents/skills/google-drive/scripts/upload_file.py \
  -f "data/export.xlsx" \
  --name "Quarterly_Export_2026.xlsx" \
  --folder-id "<FOLDER_ID>" \
  --json
```

### 3. Скачивание файла
```bash
python .agents/skills/google-drive/scripts/download_file.py \
  -i "<FILE_ID>" \
  -o "downloads/imported_document.pdf" \
  --json
```

---

## 🛠️ Состав скриптов (`scripts/`)

- **`drive_client.py`**: Ядро `GoogleDriveClient` (работа с `build('drive', 'v3')`, чанковая загрузка и скачивание).
- **`list_files.py`**: CLI поиск файлов по фильтрам, MIME-типам и папкам.
- **`upload_file.py`**: CLI загрузка локальных файлов на Drive.
- **`download_file.py`**: CLI скачивание и экспорт файлов на локальный диск.

---

## 🔒 Безопасность

- Использует область видимости (scope) `https://www.googleapis.com/auth/drive`.
- Учетные данные хранятся изолированно в `src/secrets/`.
