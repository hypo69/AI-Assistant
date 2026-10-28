# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Core NLP - Russian Module
# =============================================================================
# Description:
#   Морфологический и синтаксический анализатор русского языка (RussianMorphology,
#   RussianAnalyzer). Выполняет лемматизацию, распознавание частей речи (NOUN,
#   VERB, ADJ, PART, AUX), учёт отрицания, склонение по 6 падежам, обработку
#   многословных сущностей, конструкций принадлежности и строк таблиц Markdown.
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.core.nlp.russian import RussianAnalyzer, RussianMorphology
#
#     analyzer = RussianAnalyzer()
#     res = analyzer.analyze("Мама мыла раму.", document_id="mama.txt")
#
# File: core/nlp/russian.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.core.nlp
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-25 23:15:00
# =============================================================================

from __future__ import annotations
"""Русский языковой модуль морфологии, склонения и извлечения фактов."""

import re
from typing import Any, Callable, Dict, List, Optional, Tuple

_RU_VERB_LEXICON: Dict[str, Dict[str, Any]] = {
    "мыть": {"lemma": "мыть", "tense": "inf", "voice": "active"},
    "мыл": {"lemma": "мыть", "tense": "past", "gender": "masc", "voice": "active"},
    "мыла": {"lemma": "мыть", "tense": "past", "gender": "femn", "voice": "active"},
    "мыло": {"lemma": "мыть", "tense": "past", "gender": "neut", "voice": "active"},
    "мыли": {"lemma": "мыть", "tense": "past", "number": "plur", "voice": "active"},
    "моет": {"lemma": "мыть", "tense": "pres", "voice": "active"},
    "вымыл": {"lemma": "мыть", "tense": "past", "gender": "masc", "voice": "active"},
    "вымыла": {"lemma": "мыть", "tense": "past", "gender": "femn", "voice": "active"},
    "помыл": {"lemma": "мыть", "tense": "past", "gender": "masc", "voice": "active"},
    "помыла": {"lemma": "мыть", "tense": "past", "gender": "femn", "voice": "active"},
    "очистил": {"lemma": "очистить", "tense": "past", "gender": "masc", "voice": "active"},
    "очистила": {"lemma": "очистить", "tense": "past", "gender": "femn", "voice": "active"},
    "очищена": {"lemma": "очистить", "tense": "past", "gender": "femn", "voice": "passive"},
    "вымыта": {"lemma": "мыть", "tense": "past", "gender": "femn", "voice": "passive"},
    "вымыт": {"lemma": "мыть", "tense": "past", "gender": "masc", "voice": "passive"},
    "вымыто": {"lemma": "мыть", "tense": "past", "gender": "neut", "voice": "passive"},
    "вымыты": {"lemma": "мыть", "tense": "past", "number": "plur", "voice": "passive"},
    "помыта": {"lemma": "мыть", "tense": "past", "gender": "femn", "voice": "passive"},
    "мыта": {"lemma": "мыть", "tense": "past", "gender": "femn", "voice": "passive"},
    "мылась": {"lemma": "мыть", "tense": "past", "gender": "femn", "voice": "passive"},
    "делал": {"lemma": "делать", "tense": "past", "gender": "masc", "voice": "active"},
    "делала": {"lemma": "делать", "tense": "past", "gender": "femn", "voice": "active"},
    "сделал": {"lemma": "делать", "tense": "past", "gender": "masc", "voice": "active"},
    "сделала": {"lemma": "делать", "tense": "past", "gender": "femn", "voice": "active"},
    "сделана": {"lemma": "делать", "tense": "past", "gender": "femn", "voice": "passive"},
    "сделан": {"lemma": "делать", "tense": "past", "gender": "masc", "voice": "passive"},
    "писал": {"lemma": "писать", "tense": "past", "gender": "masc", "voice": "active"},
    "писала": {"lemma": "писать", "tense": "past", "gender": "femn", "voice": "active"},
    "написал": {"lemma": "писать", "tense": "past", "gender": "masc", "voice": "active"},
    "написала": {"lemma": "писать", "tense": "past", "gender": "femn", "voice": "active"},
    "написана": {"lemma": "писать", "tense": "past", "gender": "femn", "voice": "passive"},
    "написан": {"lemma": "писать", "tense": "past", "gender": "masc", "voice": "passive"},
    "читал": {"lemma": "читать", "tense": "past", "gender": "masc", "voice": "active"},
    "читала": {"lemma": "читать", "tense": "past", "gender": "femn", "voice": "active"},
    "прочитана": {"lemma": "читать", "tense": "past", "gender": "femn", "voice": "passive"},
    "строил": {"lemma": "строить", "tense": "past", "gender": "masc", "voice": "active"},
    "строила": {"lemma": "строить", "tense": "past", "gender": "femn", "voice": "active"},
    "построена": {"lemma": "строить", "tense": "past", "gender": "femn", "voice": "passive"},
    "построен": {"lemma": "строить", "tense": "past", "gender": "masc", "voice": "passive"},
    "купил": {"lemma": "купить", "tense": "past", "gender": "masc", "voice": "active"},
    "купила": {"lemma": "купить", "tense": "past", "gender": "femn", "voice": "active"},
    "куплена": {"lemma": "купить", "tense": "past", "gender": "femn", "voice": "passive"},
    "куплен": {"lemma": "купить", "tense": "past", "gender": "masc", "voice": "passive"},
    "открыл": {"lemma": "открыть", "tense": "past", "gender": "masc", "voice": "active"},
    "открыла": {"lemma": "открыть", "tense": "past", "gender": "femn", "voice": "active"},
    "открыта": {"lemma": "открыть", "tense": "past", "gender": "femn", "voice": "passive"},
    "закрыл": {"lemma": "закрыть", "tense": "past", "gender": "masc", "voice": "active"},
    "закрыла": {"lemma": "закрыть", "tense": "past", "gender": "femn", "voice": "active"},
    "закрыта": {"lemma": "закрыть", "tense": "past", "gender": "femn", "voice": "passive"},
    "исправил": {"lemma": "исправить", "tense": "past", "gender": "masc", "voice": "active"},
    "исправила": {"lemma": "исправить", "tense": "past", "gender": "femn", "voice": "active"},
    "исправлена": {"lemma": "исправить", "tense": "past", "gender": "femn", "voice": "passive"},
    "исправлен": {"lemma": "исправить", "tense": "past", "gender": "masc", "voice": "passive"},
    "создал": {"lemma": "создать", "tense": "past", "gender": "masc", "voice": "active"},
    "создала": {"lemma": "создать", "tense": "past", "gender": "femn", "voice": "active"},
    "создана": {"lemma": "создать", "tense": "past", "gender": "femn", "voice": "passive"},
    "создан": {"lemma": "создать", "tense": "past", "gender": "masc", "voice": "passive"},
    "красил": {"lemma": "красить", "tense": "past", "gender": "masc", "voice": "active"},
    "красила": {"lemma": "красить", "tense": "past", "gender": "femn", "voice": "active"},
    "покрасил": {"lemma": "красить", "tense": "past", "gender": "masc", "voice": "active"},
    "покрасила": {"lemma": "красить", "tense": "past", "gender": "femn", "voice": "active"},
    "покрашен": {"lemma": "красить", "tense": "past", "gender": "masc", "voice": "passive"},
    "покрашена": {"lemma": "красить", "tense": "past", "gender": "femn", "voice": "passive"},
    "готовил": {"lemma": "готовить", "tense": "past", "gender": "masc", "voice": "active"},
    "готовила": {"lemma": "готовить", "tense": "past", "gender": "femn", "voice": "active"},
    "разработал": {"lemma": "разработать", "tense": "past", "gender": "masc", "voice": "active"},
    "разработала": {"lemma": "разработать", "tense": "past", "gender": "femn", "voice": "active"},
}

