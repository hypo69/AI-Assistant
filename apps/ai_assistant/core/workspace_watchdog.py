# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Core - Workspace Watchdog
# =============================================================================
# Description:
#   Фоновый наблюдатель файловой системы на базе watchdog (Observer) для рабочих
#   областей и привязанных внешних папок/файлов.
#   1. Отслеживает изменения внутри папок рабочих пространств и автоматически
#      собирает коммиты в Git, а также переиндексирует изменённые документы.
#   2. Отслеживает привязанные внешние папки и файлы (auto_watch=True).
#   3. При появлении медиафайла со звуковой дорожкой запускает автоматическую
#      транскрибацию строго при включённом флаге `watchdog.auto_transcribe_media`
#      в файле конфигурации config.json.
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.core.workspace_watchdog import WorkspaceWatchdogService
#
#     wd = WorkspaceWatchdogService(workspace_manager)
#     wd.start(loop)
#
# File: workspace_watchdog.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-11 23:43:30
# =============================================================================

from __future__ import annotations
"""Фоновый наблюдатель watchdog для автокоммитов Git и условной транскрибации медиафайлов."""

import asyncio
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading
import time
from typing import Any, Deque, Dict, List, Optional, Set, Tuple, TYPE_CHECKING

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from header import __root__
from logger import logger
from apps.ai_assistant.core.content_extractor import ContentExtractor
from apps.ai_assistant.core.obsidian_vault import strip_obsidian_enrichment
from apps.ai_assistant.core.service_file_authenticator import ServiceFileAuthenticator
from apps.ai_assistant.core.watchdog_pdf_pipeline import WatchdogPdfPipeline
from apps.ai_assistant.core.workspace_registry import get_current_host_name

if TYPE_CHECKING:
    from apps.ai_assistant.core.workspace_manager import WorkspaceManager

DEFAULT_CONFIG_PATH = __root__ / "apps" / "ai_assistant" / "config.json"

DEFAULT_WATCHDOG_CONFIG: Dict[str, Any] = {
    "enabled": True,
    "auto_transcribe_media": True,
    "auto_git_commit": True,
    "debounce_seconds": 2.0,
}

_IGNORED_DIR_NAMES: Set[str] = {
    ".git",
    ".workspace",
    ".obsidian",
    ".extracted_snapshots",
    "faiss_indices",
    "_topics",
    "_notes",
    "_entities",
    "__pycache__",
    "node_modules",
}

_config_lock = threading.RLock()


def load_watchdog_config(config_path: Optional[Path | str] = None) -> Dict[str, Any]:
    """Читает секцию watchdog из config.json с возвратом значений по умолчанию."""
    cfg_path = Path(config_path).resolve() if config_path else DEFAULT_CONFIG_PATH
    result = dict(DEFAULT_WATCHDOG_CONFIG)
    with _config_lock:
        if cfg_path.exists():
            try:
                raw = json.loads(cfg_path.read_text(encoding="utf-8"))
                section = raw.get("watchdog") or {}
                if isinstance(section, dict):
                    if "enabled" in section:
                        result["enabled"] = bool(section["enabled"])
                    if "auto_transcribe_media" in section:
                        result["auto_transcribe_media"] = bool(section["auto_transcribe_media"])
                    if "auto_git_commit" in section:
                        result["auto_git_commit"] = bool(section["auto_git_commit"])
                    if "debounce_seconds" in section:
                        try:
                            result["debounce_seconds"] = max(0.2, min(30.0, float(section["debounce_seconds"])))
                        except (TypeError, ValueError):
                            pass
            except Exception as exc:
                logger.warning(f"[WorkspaceWatchdog] Ошибка чтения {cfg_path}: {exc}")
    return result


