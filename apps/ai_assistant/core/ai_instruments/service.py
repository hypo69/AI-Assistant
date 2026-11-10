# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Assistant AI Instruments - Service Orchestrator
# =============================================================================
# Description:
#   Координатор и сервис базы инструментов для цепочек размышлений и агента.
#   Обеспечивает сохранение, извлечение инструментов из текста рассуждений модели,
#   поиск, безопасный запуск скриптов Python/PowerShell/CMD без shell-инъекций,
#   экспорт и пакетный импорт каталога.
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.core.ai_instruments.service import AIInstrumentsService
#
#     srv = AIInstrumentsService()
#     tools = srv.extract_and_save_from_text("```python\nprint(123)\n```")
#
# File: service.py
# Project: ai-assistant
# Package: apps.ai_assistant.core.ai_instruments
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 13:57:00
# =============================================================================

from __future__ import annotations

"""Сервис управления инструментами цепочек размышлений и агента."""

import csv
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from logger import logger
from .default_catalog import DEFAULT_REASONING_INSTRUMENTS
from .models import AIInstrument, AIInstrumentCreate, get_current_iso_time
from .storage import AIInstrumentsStorage


class AIInstrumentsService:
    """Сервис жизненного цикла инструментов цепочек размышлений."""

    _CODE_BLOCK_RE = re.compile(r"```(python|py|powershell|pwsh|cmd|bat|sql)?\s*([\s\S]*?)```", re.IGNORECASE)

    def __init__(self, storage: Optional[AIInstrumentsStorage] = None) -> None:
        """Инициализация сервиса.

        Args:
            storage: Экземпляр хранилища AIInstrumentsStorage.
        """
        self.storage = storage or AIInstrumentsStorage()

    def save_instrument(self, item: AIInstrumentCreate, sync_markdown: bool = True) -> AIInstrument:
        """Сохраняет инструмент в базе данных."""
        tool_id = item.tool_id or f"inst_{uuid.uuid4().hex[:12]}"
        now = get_current_iso_time()
        inst = AIInstrument(
            tool_id=tool_id,
            name=item.name.strip(),
            tool_type=item.tool_type.strip().lower(),
            command=item.command.strip(),
            description=item.description or "",
            target_entity=item.target_entity or "system",
            parameters_schema=item.parameters_schema or {},
            risk_level=item.risk_level or "safe",
            author_agent=item.author_agent or "reasoning_chain",
            tags=item.tags or ["#agent_tool", "#reasoning"],
            created_at=now,
            updated_at=now,
        )
        saved = self.storage.save_instrument(inst, sync_markdown=sync_markdown)
        logger.info(f"[AIInstrumentsService] Инструмент '{saved.name}' ({saved.tool_id}) сохранен.")
        return saved

    def get_instrument(self, tool_id: str) -> Optional[AIInstrument]:
        """Возвращает инструмент по идентификатору."""
        return self.storage.get_instrument(tool_id)

    def list_instruments(
        self,
        limit: int = 50,
        offset: int = 0,
        tool_type: Optional[str] = "",
        target_entity: Optional[str] = "",
    ) -> List[AIInstrument]:
        """Возвращает список инструментов с фильтрацией."""
        return self.storage.list_instruments(
            limit=limit,
            offset=offset,
            tool_type=tool_type,
            target_entity=target_entity,
        )

    def search_instruments(self, query: str, limit: int = 20) -> List[AIInstrument]:
        """Ищет инструменты по запросу."""
        return self.storage.search_instruments(query, limit=limit)

    def delete_instrument(self, tool_id: str) -> bool:
        """Удаляет инструмент."""
        return self.storage.delete_instrument(tool_id)

    def seed_default_instruments(self, force: bool = False) -> List[AIInstrument]:
        """Инициализирует базовые инструменты для цепочек размышлений без N+1 перезаписей Markdown."""
        existing_ids: set[str] = set()
        if not force:
            try:
                existing = self.storage.list_instruments(limit=200)
                existing_ids = {it.tool_id for it in existing}
                if len(existing_ids) >= len(DEFAULT_REASONING_INSTRUMENTS):
                    return []
            except Exception as ex:
                logger.warning(f"[AIInstrumentsService] Ошибка проверки инструментов: {ex}")

        seeded: List[AIInstrument] = []
        for raw in DEFAULT_REASONING_INSTRUMENTS:
            if not force and raw.get("tool_id") in existing_ids:
                continue
            try:
                item = AIInstrumentCreate(**raw)
                saved = self.save_instrument(item, sync_markdown=False)
                seeded.append(saved)
            except Exception as ex:
                logger.warning(f"[AIInstrumentsService] Не удалось сохранить инструмент {raw.get('tool_id')}: {ex}")
        if seeded:
            self.storage._sync_to_markdown()
        return seeded

    def extract_and_save_from_text(
        self,
        text: str,
        target_entity: str = "reasoning",
        title_prefix: str = "Инструмент рассуждения",
        author: str = "reasoning_chain",
    ) -> List[AIInstrument]:
        """Извлекает скрипты из цепочки рассуждений (Python, PowerShell, CMD) и сохраняет их в базе."""
        if not text:
            return []

        saved_tools: List[AIInstrument] = []
        matches = self._CODE_BLOCK_RE.findall(text)

        idx = 1
        for lang, code in matches:
            clean_code = code.strip()
            if not clean_code or len(clean_code) < 10:
                continue

            lang_low = (lang or "python").lower()
            if lang_low in ("py", "python"):
                tool_type = "python"
            elif lang_low in ("cmd", "bat"):
                tool_type = "cmd"
            elif lang_low in ("powershell", "pwsh"):
                tool_type = "powershell"
            elif lang_low == "sql":
                tool_type = "sql"
            else:
                tool_type = "python"

            first_line = clean_code.splitlines()[0][:50].replace("#", "").strip()
            name = f"{title_prefix}: {first_line}" if first_line else f"{title_prefix} #{idx}"

            item = AIInstrumentCreate(
                name=name,
                tool_type=tool_type,
                command=clean_code,
                description=f"Автоматически синтезирован в цепочке рассуждений для сущности {target_entity}",
                target_entity=target_entity,
                author_agent=author,
                tags=["#reasoning_synthesized", f"#{tool_type}"],
            )
            saved = self.save_instrument(item, sync_markdown=False)
            saved_tools.append(saved)
            idx += 1

        if saved_tools:
            self.storage._sync_to_markdown()
        return saved_tools

    def execute_instrument(
        self,
        tool_id: str,
        parameters: Optional[Dict[str, Any]] = None,
        timeout_sec: int = 30,
        as_admin: bool = False,
    ) -> Dict[str, Any]:
        """Выполняет инструмент на хосте с безопасной передачей параметров и без shell=True."""
        inst = self.get_instrument(tool_id)
        if not inst:
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Инструмент {tool_id} не найден в базе данных.",
                "duration_ms": 0,
                "tool_id": tool_id,
            }

        cmd_to_run = inst.command
        params = parameters or {}
        env = os.environ.copy()
        env["AI_TOOL_PARAMS_JSON"] = json.dumps(params, ensure_ascii=False)
        for k, v in params.items():
            safe_key = re.sub(r"[^A-Za-z0-9_]", "_", str(k)).upper()
            val_str = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)
            env[f"AI_PARAM_{safe_key}"] = val_str
            cmd_to_run = cmd_to_run.replace(f"{{{k}}}", val_str).replace(f"${k}", val_str)

        start_time = time.perf_counter()
        tool_type = inst.tool_type.lower()
        success = False
        exit_code = 0
        stdout = ""
        stderr = ""

        try:
            if tool_type == "python":
                proc = subprocess.run(
                    [sys.executable, "-c", cmd_to_run],
                    capture_output=True,
                    text=True,
                    timeout=timeout_sec,
                    shell=False,
                    env=env,
                )
            elif tool_type in ("powershell", "pwsh"):
                proc = subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd_to_run],
                    capture_output=True,
                    text=True,
                    timeout=timeout_sec,
                    shell=False,
                    env=env,
                )
            else:
                proc = subprocess.run(
                    ["cmd.exe", "/d", "/s", "/c", cmd_to_run],
                    capture_output=True,
                    text=True,
                    timeout=timeout_sec,
                    shell=False,
                    env=env,
                )
            exit_code = proc.returncode
            stdout = proc.stdout
            stderr = proc.stderr
            success = exit_code == 0
        except subprocess.TimeoutExpired:
            stderr = f"Превышен таймаут выполнения ({timeout_sec} сек)"
            exit_code = -2
        except Exception as exc:
            stderr = f"Ошибка запуска процесса: {exc}"
            exit_code = -1

        duration_ms = int((time.perf_counter() - start_time) * 1000)

        if success:
            try:
                self.storage.record_execution(tool_id)
            except Exception as exc:
                logger.warning(f"[AIInstrumentsService] Не удалось обновить счётчик запусков {tool_id}: {exc}")

        return {
            "success": success,
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "duration_ms": duration_ms,
            "tool_id": tool_id,
            "command_executed": cmd_to_run,
        }

    def export_to_csv(self, file_path: Union[str, Path]) -> int:
        """Экспортирует каталог инструментов в CSV файл."""
        items = self.storage.list_instruments(limit=2000, offset=0)
        fieldnames = [
            "tool_id", "name", "tool_type", "command", "description",
            "target_entity", "parameters_schema", "risk_level",
            "author_agent", "tags", "execution_count", "last_executed_at",
            "created_at", "updated_at",
        ]
        target = Path(file_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        with target.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for it in items:
                writer.writerow({
                    "tool_id": it.tool_id,
                    "name": it.name,
                    "tool_type": it.tool_type,
                    "command": it.command,
                    "description": it.description or "",
                    "target_entity": it.target_entity or "",
                    "parameters_schema": json.dumps(it.parameters_schema, ensure_ascii=False),
                    "risk_level": it.risk_level or "safe",
                    "author_agent": it.author_agent or "reasoning_chain",
                    "tags": ", ".join(it.tags),
                    "execution_count": str(it.execution_count or 0),
                    "last_executed_at": it.last_executed_at or "",
                    "created_at": it.created_at or "",
                    "updated_at": it.updated_at or "",
                })
        return len(items)

    def import_from_csv(self, file_path: Union[str, Path]) -> List[AIInstrument]:
        """Импортирует каталог инструментов из CSV файла с единовременной синхронизацией Markdown."""
        target = Path(file_path)
        if not target.is_file():
            raise FileNotFoundError(f"Файл не найден: {file_path}")

        imported: List[AIInstrument] = []
        with target.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = (row.get("name") or "").strip()
                cmd = (row.get("command") or "").strip()
                if not name or not cmd:
                    continue

                schema_raw = row.get("parameters_schema") or "{}"
                try:
                    schema = json.loads(schema_raw)
                except Exception as exc:
                    logger.warning(f"[AIInstrumentsService] Некорректная JSON-схема в CSV для '{name}': {exc}")
                    schema = {}

                tags_raw = row.get("tags") or ""
                tags = [t.strip() for t in tags_raw.split(",") if t.strip()] or ["#agent_tool"]

                item = AIInstrumentCreate(
                    tool_id=row.get("tool_id") or "",
                    name=name,
                    tool_type=row.get("tool_type") or "python",
                    command=cmd,
                    description=row.get("description") or "",
                    target_entity=row.get("target_entity") or "system",
                    parameters_schema=schema,
                    risk_level=row.get("risk_level") or "safe",
                    author_agent=row.get("author_agent") or "csv_import",
                    tags=tags,
                )
                saved = self.save_instrument(item, sync_markdown=False)
                imported.append(saved)
        if imported:
            self.storage._sync_to_markdown()
        return imported
