# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-assistant Apps AI_Assistant Core - Service File Authenticator
# =============================================================================
# Description:
#   Централизованный аутентификатор служебных и системных файлов рабочей области.
#   Определяет, является ли файл/директория служебным объектом инфраструктуры
#   (Obsidian, Git, система индексации, кэши, манифесты и авто-конспекты)
#   на основе многоуровневых критериев:
#   1. Аутентификатор имени (Name Authenticator):
#      - Префикс точки ('.' - dotfile convention): .gitignore, .obsidian,
#        .workspace, .tracked_sources.json, .<doc_name>.md.
#      - Префикс подчёркивания ('_' - obsidian infrastructure): _Knowledge_Base.md,
#        _Topics, _notes, _Index.md.
#      - Зарезервированные имена: README.md, assets, .gitkeep.
#   2. Аутентификатор содержимого (Content Authenticator / Header Signature):
#      - Маркер 'generator: ai_assistant_obsidian' или 'generator: ai_assistant_' в YAML frontmatter.
#      - Маркер '<!-- AI-OBSIDIAN-KNOWLEDGE' или '<!-- AI-SERVICE-FILE -->'.
#   3. Аутентификатор роли и манифеста (Role & Manifest):
#      - role == 'system' или is_system == True.
#   4. Помощник именования служебных файлов (Naming Helper):
#      - Формирование имени сопутствующего конспекта Obsidian с точкой:
#        f".{stem}.md" (dot-префикс как первичный файловый аутентификатор).
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.core.service_file_authenticator import ServiceFileAuthenticator
#
#     # Проверка по имени/пути
#     is_sys = ServiceFileAuthenticator.is_service_file(".gitignore")  # True
#     is_sys = ServiceFileAuthenticator.is_service_file(".דוד משה.md")  # True
#
#     # Проверка по содержимому
#     is_sys = ServiceFileAuthenticator.is_service_file("דוד משה.md", content_snippet="generator: ai_assistant_obsidian")  # True
#
#     # Генерация имени сопутствующего файла Obsidian
#     obs_name = ServiceFileAuthenticator.resolve_obsidian_companion_filename("דוד משה.txt")  # ".דוד משה.md"
#
# File: service_file_authenticator.py
# Project: ai-assistant
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-03 17:15:00
# =============================================================================

from __future__ import annotations
"""Аутентификатор и классификатор служебных/системных файлов рабочей области."""

from pathlib import Path
from typing import Any, Dict, Optional, Set, Union


