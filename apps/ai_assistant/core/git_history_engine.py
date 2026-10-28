# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Core - Git History Engine
# =============================================================================
# Description:
#   Асинхронный движок глубокого анализа истории версий Git: построчное чтение
#   коммитов, диффов, blame и построение темпоральной шкалы контрольных точек
#   с фильтрацией гигантских бинарных/сгенерированных файлов.
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.core.git_history_engine import GitHistoryEngine
#
#     engine = GitHistoryEngine()
#     commits = await engine.get_file_history(file_path="apps/windows/main.py", limit=10)
#     diff = await engine.get_diff(commit_hash="a1b2c3", file_path="apps/windows/main.py")
#
# File: git_history_engine.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 09:40:00
# =============================================================================

from __future__ import annotations
"""Асинхронный движок анализа истории версий Git."""

import asyncio
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from logger import logger
from apps.ai_assistant.api.schemas import (
    BlameLine,
    BlameResponse,
    CommitSummary,
    DiffHunkItem,
    DiffResponse,
    TimelineEvent,
    TimelineResponse,
)


class GitHistoryEngine:
    """Асинхронный движок выполнения операций Git для модуля умной истории."""

    def __init__(self, repo_path: Path | str = ".") -> None:
        """Инициализирует движок с указанием пути к репозиторию.

        Args:
            repo_path: Корневой путь Git-репозитория.
        """
        self.repo_path = Path(repo_path).resolve()

    def _run_git_sync(self, args: List[str], timeout_sec: int = 15) -> str:
        """Синхронное выполнение команды Git с изоляцией таймаута и UTF-8 декодированием.

        Args:
            args: Аргументы утилиты git.
            timeout_sec: Таймаут в секундах.

        Returns:
            str: Вывод stdout команды.
        """
        cmd = ["git"] + args
        try:
            res = subprocess.run(
                cmd,
                cwd=str(self.repo_path),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_sec,
            )
            if res.returncode != 0:
                logger.debug(f"[GitHistoryEngine] Команда {' '.join(cmd)} вернула код {res.returncode}")
                return ""
            return res.stdout
        except subprocess.TimeoutExpired:
            logger.warning(f"[GitHistoryEngine] Таймаут выполнения ({timeout_sec}s): {' '.join(cmd)}")
            return ""
        except Exception as exc:
            logger.warning(f"[GitHistoryEngine] Ошибка выполнения Git команды: {exc}")
            return ""

    async def _run_git_async(self, args: List[str], timeout_sec: int = 15) -> str:
        """Асинхронная обертка для неблокирующего вызова Git."""
        return await asyncio.to_thread(self._run_git_sync, args, timeout_sec)

    def is_git_available(self) -> bool:
        """Синхронно проверяет доступность Git и репозитория."""
        out = self._run_git_sync(["rev-parse", "--is-inside-work-tree"], timeout_sec=5)
        return out.strip().lower() == "true"

    async def is_git_repository(self) -> bool:
        """Проверяет, является ли каталог валидным Git-репозиторием."""
        out = await self._run_git_async(["rev-parse", "--is-inside-work-tree"], timeout_sec=5)
        return out.strip().lower() == "true"

    async def get_current_head(self) -> str:
        """Возвращает хэш текущего HEAD коммита."""
        out = await self._run_git_async(["rev-parse", "HEAD"], timeout_sec=5)
        return out.strip()

    async def get_file_history(
        self,
        file_path: Optional[str] = None,
        max_count: int = 50,
        search_query: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[CommitSummary]:
        """Возвращает историю коммитов по файлу или репозиторию.

        Args:
            file_path: Опциональный путь к файлу.
            max_count: Максимальное количество коммитов.
            search_query: Строка поиска по сообщению коммита.
            limit: Алиас для max_count.

        Returns:
            List[CommitSummary]: Список коммитов.
        """
        effective_count = limit if limit is not None else max_count
        fmt = "%H||%P||%an <%ae>||%aI||%s"
        args = ["log", f"-n{effective_count}", f"--pretty=format:{fmt}"]

        if search_query:
            args.append(f"--grep={search_query}")
        if file_path:
            clean_path = file_path.replace("\\", "/")
            args.extend(["--", clean_path])

        out = await self._run_git_async(args)
        if not out:
            return []

        commits: List[CommitSummary] = []
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
                    CommitSummary(
                        commit_hash=commit_hash,
                        parent_hash=parent_hash,
                        author=author,
                        timestamp=timestamp,
                        message=message,
                    )
                )

        return commits

    async def get_diff(
        self,
        commit_hash: str,
        file_path: Optional[str] = None,
        parent_hash: Optional[str] = None,
        max_diff_lines: int = 500,
    ) -> DiffResponse:
        """Извлекает diff изменений для коммита с безопасной фильтрацией тяжелых файлов.

        Args:
            commit_hash: Хэш коммита.
            file_path: Опциональный путь к конкретному файлу.
            parent_hash: Опциональный родительский коммит.
            max_diff_lines: Лимит строк diff для защиты от зависаний.

        Returns:
            DiffResponse: Структурированный diff.
        """
        args = ["show", "--format=", "--unified=3"]

        if file_path:
            clean_path = file_path.replace("\\", "/")
            args.extend([commit_hash, "--", clean_path])
        else:
            args.extend([
                commit_hash,
                "--",
                ":(exclude)*.json",
                ":(exclude)*.sqlite",
                ":(exclude)*.pdf",
                ":(exclude)*.zip",
                ":(exclude)*.png",
                ":(exclude)*.jpg",
            ])

        raw_diff = await self._run_git_async(args, timeout_sec=20)
        lines = raw_diff.splitlines()

        truncated = False
        if len(lines) > max_diff_lines:
            lines = lines[:max_diff_lines]
            truncated = True

        hunks = self._parse_hunks(lines, file_path or "")
        diff_text = "\n".join(lines)

        return DiffResponse(
            commit_hash=commit_hash,
            parent_hash=parent_hash or "",
            file_path=file_path,
            diff_text=diff_text,
            hunks=hunks,
            truncated=truncated,
        )

    def _parse_hunks(self, lines: List[str], file_path: str) -> List[DiffHunkItem]:
        """Парсит строки git diff на hunks."""
        hunks: List[DiffHunkItem] = []
        current_item: Optional[DiffHunkItem] = None
        current_lines: List[str] = []

        for line in lines:
            if line.startswith("@@"):
                if current_item:
                    current_item.hunk_text = "\n".join(current_lines)
                    hunks.append(current_item)
                    current_lines = []

                match = re.search(r"@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@", line)
                old_start = int(match.group(1)) if match else 0
                new_start = int(match.group(3)) if match else 0

                current_item = DiffHunkItem(
                    file_path=file_path,
                    old_start=old_start,
                    new_start=new_start,
                    header=line,
                )
                current_lines.append(line)
            elif current_item:
                current_lines.append(line)

        if current_item:
            current_item.hunk_text = "\n".join(current_lines)
            hunks.append(current_item)

        return hunks

    async def get_blame(self, file_path: str, commit_hash: str = "HEAD") -> BlameResponse:
        """Извлекает построчную аннотацию файла (Git Blame).

        Args:
            file_path: Путь к файлу.
            commit_hash: Ревизия коммита.

        Returns:
            BlameResponse: Построчные сведения об авторах и коде.
        """
        clean_path = file_path.replace("\\", "/")
        args = ["blame", "-p", commit_hash, "--", clean_path]
        raw_blame = await self._run_git_async(args, timeout_sec=15)

        lines: List[BlameLine] = []
        if not raw_blame:
            return BlameResponse(file_path=file_path, commit_hash=commit_hash, lines=[])

        line_num = 1
        current_commit = ""
        current_author = "unknown"
        current_time = ""

        for entry in raw_blame.splitlines():
            if re.match(r"^[0-9a-f]{40}\s+\d+\s+(\d+)", entry):
                parts = entry.split()
                current_commit = parts[0]
                line_num = int(parts[2])
            elif entry.startswith("author "):
                current_author = entry[7:]
            elif entry.startswith("author-time "):
                current_time = entry[12:]
            elif entry.startswith("\t"):
                code_text = entry[1:]
                lines.append(
                    BlameLine(
                        line_number=line_num,
                        commit_hash=current_commit,
                        author=current_author,
                        timestamp=current_time,
                        code=code_text,
                    )
                )

        return BlameResponse(file_path=file_path, commit_hash=commit_hash, lines=lines)

    async def get_file_content(self, commit_hash: str = "HEAD", file_path: str = "") -> str:
        """Извлекает точное содержимое файла на ревизии.

        Args:
            commit_hash: Хэш коммита.
            file_path: Путь к файлу.

        Returns:
            str: Содержимое файла.
        """
        clean_path = file_path.replace("\\", "/").lstrip("/")
        return await self._run_git_async(["show", f"{commit_hash}:{clean_path}"], timeout_sec=10)

    async def get_blob_hash(self, commit_hash: str = "HEAD", file_path: str = "") -> str:
        """Возвращает хэш Git blob для файла на указанном коммите."""
        clean_path = file_path.replace("\\", "/").lstrip("/")
        out = await self._run_git_async(["ls-tree", commit_hash, clean_path], timeout_sec=5)
        if out:
            parts = out.strip().split()
            if len(parts) >= 3:
                return parts[2]
        return ""

    async def get_timeline(
        self,
        file_path: str,
        max_count: int = 50,
        limit: Optional[int] = None,
    ) -> TimelineResponse:
        """Формирует хронологическую шкалу изменений для файла.

        Args:
            file_path: Относительный путь к файлу.
            max_count: Максимальное количество коммитов.
            limit: Алиас для max_count.

        Returns:
            TimelineResponse: События таймлайна.
        """
        effective_count = limit if limit is not None else max_count
        commits = await self.get_file_history(file_path=file_path, max_count=effective_count)
        events: List[TimelineEvent] = []

        for c in commits:
            events.append(
                TimelineEvent(
                    commit_hash=c.commit_hash,
                    timestamp=c.timestamp,
                    author=c.author,
                    message=c.message,
                    status="M",
                )
            )

        return TimelineResponse(
            file_path=file_path,
            events=events,
            checkpoints=events,
            total_checkpoints=len(events),
        )
