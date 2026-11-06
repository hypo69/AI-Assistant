<!--
=============================================================================
Process Name: AI Instruments Module Documentation
=============================================================================
Description:
  Документация модуля базы инструментов для построения цепочек размышлений
  (Chain of Thought). Описывает архитектуру гибридного хранения (Hostinger
  MariaDB / SQLite), жизненный цикл инструментов и интеграцию с планировщиком.

File: README.md
Project: ai-assistant
Package: apps.ai_assistant.core.ai_instruments
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-11-03 16:25:00
=============================================================================
-->

# 🛠️ База инструментов для построения цепочек размышлений (`ai_instruments`)

Модуль `apps.ai_assistant.core.ai_instruments` предоставляет полнофункциональную систему хранения, каталогизации, динамического извлечения и выполнения инструментов, используемых искусственным интеллектом при построении пошаговых планов и цепочек рассуждений (Chain of Thought / ReAct).

---

## 🎯 Назначение и архитектура

В процессе рассуждения модель часто синтезирует специализированные скрипты, одноразовые утилиты и формулирует команды для извлечения информации. База данных `ai_instruments` позволяет:
1. **Персистировать накопленный арсенал**: инструменты сохраняются в базе данных и повторно используются в последующих сессиях без повторного синтеза.
2. **Гибридное хранение с автоматическим Fallback**:
   - **Удаленное хранилище (Hostinger)**: реляционная база MariaDB (`srv1502.hstgr.io:3306`, таблица `ai_instruments`) или REST API PHP шлюз (`wikillm_hostinger.php`).
   - **Локальное хранилище (SQLite)**: файл `data/ai_instruments/ai_instruments.db`. При отсутствии связи с хостингом или строгом файрволе система прозрачно использует локальную базу, не прерывая рассуждения.
3. **Безопасное выполнение и аудит**: инструменты исполняются с замером времени, перехватом ошибок, валидацией схемы параметров и инкрементом счётчика вызовов.

---

## 🏗️ Структура пакета

```
apps/ai_assistant/core/ai_instruments/
├── __init__.py           # Экспорт ключевых классов и фабрик
├── models.py             # Pydantic-модели AIInstrument, схемы запросов и ответов
├── storage.py            # Менеджер хранения SQLite и Hostinger MariaDB
├── service.py            # Оркестратор жизненного цикла, извлечения и запуска
├── default_catalog.py    # Базовые инструменты (хеширование, regex, JSON, SQL, ping)
├── database_tool.py      # Адаптер для планировщика цепочек размышлений
└── README.md             # Настоящая документация
```

---

## 🚀 Быстрый старт

### 1. Извлечение инструментов из текста цепочки рассуждений
```python
from apps.ai_assistant.core.ai_instruments import AIInstrumentsService

service = AIInstrumentsService()
reasoning_output = """
Для анализа структуры файла используем следующий скрипт:
```python
import json
print(json.dumps({'status': 'ok'}))
```
"""
saved_tools = service.extract_and_save_from_text(reasoning_output, target_entity="data:analysis")
print(f"Сохранено инструментов: {len(saved_tools)}")
```

### 2. Загрузка инструментов в цепочку размышлений
```python
from apps.ai_assistant.core.ai_instruments import load_reasoning_tools

tools = load_reasoning_tools()
for tool in tools:
    print(f"Доступный инструмент: {tool.name} - {tool.title}")
```