_RU_AUX_VERBS = {"был", "была", "было", "были", "быть", "будет", "есть"}
_RU_STOPWORDS = {
    "и", "в", "во", "на", "с", "со", "к", "по", "из", "за", "от", "до",
    "для", "о", "об", "ли", "же", "это", "эта", "этот", "а", "но", "или",
    "также", "тоже", "затем", "потом",
}
_RU_PRONOUNS_SUBJ = {"он", "она", "оно", "они"}
_RU_PRONOUNS_POSS = {"него", "нее", "неё", "них", "его", "ее", "её"}

# Существительные, оканчивающиеся на -ло/-ли/-ал/-ел/-ул/-ыл, которые не являются глаголами
_RU_NON_VERB_NOUNS = {
    "зеркало", "одеяло", "правило", "стекло", "кресло", "село", "крыло", "число",
    "дело", "тело", "начало", "масло", "весло", "русло", "ремесло", "зло", "тепло",
    "качели", "детали", "модели", "цели", "роли", "мысли", "новости", "части",
    "вокзал", "металл", "кристалл", "портал", "журнал", "канал", "сигнал", "терминал",
    "оригинал", "материал", "персонал", "филиал", "потенциал", "сериал", "подвал",
    "раздел", "узел", "отдел", "предел", "пробел", "прицел", "котел", "котёл", "орел", "орёл",
    "стол", "стул", "файл", "пол", "кол", "гол", "зал", "бал", "вал", "тыл", "пыл", "мул", "аул",
}

