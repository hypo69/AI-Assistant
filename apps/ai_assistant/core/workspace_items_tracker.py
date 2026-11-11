# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Core - Workspace Items Tracker
# =============================================================================
# Description:
#   Модуль добавления файлов и директорий в изолированную рабочую область.
#   Обеспечивает мгновенный запуск отслеживания Git (git init / git add / git commit),
#   конвертацию PDF -> MD, изображений -> OCR и звука -> транскрибацию
#   с выбором между локальными конвертерами и расшифровкой на моделях (Gemini).
#   Предоставляет просмотр содержимого директории, за которой следит Git.
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.core.workspace_items_tracker import WorkspaceItemsTracker
#     tracker = WorkspaceItemsTracker(workspace_manager)
#     result = await tracker.add_disk_items(workspace_id="test", paths=["C:/data/doc.pdf"], pdf_mode="model")
#
# File: workspace_items_tracker.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-11 23:50:00
# =============================================================================

from __future__ import annotations
"""Добавление файлов и директорий в рабочую область с мгновенным отслеживанием Git и конвертацией."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from logger import logger
from apps.ai_assistant.core.content_extractor import (
    IMAGE_EXTENSIONS,
    MEDIA_WITH_AUDIO_EXTENSIONS,
    PDF_EXTENSIONS,
)
from apps.ai_assistant.core.workspace_registry import (
    format_host_qualified_path,
    get_current_host_name,
    parse_host_qualified_path,
)
from apps.ai_assistant.core.service_file_authenticator import ServiceFileAuthenticator

if TYPE_CHECKING:
    from apps.ai_assistant.core.workspace_manager import WorkspaceManager

CONVERTIBLE_EXTENSIONS = PDF_EXTENSIONS | IMAGE_EXTENSIONS | MEDIA_WITH_AUDIO_EXTENSIONS


class WorkspaceItemsTracker:
    """Управляет добавлением директорий и файлов в рабочую область, конвертацией и фиксацией в Git."""

    def __init__(self, workspace_manager: WorkspaceManager) -> None:
        """Инициализирует трекер с внедрением менеджера рабочих областей."""
        self.wm = workspace_manager

    def _resolve_workspace_path(self, workspace_id: str) -> Tuple[Dict[str, Any], Path]:
        """Возвращает метаданные и абсолютный путь к репозиторию рабочей области."""
        ws, ws_path = self.wm._get_or_create_workspace(workspace_id)
        self.wm._ensure_git_repo(ws_path)
        return ws, ws_path.resolve()

    async def _process_and_commit_file(
        self,
        workspace_id: str,
        ws_path: Path,
        dest_file: Path,
        doc_id: str,
        commit_message: Optional[str] = None,
        pdf_mode: str = "local",
        ocr_mode: str = "model",
        audio_mode: str = "model",
    ) -> Dict[str, Any]:
        """Извлекает контент (через Paperless-ngx при поддержке или локально), создаёт companion .md, коммитит в Git и индексирует."""
        paperless_id: Optional[int] = None
        raw_text = ""
        is_raw = False

        from apps.ai_assistant.core.paperless_connector import PaperlessConnector, PaperlessError

        # 1. Если файл релевантен для Paperless, направляем его на обработку и OCR в Paperless-ngx
        if PaperlessConnector.is_supported_file(dest_file):
            try:
                connector = PaperlessConnector.from_config()
                if connector.ping():
                    ws_info = self.wm.get_workspace(workspace_id) if hasattr(self.wm, "get_workspace") else None
                    ws_name = (ws_info.get("name") if ws_info else None) or workspace_id
                    ingest_res = connector.ingest_file(
                        file_path=dest_file,
                        workspace_id=workspace_id,
                        workspace_name=ws_name,
                        title=dest_file.name,
                    )
                    if ingest_res and ingest_res.get("paperless_id"):
                        paperless_id = ingest_res["paperless_id"]
                        raw_text = ingest_res.get("content") or ""
                        logger.console(
                            f"[WorkspaceItemsTracker] Файл '{dest_file.name}' успешно обработан в Paperless-ngx "
                            f"(ID: #{paperless_id}, OCR символов: {len(raw_text)})."
                        )
            except (PaperlessError, Exception) as pl_exc:
                logger.warning(
                    f"[WorkspaceItemsTracker] Не удалось обработать '{dest_file.name}' в Paperless, "
                    f"переключаюсь на локальный экстрактор: {pl_exc}"
                )

        # 2. Если файл не был обработан в Paperless (аудио, недоступность сервиса или иной тип) — локальный экстрактор
        if not paperless_id:
            extracted = await self.wm.extractor.extract(
                dest_file,
                pdf_mode=pdf_mode,
                ocr_mode=ocr_mode,
                audio_mode=audio_mode,
            )
            raw_text = extracted.get("text", "")
            is_raw = bool(extracted.get("is_raw") or extracted.get("conversion_mode") == "raw")

        suffix = dest_file.suffix.lower()

        # Создаём Markdown-версию документа рядом, если это PDF, изображение или аудио и файл не оставлен сырым
        if (suffix in CONVERTIBLE_EXTENSIONS or paperless_id is not None) and raw_text and not is_raw:
            try:
                md_companion = dest_file.with_name(f"{dest_file.name}.md")
                md_companion.write_text(raw_text, encoding="utf-8")
            except Exception as md_err:
                logger.warning(f"[WorkspaceItemsTracker] Не удалось записать companion .md для {dest_file.name}: {md_err}")

        msg = commit_message or f"Добавлен файл {doc_id} (начало отслеживания)"
        self.wm.import_document(
            workspace_id=workspace_id,
            document_id=doc_id,
            content=raw_text,
            commit_message=msg,
            paperless_id=paperless_id,
        )

        is_in_assets = False
        try:
            dest_file.relative_to(ws_path / "assets")
            is_in_assets = True
        except ValueError:
            is_in_assets = False

        # Если файл НЕ в assets/ (каталог assets исключен из Git), фиксируем его в Git
        if not is_in_assets:
            if is_raw and dest_file.exists():
                try:
                    rel = dest_file.relative_to(ws_path)
                    self.wm._run_git(ws_path, ["add", "-f", str(rel)])
                except Exception:
                    self.wm._run_git(ws_path, ["add", "-f", dest_file.name])
            else:
                self.wm._run_git(ws_path, ["add", "."])
            self.wm._run_git(ws_path, ["commit", "-m", msg])

        return {
            "name": doc_id,
            "path": str(dest_file),
            "size": dest_file.stat().st_size if dest_file.exists() else 0,
            "converted": (suffix in CONVERTIBLE_EXTENSIONS or paperless_id is not None) and not is_raw,
            "is_raw": is_raw,
            "in_assets": is_in_assets,
            "tracked_by_git": not is_in_assets,
            "paperless_id": paperless_id,
        }

    async def add_disk_items(
        self,
        workspace_id: str,
        paths: List[str],
        copy_to_workspace: bool = False,
        commit_message: Optional[str] = None,
        pdf_mode: str = "local",
        ocr_mode: str = "model",
        audio_mode: str = "model",
    ) -> Dict[str, Any]:
        """Добавляет директории и/или файлы с диска в рабочую область. По умолчанию Git следит за ними на месте без копирования."""
        ws, ws_path = self._resolve_workspace_path(workspace_id)
        tracked_files: List[Dict[str, Any]] = []
        errors: List[str] = []

        for p_str in paths:
            raw_path_str = str(p_str).strip()
            if not raw_path_str:
                continue

            resolved_host, clean_local_str, _ = parse_host_qualified_path(raw_path_str)
            item_path = Path(clean_local_str).resolve()
            if not item_path.exists():
                errors.append(f"Путь не найден: {raw_path_str}")
                continue
            qualified_path = format_host_qualified_path(item_path, resolved_host)

            if item_path.is_file():
                try:
                    ext = item_path.suffix.lower()
                    force_raw_copy = (
                        (pdf_mode == "raw" and ext in PDF_EXTENSIONS)
                        or (ocr_mode == "raw" and ext in IMAGE_EXTENSIONS)
                        or (audio_mode == "raw" and ext in MEDIA_WITH_AUDIO_EXTENSIONS)
                    )
                    if copy_to_workspace or force_raw_copy:
                        safe_name = item_path.name
                        assets_dir = ws_path / "assets"
                        assets_dir.mkdir(parents=True, exist_ok=True)
                        dest_file = assets_dir / safe_name
                        if item_path != dest_file:
                            shutil.copy2(item_path, dest_file)

                        doc_id = f"assets/{safe_name}"
                        file_info = await self._process_and_commit_file(
                            workspace_id=workspace_id,
                            ws_path=ws_path,
                            dest_file=dest_file,
                            doc_id=doc_id,
                            commit_message=commit_message,
                            pdf_mode=pdf_mode,
                            ocr_mode=ocr_mode,
                            audio_mode=audio_mode,
                        )
                        file_info["type"] = "file"
                        file_info["source"] = "copy"
                        file_info["host_name"] = resolved_host
                        file_info["qualified_path"] = format_host_qualified_path(dest_file, resolved_host)
                        file_info["rel_path"] = doc_id
                        tracked_files.append(file_info)

                        if hasattr(self.wm, "scenario_service"):
                            try:
                                scen_res = await self.wm.scenario_service.handle_audio_upload_scenario(
                                    wm=self.wm,
                                    workspace_id=workspace_id,
                                    audio_path=dest_file,
                                )
                                if scen_res and scen_res.get("file_info"):
                                    tracked_files.append(scen_res["file_info"])
                            except Exception as scen_err:
                                logger.warning(f"[WorkspaceItemsTracker] Сценарий аудио: {scen_err}")
                    else:
                        self.wm.link_source(
                            workspace_id=workspace_id,
                            target=str(item_path),
                            auto_watch=True,
                            host_name=resolved_host,
                        )
                        tracked_files.append({
                            "name": item_path.name,
                            "path": str(item_path),
                            "host_name": resolved_host,
                            "qualified_path": qualified_path,
                            "type": "file",
                            "source": "linked",
                            "size": item_path.stat().st_size,
                        })
                except Exception as exc:
                    logger.error(f"[WorkspaceItemsTracker] Ошибка добавления файла {item_path}: {exc}")
                    errors.append(f"{item_path.name}: {exc}")

            elif item_path.is_dir():
                try:
                    if copy_to_workspace:
                        assets_dir = ws_path / "assets"
                        assets_dir.mkdir(parents=True, exist_ok=True)
                        files_in_dir = [
                            f for f in sorted(item_path.rglob("*"))
                            if f.is_file() and not f.name.startswith("~") and not f.name.startswith(".")
                        ]
                        for f in files_in_dir:
                            rel_subpath = f.relative_to(item_path)
                            dest_file = assets_dir / rel_subpath
                            dest_file.parent.mkdir(parents=True, exist_ok=True)
                            if f != dest_file:
                                shutil.copy2(f, dest_file)

                            doc_id = f"assets/{str(rel_subpath).replace('\\', '/')}"
                            file_info = await self._process_and_commit_file(
                                workspace_id=workspace_id,
                                ws_path=ws_path,
                                dest_file=dest_file,
                                doc_id=doc_id,
                                commit_message=commit_message or f"Добавлен файл {doc_id} из {item_path.name} в assets (Git)",
                                pdf_mode=pdf_mode,
                                ocr_mode=ocr_mode,
                                audio_mode=audio_mode,
                            )
                            file_info["type"] = "directory_file"
                            file_info["source"] = "copy"
                            file_info["host_name"] = resolved_host
                            file_info["qualified_path"] = format_host_qualified_path(dest_file, resolved_host)
                            file_info["rel_path"] = doc_id
                            tracked_files.append(file_info)
                    else:
                        self.wm.link_source(
                            workspace_id=workspace_id,
                            target=str(item_path),
                            auto_watch=True,
                            host_name=resolved_host,
                        )
                        tracked_files.append({
                            "name": item_path.name,
                            "path": str(item_path),
                            "host_name": resolved_host,
                            "qualified_path": qualified_path,
                            "type": "directory",
                            "source": "linked",
                            "size": 0,
                        })
                except Exception as exc:
                    logger.error(f"[WorkspaceItemsTracker] Ошибка добавления папки {item_path}: {exc}")
                    errors.append(f"{item_path.name}: {exc}")

        if any(item.get("source") == "linked" for item in tracked_files):
            try:
                await self.wm.sync_linked_sources(
                    workspace_id=workspace_id,
                    pdf_mode=pdf_mode,
                    ocr_mode=ocr_mode,
                    audio_mode=audio_mode,
                    commit_message=commit_message,
                )
            except Exception as sync_exc:
                logger.warning(f"[WorkspaceItemsTracker] Ошибка синхронизации связанных источников: {sync_exc}")

        head = self.wm._run_git(ws_path, ["rev-parse", "HEAD"])
        if head.startswith("fatal"):
            head = "init"

        return {
            "status": "ok" if not errors else "partial",
            "workspace_id": workspace_id,
            "git_head": head,
            "files_added": len(tracked_files),
            "tracked_files": tracked_files,
            "errors": errors,
            "message": f"Git начал отслеживание: {len(tracked_files)} файлов зафиксировано в репозитории (HEAD: {head[:8] if head else '---'})",
        }

    async def add_uploaded_files(
        self,
        workspace_id: str,
        files_data: List[Tuple[str, bytes]],
        commit_message: Optional[str] = None,
        pdf_mode: str = "local",
        ocr_mode: str = "model",
        audio_mode: str = "model",
    ) -> Dict[str, Any]:
        """Сохраняет загруженные файлы в рабочую область в каталог assets/, конвертирует и немедленно фиксирует их в Git."""
        ws, ws_path = self._resolve_workspace_path(workspace_id)
        assets_dir = ws_path / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        tracked_files: List[Dict[str, Any]] = []
        errors: List[str] = []

        for filename, content_bytes in files_data:
            safe_name = Path(filename).name
            if not safe_name:
                continue

            try:
                dest_file = assets_dir / safe_name
                dest_file.write_bytes(content_bytes)

                doc_id = f"assets/{safe_name}"
                file_info = await self._process_and_commit_file(
                    workspace_id=workspace_id,
                    ws_path=ws_path,
                    dest_file=dest_file,
                    doc_id=doc_id,
                    commit_message=commit_message or f"Загружен файл {doc_id} в assets (начало отслеживания Git)",
                    pdf_mode=pdf_mode,
                    ocr_mode=ocr_mode,
                    audio_mode=audio_mode,
                )
                file_info["type"] = "uploaded_file"
                file_info["source"] = "upload"
                file_info["size"] = len(content_bytes)
                file_info["rel_path"] = doc_id
                tracked_files.append(file_info)

                if hasattr(self.wm, "scenario_service"):
                    try:
                        scen_res = await self.wm.scenario_service.handle_audio_upload_scenario(
                            wm=self.wm,
                            workspace_id=workspace_id,
                            audio_path=dest_file,
                        )
                        if scen_res and scen_res.get("file_info"):
                            tracked_files.append(scen_res["file_info"])
                    except Exception as scen_err:
                        logger.warning(f"[WorkspaceItemsTracker] Сценарий аудио: {scen_err}")
            except Exception as exc:
                logger.error(f"[WorkspaceItemsTracker] Ошибка сохранения загруженного файла {safe_name}: {exc}")
                errors.append(f"{safe_name}: {exc}")

        head = self.wm._run_git(ws_path, ["rev-parse", "HEAD"])
        if head.startswith("fatal"):
            head = "init"

        return {
            "status": "ok" if not errors else "partial",
            "workspace_id": workspace_id,
            "git_head": head,
            "files_added": len(tracked_files),
            "tracked_files": tracked_files,
            "errors": errors,
            "message": f"Загружено файлов в assets: {len(tracked_files)} (директория assets исключена из Git)",
        }

    def get_directory_contents(self, workspace_id: str) -> Dict[str, Any]:
        """Возвращает детальное содержимое директории рабочей области, отслеживаемой Git."""
        ws, ws_path = self._resolve_workspace_path(workspace_id)
        if not ws_path.exists():
            return {
                "workspace_id": workspace_id,
                "workspace_path": str(ws_path),
                "git_head": "",
                "branch": "master",
                "total_files": 0,
                "user_files_count": 0,
                "system_files_count": 0,
                "total_size_bytes": 0,
                "items": [],
            }

        # Получаем статусы файлов от Git через porcelain с учётом .gitignore
        git_status_raw = self.wm._run_git(ws_path, ["status", "--porcelain", "-uall", "--ignored=matching"])
        status_map: Dict[str, str] = {}
        for line in git_status_raw.splitlines():
            line_str = line.strip()
            if len(line_str) >= 4:
                st_code = line[:2].strip()
                f_name = line[3:].strip().strip('"')
                norm_rel = str(Path(f_name)).replace("\\", "/")
                status_map[norm_rel] = st_code

        head = self.wm._run_git(ws_path, ["rev-parse", "HEAD"])
        if head.startswith("fatal"):
            head = ""
        branch = self.wm._run_git(ws_path, ["branch", "--show-current"]) or "master"

        cur_host = get_current_host_name()
        items: List[Dict[str, Any]] = []
        total_size = 0

        for p in sorted(ws_path.rglob("*")):
            # Пропускаем служебные каталоги и файлы .git, .workspace, .extracted_snapshots, faiss_indices, БД SQLite
            if (
                ".git" in p.parts
                or ".workspace" in p.parts
                or ".extracted_snapshots" in p.parts
                or "faiss_indices" in p.parts
                or p.suffix in (".faiss", ".db", ".db-wal", ".db-shm")
                or p.name in (".tracked_sources.json", ".gitkeep")
                or p.name.startswith("~")
            ):
                continue

            rel_path = str(p.relative_to(ws_path)).replace("\\", "/")
            is_sys = ServiceFileAuthenticator.is_service_file(rel_path, file_path=p)

            # Определяем тип генератора для служебного файла Obsidian
            generator_type = ""
            if is_sys:
                if (p.name.startswith(".") and p.suffix.lower() == ".md") or p.name in ("_Knowledge_Base.md", "_Index.md"):
                    generator_type = "ai_assistant_obsidian"
                elif p.is_file() and p.suffix.lower() == ".md":
                    try:
                        with p.open("r", encoding="utf-8", errors="ignore") as f_chk:
                            header_snippet = f_chk.read(512)
                        if ServiceFileAuthenticator.is_service_content(header_snippet):
                            generator_type = "ai_assistant_obsidian"
                    except Exception:
                        pass


            is_dir = p.is_dir()
            size = p.stat().st_size if not is_dir else 0
            if not is_dir:
                total_size += size

            st_code = status_map.get(rel_path, "")
            if st_code == "!!":
                git_status_desc = "Игнорируется (.gitignore)"
                tracked = False
            elif st_code == "??":
                git_status_desc = "Не отслеживается"
                tracked = False
            elif "R" in st_code:
                git_status_desc = "Перемещён (Git R100)"
                tracked = True
            elif "M" in st_code:
                git_status_desc = "Изменён"
                tracked = True
            elif "A" in st_code:
                git_status_desc = "Добавлен"
                tracked = True
            elif "D" in st_code:
                git_status_desc = "Удалён"
                tracked = True
            else:
                git_status_desc = "Отслеживается"
                tracked = True

            if is_dir:
                size_formatted = "папка"
            elif size < 1024:
                size_formatted = f"{size} B"
            elif size < 1024 * 1024:
                size_formatted = f"{size / 1024:.1f} KB"
            else:
                size_formatted = f"{size / (1024 * 1024):.2f} MB"

            mtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(p.stat().st_mtime))

            items.append({
                "name": p.name,
                "rel_path": rel_path,
                "host_name": cur_host,
                "qualified_path": format_host_qualified_path(p, cur_host),
                "is_current_host": True,
                "source_mode": "local",
                "role": "system" if is_sys else "user",
                "is_system": is_sys,
                "generator": generator_type,
                "is_dir": is_dir,
                "extension": p.suffix.lower() if not is_dir else "dir",
                "size_bytes": size,
                "size_formatted": size_formatted,
                "modified": mtime,
                "git_status": git_status_desc,
                "git_code": st_code,
                "tracked_by_git": tracked,
            })

        # Включаем внешние файлы на диске, отслеживаемые Git без копирования (.tracked_sources.json)
        manifest_file = ws_path / ".tracked_sources.json"
        if manifest_file.exists():
            try:
                manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
                existing_by_rel = {i["rel_path"]: i for i in items}
                for doc_id, meta in manifest_data.items():
                    if doc_id in existing_by_rel:
                        # Обогащаем существующий локальный элемент информацией о внешнем пути из .tracked_sources.json
                        raw_fp = str(meta.get("file_path") or doc_id)
                        item_host, ext_path_str, qual_path = parse_host_qualified_path(
                            raw_fp,
                            default_host=meta.get("host_name") or cur_host,
                        )
                        if meta.get("qualified_path"):
                            qual_path = str(meta["qualified_path"])
                        existing_item = existing_by_rel[doc_id]
                        existing_item["local_path"] = ext_path_str
                        existing_item["external_path"] = qual_path
                        existing_item["qualified_path"] = qual_path
                        existing_item["source_mode"] = "linked"
                        continue
                    raw_fp = str(meta.get("file_path") or doc_id)
                    item_host, ext_path_str, qual_path = parse_host_qualified_path(
                        raw_fp,
                        default_host=meta.get("host_name") or cur_host,
                    )
                    if meta.get("qualified_path"):
                        qual_path = str(meta["qualified_path"])
                    is_same_host = (item_host.upper() == cur_host.upper())
                    ext_p = Path(ext_path_str)

                    if is_same_host and ext_p.exists() and ext_p.is_file():
                        st = ext_p.stat()
                        size = st.st_size
                        mtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime))
                        saved_mtime = float(meta.get("source_mtime", 0.0))
                        saved_size = int(meta.get("source_size", -1))
                        is_changed = abs(saved_mtime - st.st_mtime) > 1e-3 or (saved_size >= 0 and saved_size != size)
                        if is_changed:
                            git_status_desc = "Изменён (на диске)"
                            st_code = "M"
                        elif meta.get("moved_from"):
                            git_status_desc = f"Перемещён ({meta['moved_from']})"
                            st_code = "R100"
                        else:
                            git_status_desc = "Отслеживается (на диске)"
                            st_code = "L"
                    elif not is_same_host:
                        size = int(meta.get("source_size", 0))
                        mtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(meta.get("updated_at", time.time()))))
                        git_status_desc = f"На другом ПК ({item_host})"
                        st_code = "H"
                    else:
                        size = int(meta.get("source_size", 0))
                        mtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(meta.get("updated_at", time.time()))))
                        git_status_desc = "Удалён на диске"
                        st_code = "D"

                    total_size += size
                    size_formatted = f"{size} B" if size < 1024 else (f"{size / 1024:.1f} KB" if size < 1048576 else f"{size / 1048576:.2f} MB")
                    ext_is_sys = ServiceFileAuthenticator.is_service_file(ext_p) or ServiceFileAuthenticator.is_service_file(doc_id)
                    items.append({
                        "name": ext_p.name or doc_id,
                        "rel_path": doc_id,
                        "host_name": item_host,
                        "local_path": ext_path_str,
                        "qualified_path": qual_path,
                        "external_path": qual_path,
                        "is_current_host": is_same_host,
                        "source_mode": "linked",
                        "is_dir": False,
                        "is_external": True,
                        "is_system": ext_is_sys,

                        "extension": ext_p.suffix.lower(),
                        "size_bytes": size,
                        "size_formatted": size_formatted,
                        "modified": mtime,
                        "git_status": git_status_desc,
                        "git_code": st_code,
                        "tracked_by_git": True,
                        "moved_from": meta.get("moved_from") or "",
                        "content_hash": meta.get("content_hash") or "",
                    })
            except Exception as man_err:
                logger.warning(f"[WorkspaceItemsTracker] Ошибка чтения .tracked_sources.json в {ws_path}: {man_err}")

        # Включаем присоединенные внешние источники (файлы и папки) из реестра рабочей области
        try:
            sources = self.wm.list_sources(workspace_id)
            existing_local_paths = {
                str(Path(i.get("local_path") or i.get("external_path") or "").resolve()).lower(): i
                for i in items
                if i.get("local_path") or i.get("external_path")
            }
            existing_rel_paths = {i["rel_path"]: i for i in items}

            for s in sources:
                src_type = s.get("source_type")
                raw_src_path = str(s.get("source_path", "")).strip()
                if not raw_src_path:
                    continue
                s_host = s.get("host_name") or cur_host
                is_same_host = (s_host.upper() == cur_host.upper())
                qual_path = s.get("qualified_path") or format_host_qualified_path(raw_src_path, s_host)
                src_name = s.get("name") or Path(raw_src_path).name or raw_src_path

                if src_type == "directory":
                    dir_p = Path(raw_src_path)
                    if is_same_host and dir_p.exists() and dir_p.is_dir():
                        dir_mtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(dir_p.stat().st_mtime))
                        # Добавляем саму директорию, если ещё не добавлена
                        if src_name not in existing_rel_paths:
                            dir_item = {
                                "name": src_name,
                                "rel_path": src_name,
                                "host_name": s_host,
                                "local_path": str(dir_p.resolve()),
                                "qualified_path": qual_path,
                                "external_path": qual_path,
                                "is_current_host": True,
                                "source_mode": "linked",
                                "is_dir": True,
                                "is_external": True,
                                "is_system": False,
                                "extension": "dir",
                                "size_bytes": 0,
                                "size_formatted": "внешняя папка",
                                "modified": dir_mtime,
                                "git_status": "Внешняя директория",
                                "git_code": "L",
                                "tracked_by_git": True,
                            }
                            items.append(dir_item)
                            existing_rel_paths[src_name] = dir_item
                        else:
                            exist_d = existing_rel_paths[src_name]
                            exist_d["source_mode"] = "linked"
                            exist_d["is_external"] = True
                            exist_d["local_path"] = str(dir_p.resolve())
                            exist_d["external_path"] = qual_path
                            exist_d["qualified_path"] = qual_path
                            exist_d["git_status"] = "Внешняя директория"
                            exist_d["git_code"] = "L"

                        # Сканируем элементы внутри внешней папки
                        for child in sorted(dir_p.rglob("*")):
                            if child.name.startswith("~") or child.name.startswith("."):
                                continue
                            if any(part.startswith(".") or part.startswith("~") for part in child.parts):
                                continue

                            child_key = str(child.resolve()).lower()
                            rel_sub = str(child.relative_to(dir_p)).replace("\\", "/")
                            child_rel = f"{src_name}/{rel_sub}"
                            if child_key in existing_local_paths:
                                old_item = existing_local_paths[child_key]
                                old_item["is_external"] = True
                                old_rel = str(old_item.get("rel_path") or "")
                                if old_rel and "/" not in old_rel:
                                    old_item["rel_path"] = child_rel
                                    old_item["parent_source"] = src_name
                                    existing_rel_paths[child_rel] = old_item
                                continue
                            if child_rel in existing_rel_paths:
                                exist_c = existing_rel_paths[child_rel]
                                exist_c["source_mode"] = "linked"
                                exist_c["is_external"] = True
                                exist_c["local_path"] = str(child.resolve())
                                exist_c["external_path"] = format_host_qualified_path(child, s_host)
                                exist_c["qualified_path"] = format_host_qualified_path(child, s_host)
                                continue

                            is_c_dir = child.is_dir()
                            c_st = child.stat()
                            c_sz = c_st.st_size if not is_c_dir else 0
                            c_m = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(c_st.st_mtime))
                            c_sz_fmt = "папка" if is_c_dir else (f"{c_sz} B" if c_sz < 1024 else (f"{c_sz / 1024:.1f} KB" if c_sz < 1048576 else f"{c_sz / 1048576:.2f} MB"))
                            c_qual = format_host_qualified_path(child, s_host)

                            child_is_sys = ServiceFileAuthenticator.is_service_file(child) or ServiceFileAuthenticator.is_service_file(child_rel)

                            child_item = {
                                "name": child.name,
                                "rel_path": child_rel,
                                "host_name": s_host,
                                "local_path": str(child.resolve()),
                                "qualified_path": c_qual,
                                "external_path": c_qual,
                                "is_current_host": True,
                                "source_mode": "linked",
                                "is_dir": is_c_dir,
                                "is_external": True,
                                "is_system": child_is_sys,
                                "extension": child.suffix.lower() if not is_c_dir else "dir",
                                "size_bytes": c_sz,
                                "size_formatted": c_sz_fmt,
                                "modified": c_m,
                                "git_status": "Отслеживается (на диске)",
                                "git_code": "L",
                                "tracked_by_git": True,
                            }
                            items.append(child_item)
                            existing_local_paths[child_key] = child_item
                            existing_rel_paths[child_rel] = child_item
                            if not is_c_dir:
                                total_size += c_sz
                    elif not is_same_host:
                        if src_name not in existing_rel_paths:
                            items.append({
                                "name": src_name,
                                "rel_path": src_name,
                                "host_name": s_host,
                                "local_path": raw_src_path,
                                "qualified_path": qual_path,
                                "external_path": qual_path,
                                "is_current_host": False,
                                "source_mode": "linked",
                                "is_dir": True,
                                "is_external": True,
                                "is_system": False,
                                "extension": "dir",
                                "size_bytes": 0,
                                "size_formatted": "внешняя папка",
                                "modified": "",
                                "git_status": f"На другом ПК ({s_host})",
                                "git_code": "H",
                                "tracked_by_git": True,
                            })
                            existing_rel_paths[src_name] = items[-1]
                elif src_type == "file":
                    file_p = Path(raw_src_path)
                    f_key = str(file_p.resolve()).lower() if is_same_host and file_p.exists() else raw_src_path.lower()
                    if is_same_host and file_p.exists() and file_p.is_file():
                        if src_name in existing_rel_paths:
                            exist_f = existing_rel_paths[src_name]
                            exist_f["source_mode"] = "linked"
                            exist_f["is_external"] = True
                            exist_f["local_path"] = str(file_p.resolve())
                            exist_f["external_path"] = qual_path
                            exist_f["qualified_path"] = qual_path
                            exist_f["git_status"] = "Внешний файл"
                            exist_f["git_code"] = "L"
                            continue
                    if f_key in existing_local_paths or src_name in existing_rel_paths:
                        continue
                    if is_same_host and file_p.exists() and file_p.is_file():
                        st = file_p.stat()
                        f_sz = st.st_size
                        f_m = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime))
                        f_sz_fmt = f"{f_sz} B" if f_sz < 1024 else (f"{f_sz / 1024:.1f} KB" if f_sz < 1048576 else f"{f_sz / 1048576:.2f} MB")
                        file_item = {
                            "name": src_name,
                            "rel_path": src_name,
                            "host_name": s_host,
                            "local_path": str(file_p.resolve()),
                            "qualified_path": qual_path,
                            "external_path": qual_path,
                            "is_current_host": True,
                            "source_mode": "linked",
                            "is_dir": False,
                            "is_external": True,
                            "is_system": False,
                            "extension": file_p.suffix.lower(),
                            "size_bytes": f_sz,
                            "size_formatted": f_sz_fmt,
                            "modified": f_m,
                            "git_status": "Отслеживается (на диске)",
                            "git_code": "L",
                            "tracked_by_git": True,
                        }
                        items.append(file_item)
                        existing_local_paths[f_key] = file_item
                        existing_rel_paths[src_name] = file_item
                        total_size += f_sz
        except Exception as src_err:
            logger.warning(f"[WorkspaceItemsTracker] Ошибка добавления внешних источников: {src_err}")

        user_files = [i for i in items if not i["is_dir"] and not i.get("is_system", False)]
        system_files = [i for i in items if not i["is_dir"] and i.get("is_system", False)]

        # Синхронизируем единый манифест содержимого (.workspace/manifest.json) внутри рабочей области
        meta_dir = ws_path / ".workspace"
        if meta_dir.exists():
            try:
                manifest_items: Dict[str, Any] = {}
                for itm in items:
                    m_key = itm.get("rel_path") or itm.get("name")
                    if m_key:
                        manifest_items[m_key] = {
                            "name": itm.get("name"),
                            "rel_path": itm.get("rel_path"),
                            "role": itm.get("role") or ("system" if itm.get("is_system") else "user"),
                            "is_system": bool(itm.get("is_system")),
                            "source_mode": itm.get("source_mode", "local"),
                            "is_dir": bool(itm.get("is_dir")),
                            "is_external": bool(itm.get("is_external", False)),
                            "local_path": itm.get("local_path"),
                            "qualified_path": itm.get("qualified_path"),
                            "host_name": itm.get("host_name"),
                            "generator": itm.get("generator", ""),
                            "tracked_by_git": bool(itm.get("tracked_by_git", True)),
                        }
                manifest_obj = {
                    "workspace_id": workspace_id,
                    "updated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                    "user_files_count": len(user_files),
                    "system_files_count": len(system_files),
                    "items": manifest_items,
                }
                manifest_path = meta_dir / "manifest.json"
                tmp_manifest = manifest_path.with_suffix(".json.tmp")
                tmp_manifest.write_text(json.dumps(manifest_obj, indent=2, ensure_ascii=False), encoding="utf-8")
                os.replace(tmp_manifest, manifest_path)
            except Exception as man_exc:
                logger.debug(f"[WorkspaceItemsTracker] Запись .workspace/manifest.json: {man_exc}")


        return {
            "workspace_id": workspace_id,
            "workspace_path": str(ws_path),
            "current_host": cur_host,
            "git_head": head[:8] if head else "init",
            "branch": branch,
            "total_files": len([i for i in items if not i["is_dir"]]),
            "user_files_count": len(user_files),
            "system_files_count": len(system_files),
            "total_size_bytes": total_size,
            "items": items,
        }

    def check_workspace_folder(self, workspace_id: str) -> Dict[str, Any]:
        """Проверяет существование рабочей папки на диске и статус инициализации Git."""
        ws = self.wm.registry.get_workspace(workspace_id)
        if not ws:
            return {
                "workspace_id": workspace_id,
                "name": workspace_id,
                "path": str(self.wm.registry.workspace_path(workspace_id)),
                "exists": False,
                "is_dir": False,
                "has_git": False,
                "git_head": "",
                "file_count": 0,
            }

        p = Path(ws["path"])
        exists = p.exists()
        is_dir = p.is_dir() if exists else False
        has_git = (p / ".git").exists() if exists else False
        head = ""
        if has_git:
            head = self.wm._run_git(p, ["rev-parse", "HEAD"])
            if head.startswith("fatal"):
                head = ""

        file_count = 0
        if exists and is_dir:
            try:
                local_cnt = len([
                    f for f in p.rglob("*")
                    if f.is_file()
                    and f.name not in (".gitkeep", ".gitignore", ".tracked_sources.json")
                    and ".git" not in f.parts
                    and ".workspace" not in f.parts
                ])
                manifest_f = p / ".tracked_sources.json"
                linked_cnt = len(json.loads(manifest_f.read_text(encoding="utf-8"))) if manifest_f.exists() else 0
                file_count = local_cnt + linked_cnt
            except Exception:
                file_count = 0

        return {
            "workspace_id": workspace_id,
            "name": ws.get("name", workspace_id),
            "path": str(p),
            "exists": exists,
            "is_dir": is_dir,
            "has_git": has_git,
            "git_head": head,
            "file_count": file_count,
        }

    def ensure_workspace_folder(self, workspace_id: str) -> Dict[str, Any]:
        """Создаёт папку workspaces/<id> с каталогом assets/ при её отсутствии и инициализирует Git-репозиторий."""
        _, ws_path = self.wm._get_or_create_workspace(workspace_id)
        (ws_path / "assets").mkdir(parents=True, exist_ok=True)
        return self.check_workspace_folder(workspace_id)

    def open_workspace_file(self, workspace_id: str, rel_path: str) -> Dict[str, Any]:
        """Открывает локальный или отслеживаемый на диске файл рабочей области в редакторе по умолчанию."""
        from apps.ai_assistant.core.workspace_file_ops import WorkspaceFileOps

        clean_rel, target_path, meta = WorkspaceFileOps.resolve_item(
            wm=self.wm,
            workspace_id=workspace_id,
            rel_path=rel_path,
            must_exist=True,
        )

        if target_path.is_dir():
            raise ValueError(f"Путь '{clean_rel}' является каталогом, а не файлом.")

        # Запуск открытия через ShellExecute (os.startfile) с fallback на системный редактор
        success = False
        method = "startfile"
        try:
            if hasattr(os, "startfile"):
                os.startfile(str(target_path))  # type: ignore[attr-defined]
                success = True
            else:
                subprocess.Popen(["cmd", "/c", "start", "", str(target_path)], shell=False)
                success = True
        except Exception as exc:
            logger.warning(
                f"[WorkspaceItemsTracker] Не удалось открыть '{target_path}' через системный ассоциатор: {exc}. "
                "Пробуем открыть через текстовый редактор по умолчанию."
            )
            try:
                editor = os.environ.get("EDITOR", "notepad.exe")
                subprocess.Popen([editor, str(target_path)], shell=False)
                success = True
                method = "editor_fallback"
            except Exception as e_exc:
                logger.error(f"[WorkspaceItemsTracker] Ошибка fallback открытия файла: {e_exc}")
                raise RuntimeError(f"Не удалось открыть файл '{clean_rel}': {exc}; {e_exc}")

        return {
            "status": "ok",
            "workspace_id": workspace_id,
            "rel_path": clean_rel,
            "path": str(target_path),
            "method": method,
            "opened": success,
        }

    def open_workspace_folder(self, workspace_id: str) -> Dict[str, Any]:
        """Открывает корневую директорию рабочей области в нативном Проводнике Windows."""
        self.ensure_workspace_folder(workspace_id)
        ws, ws_path = self._resolve_workspace_path(workspace_id)
        if not ws_path.exists():
            raise FileNotFoundError(f"Папка рабочей области '{workspace_id}' не найдена: {ws_path}")

        success = False
        method = "startfile"
        try:
            if hasattr(os, "startfile"):
                os.startfile(str(ws_path))  # type: ignore[attr-defined]
                success = True
            else:
                subprocess.Popen(["explorer.exe", str(ws_path)], shell=False)
                success = True
                method = "explorer"
        except Exception as exc:
            logger.warning(f"[WorkspaceItemsTracker] Ошибка открытия папки '{ws_path}' через startfile: {exc}")
            try:
                subprocess.Popen(["explorer.exe", str(ws_path)], shell=False)
                success = True
                method = "explorer_fallback"
            except Exception as e_exc:
                logger.error(f"[WorkspaceItemsTracker] Ошибка fallback открытия проводника: {e_exc}")
                raise RuntimeError(f"Не удалось открыть папку рабочей области '{workspace_id}': {exc}; {e_exc}")

        return {
            "status": "ok",
            "workspace_id": workspace_id,
            "path": str(ws_path),
            "method": method,
            "opened": success,
        }

    def reveal_workspace_item(self, workspace_id: str, rel_path: str = "") -> Dict[str, Any]:
        """Открывает системный проводник ОС с выделением выбранного файла или открытием папки.

        Args:
            workspace_id: Идентификатор рабочего пространства.
            rel_path: Относительный путь к файлу/папке (пустая строка открывает корень пространства).

        Returns:
            Словарь со статусом, абсолютным путём и способом запуска проводника.
        """
        from apps.ai_assistant.core.workspace_file_ops import WorkspaceFileOps

        clean_input = (rel_path or "").strip()
        if not clean_input:
            self.ensure_workspace_folder(workspace_id)
            _, ws_path = self._resolve_workspace_path(workspace_id)
            if not ws_path.exists():
                raise FileNotFoundError(f"Папка рабочей области '{workspace_id}' не найдена: {ws_path}")
            clean_rel = ""
            target_path = ws_path.resolve()
        else:
            clean_rel, target_path, _ = WorkspaceFileOps.resolve_item(
                wm=self.wm,
                workspace_id=workspace_id,
                rel_path=clean_input,
                must_exist=True,
            )
            target_path = target_path.resolve()

        is_dir = target_path.is_dir()
        method = "explorer_select"

        try:
            if os.name == "nt":
                if is_dir:
                    subprocess.Popen(["explorer.exe", str(target_path)], shell=False)
                    method = "explorer_dir"
                else:
                    subprocess.Popen(["explorer.exe", "/select,", str(target_path)], shell=False)
                    method = "explorer_select"
            elif sys.platform == "darwin":
                cmd = ["open", str(target_path)] if is_dir else ["open", "-R", str(target_path)]
                subprocess.Popen(cmd, shell=False)
                method = "finder"
            else:
                open_dir = target_path if is_dir else target_path.parent
                subprocess.Popen(["xdg-open", str(open_dir)], shell=False)
                method = "xdg_open"
        except Exception as exc:
            logger.error(f"[WorkspaceItemsTracker] Ошибка показа '{target_path}' в проводнике ОС: {exc}")
            raise RuntimeError(f"Не удалось открыть проводник ОС для '{clean_rel or workspace_id}': {exc}")

        logger.info(f"[WorkspaceItemsTracker] Открыт проводник ОС ({method}): {target_path}")
        return {
            "status": "ok",
            "workspace_id": workspace_id,
            "rel_path": clean_rel,
            "path": str(target_path),
            "is_dir": is_dir,
            "method": method,
            "opened": True,
        }

