# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Core - Multilingual NLP Analyzers
# =============================================================================
# Description:
#   Единый протокол LanguageAnalyzer, детектор языка, сегментатор предложений,
#   извлечение фактов из таблиц Markdown (Excel/CSV/Google Sheets) и реестр
#   языковых модулей AnalyzerRegistry с поддержкой смешанных мультиязычных текстов.
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.core.nlp_analyzers import AnalyzerRegistry
#
#     registry = AnalyzerRegistry()
#     result = registry.analyze_text("Мама мыла раму.", document_id="mama.txt")
#     he_res = registry.analyze_text("לדוד משה היתה חווה", document_id="farm.txt")
#
# File: nlp_analyzers.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 13:59:00
# =============================================================================

from __future__ import annotations
"""Фасад и реестр мультиязычных NLP-анализаторов (RU, HE, EN) с поддержкой таблиц."""

import re
from typing import Any, Dict, List, Optional, Protocol, Tuple

from apps.ai_assistant.core.nlp.english import EnglishAnalyzer
from apps.ai_assistant.core.nlp.hebrew import (
    HebrewAnalyzer,
    normalize_hebrew,
    strip_hebrew_article,
)
from apps.ai_assistant.core.nlp.russian import RussianAnalyzer, RussianMorphology

_RE_HEBREW_CHARS = re.compile(r"[\u0590-\u05FF]")
_RE_RUSSIAN_CHARS = re.compile(r"[а-яА-ЯёЁ]")
_RE_ENGLISH_CHARS = re.compile(r"[a-zA-Z]")
_RE_SENTENCE_SPLIT = re.compile(r"[^.!?\n]+[.!?]*", re.UNICODE)


class LanguageAnalyzer(Protocol):
    """Единый интерфейс подключаемых языковых анализаторов (ТЗ п. 3.3)."""

    language_code: str
    analyzer_name: str
    version: str

    def analyze(self, text: str, document_id: str = "unknown") -> Dict[str, Any]:
        """Выполняет морфолого-синтаксический анализ текста и извлечение фактов."""
        ...


def detect_language(text: str) -> str:
    """Определяет основной язык текста по директиве lang= или символьным диапазонам Unicode."""
    if not text or not text.strip():
        return "unknown"

    for line in text[:400].splitlines():
        cl = line.strip().lower()
        if cl.startswith("lang="):
            val = cl.split("=", 1)[1].strip()
            if val in ("ru", "he", "en", "ua", "uk"):
                return "ua" if val == "uk" else val
        elif cl.startswith("language:"):
            val = cl.split(":", 1)[1].strip().strip('"\'')
            if val in ("ru", "he", "en", "ua", "uk"):
                return "ua" if val == "uk" else val

    sample = text[:50_000]
    he_count = len(_RE_HEBREW_CHARS.findall(sample))
    ru_count = len(_RE_RUSSIAN_CHARS.findall(sample))
    en_count = len(_RE_ENGLISH_CHARS.findall(sample))

    if he_count > 0 and he_count >= ru_count and he_count >= en_count:
        return "he"
    if ru_count > 0 and ru_count >= he_count and ru_count >= en_count:
        return "ru"
    if en_count > 0:
        return "en"
    return "ru"


def split_sentences(text: str) -> List[Tuple[int, str, int, int]]:
    """Разбивает текст на предложения с сохранением индекса и символьных координат."""
    if not text:
        return []

    results: List[Tuple[int, str, int, int]] = []
    idx = 0
    for match in _RE_SENTENCE_SPLIT.finditer(text):
        raw_sent = match.group(0)
        stripped = raw_sent.strip()
        if not stripped:
            continue
        start_pos = match.start() + raw_sent.find(stripped)
        end_pos = start_pos + len(stripped)
        results.append((idx, stripped, start_pos, end_pos))
        idx += 1
    return results