def save_watchdog_config(patch: Dict[str, Any], config_path: Optional[Path | str] = None) -> Dict[str, Any]:
    """Атомарно обновляет секцию watchdog в config.json и возвращает итоговый словарь."""
    cfg_path = Path(config_path).resolve() if config_path else DEFAULT_CONFIG_PATH
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    with _config_lock:
        full_cfg: Dict[str, Any] = {}
        if cfg_path.exists():
            try:
                full_cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
                if not isinstance(full_cfg, dict):
                    full_cfg = {}
            except Exception as exc:
                logger.warning(f"[WorkspaceWatchdog] Ошибка парсинга {cfg_path}: {exc}")
                full_cfg = {}

        current = load_watchdog_config(cfg_path)
        for key in ("enabled", "auto_transcribe_media", "auto_git_commit"):
            if key in patch and patch[key] is not None:
                current[key] = bool(patch[key])
        if "debounce_seconds" in patch and patch["debounce_seconds"] is not None:
            try:
                current["debounce_seconds"] = max(0.2, min(30.0, float(patch["debounce_seconds"])))
            except (TypeError, ValueError):
                pass

        full_cfg["watchdog"] = current
        tmp_path = cfg_path.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(full_cfg, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp_path, cfg_path)
        return current


@dataclass(frozen=True)
class WatchTarget:
    """Описание наблюдаемой директории или файла (рабочая область или внешний источник)."""

    kind: str  # "workspace" | "linked_source"
    workspace_id: str
    root_path: Path
    source_id: str = ""
    source_file_only: Optional[Path] = None


class _DebouncedWatchHandler(FileSystemEventHandler):
    """Обработчик событий файловой системы watchdog с фильтрацией служебных путей."""

    def __init__(self, service: "WorkspaceWatchdogService", target: WatchTarget) -> None:
        """Инициализирует обработчик для конкретной цели наблюдения."""
        super().__init__()
        self.service = service
        self.target = target

    def on_any_event(self, event: FileSystemEvent) -> None:
        """Фильтрует события файловой системы и передаёт их в очередь дебаунса."""
        if event.is_directory:
            return
        event_type = str(getattr(event, "event_type", "") or "").lower()
        if event_type not in {"created", "modified", "deleted", "moved"}:
            return

        raw_path = getattr(event, "dest_path", None) if event_type == "moved" else event.src_path
        if not raw_path:
            return
        file_path = Path(raw_path)
        self.service.schedule_event(self.target, file_path, event_type)


