# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Core NLP - English Module
# =============================================================================
# Description:
#   Языковой NLP-адаптер для английского языка (EnglishAnalyzer).
#   Поддерживает разбор конструкций SVO (Subject-Verb-Object), отрицаний
#   (not / did not / does not / no) и отношений принадлежности (has / had / owns).
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.core.nlp.english import EnglishAnalyzer
#
#     analyzer = EnglishAnalyzer()
#     res = analyzer.analyze("Mom washed the frame.", document_id="en.txt")
#
# File: core/nlp/english.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.core.nlp
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-25 23:15:00
# =============================================================================

from __future__ import annotations
"""Английский языковой модуль морфолого-синтаксического анализа."""

from typing import Any, Dict, List, Optional

_EN_PRONOUNS_SUBJ = {"he", "she", "they", "it"}


class EnglishAnalyzer:
    """Базовый языковой NLP-адаптер для английского языка (подтверждение расширяемости ядра)."""

    language_code: str = "en"
    analyzer_name: str = "EnglishSVOAnalyzer"
    version: str = "1.2.0"

    def analyze(self, text: str, document_id: str = "unknown") -> Dict[str, Any]:
        """Анализирует английский текст и извлекает базовые факты SVO и possession с разрешением кореференции."""
        from apps.ai_assistant.core.nlp_analyzers import split_sentences

        sentences_raw = split_sentences(text)
        facts: List[Dict[str, Any]] = []
        entities: List[Dict[str, Any]] = []
        seen_entities = set()
        last_antecedent: Optional[Dict[str, str]] = None

        for sent_idx, sent_text, char_start, char_end in sentences_raw:
            clean = sent_text.strip().rstrip(".!?")
            words = clean.split()
            lower_words = [w.lower() for w in words]
            is_negated = any(neg in lower_words for neg in ("not", "never", "no", "didn't", "doesn't", "hasn't", "hadn't"))
            filtered_words = [w for w in words if w.lower() not in ("not", "never", "did", "does", "didn't", "doesn't", "the", "a", "an", "also", "then")]

            if len(filtered_words) >= 3:
                subj = filtered_words[0]
                if subj.lower() in _EN_PRONOUNS_SUBJ and last_antecedent is not None:
                    subj = last_antecedent["text"]
                elif subj.lower() not in _EN_PRONOUNS_SUBJ:
                    last_antecedent = {"text": subj, "lemma": subj.lower()}

                pred = filtered_words[1].lower()
                obj = " ".join(filtered_words[2:])
                for ent_val in (subj, obj):
                    norm_e = ent_val.lower()
                    if norm_e and norm_e not in seen_entities:
                        seen_entities.add(norm_e)
                        entities.append({
                            "text": ent_val,
                            "normalized": norm_e,
                            "lemma": norm_e,
                            "entity_type": "entity",
                            "language": "en",
                        })

                if pred in ("has", "had", "owns", "owned", "have"):
                    facts.append({
                        "fact_type": "possession",
                        "language": "en",
                        "relation": "has",
                        "owner": {"text": subj, "normalized": subj.lower(), "lemma": subj.lower(), "entity_type": "person"},
                        "possessed_entity": {"text": obj, "normalized": obj.lower(), "lemma": obj.lower(), "entity_type": "property"},
                        "is_negated": is_negated,
                        "confidence": 0.9,
                        "source": {"document_id": document_id, "sentence_index": sent_idx, "char_start": char_start, "char_end": char_end, "quote": sent_text},
                    })
                else:
                    facts.append({
                        "fact_type": "action",
                        "language": "en",
                        "relation": pred,
                        "subject": {"text": subj, "lemma": subj.lower(), "normalized": subj.lower()},
                        "predicate": {"text": filtered_words[1], "lemma": pred, "tense": "past", "voice": "active"},
                        "object": {"text": obj, "lemma": obj.lower(), "normalized": obj.lower()},
                        "is_negated": is_negated,
                        "confidence": 0.85,
                        "source": {"document_id": document_id, "sentence_index": sent_idx, "char_start": char_start, "char_end": char_end, "quote": sent_text},
                    })

        return {
            "language": "en",
            "analyzer": self.analyzer_name,
            "version": self.version,
            "document_id": document_id,
            "sentences": [{"sentence_index": i, "text": s, "char_start": cs, "char_end": ce} for i, s, cs, ce in sentences_raw],
            "entities": entities,
            "facts": facts,
            "confidence": 0.88 if facts else 0.5,
        }
