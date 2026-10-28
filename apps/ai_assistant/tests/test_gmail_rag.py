# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant - Gmail RAG Unit Tests
# =============================================================================
# Description:
#   Модульные тесты для сервиса семантического поиска GmailRagService:
#   проверка NLU разбора естественно-языковых запросов, извлечения намерений,
#   нормализации опечаток и падежей, расширения запросов синонимами (Query Expansion),
#   векторного переранжирования и валидации REST API эндпоинта /api/v1/gmail/semantic_search.
#
# File: test_gmail_rag.py
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-27 21:30:00
# =============================================================================

from __future__ import annotations
"""Тесты валидации сервиса Gmail RAG и семантического поиска писем."""

import pytest
from fastapi.testclient import TestClient

from apps.ai_assistant.core.gmail_rag_service import GmailRagService, gmail_rag_service
from apps.ai_assistant.main import app


@pytest.fixture
def client() -> TestClient:
    """Фикстура тестового клиента FastAPI."""
    return TestClient(app)


def test_gmail_rag_intent_parsing_natural_language():
    """Проверяет разбор естественного запроса с опечатками и падежными формами."""
    rag = GmailRagService()
    query = "Найди все письма по сделаке по корове зина"
    intent = rag.extract_search_intent(query)

    assert intent["raw_query"] == query
    # Проверка фильтрации стоп-слов
    for stop_word in ["найди", "все", "письма", "по"]:
        assert stop_word not in intent["significant_terms"]

    # Проверка выделения ключевых терминов
    assert "сделаке" in intent["significant_terms"]
    assert "корове" in intent["significant_terms"]
    assert "зина" in intent["significant_terms"]

    # Проверка нормализации опечатки 'сделаке' -> 'сделка' и форм 'корове' -> 'корова'
    assert "сделка" in intent["normalized_terms"]
    assert "корова" in intent["normalized_terms"]
    assert "зина" in intent["normalized_terms"]

    # Проверка расширения синонимами (Query Expansion)
    expanded = intent["expanded_keywords"]
    assert any(term in expanded for term in ["договор", "контракт", "счет", "оплата"])
    assert intent["gmail_api_query"] != ""


def test_gmail_rag_intent_parsing_with_gmail_operators():
    """Проверяет сохранение специфических поисковых операторов Gmail."""
    rag = GmailRagService()
    query = "from:boss@corp.com is:unread отчет по проекту"
    intent = rag.extract_search_intent(query)

    assert "from:boss@corp.com" in intent["gmail_api_query"]
    assert "is:unread" in intent["gmail_api_query"]
    assert "отчет" in intent["significant_terms"] or "проекту" in intent["significant_terms"]


def test_gmail_rag_calculate_message_relevance():
    """Проверяет точный расчет семантического скора и объяснения релевантности."""
    rag = GmailRagService()
    intent = rag.extract_search_intent("Найди все письма по сделаке по корове зина")

    # Релевантное письмо
    score_rel, reason_rel, concepts_rel = rag.calculate_message_relevance(
        intent=intent,
        subject="Договор купли-продажи коровы Зины",
        snippet="Направляем подписанный договор и счет на оплату коровы Зина.",
        sender="farm-agro@example.com",
        vector_similarity=0.85,
    )
    assert score_rel >= 0.65
    assert len(concepts_rel) > 0
    assert "договор" in concepts_rel or "корова" in concepts_rel or "зина" in concepts_rel
    assert "соответствие" in reason_rel.lower() or "совпадение" in reason_rel.lower()

    # Нерелевантное письмо
    score_irrel, reason_irrel, concepts_irrel = rag.calculate_message_relevance(
        intent=intent,
        subject="Еженедельный дайджест новостей погоды",
        snippet="В выходные ожидается солнечная погода без осадков.",
        sender="weather-news@example.com",
        vector_similarity=0.0,
    )
    assert score_irrel < 0.2
    assert len(concepts_irrel) == 0


def test_gmail_rag_semantic_search_with_mocked_messages(monkeypatch):
    """Проверяет сквозной поиск и сортировку по релевантности на мокированных данных."""
    mock_messages = [
        {
            "id": "msg_001",
            "thread_id": "thr_001",
            "subject": "Еженедельный дайджест сервиса",
            "snippet": "Информация о новых тарифах облачного хранилища.",
            "from": "cloud-notify@example.com",
            "date": "2026-10-25",
            "unread": False,
            "starred": False,
        },
        {
            "id": "msg_002",
            "thread_id": "thr_002",
            "subject": "Сделка: покупка коровы Зина (договор и счет)",
            "snippet": "Здравствуйте! Высылаем согласованный договор на продажу племенной коровы Зинаида.",
            "from": "seller-agro@example.com",
            "date": "2026-10-26",
            "unread": True,
            "starred": True,
        },
    ]

    from apps.ai_assistant.core.gmail_manager import gmail_manager
    monkeypatch.setattr(
        gmail_manager,
        "list_messages",
        lambda query="", label_ids=None, max_results=20, page_token=None, account_name=None: {
            "status": "success",
            "account": "davidka",
            "messages": mock_messages,
            "next_page_token": "",
            "total_estimate": 2,
        },
    )

    rag = GmailRagService()
    res = rag.semantic_search("Найди все письма по сделаке по корове зина", limit=5)

    assert res["status"] == "success"
    assert res["count"] >= 1
    top_msg = res["messages"][0]
    assert top_msg["id"] == "msg_002"
    assert top_msg["semantic_score"] > 0.6
    assert "relevance_reason" in top_msg
    assert res.get("engine") == "gmail-rag-faiss"


def test_api_gmail_semantic_search_endpoint(client: TestClient, monkeypatch):
    """Проверяет REST эндпоинт GET /api/v1/gmail/semantic_search."""
    monkeypatch.setattr(
        gmail_rag_service,
        "semantic_search",
        lambda query, limit=15, account_name=None: {
            "status": "success",
            "query": query,
            "count": 1,
            "messages": [
                {
                    "id": "msg_test",
                    "subject": "Договор по корове Зина",
                    "snippet": "Сделка утверждена",
                    "from": "partner@example.com",
                    "semantic_score": 0.92,
                    "relevance_reason": "Высокое совпадение всех ключевых понятий",
                }
            ],
            "expanded_query": "(корова OR сделка)",
            "engine": "gmail-rag-faiss",
        },
    )

    resp = client.get("/api/v1/gmail/semantic_search?q=Найди+все+письма+по+сделаке+по+корове+зина")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["count"] == 1
    assert data["messages"][0]["id"] == "msg_test"
    assert data["messages"][0]["semantic_score"] == 0.92
