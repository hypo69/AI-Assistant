# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-assistant Workspace Prompt Generator
# =============================================================================
# Description:
#   Сервис динамической генерации контекстных вопросов и быстрых подсказок
#   (Prompt Chips) на основе содержимого рабочей области: истории Git-коммитов,
#   проиндексированных документов и сущностей базы знаний с мультиязычной
#   поддержкой (ru, en, he, uk).
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.core.workspace_prompt_generator import WorkspacePromptGenerator
#     gen = WorkspacePromptGenerator(workspace_manager)
#     data = await gen.generate_prompts(workspace_id="ws1", language="he", limit=3)
#
# File: workspace_prompt_generator.py
# Project: ai-assistant
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 13:50:00
# =============================================================================

from __future__ import annotations
"""Генератор контекстных подсказок и вопросов по содержанию рабочей области."""

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional
from logger import logger

# Поддерживаемые языки
VALID_LANGUAGES = ("ru", "en", "he", "uk")

# Статические стартовые вопросы по умолчанию (Fallback для пустых областей)
FALLBACK_PROMPTS: Dict[str, List[Dict[str, str]]] = {
    "ru": [
        {"icon": "bi-lightbulb", "text": "Что содержит текущая рабочая область?", "type": "overview"},
        {"icon": "bi-diagram-2", "text": "Покажи структуру файлов и документов", "type": "structure"},
        {"icon": "bi-git", "text": "Какие последние изменения зафиксированы?", "type": "history"},
    ],
    "en": [
        {"icon": "bi-lightbulb", "text": "What does this workspace contain?", "type": "overview"},
        {"icon": "bi-diagram-2", "text": "Show file and document structure", "type": "structure"},
        {"icon": "bi-git", "text": "What are the latest changes recorded?", "type": "history"},
    ],
    "he": [
        {"icon": "bi-lightbulb", "text": "מה מכילה סביבת העבודה הנוכחית?", "type": "overview"},
        {"icon": "bi-diagram-2", "text": "הצג את מבנה הקבצים והמסמכים", "type": "structure"},
        {"icon": "bi-git", "text": "מהם השינויים האחרונים שנרשמו?", "type": "history"},
    ],
    "uk": [
        {"icon": "bi-lightbulb", "text": "Що містить поточна робоча область?", "type": "overview"},
        {"icon": "bi-diagram-2", "text": "Покажи структуру файлів та документів", "type": "structure"},
        {"icon": "bi-git", "text": "Які останні зміни зафіксовано?", "type": "history"},
    ],
}

# Шаблоны вопросов по коммиту
COMMIT_PROMPT_TEMPLATES: Dict[str, str] = {
    "ru": "Какие изменения зафиксированы в коммите {hash}?",
    "en": "What changes are recorded in commit {hash}?",
    "he": "אילו שינויים נרשמו ב-commit {hash}?",
    "uk": "Які зміни зафіксовано в коміті {hash}?",
}

# Шаблоны вопросов по измененному файлу
FILE_CHANGE_TEMPLATES: Dict[str, str] = {
    "ru": "Что изменилось в файле «{filename}»?",
    "en": "What changed in file \"{filename}\"?",
    "he": "מה השתנה בקובץ «{filename}»?",
    "uk": "Що змінилося у файлі «{filename}»?",
}

# Шаблоны вопросов по документу
DOCUMENT_PROMPT_TEMPLATES: Dict[str, str] = {
    "ru": "Что содержит документ «{doc_name}»?",
    "en": "What does document \"{doc_name}\" contain?",
    "he": "מה מכיל המסמך «{doc_name}»?",
    "uk": "Що містить документ «{doc_name}»?",
}

# Шаблоны вопросов по сущности базы знаний
ENTITY_PROMPT_TEMPLATES: Dict[str, str] = {
    "ru": "Какие факты зафиксированы о «{entity_name}»?",
    "en": "What facts are recorded about \"{entity_name}\"?",
    "he": "אילו עובדות נרשמו לגבי «{entity_name}»?",
    "uk": "Які факти зафіксовано про «{entity_name}»?",
}

