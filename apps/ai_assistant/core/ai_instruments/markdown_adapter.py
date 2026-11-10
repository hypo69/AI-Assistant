# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Assistant AI Instruments - Markdown Storage Adapter
# =============================================================================
# Description:
#   Адаптер сериализации и парсинга базы инструментов цепочек размышлений
#   в формате локального Markdown документа (toolchain_tools.md).
#   Обеспечивает атомарную запись, чтение, обновление счётчиков запусков
#   и редактируемость через Obsidian Vault и текстовые редакторы.
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.core.ai_instruments.markdown_adapter import (
#         load_markdown_tools, save_markdown_tools
#     )
#
#     tools = load_markdown_tools("data/apps/ai_assistent/toolchain_tools.md")
#
# File: markdown_adapter.py
# Project: ai-assistant
# Package: apps.ai_assistant.core.ai_instruments
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 13:55:00
# =============================================================================

from __future__ import annotations

"""Модуль сериализации и парсинга каталога инструментов в Markdown файл."""

import json
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from logger import logger
from .models import AIInstrument, get_current_iso_time


DEFAULT_MD_HEADER = """<!--
=============================================================================
Process Name: Toolchain Tools Catalog (Markdown Database)
=============================================================================
Description:
  Локальная база данных инструментов для построения цепочек размышлений
  (Chain of Thought). Редактируемый каталог утилит, Python-скриптов и команд.
Updated: {updated_time}
=============================================================================
-->

# 🛠️ База инструментов цепочек размышлений (`toolchain_tools.md`)

Каталог исполняемых инструментов, используемых агентом для решения многошаговых задач,
анализа данных, документов, Git-репозиториев и системных проверок.

---
"""


def serialize_instruments_to_markdown(
    instruments: List[AIInstrument],
    updated_time: Optional[str] = "",
) -> str:
    """Сериализует список инструментов в читаемый Markdown формат.

    Args:
        instruments: Список объектов AIInstrument.
        updated_time: Строка времени обновления в UTC ISO 8601 (по умолчанию текущее время UTC).

    Returns:
        Строка с разметкой Markdown.
    """
    now_str = updated_time or get_current_iso_time()
    out = [DEFAULT_MD_HEADER.format(updated_time=now_str)]

    for inst in instruments:
        tags_str = ", ".join(inst.tags) if inst.tags else "#agent_tool"
        params_json = json.dumps(inst.parameters_schema, ensure_ascii=False, indent=2)

        code_fence = inst.tool_type.lower()
        if code_fence in ("powershell", "pwsh"):
            fence_lang = "powershell"
        elif code_fence in ("cmd", "bat"):
            fence_lang = "cmd"
        elif code_fence == "sql":
            fence_lang = "sql"
        else:
            fence_lang = "python"

        item_md = f"""## `{inst.tool_id}` — {inst.name}

- **ID:** `{inst.tool_id}`
- **Название:** {inst.name}
- **Тип:** `{inst.tool_type}`
- **Сущность:** `{inst.target_entity}`
- **Уровень риска:** `{inst.risk_level}`
- **Автор:** `{inst.author_agent}`
- **Теги:** {tags_str}
- **Вызовов:** `{inst.execution_count}`
- **Последний запуск:** `{inst.last_executed_at or 'Никогда'}`
- **Создан:** `{inst.created_at}`
- **Обновлен:** `{inst.updated_at}`
- **Описание:** {inst.description or 'Нет описания'}

### Схема параметров
```json
{params_json}
```

### Команда / Скрипт
```{fence_lang}
{inst.command}
```

---
"""
        out.append(item_md)

    return "\n".join(out)


def parse_instruments_from_markdown(content: str) -> List[AIInstrument]:
    """Парсит Markdown контент файла toolchain_tools.md в список инструментов.

    Args:
        content: Текст Markdown файла.

    Returns:
        Список распарсенных объектов AIInstrument.
    """
    instruments: List[AIInstrument] = []
    sections = re.split(r"\n(?=##\s+`[^`]+`)", content)

    for sec in sections:
        sec = sec.strip()
        if not sec.startswith("## "):
            continue

        header_match = re.search(r"##\s+`([^`]+)`(?:\s*—\s*(.+))?", sec)
        if not header_match:
            continue

        tool_id = header_match.group(1).strip()
        name_from_header = (header_match.group(2) or tool_id).strip()

        def extract_field(field_name: str, default: str = "") -> str:
            m = re.search(rf"-\s+\*\*{field_name}:\*\*\s*(?:`([^`]+)`|([^\n]+))", sec, re.IGNORECASE)
            if m:
                return (m.group(1) or m.group(2) or "").strip()
            return default

        name = extract_field("Название", name_from_header)
        tool_type = extract_field("Тип", "python").lower()
        target_entity = extract_field("Сущность", "system")
        risk_level = extract_field("Уровень риска", "safe")
        author_agent = extract_field("Автор", "reasoning_chain")
        tags_raw = extract_field("Теги", "#agent_tool")
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()]

        try:
            execution_count = int(extract_field("Вызовов", "0"))
        except ValueError:
            execution_count = 0

        last_executed_at = extract_field("Последний запуск", "")
        if last_executed_at in ("Никогда", "None", ""):
            last_executed_at = ""

        created_at = extract_field("Создан", get_current_iso_time())
        updated_at = extract_field("Обновлен", get_current_iso_time())
        description = extract_field("Описание", "")

        params_schema: Dict[str, Any] = {}
        schema_match = re.search(r"###\s+Схема параметров\s*```(?:json)?\s*([\s\S]*?)```", sec, re.IGNORECASE)
        if schema_match:
            try:
                params_schema = json.loads(schema_match.group(1).strip())
            except Exception as exc:
                logger.warning(f"[markdown_adapter] Ошибка разбора JSON-схемы параметров {tool_id}: {exc}")
                params_schema = {}

        command = ""
        cmd_match = re.search(r"###\s+Команда\s*/\s*Скрипт\s*```(?:[a-zA-Z0-9_-]+)?\s*([\s\S]*?)```", sec, re.IGNORECASE)
        if cmd_match:
            command = cmd_match.group(1).strip()
        else:
            code_blocks = re.findall(r"```(?:[a-zA-Z0-9_-]+)?\s*([\s\S]*?)```", sec)
            if len(code_blocks) >= 2:
                command = code_blocks[1].strip()
            elif len(code_blocks) == 1:
                command = code_blocks[0].strip()

        if not command:
            continue

        inst = AIInstrument(
            tool_id=tool_id,
            name=name or tool_id,
            tool_type=tool_type,
            command=command,
            description=description,
            target_entity=target_entity,
            parameters_schema=params_schema,
            risk_level=risk_level,
            author_agent=author_agent,
            tags=tags,
            execution_count=execution_count,
            last_executed_at=last_executed_at,
            created_at=created_at,
            updated_at=updated_at,
        )
        instruments.append(inst)

    return instruments


def load_markdown_tools(file_path: Path | str) -> List[AIInstrument]:
    """Загружает каталог инструментов из Markdown файла.

    Args:
        file_path: Путь к файлу toolchain_tools.md.

    Returns:
        Список распарсенных инструментов.
    """
    path = Path(file_path)
    if not path.is_file():
        return []
    try:
        content = path.read_text(encoding="utf-8")
        return parse_instruments_from_markdown(content)
    except Exception as exc:
        logger.error(f"[markdown_adapter] Ошибка чтения {path}: {exc}")
        return []


def save_markdown_tools(instruments: List[AIInstrument], file_path: Path | str) -> bool:
    """Атомарно сохраняет каталог инструментов в Markdown файл через временный файл.

    Args:
        instruments: Список инструментов.
        file_path: Целевой путь для записи toolchain_tools.md.
    """
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    md_text = serialize_instruments_to_markdown(instruments)
    tmp_path = path.with_suffix(f"{path.suffix}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        tmp_path.write_text(md_text, encoding="utf-8")
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
    logger.info(f"[markdown_adapter] Сохранено {len(instruments)} инструментов в {path}")
    return True
