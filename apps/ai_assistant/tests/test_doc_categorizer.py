# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant - Document Categorizer & WebGUI Tab Tests
# =============================================================================
# Description:
#   Тесты сервиса классификации документов, RAG-поиска и WebGUI вкладки tab_doc_categorizer.
#
# File: test_doc_categorizer.py
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-30 15:51:00
# =============================================================================

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from apps.ai_assistant.core.doc_categorizer import DocumentCategorizerService
from apps.ai_assistant.main import app
from header import __root__


@pytest.fixture
def temp_categorizer(tmp_path: Path) -> DocumentCategorizerService:
    """Создает изолированный экземпляр DocumentCategorizerService во временной директории."""
    db_file = tmp_path / "test_doc_categorizer.db"
    return DocumentCategorizerService(db_path=db_file)


def test_categorizer_initial_status(temp_categorizer: DocumentCategorizerService) -> None:
    """Проверяет начальный статус и готовность категорий сервиса."""
    status = temp_categorizer.get_status()
    assert "total_documents" in status
    assert status["total_documents"] == 0
    assert "default_categories" in status
    assert "finance" in status["default_categories"]
    assert "legal" in status["default_categories"]


def test_heuristic_classification_and_uncertainty(temp_categorizer: DocumentCategorizerService, tmp_path: Path) -> None:
    """Проверяет категоризацию известных шаблонов и определение пограничных документов."""
    # Создаем тестовые файлы
    finance_file = tmp_path / "invoice_march_2026.pdf"
    finance_file.write_text("Счет на оплату хостинга", encoding="utf-8")

    uncertain_file = tmp_path / "notes_38472.txt"
    uncertain_file.write_text("Некоторые разрозненные заметки", encoding="utf-8")

    rules = temp_categorizer._load_rules()
    temp_categorizer._process_single_file(finance_file, rules)
    temp_categorizer._process_single_file(uncertain_file, rules)

    status = temp_categorizer.get_status()
    assert status["total_documents"] == 2
    assert status["classified_count"] >= 1
    assert status["uncertain_count"] >= 1

    # Проверяем очередь вопросов
    uncertain_items = temp_categorizer.get_uncertain_documents()
    assert len(uncertain_items) >= 1
    assert any("notes_38472" in item["file_name"] for item in uncertain_items)


def test_resolve_uncertain_and_rule_learning(temp_categorizer: DocumentCategorizerService, tmp_path: Path) -> None:
    """Проверяет подтверждение категории пользователем и создание правила авто-классификации."""
    sub_dir = tmp_path / "AutoRepair"
    sub_dir.mkdir(parents=True, exist_ok=True)

    f1 = sub_dir / "remont_1.txt"
    f2 = sub_dir / "remont_2.txt"
    f1.write_text("Замена масла", encoding="utf-8")
    f2.write_text("Замена фильтра", encoding="utf-8")

    rules = temp_categorizer._load_rules()
    temp_categorizer._process_single_file(f1, rules)
    temp_categorizer._process_single_file(f2, rules)

    items = temp_categorizer.get_uncertain_documents()
    assert len(items) == 2

    target_id = items[0]["id"]
    # Пользователь подтверждает категорию 'personal' и создает правило для папки 'AutoRepair'
    temp_categorizer.resolve_uncertain(
        doc_id=target_id,
        category="personal",
        create_rule=True,
        rule_pattern="AutoRepair"
    )

    # Проверяем, что оба файла теперь категоризированы
    items_after = temp_categorizer.get_uncertain_documents()
    assert len(items_after) == 0

    all_docs = temp_categorizer.list_documents(category="personal")
    assert all_docs["total"] == 2


def test_rag_fts5_search(temp_categorizer: DocumentCategorizerService, tmp_path: Path) -> None:
    """Проверяет полнотекстовый поиск FTS5 по проиндексированным документам."""
    f = tmp_path / "nda_agreement_partner.txt"
    f.write_text("Соглашение о неразглашении конфиденциальной информации компании Вектор", encoding="utf-8")

    rules = temp_categorizer._load_rules()
    temp_categorizer._process_single_file(f, rules)

    hits = temp_categorizer.search_rag(query="неразглашении конфиденциальной")
    assert len(hits) == 1
    assert hits[0]["file_name"] == "nda_agreement_partner.txt"


def test_rest_api_endpoints() -> None:
    """Проверяет REST API маршруты /api/v1/documents/*."""
    client = TestClient(app)

    res_status = client.get("/api/v1/documents/status")
    assert res_status.status_code == 200
    data = res_status.json()
    assert "total_documents" in data

    res_items = client.get("/api/v1/documents/items")
    assert res_items.status_code == 200

    res_uncertain = client.get("/api/v1/documents/uncertain")
    assert res_uncertain.status_code == 200
    assert isinstance(res_uncertain.json(), list)

    res_search = client.post("/api/v1/documents/search", json={"query": "test query", "limit": 5})
    assert res_search.status_code == 200
    assert "hits" in res_search.json()


def test_webgui_tab_structure_and_integration() -> None:
    """Проверяет интеграцию вкладки tab_doc_categorizer в разметку и скрипты WebGUI."""
    webgui_dir = __root__ / "apps" / "ai_assistant" / "api" / "webgui"
    tab_dir = webgui_dir / "tab_doc_categorizer"

    assert tab_dir.exists(), "Каталог tab_doc_categorizer должен существовать"
    assert (tab_dir / "index.html").exists(), "index.html вкладки должен существовать"
    assert (tab_dir / "main.js").exists(), "main.js вкладки должен существовать"
    assert (tab_dir / "README.md").exists(), "README.md вкладки должен существовать"

    index_html = (webgui_dir / "index.html").read_text(encoding="utf-8")
    assert 'data-tab="tab-doc-categorizer"' in index_html, "Кнопка вкладки должна присутствовать в Activity Bar"
    assert 'id="tab-doc-categorizer"' in index_html, "Контейнер вкладки должен присутствовать в DOM"

    main_js = (webgui_dir / "js" / "main.js").read_text(encoding="utf-8")
    assert "'doc-categorizer'" in main_js, "Вкладка doc-categorizer должна быть зарегистрирована в TABS"

    ru_json = json.loads((webgui_dir / "locales" / "ru.json").read_text(encoding="utf-8"))
    assert "docCategorizer" in ru_json["tabs"], "Ключ вкладки должен быть в locales/ru.json"
    assert "docCategorizer" in ru_json["ui"], "Секция ui.docCategorizer должна быть в locales/ru.json"