# Несклоняемые существительные на -у/-ю/-о/-е/-и
_RU_INDECLINABLE_NOUNS = {
    "кенгуру", "шоу", "меню", "интервью", "такси", "кафе", "пальто", "метро",
    "радио", "кино", "видео", "аудио", "фото", "резюме", "кашне", "купе", "шоссе", "кофе",
}

_RU_NOUN_PARADIGMS: Dict[str, Dict[str, str]] = {
    "мама": {"nomn": "мама", "gent": "мамы", "datv": "маме", "accs": "маму", "inst": "мамой", "loct": "маме", "anim": "true"},
    "рама": {"nomn": "рама", "gent": "рамы", "datv": "раме", "accs": "раму", "inst": "рамой", "loct": "раме", "anim": "false"},
    "папа": {"nomn": "папа", "gent": "папы", "datv": "папе", "accs": "папу", "inst": "папой", "loct": "папе", "anim": "true"},
    "отец": {"nomn": "отец", "gent": "отца", "datv": "отцу", "accs": "отца", "inst": "отцом", "loct": "отце", "anim": "true"},
    "мать": {"nomn": "мать", "gent": "матери", "datv": "матери", "accs": "мать", "inst": "матерью", "loct": "матери", "anim": "true"},
    "сестра": {"nomn": "сестра", "gent": "сестры", "datv": "сестре", "accs": "сестру", "inst": "сестрой", "loct": "сестре", "anim": "true"},
    "брат": {"nomn": "брат", "gent": "брата", "datv": "брату", "accs": "брата", "inst": "братом", "loct": "брате", "anim": "true"},
    "бабушка": {"nomn": "бабушка", "gent": "бабушки", "datv": "бабушке", "accs": "бабушку", "inst": "бабушкой", "loct": "бабушке", "anim": "true"},
    "дедушка": {"nomn": "дедушка", "gent": "дедушки", "datv": "дедушке", "accs": "дедушку", "inst": "дедушкой", "loct": "дедушке", "anim": "true"},
    "окно": {"nomn": "окно", "gent": "окна", "datv": "окну", "accs": "окно", "inst": "окном", "loct": "окне", "anim": "false"},
    "дом": {"nomn": "дом", "gent": "дома", "datv": "дому", "accs": "дом", "inst": "домом", "loct": "доме", "anim": "false"},
    "ферма": {"nomn": "ферма", "gent": "фермы", "datv": "ферме", "accs": "ферму", "inst": "фермой", "loct": "ферме", "anim": "false"},
    "книга": {"nomn": "книга", "gent": "книги", "datv": "книге", "accs": "книгу", "inst": "книгой", "loct": "книге", "anim": "false"},
    "машина": {"nomn": "машина", "gent": "машины", "datv": "машине", "accs": "машину", "inst": "машиной", "loct": "машине", "anim": "false"},
    "посуда": {"nomn": "посуда", "gent": "посуды", "datv": "посуде", "accs": "посуду", "inst": "посудой", "loct": "посуде", "anim": "false"},
    "пол": {"nomn": "пол", "gent": "пола", "datv": "полу", "accs": "пол", "inst": "полом", "loct": "полу", "anim": "false"},
    "стол": {"nomn": "стол", "gent": "стола", "datv": "столу", "accs": "стол", "inst": "столом", "loct": "столе", "anim": "false"},
    "дверь": {"nomn": "дверь", "gent": "двери", "datv": "двери", "accs": "дверь", "inst": "дверью", "loct": "двери", "anim": "false"},
    "забор": {"nomn": "забор", "gent": "забора", "datv": "забору", "accs": "забор", "inst": "забором", "loct": "заборе", "anim": "false"},
    "ужин": {"nomn": "ужин", "gent": "ужина", "datv": "ужину", "accs": "ужин", "inst": "ужином", "loct": "ужине", "anim": "false"},
    "давид": {"nomn": "давид", "gent": "давида", "datv": "давиду", "accs": "давида", "inst": "давидом", "loct": "давиде", "anim": "true"},
}

