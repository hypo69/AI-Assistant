# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Assistant AI Instruments - Default Catalog
# =============================================================================
# Description:
#   Базовый каталог предустановленных инструментов для построения цепочек
#   размышлений (Chain of Thought), анализа документов, данных, системных проверок
#   и поиска по локальной файловой системе и службам Google Workspace
#   (Drive, Mail, Contacts, Calendar, Sheets, Docs).
#
# File: default_catalog.py
# Project: ai-assistant
# Package: apps.ai_assistant.core.ai_instruments
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-03 16:35:00
# =============================================================================

from __future__ import annotations

"""Стандартный каталог инструментов для цепочек размышлений и агента."""

from typing import Any, Dict, List

DEFAULT_REASONING_INSTRUMENTS: List[Dict[str, Any]] = [
    {
        "tool_id": "inst_calc_file_hash",
        "name": "Расчет хеш-суммы файла (SHA-256)",
        "tool_type": "python",
        "command": (
            "import hashlib, json, sys\n"
            "path = r'{file_path}'\n"
            "h = hashlib.sha256()\n"
            "with open(path, 'rb') as f:\n"
            "    while chunk := f.read(65536):\n"
            "        h.update(chunk)\n"
            "print(json.dumps({'file': path, 'sha256': h.hexdigest()}))"
        ),
        "description": "Вычисляет SHA-256 хеш указанного файла для верификации целостности в цепочке рассуждений.",
        "target_entity": "file:checksum",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Абсолютный путь к файлу"}
            },
            "required": ["file_path"],
        },
        "risk_level": "safe",
        "author_agent": "cot_planner",
        "tags": ["#hash", "#file", "#checksum", "#cot"],
    },
    {
        "tool_id": "inst_analyze_json_schema",
        "name": "Анализ структуры и типов JSON",
        "tool_type": "python",
        "command": (
            "import json, sys\n"
            "raw = '''{json_data}'''\n"
            "data = json.loads(raw)\n"
            "def inspect(obj):\n"
            "    if isinstance(obj, dict):\n"
            "        return {k: inspect(v) for k, v in obj.items()}\n"
            "    elif isinstance(obj, list):\n"
            "        return [inspect(obj[0])] if obj else []\n"
            "    return type(obj).__name__\n"
            "print(json.dumps({'schema': inspect(data)}, ensure_ascii=False))"
        ),
        "description": "Извлекает структуру и типы полей переданного JSON объекта для построения шагов логики.",
        "target_entity": "data:json",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "json_data": {"type": "string", "description": "Строка JSON для анализа структуры"}
            },
            "required": ["json_data"],
        },
        "risk_level": "safe",
        "author_agent": "reasoning_chain",
        "tags": ["#json", "#schema", "#analysis"],
    },
    {
        "tool_id": "inst_regex_extractor",
        "name": "Извлечение сущностей по регулярному выражению",
        "tool_type": "python",
        "command": (
            "import re, json\n"
            "pattern = r'{regex_pattern}'\n"
            "text = '''{target_text}'''\n"
            "matches = re.findall(pattern, text)\n"
            "print(json.dumps({'pattern': pattern, 'count': len(matches), 'matches': matches[:50]}, ensure_ascii=False))"
        ),
        "description": "Поиск и извлечение подстрок по регулярному выражению в тексте документа или лога.",
        "target_entity": "text:regex",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "regex_pattern": {"type": "string", "description": "Регулярное выражение Python"},
                "target_text": {"type": "string", "description": "Анализируемый текст"}
            },
            "required": ["regex_pattern", "target_text"],
        },
        "risk_level": "safe",
        "author_agent": "reasoning_chain",
        "tags": ["#regex", "#extractor", "#text"],
    },
    {
        "tool_id": "inst_sqlite_query_safe",
        "name": "Безопасный запрос к SQLite базе знаний",
        "tool_type": "python",
        "command": (
            "import sqlite3, json\n"
            "db_path = r'{db_path}'\n"
            "query = '''{sql_query}'''\n"
            "if not query.strip().lower().startswith(('select', 'pragma')):\n"
            "    raise ValueError('Разрешены только SELECT и PRAGMA запросы')\n"
            "conn = sqlite3.connect(db_path)\n"
            "conn.row_factory = sqlite3.Row\n"
            "rows = [dict(r) for r in conn.execute(query).fetchall()[:100]]\n"
            "conn.close()\n"
            "print(json.dumps({'count': len(rows), 'rows': rows}, ensure_ascii=False, default=str))"
        ),
        "description": "Выполняет чтение данных (SELECT/PRAGMA) из SQLite базы данных и возвращает строки в формате JSON.",
        "target_entity": "database:sqlite",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "db_path": {"type": "string", "description": "Путь к файлу SQLite базы"},
                "sql_query": {"type": "string", "description": "SQL запрос SELECT"}
            },
            "required": ["db_path", "sql_query"],
        },
        "risk_level": "safe",
        "author_agent": "cot_planner",
        "tags": ["#sqlite", "#sql", "#knowledge"],
    },
    {
        "tool_id": "inst_check_network_socket",
        "name": "Проверка сетевого сокета и порта",
        "tool_type": "python",
        "command": (
            "import socket, json, time\n"
            "host = '{host}'\n"
            "port = int('{port}')\n"
            "t0 = time.time()\n"
            "try:\n"
            "    with socket.create_connection((host, port), timeout=5):\n"
            "        lat = round((time.time() - t0) * 1000, 2)\n"
            "        print(json.dumps({'host': host, 'port': port, 'open': True, 'latency_ms': lat}))\n"
            "except Exception as e:\n"
            "    print(json.dumps({'host': host, 'port': port, 'open': False, 'error': str(e)}))"
        ),
        "description": "Проверяет доступность удаленного порта TCP (MariaDB, SSH, FTP, SMTP, IMAP) с замером задержки.",
        "target_entity": "network:port",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "Хост или IP-адрес"},
                "port": {"type": "integer", "description": "Номер TCP порта"}
            },
            "required": ["host", "port"],
        },
        "risk_level": "safe",
        "author_agent": "reasoning_chain",
        "tags": ["#network", "#socket", "#ping"],
    },
    {
        "tool_id": "inst_git_status_inspector",
        "name": "Инспекция изменений Git рабочего пространства",
        "tool_type": "powershell",
        "command": "git -C '{workspace_path}' status --short --branch",
        "description": "Быстрая проверка состояния Git-репозитория и незафиксированных изменений в рабочей области.",
        "target_entity": "workspace:git",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "workspace_path": {"type": "string", "description": "Путь к каталогу рабочего пространства"}
            },
            "required": ["workspace_path"],
        },
        "risk_level": "safe",
        "author_agent": "reasoning_chain",
        "tags": ["#git", "#workspace", "#status"],
    },
    {
        "tool_id": "inst_search_files_and_dirs",
        "name": "Поиск файлов и каталогов",
        "tool_type": "python",
        "command": (
            "import os, sys, json, fnmatch\n"
            "from pathlib import Path\n"
            "root = Path(r'{root_path}').resolve()\n"
            "pattern = '{pattern}'.strip() or '*'\n"
            "entry_type = '{entry_type}'.strip().lower() or 'all'\n"
            "max_res = int('{max_results}') if '{max_results}'.isdigit() else 50\n"
            "case_sensitive = '{case_sensitive}'.strip().lower() in ('true', '1', 'yes')\n"
            "results = []\n"
            "if not root.exists():\n"
            "    print(json.dumps({'error': f'Каталог {root} не найден', 'results': []}, ensure_ascii=False))\n"
            "    sys.exit(0)\n"
            "for dirpath, dirnames, filenames in os.walk(str(root)):\n"
            "    dirnames[:] = [d for d in dirnames if not d.startswith('.') and not d.startswith('~') and d != '__pycache__']\n"
            "    entries = []\n"
            "    if entry_type in ('all', 'dir'):\n"
            "        for d in dirnames:\n"
            "            entries.append((d, True, os.path.join(dirpath, d)))\n"
            "    if entry_type in ('all', 'file'):\n"
            "        for f in filenames:\n"
            "            if not f.startswith('~'):\n"
            "                entries.append((f, False, os.path.join(dirpath, f)))\n"
            "    for name, is_dir, full_path in entries:\n"
            "        match = fnmatch.fncase(name, pattern) if case_sensitive else fnmatch.fnmatch(name.lower(), pattern.lower())\n"
            "        if match:\n"
            "            size = 0 if is_dir else (os.path.getsize(full_path) if os.path.exists(full_path) else 0)\n"
            "            results.append({'name': name, 'path': full_path.replace('\\\\', '/'), 'type': 'directory' if is_dir else 'file', 'size': size})\n"
            "            if len(results) >= max_res:\n"
            "                break\n"
            "    if len(results) >= max_res:\n"
            "        break\n"
            "print(json.dumps({'root': str(root).replace('\\\\', '/'), 'pattern': pattern, 'count': len(results), 'results': results}, ensure_ascii=False))"
        ),
        "description": "Локальный поиск файлов и каталогов по маске, имени, типу и глубине в файловой системе.",
        "target_entity": "filesystem:search",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "root_path": {"type": "string", "description": "Корневой каталог для поиска (например '.' или 'C:/data')", "default": "."},
                "pattern": {"type": "string", "description": "Шаблон или маска поиска (например '*.py', 'report*', '*')", "default": "*"},
                "entry_type": {"type": "string", "description": "Тип объекта для фильтрации ('all', 'file', 'dir')", "default": "all"},
                "max_results": {"type": "integer", "description": "Максимальное количество возвращаемых записей", "default": 50},
                "case_sensitive": {"type": "boolean", "description": "Учитывать ли регистр символов", "default": False},
            },
            "required": ["root_path"],
        },
        "risk_level": "safe",
        "author_agent": "cot_planner",
        "tags": ["#search", "#filesystem", "#files", "#directories", "#find"],
    },
    {
        "tool_id": "inst_google_drive_search",
        "name": "Поиск файлов на Google Диске",
        "tool_type": "python",
        "command": (
            "import json, sys\n"
            "from apps.ai_assistant.core.skills_bridge import get_drive_client\n"
            "query = '{query}'.strip()\n"
            "folder_id = '{folder_id}'.strip() or None\n"
            "mime_type = '{mime_type}'.strip() or None\n"
            "max_res = int('{max_results}') if '{max_results}'.isdigit() else 20\n"
            "account = '{account_name}'.strip() or None\n"
            "q_filter = None\n"
            "if query:\n"
            "    if any(op in query for op in (' contains ', '=', '!=', ' in ', '<', '>')):\n"
            "        q_filter = query\n"
            "    else:\n"
            "        q_filter = f\"name contains '{query}'\"\n"
            "try:\n"
            "    client = get_drive_client(account_name=account)\n"
            "    files = client.list_files(query=q_filter, folder_id=folder_id, mime_type=mime_type, max_results=max_res)\n"
            "    print(json.dumps({'count': len(files), 'files': files}, ensure_ascii=False))\n"
            "except Exception as e:\n"
            "    print(json.dumps({'error': str(e), 'files': []}, ensure_ascii=False))"
        ),
        "description": "Поиск файлов и папок в облачном хранилище Google Drive по текстовому запросу, MIME-типу или ID папки.",
        "target_entity": "google:drive",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Поисковый запрос (например: name contains 'отчет' или фрагмент названия)", "default": ""},
                "folder_id": {"type": "string", "description": "ID родительской папки для поиска внутри неё", "default": ""},
                "mime_type": {"type": "string", "description": "MIME-тип для фильтрации (например: application/pdf)", "default": ""},
                "max_results": {"type": "integer", "description": "Максимальное количество файлов (по умолчанию 20)", "default": 20},
                "account_name": {"type": "string", "description": "Имя аккаунта Google (опционально)", "default": ""},
            },
        },
        "risk_level": "safe",
        "author_agent": "secretary_agent",
        "tags": ["#google", "#drive", "#search", "#cloud", "#files"],
    },
    {
        "tool_id": "inst_google_mail_search",
        "name": "Поиск писем в Google Mail (Gmail)",
        "tool_type": "python",
        "command": (
            "import json, sys\n"
            "from apps.ai_assistant.core.skills_bridge import get_mail_client\n"
            "query = '{query}'.strip()\n"
            "max_res = int('{max_results}') if '{max_results}'.isdigit() else 10\n"
            "account = '{account_name}'.strip() or None\n"
            "try:\n"
            "    client = get_mail_client(account_name=account)\n"
            "    messages = client.list_messages(query=query, max_results=max_res)\n"
            "    print(json.dumps({'count': len(messages), 'messages': messages}, ensure_ascii=False))\n"
            "except Exception as e:\n"
            "    print(json.dumps({'error': str(e), 'messages': []}, ensure_ascii=False))"
        ),
        "description": "Поиск входящих и отправленных писем в почтовом ящике Gmail по поисковой строке (from, subject, label, ключевые слова).",
        "target_entity": "google:mail",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Строка поиска Gmail (например 'is:unread', 'from:partner', 'договор')", "default": ""},
                "max_results": {"type": "integer", "description": "Максимальное количество возвращаемых писем", "default": 10},
                "account_name": {"type": "string", "description": "Имя аккаунта Google (опционально)", "default": ""},
            },
        },
        "risk_level": "safe",
        "author_agent": "secretary_agent",
        "tags": ["#google", "#gmail", "#mail", "#search", "#email"],
    },
    {
        "tool_id": "inst_google_contacts_search",
        "name": "Поиск в Google Контактах",
        "tool_type": "python",
        "command": (
            "import json, sys\n"
            "from apps.ai_assistant.core.skills_bridge import get_contacts_client\n"
            "query = '{query}'.strip() or None\n"
            "max_res = int('{max_results}') if '{max_results}'.isdigit() else 20\n"
            "account = '{account_name}'.strip() or None\n"
            "try:\n"
            "    client = get_contacts_client(account_name=account)\n"
            "    contacts = client.list_contacts(query=query, max_results=max_res)\n"
            "    print(json.dumps({'count': len(contacts), 'contacts': contacts}, ensure_ascii=False))\n"
            "except Exception as e:\n"
            "    print(json.dumps({'error': str(e), 'contacts': []}, ensure_ascii=False))"
        ),
        "description": "Поиск абонентов в адресной книге Google Contacts (People API) по имени, фамилии, компании, телефону или email.",
        "target_entity": "google:contacts",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Поисковая строка: имя, номер телефона, организация или email", "default": ""},
                "max_results": {"type": "integer", "description": "Максимальное количество контактов", "default": 20},
                "account_name": {"type": "string", "description": "Имя аккаунта Google (опционально)", "default": ""},
            },
        },
        "risk_level": "safe",
        "author_agent": "secretary_agent",
        "tags": ["#google", "#contacts", "#search", "#people", "#phone"],
    },
    {
        "tool_id": "inst_google_calendar_search",
        "name": "Поиск событий в Google Календаре",
        "tool_type": "python",
        "command": (
            "import json, sys\n"
            "from apps.ai_assistant.core.skills_bridge import get_calendar_client\n"
            "query = '{query}'.strip() or None\n"
            "calendar_id = '{calendar_id}'.strip() or 'primary'\n"
            "time_min = '{time_min}'.strip() or None\n"
            "time_max = '{time_max}'.strip() or None\n"
            "max_res = int('{max_results}') if '{max_results}'.isdigit() else 20\n"
            "account = '{account_name}'.strip() or None\n"
            "try:\n"
            "    client = get_calendar_client(account_name=account)\n"
            "    events = client.list_events(calendar_id=calendar_id, query=query, time_min=time_min, time_max=time_max, max_results=max_res)\n"
            "    print(json.dumps({'count': len(events), 'events': events}, ensure_ascii=False))\n"
            "except Exception as e:\n"
            "    print(json.dumps({'error': str(e), 'events': []}, ensure_ascii=False))"
        ),
        "description": "Поиск встреч, совещаний и событий в Google Calendar по теме, описанию или интервалу дат.",
        "target_entity": "google:calendar",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Поисковый запрос по заголовку или описанию события", "default": ""},
                "calendar_id": {"type": "string", "description": "ID календаря (по умолчанию 'primary')", "default": "primary"},
                "time_min": {"type": "string", "description": "Начальная дата/время поиска в формате ISO 8601", "default": ""},
                "time_max": {"type": "string", "description": "Конечная дата/время поиска в формате ISO 8601", "default": ""},
                "max_results": {"type": "integer", "description": "Максимальное количество событий", "default": 20},
                "account_name": {"type": "string", "description": "Имя аккаунта Google (опционально)", "default": ""},
            },
        },
        "risk_level": "safe",
        "author_agent": "secretary_agent",
        "tags": ["#google", "#calendar", "#search", "#events", "#schedule"],
    },
    {
        "tool_id": "inst_google_sheets_search",
        "name": "Поиск таблиц Google Sheets",
        "tool_type": "python",
        "command": (
            "import json, sys\n"
            "from apps.ai_assistant.core.skills_bridge import get_drive_client\n"
            "query = '{query}'.strip()\n"
            "max_res = int('{max_results}') if '{max_results}'.isdigit() else 20\n"
            "account = '{account_name}'.strip() or None\n"
            "q_filter = None\n"
            "if query:\n"
            "    if any(op in query for op in (' contains ', '=', '!=', ' in ', '<', '>')):\n"
            "        q_filter = query\n"
            "    else:\n"
            "        q_filter = f\"name contains '{query}'\"\n"
            "try:\n"
            "    client = get_drive_client(account_name=account)\n"
            "    files = client.list_files(query=q_filter, mime_type='application/vnd.google-apps.spreadsheet', max_results=max_res)\n"
            "    sheets = [{'id': f.get('id'), 'name': f.get('name'), 'modifiedTime': f.get('modifiedTime'), 'webViewLink': f.get('webViewLink')} for f in files]\n"
            "    print(json.dumps({'count': len(sheets), 'sheets': sheets}, ensure_ascii=False))\n"
            "except Exception as e:\n"
            "    print(json.dumps({'error': str(e), 'sheets': []}, ensure_ascii=False))"
        ),
        "description": "Поиск электронных таблиц Google Sheets в Google Drive по названию и ключевым словам.",
        "target_entity": "google:sheets",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Поисковый запрос по названию таблицы", "default": ""},
                "max_results": {"type": "integer", "description": "Максимальное количество таблиц", "default": 20},
                "account_name": {"type": "string", "description": "Имя аккаунта Google (опционально)", "default": ""},
            },
        },
        "risk_level": "safe",
        "author_agent": "secretary_agent",
        "tags": ["#google", "#sheets", "#spreadsheets", "#search", "#tables"],
    },
    {
        "tool_id": "inst_google_docs_search",
        "name": "Поиск документов Google Docs",
        "tool_type": "python",
        "command": (
            "import json, sys\n"
            "from apps.ai_assistant.core.skills_bridge import get_drive_client\n"
            "query = '{query}'.strip()\n"
            "max_res = int('{max_results}') if '{max_results}'.isdigit() else 20\n"
            "account = '{account_name}'.strip() or None\n"
            "q_filter = None\n"
            "if query:\n"
            "    if any(op in query for op in (' contains ', '=', '!=', ' in ', '<', '>')):\n"
            "        q_filter = query\n"
            "    else:\n"
            "        q_filter = f\"name contains '{query}'\"\n"
            "try:\n"
            "    client = get_drive_client(account_name=account)\n"
            "    files = client.list_files(query=q_filter, mime_type='application/vnd.google-apps.document', max_results=max_res)\n"
            "    docs = [{'id': f.get('id'), 'name': f.get('name'), 'modifiedTime': f.get('modifiedTime'), 'webViewLink': f.get('webViewLink')} for f in files]\n"
            "    print(json.dumps({'count': len(docs), 'documents': docs}, ensure_ascii=False))\n"
            "except Exception as e:\n"
            "    print(json.dumps({'error': str(e), 'documents': []}, ensure_ascii=False))"
        ),
        "description": "Поиск текстовых документов Google Docs в Google Drive по названию и контексту.",
        "target_entity": "google:docs",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Поисковый запрос по названию документа", "default": ""},
                "max_results": {"type": "integer", "description": "Максимальное количество документов", "default": 20},
                "account_name": {"type": "string", "description": "Имя аккаунта Google (опционально)", "default": ""},
            },
        },
        "risk_level": "safe",
        "author_agent": "secretary_agent",
        "tags": ["#google", "#docs", "#documents", "#search", "#text"],
    },
]
