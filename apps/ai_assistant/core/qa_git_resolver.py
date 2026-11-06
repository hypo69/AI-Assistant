# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-assistant Apps AI_Assistant Core QA Git Resolver
# =============================================================================
# Description:
#   Модуль глубокого анализа Git-истории и извлечения контекста коммитов для
#   вопросно-ответного механизма QAEngine. Извлекает diff изменений, метаданные
#   коммита (автор, дата, комментарий) и формирует контекст для языковой модели
#   и локального ответа без потери точности.
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.core.qa_git_resolver import QaGitResolver
#
#     git_ctx, sources, fallback_ans = await QaGitResolver.resolve(
#         wm=workspace_manager,
#         workspace_id="דוד_משה",
#         parsed_q=parsed_question,
#         language="he",
#     )
#
# File: core/qa_git_resolver.py
# Project: ai-assistant
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-03 16:53:00
# =============================================================================

from __future__ import annotations
"""Модуль извлечения Git-контекста и анализа изменений для QAEngine."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from apps.ai_assistant.core.git_history_engine import GitHistoryEngine

logger = logging.getLogger("ai_assistant")


class QaGitResolver:
    """Анализатор Git-запросов и поставщик контекста коммитов для RAG и QAEngine."""

    @classmethod
    async def resolve(
        cls,
        wm: Any,
        workspace_id: str,
        parsed_q: Dict[str, Any],
        language: str = "ru",
    ) -> Tuple[Optional[str], List[Dict[str, Any]], Optional[str]]:
        """Извлекает подробный Git-контекст (diff, метаданные, список коммитов) по запросу.

        Args:
            wm: Экземпляр WorkspaceManager.
            workspace_id: Идентификатор рабочего пространства.
            parsed_q: Разобранный словарь вопроса (QuestionIntentParser).
            language: Язык ответа.

        Returns:
            Tuple[Optional[str], List[Dict[str, Any]], Optional[str]]:
                (git_context_text, sources_list, deterministic_fallback_answer).
        """
        is_git_query = parsed_q.get("is_git_query") or bool(parsed_q.get("commit_hash"))
        if not is_git_query:
            return None, [], None

        target_commit = (parsed_q.get("commit_hash") or "").strip()
        repo_dir = cls._resolve_repo_dir(wm, workspace_id)
        if not repo_dir or not repo_dir.exists():
            return None, [], None

        engine = GitHistoryEngine(repo_path=repo_dir)
        if not await engine.is_git_repository():
            return None, [], None

        if target_commit:
            return await cls._resolve_commit_details(engine, target_commit, language)

        return await cls._resolve_history_overview(engine, language)

    @classmethod
    def _resolve_repo_dir(cls, wm: Any, workspace_id: str) -> Optional[Path]:
        """Определяет директорию Git-репозитория рабочего пространства."""
        try:
            ws_entry = wm.registry.get_workspace(workspace_id)
            if ws_entry and ws_entry.get("path"):
                return Path(ws_entry["path"])
            return Path(wm.registry.workspace_path(workspace_id))
        except Exception as exc:
            logger.warning(f"[QaGitResolver] Ошибка разрешения пути рабочего пространства {workspace_id}: {exc}")
            return None

    @classmethod
    async def _resolve_commit_details(
        cls,
        engine: GitHistoryEngine,
        commit_hash: str,
        language: str,
    ) -> Tuple[Optional[str], List[Dict[str, Any]], Optional[str]]:
        """Извлекает детальные данные коммита: метаданные, изменённые файлы и diff."""
        try:
            meta_raw = await engine._run_git_async([
                "show", "-s", "--format=%H||%an <%ae>||%ad||%s", commit_hash
            ])
            if not meta_raw or "||" not in meta_raw:
                return None, [], None

            parts = meta_raw.strip().split("||")
            full_hash = parts[0].strip()
            author = parts[1].strip() if len(parts) > 1 else ""
            date_str = parts[2].strip() if len(parts) > 2 else ""
            message = parts[3].strip() if len(parts) > 3 else ""

            diff_resp = await engine.get_diff(commit_hash=full_hash, max_diff_lines=250)
            files_changed = diff_resp.files_changed or []
            files_str = ", ".join(files_changed) if files_changed else "None"
            short_h = full_hash[:7]

            git_context = (
                f"=== GIT COMMIT DETAILS ===\n"
                f"Commit Hash: {full_hash}\n"
                f"Short Hash: {short_h}\n"
                f"Author: {author}\n"
                f"Date: {date_str}\n"
                f"Commit Message: {message}\n"
                f"Changed Files ({len(files_changed)}): {files_str}\n\n"
                f"=== GIT DIFF CHUNKS ===\n"
                f"{diff_resp.diff_text[:3500]}\n"
            )

            fallback_ans = cls._build_commit_fallback_answer(language, short_h, message, files_str)
            sources = [{
                "document_id": f"git:commit:{short_h}",
                "commit_hash": full_hash,
                "sentence_index": 0,
                "quote": f"Commit {short_h}: {message} (Changed: {files_str})",
            }]
            return git_context, sources, fallback_ans
        except Exception as exc:
            logger.warning(f"[QaGitResolver] Ошибка извлечения деталей коммита {commit_hash}: {exc}")
            return None, [], None

    @classmethod
    async def _resolve_history_overview(
        cls,
        engine: GitHistoryEngine,
        language: str,
    ) -> Tuple[Optional[str], List[Dict[str, Any]], Optional[str]]:
        """Извлекает краткий перечень последних коммитов репозитория."""
        try:
            commits = await engine.get_file_history(max_count=8)
            if not commits:
                return None, [], None

            lines = [
                f"- {c.commit_hash[:7]} ({c.timestamp}): {c.message} [author: {c.author}]"
                for c in commits
            ]
            git_context = "=== RECENT GIT COMMITS ===\n" + "\n".join(lines)
            head_hash = commits[0].commit_hash

            fallback_ans = cls._build_history_fallback_answer(language, commits)
            sources = [{
                "document_id": "git:history",
                "commit_hash": head_hash,
                "sentence_index": 0,
                "quote": f"Git history: {len(commits)} recent commits",
            }]
            return git_context, sources, fallback_ans
        except Exception as exc:
            logger.warning(f"[QaGitResolver] Ошибка извлечения истории коммитов: {exc}")
            return None, [], None

    @classmethod
    def _build_commit_fallback_answer(cls, lang: str, short_h: str, message: str, files_str: str) -> str:
        """Формирует детерминированный ответ о коммите без обращения к LLM."""
        clean_lang = str(lang or "ru").strip().lower()
        if clean_lang == "he":
            return f"בקומיט {short_h} ({message}) שונו הקבצים: {files_str}."
        if clean_lang == "en":
            return f"In commit {short_h} ({message}) the following files were modified: {files_str}."
        if clean_lang in ("ua", "uk"):
            return f"У коміті {short_h} ({message}) змінено файли: {files_str}."
        return f"В коммите {short_h} ({message}) изменены файлы: {files_str}."

    @classmethod
    def _build_history_fallback_answer(cls, lang: str, commits: List[Any]) -> str:
        """Формирует детерминированный ответ со списком коммитов."""
        clean_lang = str(lang or "ru").strip().lower()
        commit_summaries = ", ".join(f"{c.commit_hash[:7]} ({c.message})" for c in commits[:3])
        if clean_lang == "he":
            return f"היסטוריית הגרסאות כוללת קומיטים אחרונים: {commit_summaries}."
        if clean_lang == "en":
            return f"Recent Git history includes commits: {commit_summaries}."
        if clean_lang in ("ua", "uk"):
            return f"Історія версій містить останні коміти: {commit_summaries}."
        return f"История версий включает последние коммиты: {commit_summaries}."