_RU_ADJ_ENDINGS = (
    "ый", "ий", "ая", "яя", "ое", "ее", "ые", "ие",
    "ого", "его", "ому", "ему", "ую", "юю", "ым", "им", "ых", "их", "ыми", "ими",
)


class RussianMorphology:
    """Морфологический процессор русского языка (лемматизация, определение падежа и склонение)."""

    @classmethod
    def is_adjective(cls, word: str) -> bool:
        """Проверяет, является ли слово прилагательным (определением) в русском языке.

        Args:
            word: Проверяемое слово.

        Returns:
            bool: True, если токен имеет типичное окончание полного прилагательного.
        """
        w_lower = word.lower().strip(".,!?:;\"'«»()")
        if len(w_lower) < 5 or w_lower in _RU_NOUN_PARADIGMS or w_lower in _RU_NON_VERB_NOUNS:
            return False
        for forms in _RU_NOUN_PARADIGMS.values():
            if w_lower in forms.values():
                return False
        return w_lower.endswith(_RU_ADJ_ENDINGS)

    @classmethod
    def analyze_noun(cls, word: str) -> Dict[str, str]:
        """Определяет лемму и вероятный падеж существительного в русском языке.

        Args:
            word: Словоформа существительного.

        Returns:
            Dict[str, str]: Словарь с полями 'lemma', 'case', 'pos'.
        """
        w_lower = word.lower().strip(".,!?:;\"'«»()")
        if not w_lower:
            return {"lemma": "", "case": "nomn", "pos": "NOUN"}

        if w_lower in _RU_INDECLINABLE_NOUNS:
            return {"lemma": w_lower, "case": "nomn", "pos": "NOUN"}

        for lemma, forms in _RU_NOUN_PARADIGMS.items():
            for case_name, form_val in forms.items():
                if case_name == "anim":
                    continue
                if form_val == w_lower:
                    return {"lemma": lemma, "case": case_name, "pos": "NOUN"}

        if w_lower in _RU_NON_VERB_NOUNS:
            return {"lemma": w_lower, "case": "nomn", "pos": "NOUN"}

        if w_lower.endswith(("ой", "ою")) and len(w_lower) > 3:
            return {"lemma": w_lower[:-2] + "а", "case": "inst", "pos": "NOUN"}
        if w_lower.endswith(("ей", "ею", "ёй")) and len(w_lower) > 3:
            return {"lemma": w_lower[:-2] + "я", "case": "inst", "pos": "NOUN"}
        if w_lower.endswith("ью") and len(w_lower) > 3:
            return {"lemma": w_lower[:-1], "case": "inst", "pos": "NOUN"}
        if w_lower.endswith("ом") and len(w_lower) > 3:
            return {"lemma": w_lower[:-2], "case": "inst", "pos": "NOUN"}
        if w_lower.endswith("ем") and len(w_lower) > 3:
            return {"lemma": w_lower[:-2], "case": "inst", "pos": "NOUN"}
        if w_lower.endswith("у") and len(w_lower) > 2:
            return {"lemma": w_lower[:-1] + "а", "case": "accs", "pos": "NOUN"}
        if w_lower.endswith("ю") and len(w_lower) > 2:
            return {"lemma": w_lower[:-1] + "я", "case": "accs", "pos": "NOUN"}
        if w_lower.endswith("ы") and len(w_lower) > 2:
            return {"lemma": w_lower[:-1] + "а", "case": "gent", "pos": "NOUN"}
        if w_lower.endswith("е") and len(w_lower) > 2 and not w_lower.endswith(("ие", "ье", "ще", "це", "ле", "ре")):
            return {"lemma": w_lower[:-1] + "а", "case": "datv", "pos": "NOUN"}
        if w_lower.endswith(("а", "я")):
            return {"lemma": w_lower, "case": "nomn", "pos": "NOUN"}

        return {"lemma": w_lower, "case": "nomn", "pos": "NOUN"}

    @classmethod
    def analyze_verb(cls, word: str) -> Optional[Dict[str, str]]:
        """Проверяет, является ли слово глаголом или кратким страдательным причастием.

        Args:
            word: Токен предложения.

        Returns:
            Optional[Dict[str, str]]: Сведения о глаголе или None.
        """
        w_lower = word.lower().strip(".,!?:;\"'«»()")
        if w_lower in _RU_VERB_LEXICON:
            info = dict(_RU_VERB_LEXICON[w_lower])
            info["pos"] = "VERB"
            return info

        if (
            w_lower in _RU_NON_VERB_NOUNS
            or w_lower in _RU_INDECLINABLE_NOUNS
            or w_lower in _RU_NOUN_PARADIGMS
            or w_lower in _RU_PRONOUNS_SUBJ
            or w_lower in _RU_PRONOUNS_POSS
        ):
            return None
        for forms in _RU_NOUN_PARADIGMS.values():
            if w_lower in forms.values():
                return None

        if len(w_lower) >= 3:
            if w_lower.endswith(("лась", "лся", "лись")):
                stem = re.sub(r"(лась|лся|лись)$", "", w_lower)
                return {"lemma": stem + "ть", "tense": "past", "voice": "passive", "pos": "VERB"}
            if w_lower.endswith(("та", "на")) and w_lower.startswith(("вы", "по", "на", "про", "ис", "со", "от", "за", "с", "о")):
                return {"lemma": w_lower[:-2] + "ть", "tense": "past", "voice": "passive", "pos": "VERB"}
            if w_lower.endswith(("ла", "ло", "ли")) and w_lower not in _RU_AUX_VERBS:
                return {"lemma": w_lower[:-2] + "ть", "tense": "past", "voice": "active", "pos": "VERB"}
            if w_lower.endswith(("ил", "ал", "ел", "ял", "ул", "ыл")) and w_lower not in _RU_AUX_VERBS:
                return {"lemma": w_lower[:-1] + "ть", "tense": "past", "gender": "masc", "voice": "active", "pos": "VERB"}
            if w_lower.endswith(("ть", "ться", "ти")):
                return {"lemma": w_lower, "tense": "inf", "voice": "active", "pos": "VERB"}
            if w_lower.endswith(("ет", "ит", "ут", "ют", "ат", "ят")) and len(w_lower) >= 4:
                return {"lemma": w_lower[:-2] + "ть", "tense": "pres", "voice": "active", "pos": "VERB"}

        return None

    @classmethod
    def _inflect_single(cls, word_or_lemma: str, case_norm: str) -> str:
        """Склоняет одиночное слово в указанный падеж."""
        w_low = word_or_lemma.lower().strip()
        if w_low in _RU_INDECLINABLE_NOUNS:
            return w_low

        parsed = cls.analyze_noun(w_low)
        lemma = parsed["lemma"]

        result = lemma
        if lemma in _RU_NOUN_PARADIGMS and case_norm in _RU_NOUN_PARADIGMS[lemma]:
            result = _RU_NOUN_PARADIGMS[lemma][case_norm]
        elif lemma.endswith("а"):
            stem = lemma[:-1]
            if case_norm == "nomn":
                result = lemma
            elif case_norm == "gent":
                result = stem + ("и" if stem.endswith(("г", "к", "х", "ж", "ш", "щ", "ч")) else "ы")
            elif case_norm in ("datv", "loct"):
                result = stem + "е"
            elif case_norm == "accs":
                result = stem + "у"
            elif case_norm == "inst":
                result = stem + ("ей" if stem.endswith(("ж", "ш", "щ", "ч", "ц")) else "ой")
        elif lemma.endswith("я"):
            stem = lemma[:-1]
            if case_norm == "nomn":
                result = lemma
            elif case_norm == "gent":
                result = stem + "и"
            elif case_norm in ("datv", "loct"):
                result = stem + ("и" if stem.endswith("и") else "е")
            elif case_norm == "accs":
                result = stem + "ю"
            elif case_norm == "inst":
                result = stem + "ей"
        elif lemma.endswith("ь"):
            stem = lemma[:-1]
            if case_norm == "inst":
                result = stem + "ью"
            elif case_norm in ("gent", "datv", "loct"):
                result = stem + "и"
        elif lemma.endswith(("о", "е")):
            stem = lemma[:-1]
            if case_norm == "gent":
                result = stem + ("я" if lemma.endswith("е") else "а")
            elif case_norm == "datv":
                result = stem + ("ю" if lemma.endswith("е") else "у")
            elif case_norm == "inst":
                result = stem + ("ем" if lemma.endswith("е") else "ом")
            elif case_norm == "loct":
                result = stem + "е"
        else:
            if case_norm == "gent":
                result = lemma + "а"
            elif case_norm == "datv":
                result = lemma + "у"
            elif case_norm == "inst":
                result = lemma + "ом"
            elif case_norm == "loct":
                result = lemma + "е"
        return result

    @classmethod
    def inflect(cls, word_or_lemma: str, target_case: str, capitalize: bool = True) -> str:
        """Склоняет русское существительное или именную группу в требуемый падеж.

        Args:
            word_or_lemma: Исходное слово или словосочетание (например, 'мама', 'давид моше').
            target_case: Целевой падеж ('nomn', 'gent', 'datv', 'accs', 'inst'/'ablt', 'loct').
            capitalize: Сделать ли первую букву заглавной.

        Returns:
            str: Словоформа в нужном падеже.
        """
        case_norm = "inst" if target_case in ("inst", "ablt") else target_case
        parts = [p for p in word_or_lemma.strip().split() if p]
        if not parts:
            return ""

        inflected_parts = [cls._inflect_single(p, case_norm) for p in parts]
        result = " ".join(inflected_parts)
        if capitalize and result:
            return result[0].upper() + result[1:]
        return result


