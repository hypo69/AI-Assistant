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
# Updated: 2026-11-10 13:59:00
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

    _RE_COMMIT_HASH = re.compile(r"\b([0-9a-f]{7,40})\b", re.IGNORECASE)
    _RE_RU_TOKENS = re.compile(r"[а-яА-ЯёЁa-zA-Z0-9-]+")
    _RE_RU_ACTION = re.compile(r"\bчто\s+(?:не\s+)?(?:делал|делала|делало|делали|сделал|сделала)\b")
    _RE_RU_POSSESSED = re.compile(r"^что\s+(?:не\s+)?(?:было|был|была|были|есть)\s+у\b")
    _RE_EN_WORDS = re.compile(r"[a-z0-9']+")

    _GIT_KEYWORDS = (
        "commit", "קומיט", "קוממיט", "коммит", "коммите", "коммита", "коммиту",
        "diff", "дифф", "ревизи", "גרסה", "git", "гит",
    )
    _RU_NEGATIONS = frozenset({"не", "ни"})
    _RU_IGNORE = frozenset({
        "кто", "что", "кем", "чем", "кого", "чего", "какой", "какую", "какое", "предмет",
        "именно", "занимался", "занималась", "был", "была", "было", "были", "есть",
        "ли", "у", "и", "в", "на", "не", "ни",
    })
    _HE_NEGATIONS = frozenset({"לא", "אין"})
    _HE_POSSESSION_VERBS = frozenset({"היה", "הייתה", "היתה", "יש", "אין"})
    _HE_STOP = frozenset({
        "מה", "מי", "למי", "האם", "היה", "הייתה", "היתה", "יש", "אין", "לא",
        "את", "הקשר", "קשר", "בין", "על", "ידי",
    })
    _EN_NEGATIONS = frozenset({"not", "never", "didn't", "doesn't", "wasn't", "weren't"})
    _EN_STOP = frozenset({
        "who", "what", "whom", "by", "did", "does", "was", "were",
        "the", "a", "an", "is", "has", "had", "not", "never",
    })

    @classmethod
    def parse_question(cls, question: str, language: Optional[str] = "") -> Dict[str, Any]:
        """Определяет язык, намерение вопроса, целевую роль и падеж/предлог ответа."""
        lang = language if language in ("ru", "he", "en") else detect_language(question)
        q_clean = question.strip()

        if lang == "he":
            parsed = cls._parse_hebrew_question(q_clean)
        elif lang == "en":
            parsed = cls._parse_english_question(q_clean)
        else:
            parsed = cls._parse_russian_question(q_clean)

        q_low = q_clean.lower()
        commit_hash_match = cls._RE_COMMIT_HASH.search(q_clean)
        commit_hash = commit_hash_match.group(1).lower() if commit_hash_match else ""

        is_git_kw = any(kw in q_low for kw in cls._GIT_KEYWORDS)

        if commit_hash:
            parsed["intent"] = "git_commit_query"
            parsed["commit_hash"] = commit_hash
            parsed["is_git_query"] = True
        elif is_git_kw:
            parsed["intent"] = "git_history_query"
            parsed["commit_hash"] = ""
            parsed["is_git_query"] = True
        else:
            parsed["commit_hash"] = ""
            parsed["is_git_query"] = False

        return parsed

    @classmethod
    def _parse_russian_question(cls, q: str) -> Dict[str, Any]:
        """Разбирает русскоязычный вопрос с определением падежа ответа и ключевых лемм."""
        q_low = q.lower().strip("?!. ")
        raw_tokens = cls._RE_RU_TOKENS.findall(q_low)
        token_set = set(raw_tokens)
        is_negated = bool(token_set & cls._RU_NEGATIONS)

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
        elif cls._RE_RU_ACTION.search(q_low):
            intent = "action_query"
            target_role = "predicate"
            target_case = "nomn"
        elif q_low.startswith("у кого"):
            intent = "owner_query"
            target_role = "owner"
            target_case = "gent"
        elif cls._RE_RU_POSSESSED.search(q_low):
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

        content_lemmas: List[str] = []
        noun_lemmas: List[str] = []
        predicate_lemma: Optional[str] = None

        for t in raw_tokens:
            if t in cls._RU_IGNORE:
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
        token_set = set(tokens)
        is_negated = bool(token_set & cls._HE_NEGATIONS)

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
        elif q_norm.startswith("מה") and bool(token_set & cls._HE_POSSESSION_VERBS):
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

        content_terms: List[str] = []
        for t in tokens:
            if t in cls._HE_STOP:
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
            "predicate_lemma": None,
            "content_lemmas": content_terms,
            "noun_lemmas": content_terms,
            "raw_question": q,
            "normalized_question": q_norm,
        }

    @classmethod
    def _parse_english_question(cls, q: str) -> Dict[str, Any]:
        """Разбирает вопрос на английском языке."""
        q_low = q.lower().strip("?!. ")
        words = cls._RE_EN_WORDS.findall(q_low)
        word_set = set(words)
        is_negated = bool(word_set & cls._EN_NEGATIONS)
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
        lemmas = [w for w in words if w not in cls._EN_STOP]
        return {
            "language": "en",
            "intent": intent,
            "target_role": target_role,
            "target_case": "base",
            "is_negated": is_negated,
            "predicate_lemma": None,
            "content_lemmas": lemmas,
            "noun_lemmas": lemmas,
            "raw_question": q,
        }
