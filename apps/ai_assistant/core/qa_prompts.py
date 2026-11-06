# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-assistant Apps AI_Assistant Core QA Prompts (i18n)
# =============================================================================
# Description:
#   Мультиязычные шаблоны системных и пользовательских промптов для вопросно-
#   ответного механизма QAEngine (RU, HE, EN, UA). Предотвращает проникновение
#   чужеродных языков в запросы к языковым моделям и обеспечивает строгую
#   интернационализацию контекста и системных инструкций.
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.core.qa_prompts import get_qa_prompts, get_insufficient_data_message
#
#     sys_prompt, user_prompt = get_qa_prompts("he", context="...", question="...")
#     fallback_msg = get_insufficient_data_message("he")
#
# File: core/qa_prompts.py
# Project: ai-assistant
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-03 16:53:00
# =============================================================================

from __future__ import annotations
"""Мультиязычные шаблоны промптов и системных инструкций для QAEngine."""

from typing import Dict, Tuple

QA_PROMPTS_I18N: Dict[str, Dict[str, str]] = {
    "ru": {
        "system_instruction": (
            "Ты — точный мультиязычный модуль извлечения фактов, анализа данных и формирования "
            "грамматически согласованных ответов. Анализируй предоставленный контекст документов и историю Git. "
            "Отвечай строго на основе контекста. Если информации действительно нет, ответь строго: INSUFFICIENT_DATA. "
            "Формируй ясный, глубокий и грамматически точный ответ на языке вопроса."
        ),
        "context_header": "Контекст документов и данных:",
        "question_header": "Вопрос ({language}):",
        "answer_header": "Краткий точный ответ:",
        "insufficient_data": "Недостаточно сведений в документах рабочей области для ответа на вопрос.",
    },
    "he": {
        "system_instruction": (
            "אתה מודול רב-לשוני מדויק לחילוץ עובדות, ניתוח נתונים וניסוח תשובות תקינות דקדוקית. "
            "נתח לעומק את הקשר המסמכים והיסטוריית Git המצורפים. ענה אך ורק על סמך ההקשר המצורף. "
            "אם אין מספיק מידע בהקשר, ענה בדיוק: INSUFFICIENT_DATA. "
            "נסח תשובה בהירה, מעמיקה ומדויקת דקדוקית בשפת השאלה."
        ),
        "context_header": "הקשר מסמכים ונתונים:",
        "question_header": "שאלה ({language}):",
        "answer_header": "תשובה מדויקת ומפורטת:",
        "insufficient_data": "אין מספיק מידע במסמכי סביבת העבודה כדי לענות על השאלה.",
    },
    "en": {
        "system_instruction": (
            "You are a precise multilingual module for extracting facts, data analysis, and grammatically "
            "correct answers. Deeply analyze the provided document context and Git history. "
            "Answer strictly based on the context. If the required information is missing, respond strictly: INSUFFICIENT_DATA. "
            "Provide a clear, in-depth, and accurate answer in the language of the question."
        ),
        "context_header": "Context of documents and data:",
        "question_header": "Question ({language}):",
        "answer_header": "Concise and accurate answer:",
        "insufficient_data": "Insufficient data in the workspace documents to answer this question.",
    },
    "ua": {
        "system_instruction": (
            "Ти — точний багатомовний модуль вилучення фактів, аналізу даних та формування граматично узгоджених відповідей. "
            "Глибоко аналізуй наданий контекст документів та історію Git. Відповідай строго на основі контексту. "
            "Якщо в контексті немає відповіді, відповідай строго: INSUFFICIENT_DATA. "
            "Формуй коротку, змістовну та граматично точну відповідь мовою запитання."
        ),
        "context_header": "Контекст документів та даних:",
        "question_header": "Запитання ({language}):",
        "answer_header": "Коротка точна відповідь:",
        "insufficient_data": "Недостатньо відомостей у документах робочої області для відповіді на запитання.",
    },
}


def get_qa_prompts(language: str, context: str, question: str) -> Tuple[str, str]:
    """Формирует мультиязычные системную инструкцию и пользовательский запрос к языковой модели.

    Args:
        language: Код языка вопроса или рабочей области ('ru', 'he', 'en', 'ua'/'uk').
        context: Ограниченный текстовый контекст документов или Git-данных.
        question: Исходный вопрос пользователя.

    Returns:
        Tuple[str, str]: Кортеж (system_instruction, user_prompt).
    """
    clean_lang = str(language or "ru").strip().lower()
    if clean_lang == "uk":
        clean_lang = "ua"
    loc = QA_PROMPTS_I18N.get(clean_lang, QA_PROMPTS_I18N["ru"])

    sys_instruction = loc["system_instruction"]
    ctx_header = loc["context_header"]
    q_header = loc["question_header"].format(language=clean_lang)
    ans_header = loc["answer_header"]

    user_prompt = f"{ctx_header}\n{context}\n\n{q_header} {question}\n{ans_header}"
    return sys_instruction, user_prompt


def get_insufficient_data_message(language: str) -> str:
    """Возвращает локализованное сообщение об отсутствии данных для ответа на вопрос.

    Args:
        language: Код языка.

    Returns:
        str: Локализованный текст ответа.
    """
    clean_lang = str(language or "ru").strip().lower()
    if clean_lang == "uk":
        clean_lang = "ua"
    loc = QA_PROMPTS_I18N.get(clean_lang, QA_PROMPTS_I18N["ru"])
    return loc["insufficient_data"]