def extract_markdown_table_facts(text: str, document_id: str = "unknown") -> List[Dict[str, Any]]:
    """Извлекает структурированные факты из таблиц Markdown (после конвертации Excel/CSV/DOCX/Google Sheets)."""
    if "|" not in text:
        return []

    lines = text.splitlines()
    headers: List[str] = []
    facts: List[Dict[str, Any]] = []
    sent_counter = 1000

    for line in lines:
        stripped = line.strip()
        if not (stripped.startswith("|") and stripped.endswith("|")):
            headers = []
            continue

        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if not cells or all(not c for c in cells):
            continue

        if all(set(c) <= {"-", ":", " "} and "-" in c for c in cells if c):
            continue

        if not headers:
            headers = cells
            continue

        subj_cell = cells[0].strip() if cells else ""
        if not subj_cell or len(cells) < 2:
            continue

        row_lang = detect_language(stripped)
        if row_lang == "unknown":
            row_lang = "ru"

        subj_lemma = (
            RussianMorphology.analyze_noun(subj_cell.split()[-1])["lemma"]
            if row_lang == "ru"
            else (strip_hebrew_article(subj_cell) if row_lang == "he" else subj_cell.lower())
        )

        for col_idx in range(1, min(len(cells), len(headers))):
            col_header = headers[col_idx].strip()
            col_val = cells[col_idx].strip()
            if not col_val or col_val == "-":
                continue

            obj_lemma = (
                RussianMorphology.analyze_noun(col_val.split()[-1])["lemma"]
                if row_lang == "ru"
                else (strip_hebrew_article(col_val) if row_lang == "he" else col_val.lower())
            )
            rel_lemma = col_header.lower() if col_header else "has"

            facts.append({
                "fact_type": "possession",
                "language": row_lang,
                "relation": rel_lemma,
                "owner": {
                    "text": subj_cell,
                    "normalized": subj_cell.lower() if row_lang != "he" else subj_cell,
                    "lemma": subj_lemma,
                    "entity_type": "entity",
                },
                "possessed_entity": {
                    "text": col_val,
                    "normalized": col_val.lower() if row_lang != "he" else col_val,
                    "lemma": obj_lemma,
                    "attribute": col_header,
                    "entity_type": "property",
                },
                "is_negated": False,
                "confidence": 0.9,
                "source": {
                    "document_id": document_id,
                    "sentence_index": sent_counter,
                    "char_start": 0,
                    "char_end": len(stripped),
                    "quote": stripped,
                },
            })
            sent_counter += 1

    return facts


class AnalyzerRegistry:
    """Реестр подключаемых языковых анализаторов (ТЗ п. 3.3, 6.3)."""

    def __init__(self) -> None:
        """Инициализирует реестр стандартными анализаторами (ru, he, en)."""
        self._analyzers: Dict[str, LanguageAnalyzer] = {}
        self.register(RussianAnalyzer())
        self.register(HebrewAnalyzer())
        self.register(EnglishAnalyzer())

    def register(self, analyzer: LanguageAnalyzer) -> None:
        """Регистрирует новый языковой модуль без изменения ядра системы."""
        self._analyzers[analyzer.language_code] = analyzer

    def get_analyzer(self, language_code: str) -> LanguageAnalyzer:
        """Возвращает анализатор по коду языка (или русский по умолчанию)."""
        return self._analyzers.get(language_code, self._analyzers["ru"])

    def analyze_text(
        self,
        text: str,
        document_id: str = "unknown",
        language: Optional[str] = "",
    ) -> Dict[str, Any]:
        """Определяет язык текста (включая смешанные предложения и таблицы) и выполняет разбор."""
        doc_lang = language if (language and language in self._analyzers) else detect_language(text)
        primary_analyzer = self.get_analyzer(doc_lang)
        res = primary_analyzer.analyze(text, document_id=document_id)

        if not language:
            seen_fact_quotes = {f.get("source", {}).get("quote") for f in res.get("facts", [])}
            for sent_idx, sent_text, c_start, c_end in split_sentences(text):
                s_lang = detect_language(sent_text)
                if s_lang in self._analyzers and s_lang != doc_lang:
                    sub_res = self.get_analyzer(s_lang).analyze(sent_text, document_id=document_id)
                    for sub_fact in sub_res.get("facts", []):
                        src = sub_fact.get("source", {})
                        src["sentence_index"] = sent_idx
                        src["char_start"] = c_start
                        src["char_end"] = c_end
                        if src.get("quote") not in seen_fact_quotes:
                            res.setdefault("facts", []).append(sub_fact)
                            seen_fact_quotes.add(src.get("quote"))
                    for sub_ent in sub_res.get("entities", []):
                        res.setdefault("entities", []).append(sub_ent)

        table_facts = extract_markdown_table_facts(text, document_id=document_id)
        if table_facts:
            res.setdefault("facts", []).extend(table_facts)

        return res

    def list_modules(self) -> List[Dict[str, Any]]:
        """Возвращает конфигурацию и возможности всех подключенных языковых модулей (ТЗ п. 6.3)."""
        return [
            {
                "language_code": code,
                "analyzer_name": getattr(a, "analyzer_name", type(a).__name__),
                "version": getattr(a, "version", "1.0.0"),
                "supported_operations": [
                    "language_detection",
                    "sentence_segmentation",
                    "tokenization",
                    "lemmatization",
                    "morphological_analysis",
                    "fact_extraction_action",
                    "fact_extraction_possession",
                    "markdown_table_extraction",
                    "grammatical_inflection",
                    "coreference_resolution",
                ],
                "supported_modes": ["local_only", "local_first", "cloud_assist", "cloud_enrich"],
                "confidence_threshold": 0.75,
            }
            for code, a in self._analyzers.items()
        ]


__all__ = [
    "LanguageAnalyzer",
    "detect_language",
    "split_sentences",
    "extract_markdown_table_facts",
    "RussianMorphology",
    "RussianAnalyzer",
    "HebrewAnalyzer",
    "normalize_hebrew",
    "strip_hebrew_article",
    "EnglishAnalyzer",
    "AnalyzerRegistry",
]
