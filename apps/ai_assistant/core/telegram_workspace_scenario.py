# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Core - Telegram Workspace Scenario
# =============================================================================
# Description:
#   Сервис оркестрации специального сценария обработки рабочего пространства
#   «דוד משה» при получении файла «שיחה בין דוד משה לשמוליק» через Telegram-бота
#   или WebGUI: запускает 10-секундный индикатор обработки (спиннер) и по
#   завершении таймера добавляет целевой файл в рабочую область с фиксацией
#   в Git, SQLite (KnowledgeStore), векторном индексе FAISS и Obsidian Vault.
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.core.telegram_workspace_scenario import TelegramWorkspaceScenarioService
#
#     service = TelegramWorkspaceScenarioService()
#     state = await service.trigger_scenario(wm, workspace_id="דוד_משה")
#
# File: telegram_workspace_scenario.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 05:00:00
# =============================================================================

from __future__ import annotations
"""Оркестратор специального сценария Telegram-бота для рабочего пространства דוד משה."""

import asyncio
import json
from pathlib import Path
import re
import time
import unicodedata
import uuid
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from header import __root__
from logger import logger
from apps.ai_assistant.core.workspace_registry import (
    format_host_qualified_path,
    get_current_host_name,
)

if TYPE_CHECKING:
    from apps.ai_assistant.core.workspace_manager import WorkspaceManager


def _normalize_hebrew_token(value: Optional[str]) -> str:
    """Нормализует строку для сопоставления ивритских имен пространств и файлов без огласовок."""
    if not value:
        return ""
    text = unicodedata.normalize("NFC", str(value)).strip()
    # Отбрасываем путь и расширение, если передано полное имя файла
    base = Path(text).name if ("\\" in text or "/" in text) else text
    stem = Path(base).stem if "." in base else base
    # Удаляем диакритические знаки (огласовки иврита niqqud: U+0591..U+05C7)
    no_niqqud = "".join(ch for ch in stem if not (0x0591 <= ord(ch) <= 0x05C7))
    # Приводим пробелы, дефисы и подчеркивания к единому пробелу
    collapsed = re.sub(r"[\s_\-—–]+", " ", no_niqqud).strip().lower()
    return collapsed


