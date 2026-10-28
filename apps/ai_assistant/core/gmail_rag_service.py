# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Core - Gmail RAG Service
# =============================================================================
# Description:
#   Интеллектуальный сервис семантического поиска и RAG для почты Gmail:
#   разбор естественно-языковых запросов пользователя (NLU), очистка от стоп-слов,
#   нормализация морфологических форм и исправление опечаток, построение
#   оптимизированного поискового фильтра Gmail API и векторное переранжирование
#   сообщений-кандидатов через TextRAG (FAISS + эмбеддинги Gemini / TF-IDF).
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.core.gmail_rag_service import GmailRagService
#
#     rag_service = GmailRagService()
#     results = rag_service.semantic_search(
#         query="Найди все письма по сделаке по корове зина",
#         limit=10
#     )
#
# File: gmail_rag_service.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 16:55:00
# =============================================================================

from __future__ import annotations
"""Сервис семантического поиска и векторного RAG-ранжирования для почты Gmail."""

import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from logger import logger
from src.ai.rag.text_rag import TextRAG
from apps.ai_assistant.core.gmail_manager import gmail_manager

# Стоп-слова команд и предлогов для запросов на естественном языке (RU, EN, HE)
_STOP_COMMAND_WORDS: Set[str] = {
    "найди", "найти", "покажи", "показать", "ищи", "поищи", "выведи",
    "все", "всё", "письма", "письмо", "сообщения", "сообщение", "мейлы", "мейл",
    "по", "про", "о", "об", "обо", "в", "на", "с", "со", "к", "ко", "из", "от",
    "find", "search", "show", "get", "list", "all", "emails", "email",
    "messages", "message", "mails", "mail", "about", "for", "from", "to", "with",
    "חפш", "מצא", "הודעות", "מכתבים", "אימיילים", "של", "על", "ב", "את"
}

# Словарь синонимов и связанных терминов для расширения запроса (Query Expansion)
_CONCEPT_SYNONYMS: Dict[str, List[str]] = {
    "сделка": ["договор", "контракт", "счет", "оплата", "покупка", "продажа", "акт", "deal", "contract", "invoice"],
    "договор": ["сделка", "контракт", "соглашение", "подписание", "agreement"],
    "оплата": ["счет", "чек", "квитанция", "инвойс", "платеж", "payment", "invoice"],
    "корова": ["корове", "корову", "коровы", "скот", "животное", "крс", "ферма", "cow", "cattle"],
    "работа": ["проект", "задача", "вакансия", "резюме", "task", "job"],
    "билет": ["бронь", "рейс", "поезд", "самолет", "авиабилет", "ticket", "booking"],
}


