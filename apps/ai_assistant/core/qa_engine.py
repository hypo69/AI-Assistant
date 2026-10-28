# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Core - Knowledge QA Engine
# =============================================================================
# Description:
#   Гибридный движок анализа вопросов, поиска фактов (SQLite + FAISS + WikiLLM),
#   проверки непротиворечивости субъектов/объектов, учёта отрицаний (is_negated),
#   морфологического согласования ответов (RU, HE, EN) и маршрутизации к моделям
#   из модуля src/ai (UnifiedChatModel: Gemini, AGY, OpenAI, Ollama, Foundry).
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.core.qa_engine import KnowledgeQAEngine
#
#     qa = KnowledgeQAEngine(workspace_manager=wm)
#     res = await qa.ask("Кем была вымыта рама?", workspace_id="default", mode="local_first")
#
# File: qa_engine.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-25 23:18:00
# =============================================================================

from __future__ import annotations
"""Движок обработки вопросов, гибридного поиска и грамматического синтеза ответов."""

import asyncio, time
from typing import Any, Callable, Dict, List, Optional, Tuple

from logger import logger
from apps.ai_assistant.core.nlp.intent_parser import QuestionIntentParser
from apps.ai_assistant.core.nlp_analyzers import (
    RussianMorphology,
    strip_hebrew_article,
)
from apps.ai_assistant.core.workspace_manager import WorkspaceManager

VALID_MODES = {"local_only", "local_first", "cloud_assist", "cloud_enrich"}


def _tokens_match(query_lemma: str, target_text: str) -> bool:
    """Проверяет совпадение леммы вопроса с леммой или словами сущности без ложных подстрок."""
    ql = query_lemma.strip().lower()
    tt = target_text.strip().lower()
    if not ql or not tt:
        return False
    if ql == tt:
        return True
    target_words = tt.split()
    if ql in target_words:
        return True
    # Допускаем совпадение по корню от 4 символов в начале слова
    if len(ql) >= 4 and any(w.startswith(ql[:4]) or ql.startswith(w[:4]) for w in target_words if len(w) >= 4):
        return True
    return False