class TelegramWorkspaceScenarioService:
    """Управляет специальным сценарием добавления файла через Telegram-бота в рабочую область דוד משה."""

    def __init__(
        self,
        config_path: Optional[Path] = None,
        state_file: Optional[Path] = None,
    ) -> None:
        """Инициализирует сервис сценария с загрузкой параметров из config.json."""
        self.config_path = config_path or (__root__ / "apps" / "ai_assistant" / "config.json")
        self.state_file = state_file or (__root__ / "data" / "ai_assistant" / "telegram_scenario_state.json")
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self._active_tasks: Dict[str, asyncio.Task[Any]] = {}

    def load_scenario_config(self) -> Dict[str, Any]:
        """Считывает секцию scenarios.david_moshe_telegram из конфигурационного файла."""
        cfg_data: Dict[str, Any] = {}
        if self.config_path.exists():
            try:
                raw = json.loads(self.config_path.read_text(encoding="utf-8"))
                cfg_data = (raw.get("scenarios") or {}).get("david_moshe_telegram") or {}
            except Exception as exc:
                logger.warning(f"[TelegramWorkspaceScenario] Ошибка чтения {self.config_path}: {exc}")

        return {
            "enabled": bool(cfg_data.get("enabled", True)),
            "workspace_id": str(cfg_data.get("workspace_id") or "דוד_משה"),
            "workspace_name": str(cfg_data.get("workspace_name") or "דוד משה"),
            "workspace_aliases": list(
                cfg_data.get("workspace_aliases")
                or ["דוד משה", "דוד_משה", "דוד מושה", "דוד_מושה"]
            ),
            "trigger_file_names": list(
                cfg_data.get("trigger_file_names")
                or [
                    "שיחה בין דוד משה לשמוליק",
                    "שיחה_בין_דוד_משה_לשמוליק",
                    "שיחה בין דוד מושה לשמוליק",
                    "שיחה_בין_דוד_מושה_לשמוליק",
                ]
            ),
            "target_file_path": str(
                cfg_data.get("target_file_path")
                or r"C:\Users\onela\Desktop\דוד מושה — רשימת מסמכים\שיחה בין דוד משה לשמוליק.md"
            ),
            "delay_seconds": float(cfg_data.get("delay_seconds", 10)),
        }

    def is_david_moshe_workspace(self, workspace_id_or_name: Optional[str]) -> bool:
        """Проверяет, соответствует ли переданный идентификатор или название рабочему пространству דוד משה."""
        if not workspace_id_or_name:
            return False
        cfg = self.load_scenario_config()
        if not cfg.get("enabled", True):
            return False
        norm_candidate = _normalize_hebrew_token(workspace_id_or_name)
        if not norm_candidate:
            return False
        aliases: List[str] = [
            cfg["workspace_id"],
            cfg["workspace_name"],
            *cfg.get("workspace_aliases", []),
        ]
        for alias in aliases:
            if _normalize_hebrew_token(alias) == norm_candidate:
                return True
        return False

    def is_trigger_file(self, filename_or_text: Optional[str]) -> bool:
        """Проверяет, соответствует ли имя файла, подпись или текст триггеру «שיחה בין דוד משה לשמוליק»."""
        if not filename_or_text:
            return False
        cfg = self.load_scenario_config()
        if not cfg.get("enabled", True):
            return False
        norm_input = _normalize_hebrew_token(filename_or_text)
        raw_clean = re.sub(r"[\s_\-—–]+", " ", str(filename_or_text)).strip().lower()
        for trigger in cfg.get("trigger_file_names", []):
            norm_trig = _normalize_hebrew_token(trigger)
            if not norm_trig:
                continue
            if norm_input == norm_trig or norm_trig in norm_input or norm_trig in raw_clean:
                return True
        return False

    def resolve_david_moshe_workspace_id(self, wm: WorkspaceManager, preferred_id: Optional[str] = None) -> str:
        """Находит существующий идентификатор рабочей области דוד משה в реестре или возвращает канонический."""
        if preferred_id and self.is_david_moshe_workspace(preferred_id):
            ws = wm.get_workspace(preferred_id)
            if ws and ws.get("workspace_id"):
                return str(ws["workspace_id"])
        for ws in wm.registry.list_workspaces():
            ws_id = str(ws.get("workspace_id") or "")
            ws_name = str(ws.get("name") or "")
            if self.is_david_moshe_workspace(ws_id) or self.is_david_moshe_workspace(ws_name):
                return ws_id
        cfg = self.load_scenario_config()
        return str(cfg["workspace_id"])

    def _read_state(self) -> Dict[str, Any]:
        """Считывает текущее состояние сценария из JSON-файла синхронизации."""
        if not self.state_file.exists():
            return {"status": "idle"}
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {"status": "idle"}
        except Exception as exc:
            logger.debug(f"[TelegramWorkspaceScenario] Ошибка чтения файла состояния: {exc}")
            return {"status": "idle"}

    def _write_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Записывает состояние сценария в JSON-файл для межпроцессной синхронизации (бот <-> WebGUI)."""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            self.state_file.write_text(
                json.dumps(state, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning(f"[TelegramWorkspaceScenario] Не удалось сохранить состояние: {exc}")
        return state

    async def trigger_scenario(
        self,
        wm: WorkspaceManager,
        workspace_id: Optional[str] = None,
        trigger_source: str = "telegram_bot",
        trigger_file_name: Optional[str] = None,
        delay_seconds: Optional[float] = None,
        wait_for_completion: bool = False,
    ) -> Dict[str, Any]:
        """Запускает сценарий: выставляет статус processing (для спиннера) и планирует добавление файла через 10 секунд."""
        cfg = self.load_scenario_config()
        resolved_ws_id = self.resolve_david_moshe_workspace_id(wm, preferred_id=workspace_id)

        # Гарантируем, что рабочее пространство דוד משה существует и активно
        ws = wm.get_workspace(resolved_ws_id)
        if not ws:
            ws = wm.create_or_select_workspace(
                workspace_id=resolved_ws_id,
                name=cfg["workspace_name"],
            )
        try:
            wm.store.set_active_workspace(resolved_ws_id)
        except Exception as exc:
            logger.debug(f"[TelegramWorkspaceScenario] Не удалось переключить активную область: {exc}")

        effective_delay = float(delay_seconds if delay_seconds is not None else cfg["delay_seconds"])
        run_id = uuid.uuid4().hex[:12]
        now_ts = time.time()
        target_path = cfg["target_file_path"]
        trigger_label = trigger_file_name or cfg["trigger_file_names"][0]

        state: Dict[str, Any] = {
            "run_id": run_id,
            "status": "processing",
            "workspace_id": resolved_ws_id,
            "workspace_name": ws.get("name") or cfg["workspace_name"],
            "trigger_source": trigger_source,
            "trigger_file": trigger_label,
            "target_file_path": target_path,
            "target_file_name": Path(target_path).name,
            "delay_seconds": effective_delay,
            "started_at": now_ts,
            "completed_at": None,
            "elapsed_seconds": 0.0,
            "remaining_seconds": effective_delay,
        }
        self._write_state(state)
        logger.console(
            f"[TelegramScenario] Запущен сценарий для '{resolved_ws_id}' (источник: {trigger_source}, "
            f"файл: '{trigger_label}', ожидание: {effective_delay} сек) -> {target_path}"
        )

        if wait_for_completion:
            if effective_delay > 0:
                await asyncio.sleep(effective_delay)
            return await self.complete_scenario(wm, run_id=run_id)

        task = asyncio.create_task(self._delayed_complete_worker(wm, run_id, effective_delay))
        self._active_tasks[run_id] = task
        return state

    async def _delayed_complete_worker(
        self,
        wm: WorkspaceManager,
        run_id: str,
        delay_seconds: float,
    ) -> None:
        """Фоновая корутина ожидания таймера спиннера и последующего добавления файла."""
        try:
            if delay_seconds > 0:
                await asyncio.sleep(delay_seconds)
            await self.complete_scenario(wm, run_id=run_id)
        except Exception as exc:
            logger.error(f"[TelegramWorkspaceScenario] Ошибка фонового завершения сценария {run_id}: {exc}")
        finally:
            self._active_tasks.pop(run_id, None)

    async def complete_scenario(
        self,
        wm: WorkspaceManager,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Завершает сценарий: добавляет целевой файл с рабочего стола в рабочую область דוד משה."""
        state = self._read_state()
        if run_id and state.get("run_id") and state.get("run_id") != run_id:
            return state
        if state.get("status") == "completed" and state.get("result"):
            return state

        cfg = self.load_scenario_config()
        ws_id = str(state.get("workspace_id") or self.resolve_david_moshe_workspace_id(wm))
        target_path_str = str(state.get("target_file_path") or cfg["target_file_path"])
        target_path = Path(target_path_str)

        try:
            if not target_path.exists():
                raise FileNotFoundError(f"Целевой файл сценария не найден: {target_path_str}")

            commit_msg = f"Telegram сценарий (דוד משה): добавлен файл {target_path.name}"
            # 1. Копируем и индексируем документ внутри рабочей области (Git + SQLite + FAISS + Obsidian)
            add_res = await wm.add_items_to_workspace(
                workspace_id=ws_id,
                paths=[str(target_path)],
                copy_to_workspace=True,
                commit_message=commit_msg,
            )

            # 2. Дополнительно привязываем исходный внешний путь в sources и .tracked_sources.json,
            #    чтобы в UI отображался полный путь "C:\Users\onela\Desktop\דוד מושה — רשימת מסמכים\שיחה בין דוד משה לשמוליק.md"
            cur_host = get_current_host_name()
            qual_path = format_host_qualified_path(target_path, cur_host)
            try:
                wm.link_source(
                    workspace_id=ws_id,
                    target=str(target_path),
                    name=target_path.stem,
                    auto_watch=True,
                    host_name=cur_host,
                )
            except Exception as link_exc:
                logger.debug(f"[TelegramWorkspaceScenario] Привязка внешнего источника: {link_exc}")

            try:
                _, ws_path = wm._get_or_create_workspace(ws_id)
                manifest_file = Path(ws_path) / ".tracked_sources.json"
                manifest_data: Dict[str, Any] = {}
                if manifest_file.exists():
                    manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
                st = target_path.stat()
                manifest_data[target_path.name] = {
                    "host_name": cur_host,
                    "file_path": str(target_path),
                    "qualified_path": qual_path,
                    "updated_at": time.time(),
                    "source_mtime": st.st_mtime,
                    "source_size": st.st_size,
                }
                manifest_file.write_text(
                    json.dumps(manifest_data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            except Exception as man_exc:
                logger.debug(f"[TelegramWorkspaceScenario] Запись .tracked_sources.json: {man_exc}")

            now_ts = time.time()
            started_at = float(state.get("started_at") or now_ts)
            state.update({
                "status": "completed",
                "workspace_id": ws_id,
                "target_file_path": str(target_path),
                "target_file_name": target_path.name,
                "completed_at": now_ts,
                "elapsed_seconds": round(max(0.0, now_ts - started_at), 2),
                "remaining_seconds": 0.0,
                "result": {
                    "files_added": add_res.get("files_added", 1),
                    "git_head": add_res.get("git_head", ""),
                    "tracked_files": add_res.get("tracked_files", []),
                },
            })
            self._write_state(state)
            logger.console(
                f"[TelegramScenario] Сценарий завершён: файл '{target_path}' добавлен в рабочую область '{ws_id}'."
            )
            return state
        except Exception as exc:
            logger.error(f"[TelegramWorkspaceScenario] Ошибка добавления целевого файла: {exc}")
            state.update({
                "status": "error",
                "error": str(exc),
                "completed_at": time.time(),
                "remaining_seconds": 0.0,
            })
            self._write_state(state)
            return state

    async def get_status(self, wm: WorkspaceManager) -> Dict[str, Any]:
        """Возвращает актуальный статус сценария и автоматически завершает его по истечении 10 секунд."""
        state = self._read_state()
        status = state.get("status", "idle")
        if status == "processing":
            now_ts = time.time()
            started_at = float(state.get("started_at") or now_ts)
            delay = float(state.get("delay_seconds") or 10.0)
            elapsed = max(0.0, now_ts - started_at)
            remaining = max(0.0, delay - elapsed)
            state["elapsed_seconds"] = round(elapsed, 2)
            state["remaining_seconds"] = round(remaining, 2)
            if elapsed >= delay:
                state = await self.complete_scenario(wm, run_id=state.get("run_id"))
        return state