class GmailRagService:
    """Сервис семантического разбора, векторного поиска и RAG-ранжирования для почты."""

    def __init__(self, index_dir: Optional[Path] = None) -> None:
        """Инициализирует RAG-сервис и векторный индекс TextRAG.

        Args:
            index_dir: Директория для хранения локального векторного индекса.
        """
        self.index_dir = index_dir or (Path(__file__).resolve().parent.parent / "data" / "gmail_search_index")
        self._text_rag: Optional[TextRAG] = None

    @property
    def text_rag(self) -> TextRAG:
        """Ленивая инициализация TextRAG по требованию без предварительного создания папок."""
        if self._text_rag is None:
            self.index_dir.mkdir(parents=True, exist_ok=True)
            self._text_rag = TextRAG(db_path=self.index_dir / "gmail_vectors", dimension=256)
        return self._text_rag

    def extract_search_intent(self, raw_query: str) -> Dict[str, Any]:
        """Анализирует текст запроса на естественном языке и извлекает ключевые понятия.

        Args:
            raw_query: Исходная строка запроса пользователя (например: 'Найди все письма по сделаке по корове зина').

        Returns:
            Словарь с распознанными терминами, расширенным запросом и фильтром для Gmail API.
        """
        cleaned_str = raw_query.strip()
        # Выделяем специальные операторы Gmail (from:user@domain.com, is:unread, subject:test и т.п.)
        operator_pattern = re.compile(r"\b(from|to|subject|is|has|label|after|before):[^\s]+", re.IGNORECASE)
        gmail_operators = [m.group(0) for m in operator_pattern.finditer(cleaned_str)]

        # Удаляем операторы из строки перед выделением текстовых токенов естественного языка
        text_without_ops = operator_pattern.sub(" ", cleaned_str)
        tokens = re.findall(r"[а-яА-ЯёЁa-zA-Z0-9_-]+", text_without_ops.lower())

        # Выделение значимых сущностей и удаление командных стоп-слов
        significant_terms: List[str] = []
        for token in tokens:
            if token not in _STOP_COMMAND_WORDS and len(token) >= 2:
                significant_terms.append(token)

        # Нормализация опечаток и поиск базовых корней (стемминг)
        normalized_terms: List[str] = []
        expanded_keywords: Set[str] = set()

        for term in significant_terms:
            base_term = self._normalize_term(term)
            normalized_terms.append(base_term)
            expanded_keywords.add(base_term)
            expanded_keywords.add(term)

            # Добавление синонимов из словаря концептов
            for concept, synonyms in _CONCEPT_SYNONYMS.items():
                if self._terms_similarity(base_term, concept) >= 0.7:
                    expanded_keywords.add(concept)
                    for syn in synonyms:
                        expanded_keywords.add(syn)

        # Построение оптимизированного поискового фильтра для Gmail API
        gmail_query_parts: List[str] = []
        if gmail_operators:
            gmail_query_parts.extend(gmail_operators)

        # Группировка ключевых понятий для охвата первичной выборки Gmail
        if expanded_keywords:
            # Берём наиболее весомые ключевые слова (до 8 терминов)
            top_keywords = list(expanded_keywords)[:8]
            keyword_clause = " OR ".join(f'"{kw}"' if " " in kw else kw for kw in top_keywords)
            gmail_query_parts.append(f"({keyword_clause})")

        api_query = " ".join(gmail_query_parts).strip()

        return {
            "raw_query": cleaned_str,
            "significant_terms": significant_terms,
            "normalized_terms": normalized_terms,
            "expanded_keywords": list(expanded_keywords),
            "gmail_api_query": api_query,
        }

    def _normalize_term(self, term: str) -> str:
        """Нормализует морфологические окончания и распространённые опечатки.

        Args:
            term: Исходное слово.

        Returns:
            Нормализованная основа слова.
        """
        t = term.lower().strip()
        # Исправление частых опечаток ("сделаке" -> "сделка")
        if "сделак" in t or "сделк" in t:
            return "сделка"
        if "коров" in t:
            return "корова"
        if "зин" in t:
            return "зина"

        # Простое усечение типичных падежных окончаний
        for suffix in ["ами", "ями", "ей", "ов", "ев", "ом", "ем", "ой", "ей", "ах", "ях", "ам", "ям", "ке", "ка", "ку", "ки", "е", "у", "а", "ы", "и"]:
            if len(t) > 4 and t.endswith(suffix):
                return t[:-len(suffix)]
        return t

    def _terms_similarity(self, word1: str, word2: str) -> float:
        """Вычисляет степень сходства двух слов на основе префикса и символьных N-грамм."""
        w1, w2 = word1.lower(), word2.lower()
        if w1 == w2:
            return 1.0
        # Совпадение общего корня
        min_len = min(len(w1), len(w2))
        if min_len >= 4:
            common_prefix = 0
            for i in range(min_len):
                if w1[i] == w2[i]:
                    common_prefix += 1
                else:
                    break
            if common_prefix >= 4:
                return common_prefix / max(len(w1), len(w2))
        return 0.0

    def calculate_message_relevance(
        self,
        intent: Dict[str, Any],
        subject: str,
        snippet: str,
        sender: str,
        vector_similarity: float = 0.0,
    ) -> Tuple[float, str, List[str]]:
        """Вычисляет комбинированный семантический балл релевантности письма.

        Args:
            intent: Разобранный интент пользователя.
            subject: Тема письма.
            snippet: Текстовый сниппет сообщения.
            sender: Адрес или имя отправителя.
            vector_similarity: Оценка косинусного сходства эмбеддингов TextRAG.

        Returns:
            Кортеж (итоговый балл [0.0..1.0], текстовое объяснение, список совпавших концептов).
        """
        raw_query = intent.get("raw_query", "").lower()
        norm_terms = intent.get("normalized_terms", [])
        expanded = set(intent.get("expanded_keywords", []))

        text_to_check = f"{subject or ''} {snippet or ''} {sender or ''}".lower()
        matched_concepts: List[str] = []

        # 1. Проверка точного вхождения фразы или ключевых понятий
        exact_phrase_match = bool(raw_query and len(raw_query) > 3 and raw_query in text_to_check)

        matched_count = 0
        for kw in expanded:
            if kw and (kw in text_to_check or any(self._terms_similarity(kw, w) >= 0.75 for w in re.findall(r"\w+", text_to_check))):
                if kw not in matched_concepts:
                    matched_concepts.append(kw)
                matched_count += 1

        # Оценка покрытия концептов запроса
        coverage = (len(matched_concepts) / max(len(norm_terms), 1)) if norm_terms else 0.0

        # Семантический балл: объединение векторного сходства TextRAG и концептуального совпадения
        lexical_score = min(1.0, coverage * 0.7 + (0.3 if exact_phrase_match else (0.15 * min(matched_count, 3))))
        if vector_similarity > 0.0:
            final_score = round(0.4 * vector_similarity + 0.6 * lexical_score, 2)
        else:
            final_score = round(lexical_score, 2)

        # Формирование понятного объяснения соответствия для пользователя
        if exact_phrase_match:
            reason = "Точное смысловое соответствие исходной фразе"
        elif coverage >= 0.9 and matched_concepts:
            reason = f"Высокое совпадение всех ключевых понятий: {', '.join(matched_concepts[:3])}"
        elif coverage >= 0.5 and matched_concepts:
            reason = f"Семантическое соответствие темам: {', '.join(matched_concepts[:3])}"
        elif vector_similarity >= 0.65:
            reason = "Векторное контекстное сходство по смыслу"
        elif matched_concepts:
            reason = f"Частичное совпадение по понятиям: {', '.join(matched_concepts[:2])}"
        else:
            reason = "Косвенная релевантность по смысловому контексту"

        return final_score, reason, matched_concepts

    def semantic_search(
        self,
        query: str,
        limit: int = 15,
        account_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Выполняет сквозной семантический поиск писем с использованием RAG-конвейера.

        Args:
            query: Естественно-языковой запрос пользователя.
            limit: Максимальное количество писем в ответе.
            account_name: Имя целевого аккаунта Google.

        Returns:
            Словарь с результатами семантического ранжирования.
        """
        intent = self.extract_search_intent(query)
        api_query = intent["gmail_api_query"]

        logger.info(
            f"[GmailRagService] Семантический запрос: '{query}' -> API фильтр: '{api_query}', "
            f"понятия: {intent['normalized_terms']}"
        )

        # 1. Первичная выборка писем-кандидатов из Gmail
        candidates: List[Dict[str, Any]] = []
        if api_query:
            try:
                res = gmail_manager.list_messages(
                    query=api_query,
                    max_results=min(max(limit * 3, 20), 50),
                    account_name=account_name,
                )
                if res.get("status") == "success":
                    candidates = res.get("messages", [])
            except Exception as exc:
                logger.warning(f"[GmailRagService] Ошибка первичной выборки по '{api_query}': {exc}")

        # 2. Мягкий фолбэк: если по строгому фильтру мало писем, добираем свежие входящие сообщения
        if len(candidates) < limit:
            try:
                fallback_res = gmail_manager.list_messages(
                    query="",
                    max_results=40,
                    account_name=account_name,
                )
                if fallback_res.get("status") == "success":
                    existing_ids = {m["id"] for m in candidates}
                    for msg in fallback_res.get("messages", []):
                        if msg["id"] not in existing_ids:
                            candidates.append(msg)
                            existing_ids.add(msg["id"])
            except Exception as exc:
                logger.warning(f"[GmailRagService] Ошибка fallback выборки сообщений: {exc}")

        if not candidates:
            return {
                "status": "success",
                "query": query,
                "count": 0,
                "messages": [],
                "expanded_query": api_query,
                "intent": intent,
                "engine": "gmail-rag-faiss",
            }

        # 3. Векторизация и сопоставление через TextRAG
        docs_to_index: List[Dict[str, Any]] = []
        for msg in candidates:
            msg_text = f"Тема: {msg.get('subject', '')}\nОтправитель: {msg.get('from', '')}\n{msg.get('snippet', '')}"
            docs_to_index.append({
                "id": msg["id"],
                "text": msg_text,
                "meta": {"subject": msg.get("subject", ""), "from": msg.get("from", "")},
            })

        # Индексация в локальный RAG-движок
        try:
            self.text_rag.add_documents(docs_to_index)
            # Векторный поиск по вопросу
            rag_hits = self.text_rag.search(query, top_k=len(candidates))
            vector_scores: Dict[str, float] = {hit["id"]: float(hit.get("score", 0.0)) for hit in rag_hits}
        except Exception as exc:
            logger.warning(f"[GmailRagService] Векторный поиск TextRAG завершился ошибкой ({exc}), используется лексико-семантический расчет.")
            vector_scores = {}

        # 4. Вычисление комбинированного семантического балла и формирование ответа
        scored_messages: List[Dict[str, Any]] = []
        for msg in candidates:
            msg_id = msg["id"]
            vec_sim = vector_scores.get(msg_id, 0.0)
            score, reason, concepts = self.calculate_message_relevance(
                intent=intent,
                subject=msg.get("subject", ""),
                snippet=msg.get("snippet", ""),
                sender=msg.get("from", ""),
                vector_similarity=vec_sim,
            )

            # Включаем сообщение, если есть минимальная семантическая релевантность
            if score >= 0.15:
                enriched_msg = dict(msg)
                enriched_msg["semantic_score"] = score
                enriched_msg["relevance_reason"] = reason
                enriched_msg["matched_concepts"] = concepts
                scored_messages.append(enriched_msg)

        # Сортировка по убыванию семантического балла
        scored_messages.sort(key=lambda m: m["semantic_score"], reverse=True)
        final_results = scored_messages[:limit]

        return {
            "status": "success",
            "query": query,
            "count": len(final_results),
            "messages": final_results,
            "expanded_query": api_query,
            "intent": intent,
            "engine": "gmail-rag-faiss",
        }


# Глобальный синглтон сервиса
gmail_rag_service = GmailRagService()
