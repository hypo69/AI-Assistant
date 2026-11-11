# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Core - Obsidian i18n
# =============================================================================
# Description:
#   Словари локализации и вспомогательные функции интернационализации для
#   компактного хранилища Obsidian Vault (`_Knowledge_Base.md`, блоки знаний
#   в документах и тематические конспекты `_Topics/<Тема>.md`).
#   Поддерживает языки: ru, he, en, uk (ua).
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.core.obsidian_i18n import get_obsidian_locale
#
#     loc = get_obsidian_locale("he")
#     print(loc["kb_title"].format(ws_name="דוד משה"))
#
# File: obsidian_i18n.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-11 21:20:00
# =============================================================================

from __future__ import annotations
"""Мультиязычные словари шаблонов для Obsidian Vault (ru, he, en, uk/ua)."""

from typing import Dict, Optional


OBSIDIAN_I18N: Dict[str, Dict[str, str]] = {
    "ru": {
        "kb_link_label": "Сводная база знаний",
        "doc_knowledge_header": "### 🧠 Извлечённые знания (Obsidian · [[{kb_stem}|{kb_label}]])",
        "doc_facts_header": "#### 📌 Структурированные факты:",
        "doc_no_facts": "*Структурированных фактов (action / possession) в этой ревизии не выделено.*",
        "doc_related_entities": "**Связанные сущности:** {links}",
        "source_ref": " *(источник: [[{doc_stem}|{doc_id}]])*",
        "poss_has": "владеет (`has`)",
        "poss_not_has": "не владеет (not has)",
        "fact_possession": "- 🏠 **Принадлежность ({lang}):** {owner_link} — *{rel_label}* → {poss_link}{doc_ref}",
        "default_action_predicate": "действие",
        "neg_prefix": "НЕ ",
        "fact_action": "- ⚡ **Действие ({lang}):** {subj_link} — *{neg_prefix}{pred_text}* (`{pred_lemma}`) → {obj_link}{doc_ref}",
        "kb_title": "Сводная база знаний — {ws_name}",
        "kb_h1": "# 🧠 Сводная база знаний: {ws_name}",
        "kb_info_callout": "> [!INFO] Компактный Obsidian Vault рабочего пространства `{workspace_id}`",
        "kb_stats_line": "> Документов: **{docs_count}** | Активных фактов: **{facts_count}** | Сущностей: **{entities_count}** | Git HEAD: `{git_head}`",
        "kb_docs_header": "## 📄 Документы рабочей области",
        "kb_docs_table_header": "| Документ | Язык | Версия | Активных фактов | Git ревизия |",
        "kb_no_docs": "*В рабочей области пока нет проиндексированных документов.*",
        "kb_facts_header": "## 📌 Извлечённые канонические факты",
        "kb_no_facts": "*Факты ещё не извлечены.*",
        "kb_graph_header": "## 🕸 Семантический граф связей (Mermaid)",
        "mermaid_has": "владеет",
        "mermaid_not_has": "не владеет",
        "mermaid_empty": "Нет активных связей",
        "kb_entities_header": "## 🏷 Индекс сущностей и понятий",
        "kb_no_entities": "*Сущности не найдены.*",
        "kb_topics_header": "## 🎯 Целенаправленно собранные тематические конспекты",
        "kb_qa_header": "## 💬 Ответы ИИ и проверенные знания (QA)",
        "qa_q_label": "В",
        "qa_a_label": "О",
        "kb_no_qa": "*Задайте вопрос во вкладке «Вопрос-Ответ (QA)» или «Чат», и ответы автоматически появятся здесь.*",
        "topic_default_name": "Тематический_срез",
        "topic_title_prefix": "Тема",
        "topic_h1_prefix": "Тематический конспект",
        "topic_back_to": "Вернуться в",
        "topic_back_label": "Сводную базу знаний",
        "topic_summary_prefix": "Целенаправленная выборка знаний по запросу",
        "topic_facts_found": "Найдено фактов",
        "topic_faiss_found": "Семантических фрагментов (FAISS)",
        "topic_facts_header": "Собранные факты по теме",
        "topic_no_facts": "Подходящих фактов не обнаружено.",
        "topic_rag_header": "Контекстные фрагменты и цитаты (RAG / FAISS)",
        "topic_default_doc": "документ",
        "topic_from_doc": "из",
        "topic_sentence_idx": "предложение",
        "topic_no_rag": "Семантических совпадений в FAISS не найдено.",
        "topic_sources_header": "Первоисточники",
    },
    "he": {
        "kb_link_label": "מאגר הידע המרכזי",
        "doc_knowledge_header": "### 🧠 ידע שחולץ (Obsidian · [[{kb_stem}|{kb_label}]])",
        "doc_facts_header": "#### 📌 עובדות מובנות:",
        "doc_no_facts": "*לא חולצו עובדות מובנות (action / possession) בגרסה זו.*",
        "doc_related_entities": "**ישויות קשורות:** {links}",
        "source_ref": " *(מקור: [[{doc_stem}|{doc_id}]])*",
        "poss_has": "בעלים של (`has`)",
        "poss_not_has": "אינו בעלים של (not has)",
        "fact_possession": "- 🏠 **שיוך ({lang}):** {owner_link} — *{rel_label}* → {poss_link}{doc_ref}",
        "default_action_predicate": "פעולה",
        "neg_prefix": "לא ",
        "fact_action": "- ⚡ **פעולה ({lang}):** {subj_link} — *{neg_prefix}{pred_text}* (`{pred_lemma}`) → {obj_link}{doc_ref}",
        "kb_title": "מאגר הידע המרכזי — {ws_name}",
        "kb_h1": "# 🧠 מאגר הידע המרכזי: {ws_name}",
        "kb_info_callout": "> [!INFO] כספת Obsidian קומפקטית של מרחב העבודה `{workspace_id}`",
        "kb_stats_line": "> מסמכים: **{docs_count}** | עובדות פעילות: **{facts_count}** | ישויות: **{entities_count}** | Git HEAD: `{git_head}`",
        "kb_docs_header": "## 📄 מסמכי מרחב העבודה",
        "kb_docs_table_header": "| מסמך | שפה | גרסה | עובדות פעילות | גרסת Git |",
        "kb_no_docs": "*אין עדיין מסמכים מאונדקסים במרחב העבודה.*",
        "kb_facts_header": "## 📌 עובדות קנוניות שחולצו",
        "kb_no_facts": "*עדיין לא חולצו עובדות.*",
        "kb_graph_header": "## 🕸 גרף קשרים סמנטי (Mermaid)",
        "mermaid_has": "בעלים של",
        "mermaid_not_has": "אינו בעלים של",
        "mermaid_empty": "אין קשרים פעילים",
        "kb_entities_header": "## 🏷 אינדקס ישויות ומושגים",
        "kb_no_entities": "*לא נמצאו ישויות.*",
        "kb_topics_header": "## 🎯 סיכומי נושאים ממוקדים",
        "kb_qa_header": "## 💬 תשובות AI וידע מאומת (QA)",
        "qa_q_label": "ש",
        "qa_a_label": "ת",
        "kb_no_qa": "*שאל שאלה בלשונית «שאלות ותשובות (QA)» או «צ'אט», והתשובות יופיעו כאן אוטומטית.*",
        "topic_default_name": "סיכום_נושא",
        "topic_title_prefix": "נושא",
        "topic_h1_prefix": "סיכום נושא",
        "topic_back_to": "חזרה אל",
        "topic_back_label": "מאגר הידע המרכזי",
        "topic_summary_prefix": "איסוף ידע ממוקד עבור השאילתה",
        "topic_facts_found": "עובדות שנמצאו",
        "topic_faiss_found": "קטעים סמנטיים (FAISS)",
        "topic_facts_header": "עובדות שנאספו בנושא",
        "topic_no_facts": "לא נמצאו עובדות מתאימות.",
        "topic_rag_header": "קטעי הקשר וציטוטים (RAG / FAISS)",
        "topic_default_doc": "מסמך",
        "topic_from_doc": "מתוך",
        "topic_sentence_idx": "משפט",
        "topic_no_rag": "לא נמצאו התאמות סמנטיות ב-FAISS.",
        "topic_sources_header": "מקורות ראשוניים",
    },
    "en": {
        "kb_link_label": "Knowledge Base Summary",
        "doc_knowledge_header": "### 🧠 Extracted Knowledge (Obsidian · [[{kb_stem}|{kb_label}]])",
        "doc_facts_header": "#### 📌 Structured Facts:",
        "doc_no_facts": "*No structured facts (action / possession) extracted in this revision.*",
        "doc_related_entities": "**Related Entities:** {links}",
        "source_ref": " *(source: [[{doc_stem}|{doc_id}]])*",
        "poss_has": "has (`has`)",
        "poss_not_has": "does not have (not has)",
        "fact_possession": "- 🏠 **Possession ({lang}):** {owner_link} — *{rel_label}* → {poss_link}{doc_ref}",
        "default_action_predicate": "action",
        "neg_prefix": "NOT ",
        "fact_action": "- ⚡ **Action ({lang}):** {subj_link} — *{neg_prefix}{pred_text}* (`{pred_lemma}`) → {obj_link}{doc_ref}",
        "kb_title": "Knowledge Base Summary — {ws_name}",
        "kb_h1": "# 🧠 Knowledge Base Summary: {ws_name}",
        "kb_info_callout": "> [!INFO] Compact Obsidian Vault for workspace `{workspace_id}`",
        "kb_stats_line": "> Documents: **{docs_count}** | Active facts: **{facts_count}** | Entities: **{entities_count}** | Git HEAD: `{git_head}`",
        "kb_docs_header": "## 📄 Workspace Documents",
        "kb_docs_table_header": "| Document | Language | Version | Active Facts | Git Revision |",
        "kb_no_docs": "*No indexed documents in the workspace yet.*",
        "kb_facts_header": "## 📌 Extracted Canonical Facts",
        "kb_no_facts": "*No facts extracted yet.*",
        "kb_graph_header": "## 🕸 Semantic Relationship Graph (Mermaid)",
        "mermaid_has": "has",
        "mermaid_not_has": "does not have",
        "mermaid_empty": "No active relationships",
        "kb_entities_header": "## 🏷 Entities & Concepts Index",
        "kb_no_entities": "*No entities found.*",
        "kb_topics_header": "## 🎯 Targeted Topic Notes",
        "kb_qa_header": "## 💬 AI Answers & Verified Knowledge (QA)",
        "qa_q_label": "Q",
        "qa_a_label": "A",
        "kb_no_qa": "*Ask a question in the \"Q&A\" or \"Chat\" tab, and answers will automatically appear here.*",
        "topic_default_name": "Topic_Dossier",
        "topic_title_prefix": "Topic",
        "topic_h1_prefix": "Topic Dossier",
        "topic_back_to": "Back to",
        "topic_back_label": "Knowledge Base Summary",
        "topic_summary_prefix": "Targeted knowledge collection for query",
        "topic_facts_found": "Facts found",
        "topic_faiss_found": "Semantic chunks (FAISS)",
        "topic_facts_header": "Collected Facts on Topic",
        "topic_no_facts": "No matching facts found.",
        "topic_rag_header": "Context Fragments & Quotes (RAG / FAISS)",
        "topic_default_doc": "document",
        "topic_from_doc": "from",
        "topic_sentence_idx": "sentence",
        "topic_no_rag": "No semantic matches found in FAISS.",
        "topic_sources_header": "Primary Sources",
    },
    "uk": {
        "kb_link_label": "Зведена база знань",
        "doc_knowledge_header": "### 🧠 Вилучені знання (Obsidian · [[{kb_stem}|{kb_label}]])",
        "doc_facts_header": "#### 📌 Структуровані факти:",
        "doc_no_facts": "*Структурованих фактів (action / possession) у цій ревізії не виявлено.*",
        "doc_related_entities": "**Пов'язані сутності:** {links}",
        "source_ref": " *(джерело: [[{doc_stem}|{doc_id}]])*",
        "poss_has": "володіє (`has`)",
        "poss_not_has": "не володіє (not has)",
        "fact_possession": "- 🏠 **Належність ({lang}):** {owner_link} — *{rel_label}* → {poss_link}{doc_ref}",
        "default_action_predicate": "дія",
        "neg_prefix": "НЕ ",
        "fact_action": "- ⚡ **Дія ({lang}):** {subj_link} — *{neg_prefix}{pred_text}* (`{pred_lemma}`) → {obj_link}{doc_ref}",
        "kb_title": "Зведена база знань — {ws_name}",
        "kb_h1": "# 🧠 Зведена база знань: {ws_name}",
        "kb_info_callout": "> [!INFO] Компактний Obsidian Vault робочого простору `{workspace_id}`",
        "kb_stats_line": "> Документів: **{docs_count}** | Активних фактів: **{facts_count}** | Сутностей: **{entities_count}** | Git HEAD: `{git_head}`",
        "kb_docs_header": "## 📄 Документи робочого простору",
        "kb_docs_table_header": "| Документ | Мова | Версія | Активних фактів | Git ревізія |",
        "kb_no_docs": "*У робочому просторі ще немає проіндексованих документів.*",
        "kb_facts_header": "## 📌 Вилучені канонічні факти",
        "kb_no_facts": "*Факти ще не вилучено.*",
        "kb_graph_header": "## 🕸 Семантичний граф зв'язків (Mermaid)",
        "mermaid_has": "володіє",
        "mermaid_not_has": "не володіє",
        "mermaid_empty": "Немає активних зв'язків",
        "kb_entities_header": "## 🏷 Індекс сутностей і понять",
        "kb_no_entities": "*Сутності не знайдено.*",
        "kb_topics_header": "## 🎯 Цілеспрямовано зібрані тематичні конспекти",
        "kb_qa_header": "## 💬 Відповіді ШІ та перевірені знання (QA)",
        "qa_q_label": "П",
        "qa_a_label": "В",
        "kb_no_qa": "*Поставте запитання у вкладці «Запитання-Відповідь (QA)» або «Чат», і відповіді автоматично з'являться тут.*",
        "topic_default_name": "Тематичний_зріз",
        "topic_title_prefix": "Тема",
        "topic_h1_prefix": "Тематичний конспект",
        "topic_back_to": "Повернутися до",
        "topic_back_label": "Зведеної бази знань",
        "topic_summary_prefix": "Цілеспрямована вибірка знань за запитом",
        "topic_facts_found": "Знайдено фактів",
        "topic_faiss_found": "Семантичних фрагментів (FAISS)",
        "topic_facts_header": "Зібрані факти за темою",
        "topic_no_facts": "Відповідних фактів не виявлено.",
        "topic_rag_header": "Контекстні фрагменти та цитати (RAG / FAISS)",
        "topic_default_doc": "документ",
        "topic_from_doc": "із",
        "topic_sentence_idx": "речення",
        "topic_no_rag": "Семантичних збігів у FAISS не знайдено.",
        "topic_sources_header": "Першоджерела",
    },
}


def normalize_obsidian_lang(language: Optional[str] = None) -> str:
    """Нормализует код языка для локализации шаблонов Obsidian Vault ('ru', 'he', 'en', 'uk').

    Args:
        language: Исходный код языка (например, 'he', 'ua', 'uk', 'en', 'ru').

    Returns:
        str: Нормализованный код поддерживаемого языка.
    """
    raw = (language or "").strip().lower()
    if not raw or raw == "unknown":
        return "ru"
    if raw in ("uk", "ukr", "ua", "ukrainian"):
        return "uk"
    if raw in ("he", "heb", "hebrew", "iw"):
        return "he"
    if raw in ("ru", "rus", "russian"):
        return "ru"
    if raw in ("en", "eng", "english"):
        return "en"
    return raw if raw in OBSIDIAN_I18N else "en"


def get_obsidian_locale(language: Optional[str] = None) -> Dict[str, str]:
    """Возвращает словарь локализованных строк Obsidian Vault для указанного языка.

    Args:
        language: Код языка рабочей области или документа.

    Returns:
        Dict[str, str]: Словарь переведённых шаблонов и меток.
    """
    norm = normalize_obsidian_lang(language)
    return OBSIDIAN_I18N.get(norm, OBSIDIAN_I18N["en"])
