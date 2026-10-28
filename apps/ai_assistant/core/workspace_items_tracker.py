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
# Updated: 2026-10-28 05:01:00
# =============================================================================

from __future__ import annotations
"""Добавление файлов и директорий в рабочую область с мгновенным отслеживанием Git и конвертацией."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from logger import logger
from apps.ai_assistant.core.workspace_registry import (
    format_host_qualified_path,
    get_current_host_name,
    parse_host_qualified_path,
)

if TYPE_CHECKING:
    from apps.ai_assistant.core.workspace_manager import WorkspaceManager

CONVERTIBLE_EXTENSIONS = {
    ".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tiff",
    ".wav", ".mp3", ".ogg", ".m4a", ".flac", ".aac",
}


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
        """Извлекает контент, создаёт companion .md при конвертации, коммитит в Git и индексирует."""
        extracted = await self.wm.extractor.extract(
            dest_file,
            pdf_mode=pdf_mode,
            ocr_mode=ocr_mode,
            audio_mode=audio_mode,
        )
        raw_text = extracted.get("text", "")
        suffix = dest_file.suffix.lower()
        is_raw = bool(extracted.get("is_raw") or extracted.get("conversion_mode") == "raw")

        # Создаём Markdown-версию документа рядом, если это PDF, изображение или аудио и файл не оставлен сырым
        if suffix in CONVERTIBLE_EXTENSIONS and raw_text and not is_raw:
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
            "converted": suffix in CONVERTIBLE_EXTENSIONS and not is_raw,
            "is_raw": is_raw,
            "in_assets": is_in_assets,
            "tracked_by_git": not is_in_assets,
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
                        (pdf_mode == "raw" and ext == ".pdf")
                        or (ocr_mode == "raw" and ext in {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tiff", ".gif"})
                        or (audio_mode == "raw" and ext in {".wav", ".mp3", ".ogg", ".m4a", ".flac", ".aac"})
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
                        existing_item["external_path"] = ext_path_str
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

        return {
            "workspace_id": workspace_id,
            "workspace_path": str(ws_path),
            "current_host": cur_host,
            "git_head": head[:8] if head else "init",
            "branch": branch,
            "total_files": len([i for i in items if not i["is_dir"]]),
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
        ws, ws_path = self._resolve_workspace_path(workspace_id)
        clean_rel = rel_path.strip().replace("\\", "/").lstrip("/")

        # 1. Проверяем, не является ли файл внешним отслеживаемым источником (.tracked_sources.json)
        manifest_file = ws_path / ".tracked_sources.json"
        target_path: Optional[Path] = None
        if manifest_file.exists():
            try:
                manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
                entry = manifest_data.get(clean_rel) or manifest_data.get(rel_path.strip())
                if entry and entry.get("file_path"):
                    cand = Path(entry["file_path"])
                    if cand.exists() and cand.is_file():
                        target_path = cand.resolve()
                    elif entry.get("snapshot"):
                        snap_cand = (ws_path / str(entry["snapshot"])).resolve()
                        if snap_cand.exists() and snap_cand.is_file():
                            target_path = snap_cand
            except Exception:
                target_path = None

        # 2. Если не найден среди внешних — резолвим внутри ws_path с защитой от path traversal
        if target_path is None:
            target_path = (ws_path / clean_rel).resolve()
            if not target_path.exists():
                assets_cand = (ws_path / "assets" / clean_rel).resolve()
                if assets_cand.exists():
                    target_path = assets_cand
            try:
                target_path.relative_to(ws_path)
            except ValueError:
                raise ValueError(f"Путь '{rel_path}' выходит за пределы каталога рабочей области.")

        if not target_path.exists():
            raise FileNotFoundError(f"Файл '{clean_rel}' не найден в рабочей области '{workspace_id}'.")
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

