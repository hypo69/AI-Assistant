# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Core NLP - Hebrew Module
# =============================================================================
# Description:
#   Языковой NLP-адаптер для иврита (HebrewAnalyzer, normalize_hebrew,
#   strip_hebrew_article). Поддерживает нормализацию орфографии (снятие огласовок
#   niqqud, היתה -> הייתה), разбор конструкций обладания с предлогом ל־ в прямом
#   и обратном порядке слов, а также конструкций активного и пассивного действия.
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.core.nlp.hebrew import HebrewAnalyzer
#
#     analyzer = HebrewAnalyzer()
#     res = analyzer.analyze("לדוד משה היתה חווה", document_id="farm.txt")
#
# File: core/nlp/hebrew.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.core.nlp
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-25 23:15:00
# =============================================================================

from __future__ import annotations
"""Ивритский языковой модуль морфологии и семантического разбора."""

import re
from typing import Any, Dict, List, Optional

_HE_POSSESSION_VERBS = {"היתה", "הייתה", "היה", "היו", "יש", "יהיה", "תהיה", "אין"}
_HE_SPATIAL_PREPOSITIONS = {"ב", "אל", "מן", "על", "מול", "ליד", "בתוך"}
_HE_PRONOUNS_SUBJ = {"הוא", "היא", "הם", "הן"}
_HE_PRONOUN_POSS_TOKENS = {"לו", "לה", "להם", "להן"}

_HE_VERB_LEXICON: Dict[str, Dict[str, str]] = {
    "רחצה": {"lemma": "רחץ", "tense": "past", "gender": "femn", "voice": "active"},
    "רחץ": {"lemma": "רחץ", "tense": "past", "gender": "masc", "voice": "active"},
    "רחצו": {"lemma": "רחץ", "tense": "past", "number": "plur", "voice": "active"},
    "נרחצה": {"lemma": "רחץ", "tense": "past", "gender": "femn", "voice": "passive"},
    "נרחץ": {"lemma": "רחץ", "tense": "past", "gender": "masc", "voice": "passive"},
    "שטפה": {"lemma": "שטף", "tense": "past", "gender": "femn", "voice": "active"},
    "שטף": {"lemma": "שטף", "tense": "past", "gender": "masc", "voice": "active"},
    "ניקתה": {"lemma": "ניקה", "tense": "past", "gender": "femn", "voice": "active"},
    "ניקה": {"lemma": "ניקה", "tense": "past", "gender": "masc", "voice": "active"},
    "בנתה": {"lemma": "בנה", "tense": "past", "gender": "femn", "voice": "active"},
    "בנה": {"lemma": "בנה", "tense": "past", "gender": "masc", "voice": "active"},
    "כתבה": {"lemma": "כתב", "tense": "past", "gender": "femn", "voice": "active"},
    "כתב": {"lemma": "כתב", "tense": "past", "gender": "masc", "voice": "active"},
    "קראה": {"lemma": "קרא", "tense": "past", "gender": "femn", "voice": "active"},
    "קרא": {"lemma": "קרא", "tense": "past", "gender": "masc", "voice": "active"},
    "גידל": {"lemma": "גידל", "tense": "past", "gender": "masc", "voice": "active"},
    "גידלה": {"lemma": "גידל", "tense": "past", "gender": "femn", "voice": "active"},
    "קנה": {"lemma": "קנה", "tense": "past", "gender": "masc", "voice": "active"},
    "קנתה": {"lemma": "קנה", "tense": "past", "gender": "femn", "voice": "active"},
    "תיקן": {"lemma": "תיקן", "tense": "past", "gender": "masc", "voice": "active"},
    "תיקנה": {"lemma": "תיקן", "tense": "past", "gender": "femn", "voice": "active"},
    "יצר": {"lemma": "יצר", "tense": "past", "gender": "masc", "voice": "active"},
    "יצרה": {"lemma": "יצר", "tense": "past", "gender": "femn", "voice": "active"},
}


