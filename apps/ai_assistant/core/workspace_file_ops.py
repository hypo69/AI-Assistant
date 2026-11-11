# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant Core - Workspace File Operations
# =============================================================================
# Description:
#   Модуль операций с файловой системой и версионированием в рабочих пространствах:
#   создание файлов и директорий, удаление с фиксацией в Git, чтение содержимого
#   и сохранение правок с автоматическим коммитом.
#
# File: workspace_file_ops.py
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 20:25:00
# =============================================================================

from __future__ import annotations
"""Операции с файлами и директориями рабочих пространств с интеграцией Git."""

import hashlib
import json
from pathlib import Path
import shutil
import time
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

from logger import logger
from apps.ai_assistant.core.workspace_registry import format_host_qualified_path, get_current_host_name

if TYPE_CHECKING:
    from apps.ai_assistant.core.workspace_manager import WorkspaceManager

MAX_TEXT_READ_BYTES = 10 * 1024 * 1024


class WorkspaceFileOps:
    """Инструментарий файловых операций (создание, удаление, редактирование) в Git-репозитории рабочей области."""

    @staticmethod
    def _normalize_and_resolve(ws_path: Path, rel_path: str) -> Tuple[str, Path]:
        """Очищает относительный путь и проверяет отсутствие выхода за границы рабочей директории.

        Args:
            ws_path: Корневая директория рабочего пространства.
            rel_path: Запрошенный относительный путь.

        Returns:
            Кортеж (нормализованный_относительный_путь, абсолютный_путь_к_файлу).

        Raises:
            ValueError: При недопустимом или пустом пути, или при попытке path traversal.
        """
        clean_rel = rel_path.strip().replace("\\", "/").strip("/")
        if not clean_rel or clean_rel in {".", ".."}:
            raise ValueError("Относительный путь не может быть пустым или корневым.")

        target = (ws_path / clean_rel).resolve()
        try:
            target.relative_to(ws_path.resolve())
        except ValueError:
            raise ValueError(f"Путь '{rel_path}' выходит за пределы каталога рабочей области.")

        return clean_rel, target

    @classmethod
    def create_item(
        cls,
        wm: WorkspaceManager,
        workspace_id: str,
        rel_path: str,
        is_dir: bool = False,
        content: str = "",
    ) -> Dict[str, Any]:
        """Создает файл или директорию в рабочей области с фиксацией в Git.

        Args:
            wm: Экземпляр WorkspaceManager.
            workspace_id: Идентификатор рабочего пространства.
            rel_path: Относительный путь к создаваемому объекту.
            is_dir: Флаг каталога (True для директории, False для файла).
            content: Начальное текстовое содержимое при создании файла.

        Returns:
            Словарь со статусом и информацией о созданном объекте.
        """
        _, ws_path = wm._get_or_create_workspace(workspace_id)
        wm._ensure_git_repo(ws_path)
        clean_rel, target = cls._normalize_and_resolve(ws_path, rel_path)

        if is_dir:
            target.mkdir(parents=True, exist_ok=True)
            # Добавляем .gitkeep, если каталог пустой, чтобы Git мог отслеживать структуру
            gitkeep = target / ".gitkeep"
            if not any(target.iterdir()):
                gitkeep.write_text("", encoding="utf-8")
                wm._run_git(ws_path, ["add", str(gitkeep.relative_to(ws_path)).replace("\\", "/")])
                wm._run_git(ws_path, ["commit", "-m", f"Создана папка: {clean_rel}"])
            logger.info(f"[WorkspaceFileOps] Создана директория: {clean_rel} в {workspace_id}")
            return {
                "status": "ok",
                "workspace_id": workspace_id,
                "rel_path": clean_rel,
                "is_dir": True,
            }

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

        wm._run_git(ws_path, ["add", clean_rel])
        wm._run_git(ws_path, ["commit", "-m", f"Создан файл: {clean_rel}"])

        # Индексируем в базе знаний
        try:
            wm.import_document(
                workspace_id=workspace_id,
                document_id=clean_rel,
                content=content,
                commit_message=f"Создан файл: {clean_rel}",
            )
        except Exception as exc:
            logger.warning(f"[WorkspaceFileOps] Ошибка индексации нового файла {clean_rel}: {exc}")

        logger.info(f"[WorkspaceFileOps] Создан файл: {clean_rel} в {workspace_id}")
        return {
            "status": "ok",
            "workspace_id": workspace_id,
            "rel_path": clean_rel,
            "is_dir": False,
            "size": len(content.encode("utf-8")),
        }

    @classmethod
    def delete_item(
        cls,
        wm: WorkspaceManager,
        workspace_id: str,
        rel_path: str,
    ) -> Dict[str, Any]:
        """Удаляет файл или директорию из рабочей области и фиксирует удаление в Git.

        Args:
            wm: Экземпляр WorkspaceManager.
            workspace_id: Идентификатор рабочего пространства.
            rel_path: Относительный путь к удаляемому объекту.

        Returns:
            Словарь с подтверждением удаления.

        Raises:
            FileNotFoundError: Если целевой объект не существует.
        """
        _, ws_path = wm._get_or_create_workspace(workspace_id)
        wm._ensure_git_repo(ws_path)

        try:
            resolved_rel, target, meta = cls.resolve_item(
                wm=wm, workspace_id=workspace_id, rel_path=rel_path, must_exist=True
            )
        except FileNotFoundError:
            raise FileNotFoundError(f"Объект '{rel_path}' не найден в рабочей области '{workspace_id}'.")

        is_directory = target.is_dir()
        is_external = meta.get("is_external", False)
        ws_resolved = ws_path.resolve()

        if not is_external:
            # Локальный файл или каталог внутри репозитория рабочей области
            git_rel = str(target.resolve().relative_to(ws_resolved)).replace("\\", "/")
            if is_directory:
                wm._run_git(ws_path, ["rm", "-r", "-f", git_rel])
                if target.exists():
                    shutil.rmtree(target, ignore_errors=True)
                wm._run_git(ws_path, ["commit", "-m", f"Удален каталог: {git_rel}"])
            else:
                wm._run_git(ws_path, ["rm", "-f", git_rel])
                if target.exists():
                    target.unlink(missing_ok=True)
                wm._run_git(ws_path, ["commit", "-m", f"Удален файл: {git_rel}"])
            deleted_name = git_rel
        else:
            # Внешний файл или внешний источник
            deleted_name = resolved_rel
            source_info = meta.get("source")
            if source_info and source_info.get("source_id"):
                try:
                    wm.registry.delete_source(workspace_id, source_info["source_id"])
                except Exception as src_del_err:
                    logger.warning(f"[WorkspaceFileOps] Ошибка отвязки источника: {src_del_err}")

            if target.exists():
                if is_directory:
                    shutil.rmtree(target, ignore_errors=True)
                else:
                    target.unlink(missing_ok=True)

            man_entry = meta.get("manifest_entry")
            if man_entry and man_entry.get("snapshot"):
                snap_path = ws_path / str(man_entry["snapshot"])
                if snap_path.exists():
                    snap_rel = str(snap_path.resolve().relative_to(ws_resolved)).replace("\\", "/")
                    wm._run_git(ws_path, ["rm", "-f", snap_rel])
                    snap_path.unlink(missing_ok=True)
                    wm._run_git(ws_path, ["commit", "-m", f"Удален снимок внешнего источника: {snap_rel}"])

        # Очистка реестра .tracked_sources.json
        manifest_file = ws_path / ".tracked_sources.json"
        if manifest_file.exists():
            try:
                m_data = json.loads(manifest_file.read_text(encoding="utf-8"))
                target_str_lower = str(target.resolve()).lower()
                keys_to_remove = [
                    k for k, v in m_data.items()
                    if k in (rel_path, resolved_rel, target.name, target.stem)
                    or str(v.get("file_path", "")).lower() == target_str_lower
                ]
                if keys_to_remove:
                    for k in keys_to_remove:
                        m_data.pop(k, None)
                    manifest_file.write_text(json.dumps(m_data, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception as man_exc:
                logger.warning(f"[WorkspaceFileOps] Ошибка очистки .tracked_sources.json: {man_exc}")

        # Очистка из базы знаний KnowledgeStore
        clean_name = target.name
        clean_stem = target.stem
        ids_to_clean = {resolved_rel, rel_path, clean_name, clean_stem, f"assets/{clean_name}", f"assets/{clean_stem}"}
        if meta.get("parent_source"):
            ids_to_clean.add(f"{meta['parent_source']}/{clean_name}")
            ids_to_clean.add(f"{meta['parent_source']}/{clean_stem}")
        for doc_id in ids_to_clean:
            try:
                wm.store.mark_document_deleted(workspace_id, doc_id)
            except Exception:
                pass

        # Очистка из таксономии виртуального дерева .workspace/virtual_taxonomy.json
        tax_path = ws_path / ".workspace" / "virtual_taxonomy.json"
        if tax_path.exists():
            try:
                tax = json.loads(tax_path.read_text(encoding="utf-8"))
                by_rel = tax.get("by_rel_path", {})
                tax_keys = [
                    k for k in by_rel
                    if k in ids_to_clean or any(k.endswith(f"/{suffix}") for suffix in (clean_name, clean_stem))
                ]
                if tax_keys:
                    for k in tax_keys:
                        by_rel.pop(k, None)
                    tax["by_rel_path"] = by_rel
                    tax_path.write_text(json.dumps(tax, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception as tax_exc:
                logger.warning(f"[WorkspaceFileOps] Ошибка очистки virtual_taxonomy.json: {tax_exc}")

        logger.info(f"[WorkspaceFileOps] Удален {'каталог' if is_directory else 'файл'}: {deleted_name} в {workspace_id}")
        return {
            "status": "ok",
            "workspace_id": workspace_id,
            "deleted": deleted_name,
            "is_dir": is_directory,
        }

    @classmethod
    def resolve_item(
        cls,
        wm: WorkspaceManager,
        workspace_id: str,
        rel_path: str,
        must_exist: bool = True,
    ) -> Tuple[str, Path, Dict[str, Any]]:
        """Разрешает относительный или внешний путь к файлу/каталогу рабочей области.

        Поддерживает:
        - Локальные файлы внутри репозитория рабочей области (<ws_path>/...)
        - Файлы в каталоге assets (<ws_path>/assets/...)
        - Поиск с расширениями (если имя указано без .md/.txt)
        - Внешние присоединенные директории и файлы из списка источников (list_sources)
        - Отслеживаемые на диске файлы из .tracked_sources.json
        - Текстовые снимки (.snapshot) при недоступности внешнего носителя/диска

        Args:
            wm: Экземпляр WorkspaceManager.
            workspace_id: Идентификатор рабочей области.
            rel_path: Относительный или внешний путь.
            must_exist: Требовать ли фактического существования объекта на диске.

        Returns:
            Кортеж (нормализованный_относительный_путь, абсолютный_путь_к_файлу, метаданные).

        Raises:
            ValueError: При попытке выхода за границы директории или пустом пути.
            FileNotFoundError: Если must_exist=True и объект не найден.
        """
        _, ws_path = wm._get_or_create_workspace(workspace_id)
        ws_resolved = ws_path.resolve()
        clean_rel = rel_path.strip().replace("\\", "/").strip("/")
        if not clean_rel or clean_rel in {".", ".."}:
            raise ValueError("Относительный путь не может быть пустым или корневым.")

        file_name = Path(clean_rel).name
        file_stem = Path(clean_rel).stem
        file_name_lower = file_name.lower()
        file_stem_lower = file_stem.lower()

        # 1. Попытка прямого разрешения внутри каталога рабочей области
        try:
            local_target = (ws_path / clean_rel).resolve()
            local_target.relative_to(ws_resolved)
            if local_target.exists():
                return clean_rel, local_target, {"source_mode": "local", "is_external": False, "is_snapshot": False}
            assets_target = (ws_path / "assets" / clean_rel).resolve()
            assets_target.relative_to(ws_resolved)
            if assets_target.exists():
                return f"assets/{clean_rel}", assets_target, {"source_mode": "local", "is_external": False, "is_snapshot": False}
        except ValueError:
            pass

        # 1.1 Поиск с расширениями в корне ws_path и assets (если clean_rel без расширения)
        try:
            for base_dir, pfx in ((ws_path, ""), (ws_path / "assets", "assets/")):
                if base_dir.exists():
                    cands = [p for p in base_dir.glob(f"{clean_rel}.*") if p.is_file()]
                    if cands:
                        chosen = cands[0].resolve()
                        chosen.relative_to(ws_resolved)
                        return f"{pfx}{chosen.name}", chosen, {"source_mode": "local", "is_external": False, "is_snapshot": False}
        except ValueError:
            pass

        # 1.2 Рекурсивный поиск в ws_path по имени файла или stem
        try:
            for cand in ws_path.rglob("*"):
                if (
                    ".git" in cand.parts
                    or ".workspace" in cand.parts
                    or ".extracted_snapshots" in cand.parts
                ):
                    continue
                if cand.is_file() and (cand.name == file_name or cand.stem == file_name or cand.stem == file_stem):
                    cand_res = cand.resolve()
                    cand_res.relative_to(ws_resolved)
                    norm_r = str(cand_res.relative_to(ws_resolved)).replace("\\", "/")
                    return norm_r, cand_res, {"source_mode": "local", "is_external": False, "is_snapshot": False}
        except ValueError:
            pass

        # 2. Поиск среди внешних источников, зарегистрированных в рабочей области
        try:
            sources = wm.list_sources(workspace_id)
        except Exception:
            sources = []

        clean_lower = clean_rel.lower()

        for s in sources:
            src_type = s.get("source_type")
            raw_src_path = str(s.get("source_path", "")).strip()
            if not raw_src_path:
                continue
            src_dir_or_file = Path(raw_src_path)
            src_name = str(s.get("name") or src_dir_or_file.name).strip()

            if src_type == "directory":
                # Совпадение с корнем внешней папки
                if clean_rel == src_name or clean_lower == src_name.lower():
                    cand = src_dir_or_file.resolve()
                    if not must_exist or cand.exists():
                        return clean_rel, cand, {"source_mode": "linked", "is_external": True, "source": s, "is_snapshot": False}
                # Элемент внутри внешней папки (например: clean_rel = "דוד משה/דוד משה.txt")
                prefix = f"{src_name}/"
                if clean_rel.startswith(prefix) or clean_lower.startswith(prefix.lower()):
                    sub_rel = clean_rel[len(prefix):].lstrip("/")
                    cand = (src_dir_or_file / sub_rel).resolve()
                    try:
                        cand.relative_to(src_dir_or_file.resolve())
                        if not must_exist or cand.exists():
                            return clean_rel, cand, {"source_mode": "linked", "is_external": True, "source": s, "parent_source": src_name, "is_snapshot": False}
                    except ValueError:
                        pass
                # Поиск по имени файла или по stem внутри директории источника
                if file_name:
                    cand_child = (src_dir_or_file / file_name).resolve()
                    try:
                        cand_child.relative_to(src_dir_or_file.resolve())
                        if cand_child.exists():
                            return f"{src_name}/{cand_child.name}", cand_child, {"source_mode": "linked", "is_external": True, "source": s, "parent_source": src_name, "is_snapshot": False}
                    except ValueError:
                        pass
                    # Поиск с расширением внутри папки источника
                    for ext_cand in src_dir_or_file.glob(f"{file_name}.*"):
                        if ext_cand.is_file():
                            try:
                                ext_cand_res = ext_cand.resolve()
                                ext_cand_res.relative_to(src_dir_or_file.resolve())
                                return f"{src_name}/{ext_cand.name}", ext_cand_res, {"source_mode": "linked", "is_external": True, "source": s, "parent_source": src_name, "is_snapshot": False}
                            except ValueError:
                                pass
            elif src_type == "file":
                if clean_rel in (src_name, src_dir_or_file.name, src_dir_or_file.stem) or clean_lower in (src_name.lower(), src_dir_or_file.name.lower(), src_dir_or_file.stem.lower()):
                    cand = src_dir_or_file.resolve()
                    if not must_exist or cand.exists():
                        return clean_rel, cand, {"source_mode": "linked", "is_external": True, "source": s, "is_snapshot": False}

        # 3. Поиск в реестре отслеживаемых внешних файлов .tracked_sources.json
        manifest_file = ws_path / ".tracked_sources.json"
        if manifest_file.exists():
            try:
                manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
                entry = None
                matched_key = None

                for k in (clean_rel, file_name, rel_path.strip()):
                    if k in manifest_data:
                        entry = manifest_data[k]
                        matched_key = k
                        break

                if not entry:
                    for m_key, m_val in manifest_data.items():
                        m_stem = Path(m_key).stem.lower()
                        if (
                            m_key.lower() == file_name_lower
                            or Path(m_key).name.lower() == file_name_lower
                            or m_stem == file_name_lower
                            or m_stem == file_stem_lower
                        ):
                            entry = m_val
                            matched_key = m_key
                            break
                        raw_fp = str(m_val.get("file_path", "")).replace("\\", "/").rstrip("/")
                        if raw_fp.endswith(f"/{clean_rel}") or raw_fp.endswith(f"/{file_name}"):
                            entry = m_val
                            matched_key = m_key
                            break

                if entry:
                    if entry.get("file_path"):
                        cand = Path(entry["file_path"]).resolve()
                        if cand.exists():
                            return clean_rel, cand, {
                                "source_mode": "linked",
                                "is_external": True,
                                "manifest_entry": entry,
                                "manifest_key": matched_key,
                                "is_snapshot": False,
                            }
                    if entry.get("snapshot"):
                        snap_cand = (ws_path / str(entry["snapshot"])).resolve()
                        try:
                            snap_cand.relative_to(ws_resolved)
                            if snap_cand.exists():
                                return clean_rel, snap_cand, {
                                    "source_mode": "linked",
                                    "is_external": True,
                                    "manifest_entry": entry,
                                    "manifest_key": matched_key,
                                    "is_snapshot": True,
                                }
                        except ValueError:
                            pass
            except Exception as man_err:
                logger.warning(f"[WorkspaceFileOps] Ошибка чтения .tracked_sources.json в {ws_path}: {man_err}")

        # 4. Поиск в каталоге снимков .extracted_snapshots
        snaps_dir = ws_path / ".extracted_snapshots"
        if snaps_dir.exists() and file_name:
            for snap in snaps_dir.iterdir():
                if snap.is_file() and snap.name.endswith(".snapshot"):
                    if file_name_lower in snap.name.lower() or file_stem_lower in snap.name.lower():
                        return clean_rel, snap, {"source_mode": "linked", "is_external": True, "is_snapshot": True}

        # 5. Если создание нового локального файла
        if not must_exist:
            local_target = (ws_path / clean_rel).resolve()
            try:
                local_target.relative_to(ws_resolved)
                return clean_rel, local_target, {"source_mode": "local", "is_external": False, "is_snapshot": False}
            except ValueError:
                raise ValueError(f"Путь '{rel_path}' выходит за пределы каталога рабочей области.")

        raise FileNotFoundError(f"Файл '{clean_rel}' не найден в рабочей области '{workspace_id}'.")

    @classmethod
    def get_content(
        cls,
        wm: WorkspaceManager,
        workspace_id: str,
        rel_path: str,
    ) -> Dict[str, Any]:
        """Возвращает текущее текстовое содержимое файла из рабочей области.

        Args:
            wm: Экземпляр WorkspaceManager.
            workspace_id: Идентификатор рабочего пространства.
            rel_path: Относительный путь к файлу.

        Returns:
            Словарь с содержимым файла, признаком бинарности и размером.

        Raises:
            FileNotFoundError: Если файл не найден.
            ValueError: Если путь указывает на каталог.
        """
        clean_rel, target, meta = cls.resolve_item(
            wm=wm, workspace_id=workspace_id, rel_path=rel_path, must_exist=True
        )
        if target.is_dir():
            raise ValueError(f"Путь '{clean_rel}' является каталогом, а не файлом.")

        file_size = target.stat().st_size
        with open(target, "rb") as f:
            head_chunk = f.read(8192)

        # Проверка на бинарный файл (нулевой байт в первых 8 КБ) или превышение лимита чтения текста
        is_binary = b"\x00" in head_chunk
        if is_binary or file_size > MAX_TEXT_READ_BYTES:
            return {
                "status": "ok",
                "workspace_id": workspace_id,
                "rel_path": clean_rel,
                "is_binary": True,
                "content": None,
                "size": file_size,
                "is_external": meta.get("is_external", False),
            }

        raw_bytes = target.read_bytes()
        text = raw_bytes.decode("utf-8", errors="replace")

        # Определение типа файла по содержимому при отсутствии суффикса/расширения
        detected_type = None
        ext = target.suffix.lstrip(".").lower()
        if not ext and text:
            from apps.common.file_editor.catalog import SupportedFileCatalog
            detected_type = SupportedFileCatalog.detect_type_from_content(text, target.name)

        return {
            "status": "ok",
            "workspace_id": workspace_id,
            "rel_path": clean_rel,
            "is_binary": False,
            "content": text,
            "size": len(raw_bytes),
            "lines_count": len(text.splitlines()),
            "detected_type": detected_type,
            "is_external": meta.get("is_external", False),
        }

    @classmethod
    def get_raw_file_path(
        cls,
        wm: WorkspaceManager,
        workspace_id: str,
        rel_path: str,
    ) -> Tuple[str, Path, str]:
        """Возвращает проверенный путь к файлу рабочей области и его MIME-тип для потоковой отдачи.

        Args:
            wm: Экземпляр WorkspaceManager.
            workspace_id: Идентификатор рабочего пространства.
            rel_path: Относительный путь к файлу.

        Returns:
            Кортеж (нормализованный_относительный_путь, абсолютный_путь_к_файлу, mime_type).

        Raises:
            FileNotFoundError: Если целевой файл не существует.
            ValueError: Если путь указывает на директорию.
        """
        import mimetypes
        clean_rel, target, meta = cls.resolve_item(
            wm=wm, workspace_id=workspace_id, rel_path=rel_path, must_exist=True
        )
        if target.is_dir():
            raise ValueError(f"Путь '{clean_rel}' указывает на директорию, а не на файл.")

        mime_type, _ = mimetypes.guess_type(str(target))
        return clean_rel, target, mime_type or "application/octet-stream"

    @classmethod
    def save_content(
        cls,
        wm: WorkspaceManager,
        workspace_id: str,
        rel_path: str,
        content: str,
        commit_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Сохраняет отредактированный текст файла и создаёт коммит в Git.

        Args:
            wm: Экземпляр WorkspaceManager.
            workspace_id: Идентификатор рабочего пространства.
            rel_path: Относительный путь к файлу.
            content: Текстовое содержимое файла.
            commit_message: Пользовательское сообщение коммита (опционально).

        Returns:
            Словарь со статусом сохранения.
        """
        _, ws_path = wm._get_or_create_workspace(workspace_id)
        wm._ensure_git_repo(ws_path)
        clean_rel, target, meta = cls.resolve_item(
            wm=wm, workspace_id=workspace_id, rel_path=rel_path, must_exist=False
        )

        if target.exists() and target.is_dir():
            raise ValueError(f"Путь '{clean_rel}' является каталогом, невозможно сохранить текст.")

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

        msg = commit_message.strip() if commit_message and commit_message.strip() else f"Обновлен: {clean_rel}"

        if meta.get("is_external"):
            # Для внешнего отслеживаемого файла обновляем снимок и .tracked_sources.json в Git рабочей области
            raw_bytes = content.encode("utf-8")
            content_hash = hashlib.sha256(raw_bytes).hexdigest()
            mtime = target.stat().st_mtime

            manifest_file = ws_path / ".tracked_sources.json"
            manifest_data: Dict[str, Any] = {}
            if manifest_file.exists():
                try:
                    manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
                except Exception:
                    manifest_data = {}

            m_key = meta.get("manifest_key") or Path(clean_rel).name
            cur_host = get_current_host_name()
            entry = manifest_data.get(m_key) or {}
            snap_rel = entry.get("snapshot")
            if not snap_rel:
                safe_snap = "".join(c if c.isalnum() or c in ("_", "-", ".") else "_" for c in f"{cur_host}_{Path(clean_rel).name}") + ".snapshot"
                snap_rel = f".extracted_snapshots/{safe_snap}"

            snap_path = ws_path / snap_rel
            snap_path.parent.mkdir(parents=True, exist_ok=True)
            snap_path.write_text(content, encoding="utf-8")

            entry.update({
                "host_name": cur_host,
                "file_path": str(target.resolve()),
                "qualified_path": format_host_qualified_path(target, cur_host),
                "snapshot": str(snap_rel).replace("\\", "/"),
                "updated_at": time.time(),
                "content_length": len(content),
                "content_hash": content_hash,
                "source_mtime": mtime,
                "source_size": len(raw_bytes),
            })
            manifest_data[m_key] = entry
            manifest_file.write_text(json.dumps(manifest_data, indent=2, ensure_ascii=False), encoding="utf-8")

            wm._run_git(ws_path, ["add", "-A", ".tracked_sources.json", str(snap_rel).replace("\\", "/")])
            wm._run_git(ws_path, ["commit", "-m", msg])
        else:
            wm._run_git(ws_path, ["add", clean_rel])
            wm._run_git(ws_path, ["commit", "-m", msg])

        # Индексируем изменения
        try:
            wm.import_document(
                workspace_id=workspace_id,
                document_id=clean_rel,
                content=content,
                commit_message=msg,
            )
        except Exception as exc:
            logger.warning(f"[WorkspaceFileOps] Ошибка переиндексации {clean_rel}: {exc}")

        logger.info(f"[WorkspaceFileOps] Сохранен файл: {clean_rel} ({len(content)} симв.) в {workspace_id}")
        return {
            "status": "ok",
            "workspace_id": workspace_id,
            "rel_path": clean_rel,
            "size": len(content.encode("utf-8")),
            "commit_message": msg,
        }

    @classmethod
    def move_item(
        cls,
        wm: WorkspaceManager,
        workspace_id: str,
        old_rel_path: str,
        new_rel_path: str,
        commit_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Перемещает или переименовывает файл в рабочей области через git mv и перепривязывает в базе знаний."""
        from apps.ai_assistant.core.workspace_relocator import WorkspaceRelocator

        _, ws_path = wm._get_or_create_workspace(workspace_id)
        wm._ensure_git_repo(ws_path)
        clean_old, old_target = cls._normalize_and_resolve(ws_path, old_rel_path)
        clean_new, new_target = cls._normalize_and_resolve(ws_path, new_rel_path)

        if not old_target.exists():
            raise FileNotFoundError(f"Исходный объект '{clean_old}' не найден в рабочей области '{workspace_id}'.")

        new_target.parent.mkdir(parents=True, exist_ok=True)
        wm._run_git(ws_path, ["mv", "-f", clean_old, clean_new])
        if old_target.exists() and not new_target.exists():
            shutil.move(str(old_target), str(new_target))
            wm._run_git(ws_path, ["add", "-A", clean_old, clean_new])

        msg = (
            commit_message.strip()
            if commit_message and commit_message.strip()
            else f"Перемещён без изменений: {clean_old} -> {clean_new}"
        )
        wm._run_git(ws_path, ["commit", "-m", msg])
        commit_hash = wm._run_git(ws_path, ["rev-parse", "HEAD"])
        if commit_hash.startswith("fatal"):
            commit_hash = "HEAD"

        # Перепривязываем документ в SQLite, FAISS и темпоральном графе без потери истории и фактов
        old_doc_candidates = [clean_old, Path(clean_old).name]
        relocated_info = None
        for cand_old in old_doc_candidates:
            relocated_info = wm.store.relocate_document(
                workspace_id=workspace_id,
                old_document_id=cand_old,
                new_document_id=clean_new,
                new_file_path=str(new_target),
                commit_hash=commit_hash,
            )
            if relocated_info:
                WorkspaceRelocator.migrate_subsystems_on_move(
                    wm=wm,
                    workspace_id=workspace_id,
                    old_doc_id=cand_old,
                    new_doc_id=clean_new,
                    commit_hash=commit_hash,
                )
                break

        logger.info(f"[WorkspaceFileOps] Перемещён объект: {clean_old} -> {clean_new} в {workspace_id}")
        return {
            "status": "ok",
            "workspace_id": workspace_id,
            "old_rel_path": clean_old,
            "new_rel_path": clean_new,
            "commit_hash": commit_hash,
            "commit_message": msg,
            "message": msg,
            "relocated_in_store": bool(relocated_info),
        }