# Шаблоны уточняющих вопросов после ответа (Follow-up)
FOLLOW_UP_TEMPLATES: Dict[str, str] = {
    "ru": "Подробнее об источнике «{source_name}»",
    "en": "More details about source \"{source_name}\"",
    "he": "פרטים נוספים לגבי המקור «{source_name}»",
    "uk": "Докладніше про джерело «{source_name}»",
}


class WorkspacePromptGenerator:
    """Генератор контекстных быстрых вопросов по содержимому рабочей области."""

    def __init__(self, workspace_manager: Any) -> None:
        """Инициализирует генератор.

        Args:
            workspace_manager: Экземпляр WorkspaceManager с доступом к store и Git.
        """
        self.wm = workspace_manager

    def _normalize_lang(self, lang: Optional[str]) -> str:
        """Нормализует код языка к одному из поддерживаемых (ru, en, he, uk).

        Args:
            lang: Входной код языка.

        Returns:
            str: Нормализованный код.
        """
        if not lang:
            return "ru"
        clean = lang.lower().strip()[:2]
        return clean if clean in VALID_LANGUAGES else "ru"

    async def generate_prompts(
        self,
        workspace_id: str,
        language: str = "ru",
        limit: int = 3,
    ) -> Dict[str, Any]:
        """Формирует контекстные вопросы на основе содержимого рабочей области.

        Args:
            workspace_id: Идентификатор целевой рабочей области.
            language: Предпочтительный язык (ru, en, he, uk).
            limit: Максимальное число вопросов (по умолчанию 3).

        Returns:
            Dict[str, Any]: Словарь со статусом, языком, источником и списком подсказок.
        """
        lang = self._normalize_lang(language)
        prompts: List[Dict[str, str]] = []

        try:
            # 1. Извлекаем последние коммиты и затронутые файлы
            commits: List[Dict[str, Any]] = []
            try:
                commits = await self.wm.get_workspace_commits(workspace_id, limit=3)
            except Exception as git_exc:
                logger.debug(f"[WorkspacePromptGenerator] Git коммиты недоступны для {workspace_id}: {git_exc}")

            if commits:
                top_commit = commits[0]
                commit_hash = str(top_commit.get("commit_hash", ""))[:7]
                files = top_commit.get("files") or top_commit.get("changed_files") or []

                if files and isinstance(files, list):
                    first_file = Path(str(files[0])).name
                    tmpl_file = FILE_CHANGE_TEMPLATES.get(lang, FILE_CHANGE_TEMPLATES["ru"])
                    prompts.append({
                        "icon": "bi-git",
                        "text": tmpl_file.format(filename=first_file),
                        "type": "git_file",
                    })
                elif commit_hash:
                    tmpl_commit = COMMIT_PROMPT_TEMPLATES.get(lang, COMMIT_PROMPT_TEMPLATES["ru"])
                    prompts.append({
                        "icon": "bi-git",
                        "text": tmpl_commit.format(hash=commit_hash),
                        "type": "git_commit",
                    })

            # 2. Извлекаем проиндексированные документы
            docs: List[Dict[str, Any]] = []
            try:
                if hasattr(self.wm, "store") and hasattr(self.wm.store, "list_documents"):
                    docs = await asyncio.to_thread(self.wm.store.list_documents, workspace_id)
            except Exception as doc_exc:
                logger.debug(f"[WorkspacePromptGenerator] Ошибка получения документов {workspace_id}: {doc_exc}")

            if docs:
                for doc in docs[:2]:
                    raw_title = doc.get("title") or doc.get("filename") or doc.get("document_id") or ""
                    clean_title = Path(str(raw_title)).name
                    if clean_title and len(clean_title) > 1:
                        tmpl_doc = DOCUMENT_PROMPT_TEMPLATES.get(lang, DOCUMENT_PROMPT_TEMPLATES["ru"])
                        prompts.append({
                            "icon": "bi-file-earmark-text",
                            "text": tmpl_doc.format(doc_name=clean_title),
                            "type": "document",
                        })
                        if len(prompts) >= limit:
                            break

            # 3. Извлекаем извлеченные сущности базы знаний
            entities: List[Dict[str, Any]] = []
            try:
                if hasattr(self.wm, "store") and hasattr(self.wm.store, "list_entities"):
                    entities = await asyncio.to_thread(self.wm.store.list_entities, workspace_id=workspace_id)
            except Exception as ent_exc:
                logger.debug(f"[WorkspacePromptGenerator] Ошибка получения сущностей {workspace_id}: {ent_exc}")

            if entities and len(prompts) < limit:
                for ent in entities[:4]:
                    ent_name = ent.get("lemma") or ent.get("text") or ""
                    if ent_name and len(ent_name) > 2 and not any(ent_name in p["text"] for p in prompts):
                        tmpl_ent = ENTITY_PROMPT_TEMPLATES.get(lang, ENTITY_PROMPT_TEMPLATES["ru"])
                        prompts.append({
                            "icon": "bi-lightbulb",
                            "text": tmpl_ent.format(entity_name=ent_name),
                            "type": "entity",
                        })
                        if len(prompts) >= limit:
                            break

        except Exception as exc:
            logger.warning(f"[WorkspacePromptGenerator] Сбой генерации подсказок для '{workspace_id}': {exc}")

        # 4. Если контента недостаточно — дополняем или заменяем на fallback
        if not prompts:
            fallback_list = FALLBACK_PROMPTS.get(lang, FALLBACK_PROMPTS["ru"])
            return {
                "status": "ok",
                "workspace_id": workspace_id,
                "language": lang,
                "source": "fallback",
                "prompts": fallback_list[:limit],
            }

        return {
            "status": "ok",
            "workspace_id": workspace_id,
            "language": lang,
            "source": "content",
            "prompts": prompts[:limit],
        }

    def generate_follow_up_prompts(
        self,
        sources: List[Dict[str, Any]],
        entities: List[Dict[str, Any]],
        language: str = "ru",
        limit: int = 2,
    ) -> List[Dict[str, str]]:
        """Генерирует последующие уточняющие вопросы (Follow-up) после ответа модели.

        Args:
            sources: Источники, найденные в ответе.
            entities: Сущности из ответа или контекста.
            language: Код языка.
            limit: Максимальное количество.

        Returns:
            List[Dict[str, str]]: Список подсказок с иконками и текстом.
        """
        lang = self._normalize_lang(language)
        follow_ups: List[Dict[str, str]] = []

        tmpl_src = FOLLOW_UP_TEMPLATES.get(lang, FOLLOW_UP_TEMPLATES["ru"])
        for s in sources:
            doc_id = s.get("document_id") or ""
            clean_doc = Path(str(doc_id)).name
            if clean_doc and len(clean_doc) > 1:
                follow_ups.append({
                    "icon": "bi-arrow-right-circle",
                    "text": tmpl_src.format(source_name=clean_doc),
                    "type": "follow_up_source",
                })
                if len(follow_ups) >= limit:
                    break

        tmpl_ent = ENTITY_PROMPT_TEMPLATES.get(lang, ENTITY_PROMPT_TEMPLATES["ru"])
        if len(follow_ups) < limit and entities:
            for ent in entities:
                ent_name = ent.get("lemma") or ent.get("text") or ""
                if ent_name and len(ent_name) > 2:
                    follow_ups.append({
                        "icon": "bi-question-circle",
                        "text": tmpl_ent.format(entity_name=ent_name),
                        "type": "follow_up_entity",
                    })
                    if len(follow_ups) >= limit:
                        break

        return follow_ups[:limit]
