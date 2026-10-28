# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant - Git Adapter
# =============================================================================
# Description:
#   Адаптер взаимодействия с Git-репозиторием: извлечение коммитов, точных diff,
#   ревизий файлов, blob-хэшей и парсинг фрагментов изменений (diff hunks).
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.git_adapter import GitAdapter
#
#     adapter = GitAdapter()
#     commits = adapter.get_commit_history(max_count=10)
#     diff = adapter.get_file_diff(commits[0].commit_hash)
#
# File: git_adapter.py
# Project: ai-windows-admin
# Package: apps.ai_assistant
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-22 13:34:00
# =============================================================================

from __future__ import annotations
"""Адаптер репозитория Git для извлечения истории версий, ревизий и diff."""

import re
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

from logger import logger
from apps.ai_assistant.models import DiffHunk, FileChange, FileRevision, GitCommitInfo


class GitAdapter:
    """Безопасный адаптер Git для чтения истории изменений и ревизий файлов.

    Обеспечивает fail-fast обработку, изолированные таймауты и защиту от зависания процессов.
    """

    def __init__(self, repo_path: Path | str = ".") -> None:
        """Инициализирует адаптер репозитория.

        Args:
            repo_path: Путь к корневой директории Git-репозитория.
        """
        self.repo_path = Path(repo_path).resolve()

    def _run_git(self, args: List[str], timeout_sec: int = 15) -> str:
        """Выполняет команду git в каталоге репозитория с таймаутом.

        Args:
            args: Список аргументов команды git.
            timeout_sec: Максимальное время ожидания ответа в секундах.

        Returns:
            str: Вывод команды (stdout) или пустая строка при ошибке.
        """
        import os
        cmd = ["git", "--no-pager"] + args
        git_env = os.environ.copy()
        git_env["GIT_PAGER"] = "cat"
        git_env["PAGER"] = "cat"
        try:
            res = subprocess.run(
                cmd,
                cwd=str(self.repo_path),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=git_env,
                timeout=timeout_sec,
            )
            if res.returncode != 0:
                logger.debug(f"[GitAdapter] Команда {' '.join(cmd)} завершилась с кодом {res.returncode}: {res.stderr.strip()}")
                return ""
            return res.stdout
        except subprocess.TimeoutExpired:
            logger.warning(f"[GitAdapter] Таймаут выполнения git-команды ({timeout_sec}s): {' '.join(cmd)}")
            return ""
        except Exception as ex:
            logger.warning(f"[GitAdapter] Ошибка выполнения git-команды: {ex}")
            return ""

    def is_git_available(self) -> bool:
        """Проверяет доступность Git и наличие инициализированного репозитория.

        Returns:
            bool: True, если Git доступен и путь указывает на репозиторий.
        """
        out = self._run_git(["rev-parse", "--is-inside-work-tree"], timeout_sec=5)
        return out.strip().lower() == "true"

    def get_current_commit(self) -> str:
        """Возвращает полный хэш текущего HEAD коммита.

        Returns:
            str: 40-символьный хэш коммита или пустая строка.
        """
        out = self._run_git(["rev-parse", "HEAD"], timeout_sec=5)
        return out.strip()

    def get_commit_history(
        self,
        max_count: int = 50,
        file_path: Optional[str] = None,
        search_query: Optional[str] = None,
    ) -> List[GitCommitInfo]:
        """Возвращает историю коммитов с возможностью фильтрации по файлу или тексту.

        Args:
            max_count: Максимальное количество коммитов.
            file_path: Опциональный путь к файлу для фильтрации.
            search_query: Опциональная строка поиска по сообщению коммита.

        Returns:
            List[GitCommitInfo]: Список найденных коммитов.
        """
        # Формат: %H||%P||%an <%ae>||%aI||%s
        fmt = "%H||%P||%an <%ae>||%aI||%s"
        args = ["log", f"-n{max_count}", f"--pretty=format:{fmt}"]

        if search_query:
            args.extend([f"--grep={search_query}"])
        if file_path:
            args.extend(["--", file_path])

        out = self._run_git(args)
        if not out:
            return []

        commits: List[GitCommitInfo] = []
        for line in out.splitlines():
            line = line.strip()
            if not line or "||" not in line:
                continue
            parts = line.split("||")
            if len(parts) >= 5:
                commit_hash = parts[0].strip()
                parent_hash = parts[1].strip().split()[0] if parts[1].strip() else ""
                author = parts[2].strip()
                timestamp = parts[3].strip()
                message = parts[4].strip()
                commits.append(
                    GitCommitInfo(
                        commit_hash=commit_hash,
                        parent_hash=parent_hash,
                        author=author,
                        timestamp=timestamp,
                        message=message,
                    )
                )

        return commits

    def get_commit_details(self, commit_hash: str) -> Tuple[Optional[GitCommitInfo], List[FileChange]]:
        """Возвращает метаданные коммита и список затронутых файлов с типами изменений.

        Args:
            commit_hash: Хэш коммита.

        Returns:
            Tuple[Optional[GitCommitInfo], List[FileChange]]: Кортеж информации о коммите и файлах.
        """
        commits = self.get_commit_history(max_count=1, search_query=None)
        commit_info = next((c for c in commits if c.commit_hash.startswith(commit_hash)), None)
        if not commit_info:
            out_info = self._run_git(["show", "-s", "--pretty=format:%H||%P||%an <%ae>||%aI||%s", commit_hash])
            if out_info and "||" in out_info:
                p = out_info.strip().split("||")
                commit_info = GitCommitInfo(
                    commit_hash=p[0].strip(),
                    parent_hash=p[1].strip().split()[0] if p[1].strip() else "",
                    author=p[2].strip(),
                    timestamp=p[3].strip(),
                    message=p[4].strip(),
                )

        # Читаем список изменений с хэшами блобов через raw diff-tree
        raw_out = self._run_git(["diff-tree", "--no-commit-id", "--name-status", "-r", commit_hash])
        changes: List[FileChange] = []

        for line in raw_out.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(maxsplit=2)
            if len(parts) >= 2:
                status = parts[0]
                target_path = parts[1]
                old_path = ""
                if status.startswith("R") and len(parts) >= 3:
                    old_path = parts[1]
                    target_path = parts[2]
                changes.append(
                    FileChange(
                        file_path=target_path,
                        change_type=status[0],
                        old_path=old_path,
                    )
                )

        if commit_info:
            commit_info.files_changed_count = len(changes)

        return commit_info, changes

    def get_file_diff(self, commit_hash: str, file_path: Optional[str] = None) -> str:
        """Извлекает точный unified diff коммита или конкретного файла.

        Args:
            commit_hash: Хэш коммита.
            file_path: Опциональный путь к конкретному файлу.

        Returns:
            str: Текст unified diff.
        """
        if file_path:
            args = ["show", "--format=", commit_hash, "--", file_path]
        else:
            # Исключаем гигантские файлы моментальных снимков и бинарников для предотвращения зависания
            args = [
                "show",
                "--format=",
                commit_hash,
                "--",
                ":(exclude,top)*.json",
                ":(exclude,top)**/*.json",
                ":(exclude,top)*.pdf",
                ":(exclude,top)**/*.pdf",
                ":(exclude,top)*.png",
                ":(exclude,top)**/*.png",
                ":(exclude,top)*.jpg",
                ":(exclude,top)**/*.jpg",
            ]
        return self._run_git(args, timeout_sec=10)

    def get_file_revision(self, commit_hash: str, file_path: str) -> Optional[FileRevision]:
        """Восстанавливает точное содержимое файла на указанной ревизии.

        Args:
            commit_hash: Хэш коммита.
            file_path: Путь к файлу внутри репозитория.

        Returns:
            Optional[FileRevision]: Снимок файла или None, если файл не существовал.
        """
        clean_path = file_path.replace("\\", "/").lstrip("/")
        spec = f"{commit_hash}:{clean_path}"
        content = self._run_git(["show", spec], timeout_sec=15)
        if not content and content != "":
            return None

        # Получаем blob хэш через ls-tree
        ls_out = self._run_git(["ls-tree", commit_hash, clean_path])
        blob_hash = ""
        if ls_out:
            parts = ls_out.strip().split()
            if len(parts) >= 3:
                blob_hash = parts[2]

        return FileRevision(
            file_path=clean_path,
            commit_hash=commit_hash,
            blob_hash=blob_hash,
            content=content,
            size_bytes=len(content.encode("utf-8")),
        )

    def get_diff_hunks(self, commit_hash: str, file_path: str) -> List[DiffHunk]:
        """Парсит унифицированный diff на отдельные фрагменты (hunks).

        Args:
            commit_hash: Хэш коммита.
            file_path: Путь к файлу.

        Returns:
            List[DiffHunk]: Список разобранных фрагментов изменений.
        """
        # Пропускаем бинарные и тяжелые файлы данных
        lower_path = file_path.lower()
        if any(lower_path.endswith(ext) for ext in [".pdf", ".png", ".jpg", ".db", ".exe", ".pyc", ".ico"]):
            return []
        if "snapshot" in lower_path or lower_path.endswith(".sqlite"):
            return []

        diff_text = self.get_file_diff(commit_hash, file_path=file_path)
        if not diff_text:
            return []

        hunks: List[DiffHunk] = []
        hunk_header_re = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

        current_hunk: Optional[DiffHunk] = None
        current_lines: List[str] = []

        for line in diff_text.splitlines():
            match = hunk_header_re.match(line)
            if match:
                if current_hunk:
                    current_hunk.hunk_text = "\n".join(current_lines)
                    hunks.append(current_hunk)
                    current_lines = []

                old_start = int(match.group(1))
                old_lines = int(match.group(2) or 1)
                new_start = int(match.group(3))
                new_lines = int(match.group(4) or 1)

                current_hunk = DiffHunk(
                    file_path=file_path,
                    commit_hash=commit_hash,
                    old_start=old_start,
                    old_lines=old_lines,
                    new_start=new_start,
                    new_lines=new_lines,
                )
                current_lines.append(line)
            elif current_hunk:
                current_lines.append(line)

        if current_hunk:
            current_hunk.hunk_text = "\n".join(current_lines)
            hunks.append(current_hunk)

        return hunks
