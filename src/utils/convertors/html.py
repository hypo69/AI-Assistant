# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin UTILS - Html Module
# =============================================================================
# Description:
#   Утилиты конвертации и парсинга HTML: экранирование, unescape,
#   преобразование в словари/SimpleNamespace и опциональный экспорт в PDF.
#
# Usage Examples:
#   Python API:
#     from src.utils.convertors.html import html2escape, escape2html, html2dict
#
#     escaped = html2escape("<p>Hello</p>")
#     data = html2dict("<h1>Заголовок</h1>")
#
# File: html.py
# Project: ai-windows-admin
# Package: src.utils.convertors
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 19:00:00
# =============================================================================

"""Утилиты конвертации и парсинга HTML."""

from __future__ import annotations

import html
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, Optional, Union

from logger import logger


def html2escape(input_str: str) -> str:
    """Преобразует HTML-символы в escape-последовательности.

    Args:
        input_str: Исходная строка HTML.

    Returns:
        str: Строка с экранированными символами.
    """
    return html.escape(input_str)


def escape2html(input_str: str) -> str:
    """Преобразует escape-последовательности обратно в HTML.

    Args:
        input_str: Строка с escape-последовательностями.

    Returns:
        str: Восстановленная HTML-строка.
    """
    return html.unescape(input_str)


def html2dict(html_str: str) -> Dict[str, str]:
    """Преобразует HTML в словарь тег -> текстовое содержимое.

    Args:
        html_str: HTML-разметка.

    Returns:
        Dict[str, str]: Словарь тегов и их значений.
    """

    class HTMLToDictParser(HTMLParser):

        def __init__(self) -> None:
            super().__init__()
            self.result: Dict[str, str] = {}
            self.current_tag: Optional[str] = None

        def handle_starttag(self, tag: str, attrs: list) -> None:
            self.current_tag = tag

        def handle_endtag(self, tag: str) -> None:
            self.current_tag = None

        def handle_data(self, data: str) -> None:
            if self.current_tag:
                self.result[self.current_tag] = data.strip()

    parser = HTMLToDictParser()
    parser.feed(html_str)
    return parser.result


def html2ns(html_str: str) -> SimpleNamespace:
    """Преобразует HTML в объект SimpleNamespace.

    Args:
        html_str: HTML-разметка.

    Returns:
        SimpleNamespace: Объект с атрибутами тегов.
    """
    html_dict = html2dict(html_str)
    return SimpleNamespace(**html_dict)


def html2pdf(html_str: str, pdf_file: Union[str, Path]) -> Optional[bool]:
    """Конвертирует HTML-контент в PDF-файл с использованием WeasyPrint или xhtml2pdf.

    Args:
        html_str: Исходная HTML-разметка.
        pdf_file: Путь к целевому файлу PDF.

    Returns:
        Optional[bool]: True при успешной генерации, None при ошибке.
    """
    # 1. Попытка через WeasyPrint
    try:
        from weasyprint import HTML
        HTML(string=html_str).write_pdf(str(pdf_file))
        return True
    except (ImportError, Exception):
        pass

    # 2. Попытка через xhtml2pdf (pisa)
    try:
        from xhtml2pdf import pisa
        with open(pdf_file, "wb") as f:
            pisa_status = pisa.CreatePDF(html_str, dest=f)
        return not pisa_status.err
    except Exception as exc:
        logger.error(f"Ошибка при генерации PDF через xhtml2pdf/weasyprint: {exc}")
        return None