class ServiceFileAuthenticator:
    """Централизованный аутентификатор служебных файлов рабочей области."""

    # Зарезервированные имена системных файлов и каталогов (регистронезависимые)
    RESERVED_NAMES: Set[str] = {
        "readme.md",
        "assets",
        "knowledge_base.md",
        "_knowledge_base.md",
        "_index.md",
        ".gitkeep",
        ".gitignore",
        ".workspace",
        ".obsidian",
        ".extracted_snapshots",
        ".tracked_sources.json",
    }

    # Зарезервированные имена системных директорий
    RESERVED_DIRS: Set[str] = {
        "assets",
        ".workspace",
        ".extracted_snapshots",
        ".obsidian",
        ".git",
        "_topics",
        "_notes",
        "_entities",
        "faiss_indices",
    }

    # Маркеры в содержимом файла, однозначно удостоверяющие служебный файл
    CONTENT_SIGNATURES: Set[str] = {
        "generator: ai_assistant_obsidian",
        "generator: ai_assistant_",
        "<!-- AI-OBSIDIAN-KNOWLEDGE",
        "<!-- AI-SERVICE-FILE -->",
    }

    @classmethod
    def is_service_name(cls, name_or_path: Union[str, Path]) -> bool:
        """Проверяет имя или путь на соответствие шаблонам служебных файлов (точка, подчеркивание, зарезервированные имена).

        Args:
            name_or_path: Имя файла, относительный или абсолютный путь.

        Returns:
            True, если имя начинается с '.' или '_' либо входит в список зарезервированных.
        """
        raw = str(name_or_path).replace("\\", "/").rstrip("/")
        if not raw:
            return False

        name = Path(raw).name.strip()
        name_lower = name.lower()

        # 1. Первичный файловый аутентификатор: префикс точки ('.' - dotfile convention)
        if name.startswith("."):
            return True

        # 2. Инфраструктурный префикс Obsidian: подчеркивание ('_')
        if name.startswith("_"):
            return True

        # 3. Временные файлы редакторов и операционной системы
        if name.startswith("~") or name.endswith("~"):
            return True

        # 4. Зарезервированные имена
        if name_lower in cls.RESERVED_NAMES:
            return True

        # 5. Проверка по компонентам относительного пути
        parts = [p.lower() for p in Path(raw).parts]
        for part in parts:
            if part.startswith(".") or part.startswith("_") or part in cls.RESERVED_DIRS:
                return True

        return False

    @classmethod
    def is_service_content(cls, content_or_snippet: str) -> bool:
        """Проверяет содержимое или заголовочный фрагмент файла на наличие цифровой подписи служебного генератора.

        Args:
            content_or_snippet: Текст файла или первые 512-1024 байта заголовка.

        Returns:
            True, если в тексте обнаружен маркер авто-генератора Obsidian или AI-Assistant.
        """
        if not content_or_snippet:
            return False

        for sig in cls.CONTENT_SIGNATURES:
            if sig in content_or_snippet:
                return True
        return False

    @classmethod
    def is_service_file(
        cls,
        path_or_item: Union[str, Path, Dict[str, Any]],
        content_snippet: Optional[str] = None,
        file_path: Optional[Path] = None,
    ) -> bool:
        """Комплексно проверяет, является ли объект служебным/системным файлом.

        Учитывает имя, путь, метаданные словаря (role, generator, is_system)
        и сигнатуру содержимого (YAML frontmatter / HTML-маркеры).

        Args:
            path_or_item: Строка пути, экземпляр Path или словарь описания элемента (item).
            content_snippet: Опциональный текстовый сниппет содержимого для проверки сигнатуры.
            file_path: Опциональный путь к файлу на диске для ленивого чтения заголовка при необходимости.

        Returns:
            True, если объект аутентифицирован как служебный/системный файл.
        """
        # Если передан словарь элемента из API или реестра
        if isinstance(path_or_item, dict):
            if path_or_item.get("is_system") is True or path_or_item.get("role") == "system":
                return True
            gen = str(path_or_item.get("generator") or "")
            if gen.startswith("ai_assistant_"):
                return True
            raw_path = str(
                path_or_item.get("rel_path")
                or path_or_item.get("name")
                or path_or_item.get("path")
                or ""
            )
            return cls.is_service_file(raw_path, content_snippet=content_snippet, file_path=file_path)

        # Проверка по имени и структуре пути
        p = Path(path_or_item)
        if cls.is_service_name(p):
            return True

        # Проверка переданного сниппета содержимого
        if content_snippet and cls.is_service_content(content_snippet):
            return True

        # Ленивое чтение заголовка файла с диска, если это .md файл
        target_file = file_path or (p if p.is_file() else None)
        if target_file and target_file.is_file() and target_file.suffix.lower() == ".md":
            try:
                with target_file.open("r", encoding="utf-8", errors="ignore") as f:
                    snippet = f.read(512)
                if cls.is_service_content(snippet):
                    return True
            except Exception:
                pass

        return False

    @classmethod
    def resolve_obsidian_companion_filename(cls, doc_id: str) -> str:
        """Формирует имя сопутствующего конспекта Obsidian с первичным аутентификатором-точкой.

        Для не-markdown файлов (.txt, .docx, .pdf и т.д.) имя формируется как
        '.<stem>.md' (например, '.דוד משה.md'), чтобы файл гарантированно
        распознавался файловой системой и проводником как скрытый служебный dotfile.
        Для файлов, изначально являющихся .md, возвращается исходное имя.

        Args:
            doc_id: Идентификатор или относительный путь документа (например, 'דוד משה.txt').

        Returns:
            Имя файла сопутствующего конспекта Obsidian (например, '.דוד משה.md').
        """
        clean_rel = str(doc_id).replace("\\", "/").lstrip("/")
        p = Path(clean_rel)
        if p.suffix.lower() == ".md":
            # Пользовательский markdown-документ сохраняет исходное имя
            return p.name

        # Для вторичных конспектов не-markdown файлов добавляем точку-префикс
        stem = p.stem.strip()
        # Если имя уже начинается с точки, не дублируем её
        prefix = "" if stem.startswith(".") else "."
        return f"{prefix}{stem}.md"

    @classmethod
    def is_obsidian_companion_note(cls, name_or_path: Union[str, Path]) -> bool:
        """Проверяет, является ли имя сопутствующим теневым конспектом Obsidian.

        Args:
            name_or_path: Имя файла или путь.

        Returns:
            True, если файл имеет шаблон .<name>.md или начинается с точки и имеет суффикс .md.
        """
        p = Path(name_or_path)
        return p.suffix.lower() == ".md" and p.name.startswith(".")