class WorkspaceWatchdogService:
    """Сервис реального времени (watchdog.Observer) для автокоммитов Git и автозахвата транскрибации."""

    def __init__(
        self,
        workspace_manager: WorkspaceManager,
        config_path: Optional[Path | str] = None,
        pdf_pipeline: Optional[WatchdogPdfPipeline] = None,
    ) -> None:
        """Инициализирует сервис watchdog с внедрением WorkspaceManager.

        Args:
            workspace_manager: Менеджер рабочих областей.
            config_path: Путь к файлу конфигурации config.json.
            pdf_pipeline: Конвейер обработки PDF через Paperless + Gemini (опционально для DI).
        """
        self.wm = workspace_manager
        self.config_path = Path(config_path).resolve() if config_path else DEFAULT_CONFIG_PATH
        self.pdf_pipeline = pdf_pipeline or WatchdogPdfPipeline(
            workspace_manager=workspace_manager,
            suppress_callback=self.suppress_workspace,
        )
        self._observer: Optional[Observer] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._lock = threading.RLock()
        self._timers: Dict[str, threading.Timer] = {}
        self._ws_suppress_until: Dict[str, float] = {}
        self._targets: List[WatchTarget] = []
        self._recent_events: Deque[Dict[str, Any]] = deque(maxlen=50)
        self._stats: Dict[str, int] = {
            "events_processed": 0,
            "git_commits": 0,
            "pdf_processed": 0,
            "media_transcribed": 0,
            "media_skipped_by_config": 0,
            "errors": 0,
        }

    def get_config(self) -> Dict[str, Any]:
        """Возвращает текущую конфигурацию watchdog из config.json."""
        return load_watchdog_config(self.config_path)

    def update_config(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        """Обновляет конфигурацию watchdog и применяет режим активности наблюдателя."""
        updated = save_watchdog_config(patch, self.config_path)
        if updated.get("enabled", True):
            if not self.is_running():
                self.start(self._loop)
            else:
                self.refresh_watches()
        else:
            if self.is_running():
                self.stop()
        return updated

    def is_running(self) -> bool:
        """Возвращает True, если поток watchdog.Observer запущен."""
        with self._lock:
            return self._observer is not None and self._observer.is_alive()

    def suppress_workspace(self, ws_path: Path, seconds: float = 2.5) -> None:
        """Временно подавляет обработку эхо-событий для папки рабочей области после записи сервисом."""
        key = str(Path(ws_path).resolve()).lower()
        with self._lock:
            self._ws_suppress_until[key] = max(
                self._ws_suppress_until.get(key, 0.0),
                time.monotonic() + max(0.2, seconds),
            )

    def _is_workspace_suppressed(self, ws_path: Path) -> bool:
        """Проверяет, активно ли подавление эхо-событий для рабочей области."""
        key = str(Path(ws_path).resolve()).lower()
        with self._lock:
            return time.monotonic() < self._ws_suppress_until.get(key, 0.0)

    def _should_ignore_path(self, target: WatchTarget, file_path: Path) -> bool:
        """Проверяет, нужно ли игнорировать событие по служебному пути или расширению."""
        if target.source_file_only is not None:
            try:
                if file_path.resolve() != target.source_file_only.resolve():
                    return True
            except Exception:
                if file_path.name != target.source_file_only.name:
                    return True

        name = file_path.name
        if not name or name.startswith("~") or name.endswith((".tmp", ".lock", ".swp", ".part", ".crdownload")):
            return True
        if name in {".DS_Store", "Thumbs.db", "ehthumbs.db"}:
            return True

        try:
            rel_parts = file_path.resolve().relative_to(target.root_path.resolve()).parts
        except Exception:
            rel_parts = file_path.parts

        for part in rel_parts[:-1]:
            if part.lower() in _IGNORED_DIR_NAMES or part.startswith("."):
                return True

        if target.kind == "workspace":
            # Игнорируем автогенерированные служебные файлы Obsidian/системы и индексы, чтобы не зациклиться
            if ServiceFileAuthenticator.is_service_file(name, file_path=file_path if file_path.exists() else None):
                return True
            # Если в папке есть <binary>.<ext>.md, созданный как companion для медиа/PDF, и оригинал на диске — игнорируем
            if name.endswith(".md"):
                stem_path = file_path.with_name(name[:-3])
                if stem_path.exists() and ContentExtractor.is_media_with_audio_extension(stem_path):
                    return True
            if self._is_workspace_suppressed(target.root_path):
                return True
        else:
            if name.startswith("."):
                return True

        return False

    def _collect_watch_targets(self) -> List[WatchTarget]:
        """Собирает список папок рабочих областей и локальных привязанных источников."""
        targets: List[WatchTarget] = []
        seen_keys: Set[Tuple[str, str, str, str]] = set()
        cur_host = get_current_host_name().upper()

        try:
            workspaces = self.wm.registry.list_workspaces()
        except Exception as exc:
            logger.warning(f"[WorkspaceWatchdog] Не удалось получить список рабочих областей: {exc}")
            return targets

        for ws in workspaces:
            ws_id = str(ws.get("workspace_id") or "").strip()
            ws_path_str = str(ws.get("path") or "").strip()
            if not ws_id or not ws_path_str:
                continue
            ws_path = Path(ws_path_str).resolve()
            if ws_path.is_dir():
                k = ("workspace", ws_id, str(ws_path).lower(), "")
                if k not in seen_keys:
                    seen_keys.add(k)
                    targets.append(WatchTarget(kind="workspace", workspace_id=ws_id, root_path=ws_path))

            try:
                sources = self.wm.registry.list_sources(ws_id)
            except Exception:
                sources = []

            for src in sources:
                if not src.get("auto_watch", 1):
                    continue
                src_type = str(src.get("source_type") or "")
                if src_type not in {"directory", "file"}:
                    continue
                src_host = str(src.get("host_name") or cur_host).upper()
                if src_host != cur_host:
                    continue
                src_path_str = str(src.get("source_path") or "").strip()
                if not src_path_str:
                    continue
                src_p = Path(src_path_str)
                if src_type == "directory" and src_p.is_dir():
                    resolved_dir = src_p.resolve()
                    k = ("linked_source", ws_id, str(resolved_dir).lower(), "")
                    if k not in seen_keys:
                        seen_keys.add(k)
                        targets.append(
                            WatchTarget(
                                kind="linked_source",
                                workspace_id=ws_id,
                                root_path=resolved_dir,
                                source_id=str(src.get("source_id") or ""),
                            )
                        )
                elif src_type == "file" and src_p.parent.is_dir():
                    resolved_file = src_p.resolve()
                    k = ("linked_source", ws_id, str(resolved_file.parent).lower(), str(resolved_file).lower())
                    if k not in seen_keys:
                        seen_keys.add(k)
                        targets.append(
                            WatchTarget(
                                kind="linked_source",
                                workspace_id=ws_id,
                                root_path=resolved_file.parent,
                                source_id=str(src.get("source_id") or ""),
                                source_file_only=resolved_file,
                            )
                        )

        return targets

    def start(self, loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        """Запускает наблюдатель watchdog.Observer (если watchdog.enabled == True)."""
        if loop is not None:
            self._loop = loop
        else:
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                pass

        cfg = self.get_config()
        if not cfg.get("enabled", True):
            logger.info("[WorkspaceWatchdog] Наблюдатель отключён в конфигурации config.json.")
            return

        with self._lock:
            if self._observer is not None and self._observer.is_alive():
                self.refresh_watches()
                return
            observer = Observer()
            self._observer = observer
            self._schedule_targets_unlocked(observer)
            observer.start()
            logger.console(f"[WorkspaceWatchdog] Запущен (наблюдаемых путей: {len(self._targets)}, авто-транскрибация: {cfg.get('auto_transcribe_media')}).")

    def stop(self) -> None:
        """Останавливает наблюдатель watchdog.Observer и отменяет отложенные таймеры."""
        with self._lock:
            for timer in self._timers.values():
                try:
                    timer.cancel()
                except Exception:
                    pass
            self._timers.clear()
            observer = self._observer
            self._observer = None
            self._targets = []

        if observer is not None:
            try:
                observer.stop()
                observer.join(timeout=3.0)
            except Exception as exc:
                logger.debug(f"[WorkspaceWatchdog] Ошибка остановки Observer: {exc}")
            logger.info("[WorkspaceWatchdog] Остановлен.")

    def _schedule_targets_unlocked(self, observer: Observer) -> None:
        """Перерегистрирует все отслеживаемые пути в переданном Observer."""
        observer.unschedule_all()
        self._targets = self._collect_watch_targets()
        for target in self._targets:
            recursive = target.source_file_only is None
            handler = _DebouncedWatchHandler(self, target)
            try:
                observer.schedule(handler, str(target.root_path), recursive=recursive)
            except Exception as exc:
                logger.warning(f"[WorkspaceWatchdog] Не удалось подписаться на {target.root_path}: {exc}")

    def refresh_watches(self) -> None:
        """Обновляет список наблюдаемых директорий (вызывается при создании области или привязке источника)."""
        with self._lock:
            if self._observer is None or not self._observer.is_alive():
                return
            self._schedule_targets_unlocked(self._observer)

    def schedule_event(self, target: WatchTarget, file_path: Path, event_type: str) -> None:
        """Планирует отложенную обработку файлового события с дебаунсом."""
        if self._should_ignore_path(target, file_path):
            return

        cfg = self.get_config()
        if not cfg.get("enabled", True):
            return

        debounce = float(cfg.get("debounce_seconds", 2.0))
        timer_key = f"{target.kind}:{target.workspace_id}:{str(file_path).lower()}"

        def _dispatch() -> None:
            with self._lock:
                self._timers.pop(timer_key, None)
            if self._loop and self._loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self.process_file_event(target, file_path, event_type),
                    self._loop,
                )
            else:
                try:
                    asyncio.run(self.process_file_event(target, file_path, event_type))
                except Exception as exc:
                    logger.warning(f"[WorkspaceWatchdog] Ошибка синхронного диспатча {file_path}: {exc}")

        with self._lock:
            prev = self._timers.pop(timer_key, None)
            if prev is not None:
                prev.cancel()
            timer = threading.Timer(debounce, _dispatch)
            timer.daemon = True
            self._timers[timer_key] = timer
            timer.start()

    @staticmethod
    async def _wait_until_file_stable(file_path: Path, checks: int = 2, interval: float = 0.25) -> bool:
        """Ожидает стабилизации размера файла (защита от чтения недокопированного медиа)."""
        if not file_path.exists() or not file_path.is_file():
            return False
        prev_size = -1
        for _ in range(checks):
            try:
                cur_size = file_path.stat().st_size
            except OSError:
                return False
            if cur_size == prev_size and cur_size >= 0:
                return True
            prev_size = cur_size
            await asyncio.sleep(interval)
        return file_path.exists()

    def _record_event(self, target: WatchTarget, file_path: Path, event_type: str, action: str, detail: str = "") -> None:
        """Добавляет запись в журнал последних событий наблюдателя."""
        self._recent_events.appendleft({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "kind": target.kind,
            "workspace_id": target.workspace_id,
            "path": str(file_path),
            "event_type": event_type,
            "action": action,
            "detail": detail,
        })

    async def process_file_event(self, target: WatchTarget, file_path: Path, event_type: str) -> Dict[str, Any]:
        """Обрабатывает событие файла: автокоммит Git в рабочей области и условную транскрибацию медиа."""
        cfg = self.get_config()
        if not cfg.get("enabled", True):
            return {"status": "disabled"}

        ws_id = target.workspace_id
        auto_transcribe = bool(cfg.get("auto_transcribe_media", True))
        auto_git_commit = bool(cfg.get("auto_git_commit", True))
        is_media = ContentExtractor.is_media_with_audio_extension(file_path)
        is_pdf = file_path.suffix.lower() == ".pdf"

        try:
            if event_type in {"created", "modified", "moved"}:
                stable = await self._wait_until_file_stable(file_path)
                if not stable:
                    return {"status": "skipped", "reason": "file_missing_or_unstable"}

            if target.kind == "workspace":
                ws_path = target.root_path
                self.suppress_workspace(ws_path, seconds=3.0)

                if event_type == "deleted":
                    if auto_git_commit:
                        await asyncio.to_thread(self._commit_workspace_changes, ws_path, f"Watchdog: удаление {file_path.name}")
                    self._stats["events_processed"] += 1
                    self._record_event(target, file_path, event_type, "git_commit_delete")
                    return {"status": "ok", "action": "git_commit_delete"}

                if is_media:
                    if not auto_transcribe:
                        if auto_git_commit:
                            await asyncio.to_thread(self._commit_workspace_changes, ws_path, f"Watchdog: изменения в {ws_id}")
                        self._stats["media_skipped_by_config"] += 1
                        self._stats["events_processed"] += 1
                        self._record_event(target, file_path, event_type, "media_skipped", "auto_transcribe_media=false")
                        return {"status": "skipped_transcribe", "reason": "auto_transcribe_media=false"}

                    res = await self._transcribe_and_index(
                        ws_id=ws_id,
                        ws_path=ws_path,
                        file_path=file_path,
                        doc_id=str(file_path.relative_to(ws_path)).replace("\\", "/"),
                        is_workspace_internal=True,
                        auto_git_commit=auto_git_commit,
                    )
                    self._stats["events_processed"] += 1
                    self._record_event(target, file_path, event_type, res.get("action", "transcribed"), res.get("detail", ""))
                    return res

                # PDF внутри рабочей области: Paperless -> .md -> размещение Gemini -> Git commit
                if is_pdf:
                    return await self._handle_pdf_event(target, ws_path, file_path, event_type, auto_git_commit)

                # Обычный документ внутри папки рабочей области
                if self.wm.extractor.is_supported_file(file_path):
                    rel_id = str(file_path.relative_to(ws_path)).replace("\\", "/")
                    extracted = await self.wm.extractor.extract(file_path, audio_mode="model" if auto_transcribe else "raw")
                    text = strip_obsidian_enrichment(extracted.get("text") or "")
                    await asyncio.to_thread(
                        self.wm.import_document,
                        workspace_id=ws_id,
                        document_id=rel_id,
                        content=text,
                        commit_message=f"Watchdog: обновление {rel_id}",
                    )
                    self._stats["git_commits"] += 1
                    self._stats["events_processed"] += 1
                    self._record_event(target, file_path, event_type, "indexed_and_committed", rel_id)
                    return {"status": "ok", "action": "indexed_and_committed", "document_id": rel_id}

                # Любой другой неотфильтрованный файл в рабочей области — коммитим изменения в Git
                if auto_git_commit:
                    committed = await asyncio.to_thread(
                        self._commit_workspace_changes, ws_path, f"Watchdog: изменение {file_path.name}"
                    )
                    self._stats["events_processed"] += 1
                    self._record_event(target, file_path, event_type, "git_commit" if committed else "no_git_diff")
                    return {"status": "ok", "action": "git_commit" if committed else "no_git_diff"}
                return {"status": "ignored"}

            # Внешний связанный источник (linked_source)
            ws = self.wm.registry.get_workspace(ws_id)
            if not ws:
                return {"status": "skipped", "reason": "workspace_not_found"}
            ws_path = Path(ws["path"]).resolve()
            self.suppress_workspace(ws_path, seconds=3.0)

            if event_type == "deleted":
                try:
                    rel_doc = (
                        file_path.name
                        if target.source_file_only is not None
                        else str(file_path.relative_to(target.root_path)).replace("\\", "/")
                    )
                except ValueError:
                    rel_doc = file_path.name
                await asyncio.to_thread(self.wm.store.mark_document_deleted, ws_id, rel_doc)
                self._stats["events_processed"] += 1
                self._record_event(target, file_path, event_type, "marked_deleted", rel_doc)
                return {"status": "ok", "action": "marked_deleted", "document_id": rel_doc}

            if not self.wm.extractor.is_supported_file(file_path):
                return {"status": "ignored", "reason": "unsupported_extension"}

            try:
                rel_doc = (
                    file_path.name
                    if target.source_file_only is not None
                    else str(file_path.relative_to(target.root_path)).replace("\\", "/")
                )
            except ValueError:
                rel_doc = file_path.name

            if is_media:
                if not auto_transcribe:
                    self._stats["media_skipped_by_config"] += 1
                    self._stats["events_processed"] += 1
                    self._record_event(target, file_path, event_type, "media_skipped", "auto_transcribe_media=false")
                    return {"status": "skipped_transcribe", "reason": "auto_transcribe_media=false"}

                res = await self._transcribe_and_index(
                    ws_id=ws_id,
                    ws_path=ws_path,
                    file_path=file_path,
                    doc_id=rel_doc,
                    is_workspace_internal=False,
                    auto_git_commit=auto_git_commit,
                )
                self._stats["events_processed"] += 1
                self._record_event(target, file_path, event_type, res.get("action", "transcribed"), rel_doc)
                return res

            # PDF во внешнем связанном источнике: Paperless -> .md в подходящую папку -> Git commit
            if is_pdf:
                return await self._handle_pdf_event(target, ws_path, file_path, event_type, auto_git_commit)

            extracted = await self.wm.extractor.extract(file_path)
            await asyncio.to_thread(
                self.wm.index_document_from_source,
                workspace_id=ws_id,
                document_id=rel_doc,
                content=extracted.get("text") or "",
                file_path=str(file_path),
                commit_message=f"Watchdog sync: {rel_doc}",
            )
            self._stats["git_commits"] += 1
            self._stats["events_processed"] += 1
            self._record_event(target, file_path, event_type, "linked_indexed", rel_doc)
            return {"status": "ok", "action": "linked_indexed", "document_id": rel_doc}

        except Exception as exc:
            self._stats["errors"] += 1
            logger.warning(f"[WorkspaceWatchdog] Ошибка обработки события {event_type} для {file_path}: {exc}")
            self._record_event(target, file_path, event_type, "error", str(exc))
            return {"status": "error", "error": str(exc)}

    async def _handle_pdf_event(
        self,
        target: WatchTarget,
        ws_path: Path,
        file_path: Path,
        event_type: str,
        auto_git_commit: bool,
    ) -> Dict[str, Any]:
        """Делегирует обработку PDF в конвейер Paperless + Gemini и фиксирует статистику."""
        res = await self.pdf_pipeline.process_pdf(
            ws_id=target.workspace_id,
            ws_path=ws_path,
            file_path=file_path,
            auto_git_commit=auto_git_commit,
        )
        self._stats["pdf_processed"] += 1
        self._stats["git_commits"] += 1
        self._stats["events_processed"] += 1
        self._record_event(
            target,
            file_path,
            event_type,
            res.get("action", "pdf_paperless_gemini_committed"),
            res.get("document_id", file_path.name),
        )
        return res

    async def _transcribe_and_index(
        self,
        ws_id: str,
        ws_path: Path,
        file_path: Path,
        doc_id: str,
        is_workspace_internal: bool,
        auto_git_commit: bool,
    ) -> Dict[str, Any]:
        """Извлекает звуковую дорожку, транскрибирует её и сохраняет результат в базу знаний и Git."""
        extracted = await self.wm.extractor.extract(file_path, audio_mode="model")
        if extracted.get("has_audio") is False:
            return {"status": "skipped", "action": "media_no_audio", "detail": file_path.name}

        transcript = (extracted.get("text") or "").strip()
        if not transcript:
            return {"status": "skipped", "action": "empty_transcript", "detail": file_path.name}

        self._stats["media_transcribed"] += 1
        logger.console(f"[WorkspaceWatchdog] Авто-транскрибация завершена: {file_path.name} ({len(transcript)} симв.)")

        if is_workspace_internal:
            await asyncio.to_thread(
                self.wm.import_document,
                workspace_id=ws_id,
                document_id=doc_id,
                content=transcript,
                commit_message=f"Watchdog: транскрибация медиа {doc_id}",
            )
        else:
            await asyncio.to_thread(
                self.wm.index_document_from_source,
                workspace_id=ws_id,
                document_id=doc_id,
                content=transcript,
                file_path=str(file_path),
                commit_message=f"Watchdog: транскрибация внешнего медиа {doc_id}",
            )

        if auto_git_commit:
            await asyncio.to_thread(
                self._commit_workspace_changes,
                ws_path,
                f"Watchdog: транскрибация и обновление {doc_id}",
            )
        return {"status": "ok", "action": "media_transcribed", "document_id": doc_id, "detail": f"{len(transcript)} chars"}

    def _commit_workspace_changes(self, ws_path: Path, message: str) -> bool:
        """Фиксирует накопившиеся изменения рабочей области в её Git-репозитории."""
        self.suppress_workspace(ws_path, seconds=3.0)
        self.wm._ensure_git_repo(ws_path)
        status = self.wm._run_git(ws_path, ["status", "--porcelain"])
        if not status:
            return False
        self.wm._run_git(ws_path, ["add", "-A"])
        post_status = self.wm._run_git(ws_path, ["status", "--porcelain"])
        if not post_status:
            return False
        self.wm._run_git(ws_path, ["commit", "-m", message])
        self._stats["git_commits"] += 1
        logger.console(f"[WorkspaceWatchdog] Git-коммит в '{ws_path.name}': {message}")
        return True

    def get_status(self) -> Dict[str, Any]:
        """Возвращает текущее состояние, конфигурацию, наблюдаемые пути и статистику."""
        cfg = self.get_config()
        with self._lock:
            watched = [
                {
                    "kind": t.kind,
                    "workspace_id": t.workspace_id,
                    "path": str(t.source_file_only or t.root_path),
                    "source_id": t.source_id,
                }
                for t in self._targets
            ]
            events = list(self._recent_events)
            stats = dict(self._stats)
        return {
            "status": "ok",
            "running": self.is_running(),
            "config": cfg,
            "watched_count": len(watched),
            "watched_paths": watched,
            "recent_events": events,
            "stats": stats,
        }
