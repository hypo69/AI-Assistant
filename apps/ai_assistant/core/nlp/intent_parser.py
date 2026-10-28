# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Core NLP - Question Intent Parser
# =============================================================================
# Description:
#   Анализатор намерения вопроса (QuestionIntentParser) для русского языка,
#   иврита и английского языка (ТЗ п. 3.5, 3.6). Определяет искомый тип факта,
#   семантическую роль ответа, требуемый грамматический падеж/предлог, наличие
#   отрицания в вопросе и разделяет глагольные и именные леммы.
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.core.nlp.intent_parser import QuestionIntentParser
#
#     parsed = QuestionIntentParser.parse_question("Кем была вымыта рама?")
#
# File: core/nlp/intent_parser.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.core.nlp
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-20 12:18:00
# =============================================================================

from __future__ import annotations
"""Анализатор структуры, намерения и грамматической роли вопросов (RU, HE, EN)."""

import re
from typing import Any, Dict, List, Optional

from apps.ai_assistant.core.nlp.hebrew import normalize_hebrew, strip_hebrew_article
from apps.ai_assistant.core.nlp.russian import RussianMorphology
from apps.ai_assistant.core.nlp_analyzers import detect_language


class QuestionIntentParser:
    """Анализатор типа вопроса, целевой семантической роли и грамматической формы ответа (ТЗ п. 3.5, 3.6)."""

    @classmethod
    def parse_question(cls, question: str, language: Optional[str] = None) -> Dict[str, Any]:
        """Определяет язык, намерение вопроса, целевую роль и падеж/предлог ответа.

        Args:
            question: Текст вопроса пользователя.
            language: Опциональный код языка ('ru', 'he', 'en').

        Returns:
            Dict[str, Any]: Описание структуры вопроса.
        """
        lang = language if language in ("ru", "he", "en") else detect_language(question)
        q_clean = question.strip()

        if lang == "he":
            return cls._parse_hebrew_question(q_clean)
        if lang == "en":
            return cls._parse_english_question(q_clean)
        return cls._parse_russian_question(q_clean)

    @classmethod
    def _parse_russian_question(cls, q: str) -> Dict[str, Any]:
        """Разбирает русскоязычный вопрос с определением падежа ответа и ключевых лемм."""
        q_low = q.lower().strip("?!. ")
        raw_tokens = re.findall(r"[а-яА-ЯёЁa-zA-Z0-9-]+", q_low)
        is_negated = "не" in raw_tokens or "ни" in raw_tokens

        intent = "unknown"
        target_role = "object"
        target_case = "nomn"

        if q_low.startswith("кем") or "кем " in q_low:
            intent = "agent_instrumental_query"
            target_role = "subject"
            target_case = "inst"
        elif q_low.startswith("кто") or "кто " in q_low:
            intent = "subject_query"
            target_role = "subject"
            target_case = "nomn"
        elif re.search(r"\bчто\s+(?:не\s+)?(?:делал|делала|делало|делали|сделал|сделала)\b", q_low):
            intent = "action_query"
            target_role = "predicate"
            target_case = "nomn"
        elif q_low.startswith("у кого"):
            intent = "owner_query"
            target_role = "owner"
            target_case = "gent"
        elif re.search(r"^что\s+(?:не\s+)?(?:было|был|была|были|есть)\s+у\b", q_low):
            intent = "possessed_query"
            target_role = "possessed_entity"
            target_case = "nomn"
        elif q_low.startswith(("что", "какой", "какую", "какое", "кого")) or "что " in q_low:
            intent = "object_query"
            target_role = "object"
            target_case = "accs"
        elif " ли " in f" {q_low} ":
            intent = "yes_no_query"
            target_role = "verification"
            target_case = "nomn"

        ignore = {
            "кто", "что", "кем", "чем", "кого", "чего", "какой", "какую", "какое", "предмет",
            "именно", "занимался", "занималась", "был", "была", "было", "были", "есть",
            "ли", "у", "и", "в", "на", "не", "ни",
        }
        content_lemmas: List[str] = []
        noun_lemmas: List[str] = []
        predicate_lemma: Optional[str] = None

        for t in raw_tokens:
            if t in ignore:
                continue
            if t in ("мытьем", "мытьём", "мытье", "мытьё"):
                predicate_lemma = "мыть"
                content_lemmas.append("мыть")
                continue
            v_info = RussianMorphology.analyze_verb(t)
            if v_info:
                predicate_lemma = v_info["lemma"]
                content_lemmas.append(v_info["lemma"])
            elif RussianMorphology.is_adjective(t):
                # Прилагательные сохраняем в общих леммах, но не в ядре существительных
                content_lemmas.append(t)
            else:
                n_info = RussianMorphology.analyze_noun(t)
                content_lemmas.append(n_info["lemma"])
                noun_lemmas.append(n_info["lemma"])

        return {
            "language": "ru",
            "intent": intent,
            "target_role": target_role,
            "target_case": target_case,
            "is_negated": is_negated,
            "predicate_lemma": predicate_lemma,
            "content_lemmas": content_lemmas,
            "noun_lemmas": noun_lemmas,
            "raw_question": q,
        }

    @classmethod
    def _parse_hebrew_question(cls, q: str) -> Dict[str, Any]:
        """Разбирает вопрос на иврите (включая конструкции принадлежности ל־ и действия)."""
        q_norm = normalize_hebrew(q).strip("?!. ")
        tokens = [t.strip(".,!?:;\"'()") for t in q_norm.split() if t.strip(".,!?:;\"'()")]
        is_negated = "לא" in tokens or "אין" in tokens

        intent = "unknown"
        target_role = "object"
        target_case = "base"

        if "הקשר בין" in q_norm or "קשר בין" in q_norm:
            intent = "relation_query"
            target_role = "relation_statement"
        elif q_norm.startswith("האם"):
            intent = "yes_no_query"
            target_role = "verification"
        elif q_norm.startswith("למי") or "למי " in q_norm:
            intent = "owner_query"
            target_role = "owner"
            target_case = "lamed_prefix"
        elif q_norm.startswith("מה") and any(t in ("היה", "הייתה", "היתה", "יש", "אין") for t in tokens):
            intent = "possessed_query"
            target_role = "possessed_entity"
        elif "על ידי מי" in q_norm:
            intent = "agent_passive_query"
            target_role = "subject"
            target_case = "al_yedei"
        elif q_norm.startswith("מי") or "מי " in q_norm:
            intent = "subject_query"
            target_role = "subject"
        elif q_norm.startswith(("מה", "את מה")):
            intent = "object_query"
            target_role = "object"

        stop = {"מה", "מי", "למי", "האם", "היה", "הייתה", "היתה", "יש", "אין", "לא", "את", "הקשר", "קשר", "בין", "על", "ידי"}
        content_terms: List[str] = []
        for t in tokens:
            if t in stop:
                continue
            clean_t = t
            if clean_t.startswith("ל") and len(clean_t) > 2:
                clean_t = clean_t[1:]
            clean_t = strip_hebrew_article(clean_t)
            content_terms.append(clean_t)

        return {
            "language": "he",
            "intent": intent,
            "target_role": target_role,
            "target_case": target_case,
            "is_negated": is_negated,
            "content_lemmas": content_terms,
            "noun_lemmas": content_terms,
            "raw_question": q,
            "normalized_question": q_norm,
        }

    @classmethod
    def _parse_english_question(cls, q: str) -> Dict[str, Any]:
        """Разбирает вопрос на английском языке."""
        q_low = q.lower().strip("?!. ")
        words = re.findall(r"[a-z0-9']+", q_low)
        is_negated = any(w in ("not", "never", "didn't", "doesn't", "wasn't", "weren't") for w in words)
        intent = "object_query"
        target_role = "object"
        if q_low.startswith("who"):
            intent = "subject_query"
            target_role = "subject"
        elif q_low.startswith("by whom"):
            intent = "agent_instrumental_query"
            target_role = "subject"
        elif q_low.startswith(("did ", "was ", "were ", "is ", "has ", "had ")):
            intent = "yes_no_query"
            target_role = "verification"
        stop = {"who", "what", "whom", "by", "did", "does", "was", "were", "the", "a", "an", "is", "has", "had", "not", "never"}
        lemmas = [w for w in words if w not in stop]
        return {
            "language": "en",
            "intent": intent,
            "target_role": target_role,
            "target_case": "base",
            "is_negated": is_negated,
            "content_lemmas": lemmas,
            "noun_lemmas": lemmas,
            "raw_question": q,
        }
