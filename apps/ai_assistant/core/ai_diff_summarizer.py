# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Core - AI Diff Summarizer & Verification
# =============================================================================
# Description:
#   Интеллектуальная суммаризация диффов кода и двухшаговый контур верификации
#   (Candidate Proposal -> Validation Pipeline) для предотвращения инъекций,
#   утечек секретов и недостоверных архитектурных фактов в WikiLLM.
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.core.ai_diff_summarizer import AIDiffSummarizer
#
#     summarizer = AIDiffSummarizer()
#     proposal = summarizer.propose_annotation(commit_hash="a1b2c3", diff_text="...", author="admin")
#     is_valid, sanitized_proposal, error = summarizer.validate_candidate(proposal)
#
# File: ai_diff_summarizer.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 08:30:00
# =============================================================================

from __future__ import annotations
"""Суммаризация диффов и двухшаговый контур верификации фактов."""

import re
from typing import Any, Dict, List, Optional, Tuple

from logger import logger
from apps.ai_assistant.api.schemas import AnnotationRequest, AnnotationResponse


class AIDiffSummarizer:
    """Анализатор диффов с двухшаговым контуром верификации фактов."""

    # Регулярные выражения для выявления секретов и ключей
    SECRET_PATTERNS = [
        re.compile(r"(?i)(?:api_key|apikey|secret|token|password|passwd|bearer)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.]{12,})['\"]?"),
        re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----"),
        re.compile(r"(?i)ghp_[a-zA-Z0-9]{36}"),
        re.compile(r"(?i)AIza[0-9A-Za-z-_]{35}"),
    ]

    # Шаблоны Prompt Injection
    INJECTION_PATTERNS = [
        re.compile(r"(?i)ignore\s+(?:all\s+)?previous\s+instructions"),
        re.compile(r"(?i)system\s*:\s*you\s+are"),
        re.compile(r"(?i)<\s*script\b"),
        re.compile(r"(?i)exec\s*\(|eval\s*\("),
        re.compile(r"(?i)drop\s+table|delete\s+from"),
    ]

    def __init__(self) -> None:
        """Инициализирует анализатор диффов."""
        pass

    def summarize_diff(self, diff_text: str, file_path: str = "") -> str:
        """Формирует понятное резюме изменений на основе структуры diff.

        Args:
            diff_text: Сырой текст git diff.
            file_path: Опциональный путь к файлу.

        Returns:
            str: Сводка изменений на русском языке.
        """
        if not diff_text:
            return "Изменения отсутствуют или файл не был модифицирован."

        added_lines: List[str] = []
        removed_lines: List[str] = []
        changed_functions: List[str] = []

        for line in diff_text.splitlines():
            if line.startswith("@@"):
                func_match = re.search(r"@@\s+.*?\s+@@\s*(def\s+[a-zA-Z0-9_]+|class\s+[a-zA-Z0-9_]+)?", line)
                if func_match and func_match.group(1):
                    changed_functions.append(func_match.group(1).strip())
            elif line.startswith("+") and not line.startswith("+++"):
                stripped = line[1:].strip()
                if stripped:
                    added_lines.append(stripped)
            elif line.startswith("-") and not line.startswith("---"):
                stripped = line[1:].strip()
                if stripped:
                    removed_lines.append(stripped)

        total_added = len(added_lines)
        total_removed = len(removed_lines)

        summary_parts = [
            f"Файл: {file_path or 'указанный файл'}."
            f" Добавлено строк: {total_added}, удалено: {total_removed}."
        ]

        if changed_functions:
            unique_funcs = list(dict.fromkeys(changed_functions))[:5]
            summary_parts.append(f"Затронутые функции и классы: {', '.join(unique_funcs)}.")

        if total_added > 0 and total_removed == 0:
            summary_parts.append("Тип изменения: добавление новой функциональности или расширение конфигурации.")
        elif total_added == 0 and total_removed > 0:
            summary_parts.append("Тип изменения: рефакторинг и удаление устаревшего кода.")
        else:
            summary_parts.append("Тип изменения: модернизация логики работы и исправление поведения.")

        return " ".join(summary_parts)

    def propose_annotation(
        self,
        commit_hash: str,
        diff_text: str,
        file_path: str = "",
        author: str = "system",
    ) -> Dict[str, Any]:
        """Шаг 1: Candidate Proposal — Формирование предварительного проекта аннотации.

        Args:
            commit_hash: Хэш коммита.
            diff_text: Текст диффа.
            file_path: Путь к файлу.
            author: Инициатор предложения.

        Returns:
            Dict[str, Any]: Проект аннотации (кандидат).
        """
        summary = self.summarize_diff(diff_text, file_path=file_path)
        relation = "modifies"
        if any(kw in summary.lower() for kw in ["исправление", "ошибк", "почин"]):
            relation = "fixes"

        candidate = {
            "source_id": commit_hash,
            "target_id": file_path or "codebase",
            "relation_type": relation,
            "valid_from": commit_hash,
            "confidence": 0.9,
            "provenance": f"ai_diff_summarizer (author: {author})",
            "summary": summary,
            "author": author,
        }
        return candidate

    def validate_candidate(self, candidate: Dict[str, Any]) -> Tuple[bool, Dict[str, Any], Optional[str]]:
        """Шаг 2: Validation Pipeline — Проверка источника, санитизация от инъекций и секретов.

        Args:
            candidate: Кандидатная запись для базы знаний.

        Returns:
            Tuple[bool, Dict[str, Any], Optional[str]]:
                - Успешность валидации (True/False)
                - Очищенные данные
                - Сообщение об ошибке (если валидация не пройдена)
        """
        sanitized = dict(candidate)

        # 1. Проверка наличия обязательных полей
        if not candidate.get("source_id") or not candidate.get("target_id"):
            return False, sanitized, "Отсутствуют обязательные идентификаторы source_id или target_id."

        # 2. Проверка Prompt Injection в текстовых полях
        text_to_check = f"{candidate.get('summary', '')} {candidate.get('target_id', '')}"
        for pattern in self.INJECTION_PATTERNS:
            if pattern.search(text_to_check):
                logger.warning(f"[AIDiffSummarizer] Обнаружена попытка Prompt Injection в кандидате: {pattern.pattern}")
                return False, sanitized, "Отклонено политикой безопасности: обнаружены недопустимые команды или инъекции."

        # 3. Фильтрация и маскирование секретов
        summary = sanitized.get("summary", "")
        for pattern in self.SECRET_PATTERNS:
            if pattern.search(summary):
                logger.info("[AIDiffSummarizer] В аннотации обнаружены секреты; выполняется маскирование.")
                summary = pattern.sub(r"***REDACTED_SECRET***", summary)

        sanitized["summary"] = summary
        return True, sanitized, None