class RussianAnalyzer:
    """Языковой NLP-адаптер для русского языка."""

    language_code: str = "ru"
    analyzer_name: str = "RussianMorphoSyntacticAnalyzer"
    version: str = "1.1.0"

    def __init__(self, sentence_splitter: Optional[Callable[[str], List[Tuple[int, str, int, int]]]] = None) -> None:
        """Инициализирует русский анализатор."""
        self._splitter = sentence_splitter

    def analyze(self, text: str, document_id: str = "unknown") -> Dict[str, Any]:
        """Выполняет полный разбор русского текста и извлекает канонические факты."""
        from apps.ai_assistant.core.nlp_analyzers import split_sentences

        splitter = self._splitter or split_sentences
        sentences_raw = splitter(text)
        sentences_out: List[Dict[str, Any]] = []
        facts: List[Dict[str, Any]] = []
        entities: List[Dict[str, Any]] = []
        seen_entities = set()
        last_antecedent: Optional[Dict[str, str]] = None

        for sent_idx, sent_text, char_start, char_end in sentences_raw:
            raw_tokens = re.findall(r"[а-яА-ЯёЁa-zA-Z0-9-]+", sent_text)
            tokens_info: List[Dict[str, Any]] = []
            is_negated = any(t.lower() in ("не", "нет", "ни") for t in raw_tokens)

            # 1. Проверка конструкции принадлежности: "У <владелец> был/была/было/есть <объект>"
            poss_match = re.match(
                r"^[Уу]\s+([а-яА-ЯёЁa-zA-Z0-9\s-]+?)\s+(?:не\s+)?(?:был|была|было|были|есть)\s+([а-яА-ЯёЁa-zA-Z0-9\s-]+?)[.!?]*$",
                sent_text.strip(),
            )
            if poss_match:
                owner_raw = poss_match.group(1).strip()
                poss_raw = poss_match.group(2).strip()
                if owner_raw.lower() in _RU_PRONOUNS_POSS and last_antecedent is not None:
                    owner_text = last_antecedent["text"]
                    owner_lemma = last_antecedent["lemma"]
                else:
                    owner_text = owner_raw
                    owner_words = [RussianMorphology.analyze_noun(w)["lemma"] for w in owner_raw.split() if not RussianMorphology.is_adjective(w)]
                    if not owner_words:
                        owner_words = [RussianMorphology.analyze_noun(owner_raw.split()[0])["lemma"]]
                    owner_lemma = " ".join(owner_words)
                    if owner_raw.lower() not in _RU_PRONOUNS_POSS:
                        last_antecedent = {"text": owner_lemma, "lemma": owner_lemma}

                poss_head = RussianMorphology.analyze_noun(poss_raw.split()[-1])["lemma"]
                fact = {
                    "fact_type": "possession",
                    "language": "ru",
                    "relation": "has",
                    "owner": {
                        "text": owner_text,
                        "normalized": owner_lemma,
                        "lemma": owner_lemma,
                        "entity_type": "person",
                    },
                    "possessed_entity": {
                        "text": poss_raw,
                        "normalized": poss_head,
                        "lemma": poss_head,
                        "entity_type": "property",
                    },
                    "is_negated": is_negated,
                    "confidence": 0.95,
                    "source": {
                        "document_id": document_id,
                        "sentence_index": sent_idx,
                        "char_start": char_start,
                        "char_end": char_end,
                        "quote": sent_text,
                    },
                }
                facts.append(fact)

            subject_tok: Optional[Dict[str, Any]] = None
            predicate_tok: Optional[Dict[str, Any]] = None
            object_tok: Optional[Dict[str, Any]] = None
            pending_modifiers: List[str] = []

            for tok in raw_tokens:
                t_low = tok.lower()
                if t_low in ("не", "нет", "ни"):
                    tokens_info.append({"text": tok, "lemma": t_low, "pos": "PART", "role": "negation"})
                    continue
                if t_low in _RU_AUX_VERBS or t_low in _RU_STOPWORDS:
                    tokens_info.append({"text": tok, "lemma": t_low, "pos": "AUX", "role": "aux"})
                    continue

                v_info = RussianMorphology.analyze_verb(tok)
                if v_info and predicate_tok is None:
                    predicate_tok = {
                        "text": tok,
                        "lemma": v_info["lemma"],
                        "pos": "VERB",
                        "tense": v_info.get("tense", "past"),
                        "voice": v_info.get("voice", "active"),
                        "role": "predicate",
                    }
                    tokens_info.append(predicate_tok)
                    pending_modifiers.clear()
                    continue

                if RussianMorphology.is_adjective(tok):
                    pending_modifiers.append(tok)
                    tokens_info.append({"text": tok, "lemma": t_low, "pos": "ADJ", "role": "modifier"})
                    continue

                n_info = RussianMorphology.analyze_noun(tok)
                full_surface = (" ".join(pending_modifiers + [tok])).strip() if pending_modifiers else tok
                pending_modifiers.clear()

                tok_entry = {
                    "text": tok,
                    "full_text": full_surface,
                    "lemma": n_info["lemma"],
                    "pos": "NOUN",
                    "case": n_info["case"],
                }

                if predicate_tok and predicate_tok.get("voice") == "passive":
                    if n_info["case"] == "inst" and subject_tok is None:
                        tok_entry["role"] = "subject"
                        subject_tok = tok_entry
                    elif object_tok is None:
                        tok_entry["role"] = "object"
                        object_tok = tok_entry
                else:
                    if n_info["case"] == "nomn" and subject_tok is None:
                        tok_entry["role"] = "subject"
                        subject_tok = tok_entry
                    elif n_info["case"] in ("accs", "gent", "datv", "inst") and object_tok is None:
                        tok_entry["role"] = "object"
                        object_tok = tok_entry
                    elif subject_tok is None:
                        tok_entry["role"] = "subject"
                        subject_tok = tok_entry
                    elif object_tok is None:
                        tok_entry["role"] = "object"
                        object_tok = tok_entry

                tokens_info.append(tok_entry)
                if n_info["lemma"] not in seen_entities:
                    seen_entities.add(n_info["lemma"])
                    entities.append({
                        "text": tok,
                        "normalized": n_info["lemma"],
                        "lemma": n_info["lemma"],
                        "entity_type": "entity",
                        "language": "ru",
                    })

            if subject_tok and predicate_tok and not poss_match:
                subj_text_val = subject_tok["text"]
                subj_full_val = subject_tok.get("full_text", subj_text_val)
                subj_lemma_val = subject_tok["lemma"]
                if subj_lemma_val in _RU_PRONOUNS_SUBJ and last_antecedent is not None:
                    subj_text_val = last_antecedent["text"]
                    subj_full_val = last_antecedent["text"]
                    subj_lemma_val = last_antecedent["lemma"]
                elif subj_lemma_val not in _RU_PRONOUNS_SUBJ:
                    last_antecedent = {"text": subj_text_val, "lemma": subj_lemma_val}

                action_fact: Dict[str, Any] = {
                    "fact_type": "action",
                    "language": "ru",
                    "relation": predicate_tok["lemma"],
                    "subject": {
                        "text": subj_text_val,
                        "full_text": subj_full_val,
                        "lemma": subj_lemma_val,
                        "normalized": subj_lemma_val,
                        "case": subject_tok.get("case", "nomn"),
                    },
                    "predicate": {
                        "text": predicate_tok["text"],
                        "lemma": predicate_tok["lemma"],
                        "tense": predicate_tok.get("tense", "past"),
                        "voice": predicate_tok.get("voice", "active"),
                    },
                    "object": {
                        "text": object_tok["text"] if object_tok else "",
                        "full_text": object_tok.get("full_text", object_tok["text"]) if object_tok else "",
                        "lemma": object_tok["lemma"] if object_tok else "",
                        "normalized": object_tok["lemma"] if object_tok else "",
                        "case": object_tok.get("case", "accs") if object_tok else "",
                    } if object_tok else None,
                    "is_negated": is_negated,
                    "confidence": 0.98 if object_tok else 0.85,
                    "source": {
                        "document_id": document_id,
                        "sentence_index": sent_idx,
                        "char_start": char_start,
                        "char_end": char_end,
                        "quote": sent_text,
                    },
                }
                facts.append(action_fact)

            sentences_out.append({
                "sentence_index": sent_idx,
                "text": sent_text,
                "char_start": char_start,
                "char_end": char_end,
                "tokens": tokens_info,
                "is_negated": is_negated,
            })

        return {
            "language": "ru",
            "analyzer": self.analyzer_name,
            "version": self.version,
            "document_id": document_id,
            "sentences": sentences_out,
            "entities": entities,
            "facts": facts,
            "confidence": 0.96 if facts else 0.6,
        }
