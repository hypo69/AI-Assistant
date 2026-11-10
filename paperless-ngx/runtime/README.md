# Paperless-ngx runtime

Рабочее окружение Paperless-ngx для AI-Assistant: один инстанс (PostgreSQL + Tika/Gotenberg), Docker Desktop + WSL2.
Исходники клона (`../src`, `../src-ui`) не смешиваются с пользовательскими данными: данные — в Docker volumes, `consume/` и `export/` — рядом.

## Запуск

```powershell
py manage_tools.py paperless up            # образ ghcr.io/paperless-ngx/paperless-ngx:latest
py manage_tools.py paperless up --build    # сборка из локального клона
py manage_tools.py paperless token --username admin --password ***   # токен -> .env (PAPERLESS_API_TOKEN)
py manage_tools.py paperless status
py manage_tools.py paperless sync --workspace default
```

Веб-интерфейс: <http://127.0.0.1:8000> (при первом входе создаётся администратор).

## Конфигурация

| Файл | Назначение |
|---|---|
| `docker-compose.yml` | broker, PostgreSQL, Tika, Gotenberg, webserver; порт только на 127.0.0.1 |
| `docker-compose.build.yml` | сборка образа из локальных исходников |
| `docker-compose.env` | настройки и `PAPERLESS_SECRET_KEY` (не коммитится; шаблон — `.example`) |

Адрес API, таймауты и префикс тега рабочей области — в корневом `config.json` → `paperless`; токен — в `.env`.

## Модель данных

- Рабочая область = тег `ws-<workspace_id>` в Paperless.
- Текст документа хранится только в Paperless; в `.workspace/knowledge_store.db` — факты, связи графа и `paperless_id`.
- Граф (`temporal_evidence_links`) и хранилище знаний лежат в одном файле БД на область.

> Если на машине уже запущен стек paperless-local-source (порт 8000), AI-Assistant подключается к нему по API; этот compose нужен для чистой установки.