class KnowledgeQAEngine:
    """Главный оркестратор гибридного поиска и грамматического формирования ответов (ТЗ разделы 4, 5, 8)."""

    def __init__(
        self,
        workspace_manager: Optional[WorkspaceManager] = None,
        cloud_policy_enabled: bool = True,
        default_provider: str = "gemini",
        default_model: str = "gemini-3.1-flash-lite",
        chat_model_factory: Optional[Callable[..., Any]] = None,
    ) -> None:
        """Инициализирует QA-движок с поддержкой локального и облачного контуров.

        Args:
            workspace_manager: Менеджер рабочих областей.
            cloud_policy_enabled: Разрешены ли вызовы облачных моделей политикой безопасности.
            default_provider: Провайдер из модуля src/ai по умолчанию ('gemini', 'agy', 'openai', 'ollama').
            default_model: Идентификатор модели по умолчанию.
            chat_model_factory: Фабрика создания UnifiedChatModel (для DI и тестирования отказов).
        """
        self.wm = workspace_manager or WorkspaceManager()
        self.cloud_policy_enabled = cloud_policy_enabled
        self.default_provider = default_provider
        self.default_model = default_model
        self.chat_model_factory = chat_model_factory

    def _match_facts_locally(
        self,
        parsed_q: Dict[str, Any],
        facts: List[Dict[str, Any]],
    ) -> List[Tuple[float, Dict[str, Any]]]:
        """Сопоставляет разобранный вопрос с активными фактами SQLite с проверкой ролей и отрицаний."""
        q_lang = parsed_q["language"]
        q_lemmas = [l.lower() for l in parsed_q.get("content_lemmas", []) if l]
        q_nouns = [n.lower() for n in parsed_q.get("noun_lemmas", []) if n]
        intent = parsed_q.get("intent", "unknown")
        q_negated = bool(parsed_q.get("is_negated", False))
        scored: List[Tuple[float, Dict[str, Any]]] = []

        for fact in facts:
            if fact.get("status") in ("stale", "rejected"):
                continue
            if fact.get("language") != q_lang:
                continue

            f_type = fact.get("fact_type", "action")
            f_negated = bool(fact.get("is_negated", False))
            score = 0.0

            if f_type == "possession":
                owner = fact.get("owner") or {}
                possessed = fact.get("possessed_entity") or {}
                owner_text = (owner.get("normalized") or owner.get("text") or "").lower()
                poss_text = (possessed.get("normalized") or possessed.get("text") or "").lower()
                poss_attr = (possessed.get("attribute") or "").lower()
                poss_lemma = strip_hebrew_article(poss_text) if q_lang == "he" else poss_text

                owner_matched = any(_tokens_match(ql, owner_text) for ql in q_lemmas)
                poss_matched = any(
                    _tokens_match(ql, poss_lemma) or _tokens_match(ql, poss_text) or (poss_attr and _tokens_match(ql, poss_attr))
                    for ql in q_lemmas
                )

                # Контроль непротиворечивости ролей для вопросов о принадлежности
                if intent == "possessed_query" and not owner_matched:
                    continue
                if intent == "owner_query" and not poss_matched:
                    continue

                if owner_matched:
                    score += 2.5
                if poss_matched:
                    score += 2.5

                if (owner_matched or poss_matched) and intent in (
                    "possessed_query",
                    "owner_query",
                    "yes_no_query",
                    "relation_query",
                    "object_query",
                ):
                    score += 1.5

            elif f_type == "action":
                subj = fact.get("subject") or {}
                pred = fact.get("predicate") or {}
                obj = fact.get("object") or {}

                subj_lemma = (subj.get("lemma") or subj.get("normalized") or subj.get("text") or "").lower()
                pred_lemma = (pred.get("lemma") or pred.get("text") or "").lower()
                obj_lemma = (obj.get("lemma") or obj.get("normalized") or obj.get("text") or "").lower()
                if q_lang == "he":
                    obj_lemma = strip_hebrew_article(obj_lemma)
                    subj_lemma = strip_hebrew_article(subj_lemma)

                subj_matched = any(_tokens_match(ql, subj_lemma) for ql in q_lemmas)
                pred_matched = any(_tokens_match(ql, pred_lemma) for ql in q_lemmas)
                obj_matched = bool(obj_lemma) and any(_tokens_match(ql, obj_lemma) for ql in q_lemmas)

                # Защита от ложных срабатываний: если вопрос спрашивает про объект ("Что мыла бабушка?"),
                # но указанный в вопросе субъект ("бабушка") противоречит субъекту факта ("мама") -> отсекаем
                if intent in ("object_query", "action_query") and q_nouns:
                    if not subj_matched:
                        continue
                # Если вопрос спрашивает про субъект ("Кто мыл машину?"),
                # но указанный в вопросе объект ("машина") противоречит объекту факта ("рама") -> отсекаем
                if intent in ("subject_query", "agent_instrumental_query", "agent_passive_query") and q_nouns and obj_lemma:
                    # Для иврита и английского глагол тоже может входить в q_nouns, поэтому проверяем совпадение с obj_lemma
                    if not obj_matched:
                        continue

                if pred_matched:
                    score += 2.5
                if subj_matched:
                    score += 2.5
                if obj_matched:
                    score += 2.5

            # Приоритет утвердительным фактам для утвердительных открытых вопросов
            if intent != "yes_no_query":
                if f_negated != q_negated:
                    score -= 0.4

            if score >= 2.0:
                scored.append((score, fact))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored

    @staticmethod
    def _yes_no_confirmed(parsed_q: Dict[str, Any], fact: Dict[str, Any]) -> bool:
        """Проверяет, подтверждает ли факт ВСЕ роли, названные в вопросе «да/нет».

        Факт, совпавший только по владельцу/субъекту («לדוד מושה היתה חווה»), не подтверждает
        вопрос о другой сущности («האם הייתה לדוד מושה פרה?») — ответ должен быть отрицательным.

        Args:
            parsed_q: Разобранный вопрос (QuestionIntentParser).
            fact: Найденный факт.

        Returns:
            bool: True — все роли вопроса совпали с фактом; False — есть несовпадающая роль.
        """
        is_he = parsed_q.get("language") == "he"
        q_lemmas = [l.lower() for l in parsed_q.get("content_lemmas", []) if l]

        def role_text(entity: Dict[str, Any], *keys: str) -> str:
            text = next((entity.get(k) for k in keys if entity.get(k)), "") or ""
            text = text.lower()
            return strip_hebrew_article(text) if is_he else text

        def matched(ql: str, *targets: str) -> bool:
            return any(t and _tokens_match(ql, t) for t in targets)

        if fact.get("fact_type") == "possession":
            owner = role_text(fact.get("owner") or {}, "normalized", "text")
            possessed = fact.get("possessed_entity") or {}
            poss = role_text(possessed, "normalized", "text")
            attr = (possessed.get("attribute") or "").lower()
            return any(matched(ql, owner) for ql in q_lemmas) and any(matched(ql, poss, attr) for ql in q_lemmas)

        subj = role_text(fact.get("subject") or {}, "lemma", "normalized", "text")
        pred = role_text(fact.get("predicate") or {}, "lemma", "text")
        obj = role_text(fact.get("object") or {}, "lemma", "normalized", "text")
        if not any(matched(ql, subj) for ql in q_lemmas):
            return False
        # Все остальные леммы вопроса (кроме субъекта и сказуемого) должны совпасть с объектом факта
        leftover = [ql for ql in q_lemmas if not matched(ql, subj, pred)]
        return all(matched(ql, obj) for ql in leftover)

    def _synthesize_grammatical_answer(
        self,
        parsed_q: Dict[str, Any],
        fact: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Формирует грамматически согласованный ответ по найденному факту (ТЗ п. 3.6, 3.4.1)."""
        lang = parsed_q["language"]
        intent = parsed_q["intent"]
        target_case = parsed_q.get("target_case", "nomn")
        q_negated = bool(parsed_q.get("is_negated", False))
        f_type = fact.get("fact_type", "action")
        is_neg = bool(fact.get("is_negated"))

        # Вопрос «да/нет» о сущности, которой нет в факте -> «Нет» + известный факт из документа
        if intent == "yes_no_query" and not self._yes_no_confirmed(parsed_q, fact):
            quote = fact.get("source", {}).get("quote", "")
            prefix = {"he": ("לא", "לפי המסמכים: "), "en": ("No.", "According to the documents: ")}.get(
                lang, ("Нет.", "Согласно документам: ")
            )
            ans = f"{prefix[0]} {prefix[1]}{quote}" if quote else prefix[0]
            return {
                "answer": ans,
                "canonical_entity": prefix[0],
                "surface_form": quote,
                "grammatical_form": "boolean_role_mismatch",
            }

        # Если факт в базе отрицательный ("Мама не мыла раму"), а вопрос задан в утвердительной открытой форме
        # ("Что мыла мама?" / "Кто мыл раму?"), нельзя возвращать утвердительную сущность как факт!
        if is_neg and not q_negated and intent not in ("yes_no_query", "relation_query"):
            quote = fact.get("source", {}).get("quote", "")
            if lang == "he":
                neg_ans = f"לא בוצע ({quote})" if quote else "לא"
            elif lang == "en":
                neg_ans = f"None ({quote})" if quote else "No."
            else:
                neg_ans = f"Отрицание в источнике: {quote}" if quote else "Нет."
            return {
                "answer": neg_ans,
                "canonical_entity": "negated",
                "surface_form": quote,
                "grammatical_form": "negated_fact_notice",
            }

        if lang == "he":
            if f_type == "possession":
                owner = fact.get("owner") or {}
                possessed = fact.get("possessed_entity") or {}
                owner_norm = owner.get("normalized") or owner.get("text") or ""
                poss_text = possessed.get("text") or possessed.get("normalized") or ""

                if intent == "possessed_query":
                    return {
                        "answer": poss_text,
                        "canonical_entity": possessed.get("normalized", poss_text),
                        "surface_form": poss_text,
                        "grammatical_form": "base_noun",
                    }
                if intent == "owner_query":
                    with_prep = owner.get("with_preposition") or f"ל{owner_norm}"
                    return {
                        "answer": with_prep,
                        "canonical_entity": owner_norm,
                        "surface_form": owner.get("text", owner_norm),
                        "grammatical_form": "lamed_possession (ל־)",
                    }
                if intent == "yes_no_query":
                    ans = "לא" if is_neg else "כן"
                    return {
                        "answer": ans,
                        "canonical_entity": ans,
                        "surface_form": ans,
                        "grammatical_form": "boolean_affirmation",
                    }
                if intent == "relation_query":
                    verb_word = "לא הייתה" if is_neg else "הייתה"
                    rel_stmt = f"ל{owner_norm} {verb_word} {poss_text}"
                    return {
                        "answer": rel_stmt,
                        "canonical_entity": f"{owner_norm} -> {poss_text}",
                        "surface_form": rel_stmt,
                        "grammatical_form": "canonical_possession_statement",
                    }

            if f_type == "action":
                subj = fact.get("subject") or {}
                obj = fact.get("object") or {}

                if intent == "subject_query":
                    ans = subj.get("text") or subj.get("normalized") or ""
                    return {
                        "answer": ans,
                        "canonical_entity": subj.get("lemma", ans),
                        "surface_form": ans,
                        "grammatical_form": "nominative_subject",
                    }
                if intent == "agent_passive_query":
                    ans_base = subj.get("text") or subj.get("normalized") or ""
                    ans = f"על ידי {ans_base}"
                    return {
                        "answer": ans,
                        "canonical_entity": subj.get("lemma", ans_base),
                        "surface_form": ans_base,
                        "grammatical_form": "passive_agent (על ידי)",
                    }
                if intent == "object_query" and obj:
                    ans = obj.get("text") or obj.get("normalized") or ""
                    return {
                        "answer": ans,
                        "canonical_entity": obj.get("lemma", ans),
                        "surface_form": obj.get("raw_text", ans),
                        "grammatical_form": "direct_object",
                    }
                if intent == "yes_no_query":
                    ans = "לא" if is_neg else "כן"
                    return {
                        "answer": ans,
                        "canonical_entity": ans,
                        "surface_form": ans,
                        "grammatical_form": "boolean_affirmation",
                    }

        elif lang == "ru":
            if f_type == "action":
                subj = fact.get("subject") or {}
                pred = fact.get("predicate") or {}
                obj = fact.get("object") or {}

                if intent in ("subject_query", "agent_instrumental_query"):
                    lemma = subj.get("lemma") or subj.get("text") or ""
                    inflected = RussianMorphology.inflect(lemma, target_case, capitalize=True)
                    return {
                        "answer": f"{inflected}.",
                        "canonical_entity": lemma,
                        "surface_form": subj.get("text", lemma),
                        "grammatical_form": target_case,
                    }
                if intent == "object_query" and obj:
                    lemma = obj.get("lemma") or obj.get("text") or ""
                    inflected = RussianMorphology.inflect(lemma, target_case, capitalize=True)
                    return {
                        "answer": f"{inflected}.",
                        "canonical_entity": lemma,
                        "surface_form": obj.get("text", lemma),
                        "grammatical_form": target_case,
                    }
                if intent == "action_query":
                    p_text = (pred.get("text") or pred.get("lemma") or "").capitalize()
                    o_text = obj.get("text", "") if obj else ""
                    full_act = f"{p_text} {o_text}".strip() + "."
                    return {
                        "answer": full_act,
                        "canonical_entity": pred.get("lemma", ""),
                        "surface_form": pred.get("text", ""),
                        "grammatical_form": "predicate_phrase",
                    }
                if intent == "yes_no_query":
                    ans = "Нет." if is_neg else "Да."
                    return {
                        "answer": ans,
                        "canonical_entity": ans,
                        "surface_form": ans,
                        "grammatical_form": "boolean",
                    }

            elif f_type == "possession":
                owner = fact.get("owner") or {}
                possessed = fact.get("possessed_entity") or {}
                if intent in ("object_query", "possessed_query"):
                    ans = (possessed.get("text") or possessed.get("normalized") or "").capitalize() + "."
                    return {
                        "answer": ans,
                        "canonical_entity": possessed.get("lemma", ""),
                        "surface_form": possessed.get("text", ""),
                        "grammatical_form": "nomn",
                    }
                if intent == "owner_query":
                    lemma = owner.get("lemma") or owner.get("text") or ""
                    inflected = RussianMorphology.inflect(lemma, "gent", capitalize=True)
                    return {
                        "answer": f"У {inflected}.",
                        "canonical_entity": lemma,
                        "surface_form": owner.get("text", ""),
                        "grammatical_form": "gent_with_u",
                    }
                if intent == "yes_no_query":
                    ans = "Нет." if is_neg else "Да."
                    return {
                        "answer": ans,
                        "canonical_entity": ans,
                        "surface_form": ans,
                        "grammatical_form": "boolean",
                    }

        elif lang == "en":
            subj = fact.get("subject") or fact.get("owner") or {}
            obj = fact.get("object") or fact.get("possessed_entity") or {}
            if intent == "yes_no_query":
                ans = "No." if is_neg else "Yes."
                return {"answer": ans, "canonical_entity": ans, "surface_form": ans, "grammatical_form": "boolean"}
            if intent in ("subject_query", "agent_instrumental_query"):
                ans = subj.get("text", "")
                return {"answer": ans, "canonical_entity": subj.get("lemma", ans), "surface_form": ans, "grammatical_form": "subject"}
            if obj:
                ans = obj.get("text", "")
                return {"answer": ans, "canonical_entity": obj.get("lemma", ans), "surface_form": ans, "grammatical_form": "object"}

        return None

    async def _call_cloud_model(
        self,
        workspace_id: str,
        question: str,
        language: str,
        context_snippets: List[str],
        provider: str,
        model_name: str,
    ) -> Optional[str]:
        """Обращается к языковой модели через единый модуль src/ai (UnifiedChatModel) с контролем отказов."""
        if not self.cloud_policy_enabled:
            logger.info("[KnowledgeQAEngine] Облачные вызовы отключены политикой конфигурации.")
            return None

        t0 = time.perf_counter()
        sys_prompt = (
            "Ты — точный мультиязычный модуль извлечения фактов и формирования грамматически "
            "согласованных ответов. Отвечай ТОЛЬКО на основе предоставленного контекста документов. "
            "Если в контексте нет ответа, ответь строго: INSUFFICIENT_DATA. "
            "Формируй краткий и грамматически точный ответ на языке вопроса."
        )
        limited_ctx = "\n".join(context_snippets[:5])[:2000]
        user_prompt = f"Контекст документов:\n{limited_ctx}\n\nВопрос ({language}): {question}\nКраткий точный ответ:"

        try:
            if self.chat_model_factory:
                chat_instance = self.chat_model_factory(
                    system_instruction=sys_prompt,
                    provider=provider,
                    model=model_name,
                )
            else:
                from src.ai.orchestration.unified_chat import UnifiedChatModel

                chat_instance = UnifiedChatModel(
                    system_instruction=sys_prompt,
                    provider=provider,
                    model=model_name,
                )

            response_text = await chat_instance.ask(q=user_prompt, attempts=2, temperature=0.0)
            lat = (time.perf_counter() - t0) * 1000.0

            if not response_text or "INSUFFICIENT_DATA" in response_text:
                self.wm.store.log_model_usage(
                    workspace_id=workspace_id,
                    provider=provider,
                    model_name=model_name,
                    operation="qa_synthesis",
                    status="insufficient_data",
                    latency_ms=lat,
                    prompt_chars=len(user_prompt),
                    response_chars=len(response_text or ""),
                )
                return None

            clean_ans = response_text.strip()
            self.wm.store.log_model_usage(
                workspace_id=workspace_id,
                provider=provider,
                model_name=model_name,
                operation="qa_synthesis",
                status="success",
                latency_ms=lat,
                prompt_chars=len(user_prompt),
                response_chars=len(clean_ans),
            )
            return clean_ans
        except Exception as exc:
            lat = (time.perf_counter() - t0) * 1000.0
            logger.warning(f"[KnowledgeQAEngine] Отказ провайдера ИИ ({provider}:{model_name}): {exc}. Переход в локальный режим.")
            self.wm.store.log_model_usage(
                workspace_id=workspace_id,
                provider=provider,
                model_name=model_name,
                operation="qa_synthesis",
                status="error",
                latency_ms=lat,
                prompt_chars=len(user_prompt),
                error_message=str(exc),
            )
            return None

    async def ask(
        self,
        question: str,
        workspace_id: str = "default",
        language: Optional[str] = None,
        mode: str = "local_first",
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Выполняет гибридный поиск (SQLite + FAISS + WikiLLM) и возвращает грамматически точный ответ."""
        t0 = time.perf_counter()
        effective_mode = mode if mode in VALID_MODES else "local_first"
        eff_provider = provider or self.default_provider
        eff_model = model or self.default_model

        parsed_q = QuestionIntentParser.parse_question(question, language=language)
        q_lang = parsed_q["language"]

        all_facts = self.wm.store.get_facts(workspace_id=workspace_id, include_stale=False)
        matched_facts = self._match_facts_locally(parsed_q, all_facts)

        faiss_hits: List[Dict[str, Any]] = []
        try:
            faiss_rag = self.wm.get_faiss_rag(workspace_id)
            faiss_hits = faiss_rag.search(question, top_k=5)
        except Exception as exc:
            logger.warning(f"[KnowledgeQAEngine] Ошибка семантического поиска FAISS: {exc}")

        wiki_links = [l.model_dump() for l in self.wm.graph.get_active_links()[:10]]

        synthesized: Optional[Dict[str, Any]] = None
        top_fact: Optional[Dict[str, Any]] = None
        if matched_facts:
            top_fact = matched_facts[0][1]
            synthesized = self._synthesize_grammatical_answer(parsed_q, top_fact)

        cloud_used = False
        cloud_error_fallback = False
        cloud_insight: Optional[str] = None
        answer_text = ""
        status_str = "success"
        sources: List[Dict[str, Any]] = []

        if synthesized and top_fact:
            answer_text = synthesized["answer"]
            src = top_fact.get("source", {})
            doc_id = src.get("document_id", top_fact.get("document_id", ""))
            commit_hash = top_fact.get("commit_hash", "")
            sources.append({
                "document_id": doc_id,
                "sentence_index": src.get("sentence_index", 0),
                "commit_hash": commit_hash,
                "quote": src.get("quote", ""),
                "fact_id": top_fact.get("fact_id", ""),
            })

            if effective_mode in ("cloud_assist", "cloud_enrich") and self.cloud_policy_enabled:
                ctx_list = [src.get("quote", "")] + [h.get("text", "") for h in faiss_hits]
                cloud_ans = await self._call_cloud_model(
                    workspace_id=workspace_id,
                    question=question,
                    language=q_lang,
                    context_snippets=[c for c in ctx_list if c],
                    provider=eff_provider,
                    model_name=eff_model,
                )
                if cloud_ans:
                    cloud_used = True
                    cloud_insight = cloud_ans
                    if effective_mode == "cloud_enrich" and doc_id:
                        self.wm.graph.add_link(
                            source_id=doc_id,
                            target_id=synthesized.get("canonical_entity", answer_text),
                            relation_type="documents",
                            valid_from=commit_hash or "HEAD",
                            confidence=0.95,
                            provenance=f"cloud_enrich:{eff_provider}",
                        )
                else:
                    cloud_error_fallback = True
        else:
            if effective_mode in ("local_first", "cloud_assist", "cloud_enrich") and self.cloud_policy_enabled:
                ctx_list = [h.get("text", "") for h in faiss_hits if h.get("score", 0) > 0.1]
                if ctx_list:
                    cloud_ans = await self._call_cloud_model(
                        workspace_id=workspace_id,
                        question=question,
                        language=q_lang,
                        context_snippets=ctx_list,
                        provider=eff_provider,
                        model_name=eff_model,
                    )
                    if cloud_ans:
                        answer_text = cloud_ans
                        cloud_insight = cloud_ans
                        cloud_used = True
                        for h in faiss_hits[:2]:
                            meta = h.get("meta", {})
                            sources.append({
                                "document_id": meta.get("document_id", ""),
                                "sentence_index": meta.get("sentence_index", 0),
                                "commit_hash": meta.get("commit_hash", ""),
                                "quote": h.get("text", ""),
                            })
                    else:
                        cloud_error_fallback = True

            if not answer_text:
                status_str = "insufficient_data"
                if q_lang == "he":
                    answer_text = "אין מספיק מידע במסמכי סביבת העבודה כדי לענות על השאלה."
                elif q_lang == "en":
                    answer_text = "Insufficient data in the workspace documents to answer this question."
                else:
                    answer_text = "Недостаточно сведений в документах рабочей области для ответа на вопрос."

        latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        self.wm.store.log_query(
            workspace_id=workspace_id,
            question=question,
            language=q_lang,
            mode=effective_mode,
            answer=answer_text,
            status=status_str,
            cloud_used=cloud_used,
            latency_ms=latency_ms,
        )
        # Синхронизируем ответ «на лету» со сводной базой знаний Obsidian (_Knowledge_Base.md)
        if status_str == "success":
            try:
                await asyncio.to_thread(self.wm.obsidian.rebuild_knowledge_base_index, workspace_id)
            except Exception as obs_exc:
                logger.debug(f"[KnowledgeQAEngine] Ошибка авто-обновления _Knowledge_Base.md: {obs_exc}")

        return {
            "question": question,
            "answer": answer_text,
            "cloud_insight": cloud_insight,
            "language": q_lang,
            "status": status_str,
            "sources": sources,
            "matched_fact": top_fact,
            "grammatical_details": synthesized,
            "question_analysis": parsed_q,
            "faiss_hits": faiss_hits[:3],
            "wiki_links": wiki_links[:5],
            "processing": {
                "mode": effective_mode,
                "cloud_used": cloud_used,
                "cloud_fallback_triggered": cloud_error_fallback,
                "provider": eff_provider if cloud_used else "local_nlp_engine",
                "model": eff_model if cloud_used else "RussianMorphoSyntacticAnalyzer / HebrewSemanticMorphoAnalyzer",
                "latency_ms": latency_ms,
            },
        }