def normalize_hebrew(text: str) -> str:
    """Нормализует текст на иврите (удаление огласовок niqqud и унификация орфографии).

    Args:
        text: Исходная строка на иврите.

    Returns:
        str: Нормализованная строка.
    """
    if not text:
        return ""
    no_niqqud = re.sub(r"[\u0591-\u05C7]", "", text)
    words = no_niqqud.split()
    norm_words: List[str] = []
    for w in words:
        clean = w.strip(".,!?:;\"'()")
        if clean == "היתה":
            w = w.replace("היתה", "הייתה")
        elif clean == "אימא":
            w = w.replace("אימא", "אמא")
        norm_words.append(w)
    return " ".join(norm_words)


def strip_hebrew_article(word: str) -> str:
    """Удаляет определённый артикль ה־ в начале слова на иврите для получения базовой леммы.

    Args:
        word: Слово на иврите.

    Returns:
        str: Слово без начального артикля ה (если длина позволяет).
    """
    clean = word.strip(".,!?:;\"'()")
    if clean.startswith("ה") and len(clean) > 3 and clean not in ("היתה", "הייתה", "היה", "היו", "האם"):
        return clean[1:]
    return clean


class HebrewAnalyzer:
    """Языковой NLP-адаптер для иврита (поддержка конструкций действия и принадлежности ל־)."""

    language_code: str = "he"
    analyzer_name: str = "HebrewSemanticMorphoAnalyzer"
    version: str = "1.1.0"

    def _extract_possession_fact(
        self,
        sent_text: str,
        sent_idx: int,
        char_start: int,
        char_end: int,
        document_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Распознаёт конструкцию принадлежности с предлогом ל־ на иврите (ТЗ п. 3.4.1)."""
        clean_sent = re.sub(r"[\u0591-\u05C7]", "", sent_text).strip().rstrip(".!?")
        tokens = [t.strip(".,!?:;\"'()") for t in clean_sent.split() if t.strip(".,!?:;\"'()")]
        if len(tokens) < 2:
            return None

        is_negated = "לא" in tokens or "אין" in tokens
        verb_idx = -1
        for idx, tok in enumerate(tokens):
            if tok in _HE_POSSESSION_VERBS:
                verb_idx = idx
                break

        if verb_idx == -1:
            return None

        before_verb = [t for t in tokens[:verb_idx] if t not in ("לא", "אין")]
        after_verb = [t for t in tokens[verb_idx + 1 :] if t not in ("לא", "אין")]

        owner_tokens: List[str] = []
        possessed_tokens: List[str] = []

        if before_verb and before_verb[0].startswith("ל") and len(before_verb[0]) > 1:
            if before_verb[0] in _HE_PRONOUN_POSS_TOKENS:
                owner_tokens = [before_verb[0]]
            else:
                first_owner_word = before_verb[0][1:].lstrip("־-")
                owner_tokens = [first_owner_word] + before_verb[1:]
            possessed_tokens = after_verb
        elif after_verb:
            l_pos = -1
            for i, t in enumerate(after_verb):
                if t.startswith("ל") and len(t) > 1 and t not in ("לא", "ליד"):
                    l_pos = i
                    break
            if l_pos == 0 and len(after_verb) >= 2:
                if after_verb[0] in _HE_PRONOUN_POSS_TOKENS:
                    owner_tokens = [after_verb[0]]
                    possessed_tokens = after_verb[1:]
                else:
                    first_owner_word = after_verb[0][1:].lstrip("־-")
                    owner_tokens = [first_owner_word] + after_verb[1:-1]
                    possessed_tokens = [after_verb[-1]]
            elif l_pos > 0:
                possessed_tokens = after_verb[:l_pos]
                if after_verb[l_pos] in _HE_PRONOUN_POSS_TOKENS:
                    owner_tokens = [after_verb[l_pos]]
                else:
                    first_owner_word = after_verb[l_pos][1:].lstrip("־-")
                    owner_tokens = [first_owner_word] + after_verb[l_pos + 1 :]

        if not owner_tokens or not possessed_tokens:
            return None

        possessed_raw = " ".join(possessed_tokens)
        if possessed_tokens[0] in _HE_SPATIAL_PREPOSITIONS:
            return None

        owner_text = " ".join(owner_tokens)
        possessed_norm = strip_hebrew_article(possessed_raw)

        return {
            "fact_type": "possession",
            "language": "he",
            "relation": "has",
            "owner": {
                "text": owner_text,
                "normalized": owner_text,
                "lemma": owner_text,
                "with_preposition": f"ל{owner_text}",
                "entity_type": "person",
            },
            "possessed_entity": {
                "text": possessed_raw,
                "normalized": possessed_norm,
                "lemma": possessed_norm,
                "entity_type": "property",
            },
            "is_negated": is_negated,
            "confidence": 0.98,
            "source": {
                "document_id": document_id,
                "sentence_index": sent_idx,
                "char_start": char_start,
                "char_end": char_end,
                "quote": sent_text,
            },
        }

    def _extract_action_fact(
        self,
        sent_text: str,
        sent_idx: int,
        char_start: int,
        char_end: int,
        document_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Распознаёт субъектно-предикатно-объектную конструкцию действия на иврите."""
        clean_sent = re.sub(r"[\u0591-\u05C7]", "", sent_text).strip().rstrip(".!?")
        tokens = [t.strip(".,!?:;\"'()") for t in clean_sent.split() if t.strip(".,!?:;\"'()")]
        if len(tokens) < 2:
            return None

        is_negated = "לא" in tokens
        filtered = [t for t in tokens if t != "לא"]

        verb_idx = -1
        verb_info: Optional[Dict[str, str]] = None
        for idx, tok in enumerate(filtered):
            if tok in _HE_VERB_LEXICON:
                verb_idx = idx
                verb_info = _HE_VERB_LEXICON[tok]
                break

        if verb_idx == -1 and "את" in filtered:
            et_idx = filtered.index("את")
            if et_idx >= 2:
                verb_idx = et_idx - 1
                verb_tok = filtered[verb_idx]
                lemma_guess = verb_tok[:-1] if verb_tok.endswith("ה") and len(verb_tok) == 4 else verb_tok
                verb_info = {"lemma": lemma_guess, "tense": "past", "voice": "active"}

        if verb_idx <= 0 or verb_info is None:
            return None

        subj_tokens = filtered[:verb_idx]
        verb_tok = filtered[verb_idx]
        after_verb = filtered[verb_idx + 1 :]

        raw_obj_text = " ".join(after_verb)
        obj_clean_tokens = [t for t in after_verb if t != "את"]
        obj_text = " ".join(obj_clean_tokens)
        obj_lemma = strip_hebrew_article(obj_text) if obj_text else ""

        subj_text = " ".join(subj_tokens)
        subj_lemma = strip_hebrew_article(subj_text)

        return {
            "fact_type": "action",
            "language": "he",
            "relation": verb_info["lemma"],
            "subject": {
                "text": subj_text,
                "lemma": subj_lemma,
                "normalized": subj_text,
            },
            "predicate": {
                "text": verb_tok,
                "lemma": verb_info["lemma"],
                "tense": verb_info.get("tense", "past"),
                "voice": verb_info.get("voice", "active"),
            },
            "object": {
                "text": obj_text,
                "raw_text": raw_obj_text,
                "lemma": obj_lemma,
                "normalized": obj_text,
            } if obj_text else None,
            "is_negated": is_negated,
            "confidence": 0.97 if obj_text else 0.85,
            "source": {
                "document_id": document_id,
                "sentence_index": sent_idx,
                "char_start": char_start,
                "char_end": char_end,
                "quote": sent_text,
            },
        }

    def analyze(self, text: str, document_id: str = "unknown") -> Dict[str, Any]:
        """Выполняет анализ текста на иврите и извлекает факты принадлежности и действия."""
        from apps.ai_assistant.core.nlp_analyzers import split_sentences

        sentences_raw = split_sentences(text)
        sentences_out: List[Dict[str, Any]] = []
        facts: List[Dict[str, Any]] = []
        entities: List[Dict[str, Any]] = []
        seen_entities = set()
        last_antecedent: Optional[Dict[str, str]] = None

        for sent_idx, sent_text, char_start, char_end in sentences_raw:
            normalized_sent = normalize_hebrew(sent_text)
            poss_fact = self._extract_possession_fact(sent_text, sent_idx, char_start, char_end, document_id)
            if poss_fact:
                owner_obj = poss_fact.get("owner") or {}
                owner_txt = owner_obj.get("text", "")
                if owner_txt in _HE_PRONOUN_POSS_TOKENS and last_antecedent is not None:
                    owner_obj["text"] = last_antecedent["text"]
                    owner_obj["normalized"] = last_antecedent["text"]
                    owner_obj["lemma"] = last_antecedent["lemma"]
                    owner_obj["with_preposition"] = f"ל{last_antecedent['text']}"
                elif owner_txt and owner_txt not in _HE_PRONOUN_POSS_TOKENS:
                    last_antecedent = {"text": owner_txt, "lemma": owner_obj.get("lemma", owner_txt)}

                facts.append(poss_fact)
                for ent_key, ent_role in (("owner", "person"), ("possessed_entity", "property")):
                    ent_obj = poss_fact.get(ent_key) or {}
                    norm_val = ent_obj.get("normalized", "")
                    if norm_val and norm_val not in seen_entities:
                        seen_entities.add(norm_val)
                        entities.append({
                            "text": ent_obj.get("text", norm_val),
                            "normalized": norm_val,
                            "lemma": ent_obj.get("lemma", norm_val),
                            "entity_type": ent_role,
                            "language": "he",
                        })
            else:
                act_fact = self._extract_action_fact(sent_text, sent_idx, char_start, char_end, document_id)
                if act_fact:
                    subj_obj = act_fact.get("subject") or {}
                    subj_txt = subj_obj.get("text", "")
                    if subj_txt in _HE_PRONOUNS_SUBJ and last_antecedent is not None:
                        subj_obj["text"] = last_antecedent["text"]
                        subj_obj["lemma"] = last_antecedent["lemma"]
                        subj_obj["normalized"] = last_antecedent["text"]
                    elif subj_txt and subj_txt not in _HE_PRONOUNS_SUBJ:
                        last_antecedent = {"text": subj_txt, "lemma": subj_obj.get("lemma", subj_txt)}

                    facts.append(act_fact)
                    for role_key in ("subject", "object"):
                        r_obj = act_fact.get(role_key)
                        if isinstance(r_obj, dict) and r_obj.get("normalized"):
                            norm_val = r_obj["normalized"]
                            if norm_val not in seen_entities:
                                seen_entities.add(norm_val)
                                entities.append({
                                    "text": r_obj.get("text", norm_val),
                                    "normalized": norm_val,
                                    "lemma": r_obj.get("lemma", norm_val),
                                    "entity_type": "entity",
                                    "language": "he",
                                })

            sentences_out.append({
                "sentence_index": sent_idx,
                "text": sent_text,
                "normalized_text": normalized_sent,
                "char_start": char_start,
                "char_end": char_end,
            })

        return {
            "language": "he",
            "analyzer": self.analyzer_name,
            "version": self.version,
            "document_id": document_id,
            "sentences": sentences_out,
            "entities": entities,
            "facts": facts,
            "confidence": 0.97 if facts else 0.6,
        }
