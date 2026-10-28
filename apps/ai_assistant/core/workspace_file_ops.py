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
# Updated: 2026-10-28 17:50:00
# =============================================================================

from __future__ import annotations
"""Операции с файлами и директориями рабочих пространств с интеграцией Git."""

from pathlib import Path
import shutil
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

from logger import logger

if TYPE_CHECKING:
    from apps.ai_assistant.core.workspace_manager import WorkspaceManager


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
        clean_rel, target = cls._normalize_and_resolve(ws_path, rel_path)

        if not target.exists():
            assets_cand = (ws_path / "assets" / clean_rel).resolve()
            if assets_cand.exists():
                target = assets_cand
                clean_rel = f"assets/{clean_rel}"
            else:
                raise FileNotFoundError(f"Объект '{clean_rel}' не найден в рабочей области '{workspace_id}'.")

        is_directory = target.is_dir()
        if is_directory:
            wm._run_git(ws_path, ["rm", "-r", "-f", clean_rel])
            if target.exists():
                shutil.rmtree(target, ignore_errors=True)
            wm._run_git(ws_path, ["commit", "-m", f"Удален каталог: {clean_rel}"])
        else:
            wm._run_git(ws_path, ["rm", "-f", clean_rel])
            if target.exists():
                target.unlink(missing_ok=True)
            wm._run_git(ws_path, ["commit", "-m", f"Удален файл: {clean_rel}"])

        logger.info(f"[WorkspaceFileOps] Удален {'каталог' if is_directory else 'файл'}: {clean_rel} в {workspace_id}")
        return {
            "status": "ok",
            "workspace_id": workspace_id,
            "deleted": clean_rel,
            "is_dir": is_directory,
        }

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
        _, ws_path = wm._get_or_create_workspace(workspace_id)
        clean_rel, target = cls._normalize_and_resolve(ws_path, rel_path)

        if not target.exists():
            assets_cand = (ws_path / "assets" / clean_rel).resolve()
            if assets_cand.exists():
                target = assets_cand
                clean_rel = f"assets/{clean_rel}"
            else:
                raise FileNotFoundError(f"Файл '{clean_rel}' не найден в рабочей области '{workspace_id}'.")
        if target.is_dir():
            raise ValueError(f"Путь '{clean_rel}' является каталогом, а не файлом.")

        raw_bytes = target.read_bytes()
        # Проверка на бинарный файл (нулевой байт в первых 8 КБ)
        is_binary = b"\x00" in raw_bytes[:8192]
        if is_binary:
            return {
                "status": "ok",
                "workspace_id": workspace_id,
                "rel_path": clean_rel,
                "is_binary": True,
                "content": None,
                "size": len(raw_bytes),
            }

        text = raw_bytes.decode("utf-8", errors="replace")
        return {
            "status": "ok",
            "workspace_id": workspace_id,
            "rel_path": clean_rel,
            "is_binary": False,
            "content": text,
            "size": len(raw_bytes),
            "lines_count": len(text.splitlines()),
        }

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
        clean_rel, target = cls._normalize_and_resolve(ws_path, rel_path)

        if not target.exists():
            assets_cand = (ws_path / "assets" / clean_rel).resolve()
            if assets_cand.exists():
                target = assets_cand
                clean_rel = f"assets/{clean_rel}"

        if target.exists() and target.is_dir():
            raise ValueError(f"Путь '{clean_rel}' является каталогом, невозможно сохранить текст.")

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

        msg = commit_message.strip() if commit_message and commit_message.strip() else f"Обновлен: {clean_rel}"
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

