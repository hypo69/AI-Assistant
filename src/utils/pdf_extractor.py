# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant UTILS - Document & PDF Extractor
# =============================================================================
# Description:
#   Универсальный модуль извлечения текста из документов (PDF, DOCX, TXT).
#
# File: pdf_extractor.py
# Package: src.utils
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 18:26:00
# =============================================================================

from __future__ import annotations

"""Модуль безопасного извлечения текста из документов PDF и других форматов."""

from pathlib import Path
from typing import Optional, Union

from logger import logger
from src.utils.pdf import extract_pdf_text


async def extract_document_text(file_path: Union[str, Path]) -> str:
    """Асинхронно извлекает текст из документа (PDF, текстовых файлов, docx).

    Args:
        file_path (Union[str, Path]): Путь к файлу.

    Returns:
        str: Извлечённый текст или пустая строка при ошибке.
    """
    path = Path(file_path)
    if not path.is_file():
        logger.warning(f"[extract_document_text] Файл не существует: {path}")
        return ""

    ext = path.suffix.lower()
    try:
        if ext == ".pdf":
            text = extract_pdf_text(path)
            return text or ""
        elif ext in (".txt", ".md", ".json", ".csv"):
            return path.read_text(encoding="utf-8", errors="ignore")
        elif ext == ".docx":
            from src.utils.docx import extract_docx_text
            text = extract_docx_text(path, as_markdown=True)
            return text or ""
        else:
            return path.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:
        logger.error(f"[extract_document_text] Ошибка извлечения текста из {path.name}: {exc}")
        return ""


__all__ = ["extract_pdf_text", "extract_document_text"]
