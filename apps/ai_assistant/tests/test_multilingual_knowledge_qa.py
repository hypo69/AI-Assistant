# -*- coding: utf-8 -*-
"""
=============================================================================
Process Name: Multilingual Knowledge QA & Git Workspace Test Suite
=============================================================================
Description:
  Набор функциональных, интеграционных и регрессионных тестов для проверки
  мультиязычной системы извлечения знаний, Git-отслеживания рабочих областей,
  SQLite-хранилища, WikiLLM, FAISS и ответов на вопросы (Тесты A–I из ТЗ).

File: apps/ai_assistant/tests/test_multilingual_knowledge_qa.py
Package: apps.ai_assistant.tests
Author: hypo69
Updated: 2026-10-27 23:55:00
=============================================================================
"""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from apps.ai_assistant.core.nlp_analyzers import AnalyzerRegistry
from apps.ai_assistant.core.knowledge_store import KnowledgeStore
from apps.ai_assistant.core.workspace_manager import WorkspaceManager
from apps.ai_assistant.core.qa_engine import KnowledgeQAEngine
from apps.ai_assistant.core.temporal_code_graph import TemporalCodeGraph
from apps.ai_assistant.main import app


@pytest.fixture()
def isolated_env(tmp_path: Path):
    """Создаёт изолированное окружение с SQLite БД, реестром анализаторов, Git-менеджером и QA-движком."""
    base_dir = tmp_path / "ai_assistant_data"
    registry = AnalyzerRegistry()
    store = KnowledgeStore(db_path=base_dir / "test_knowledge.db")
    graph = TemporalCodeGraph(db_path=base_dir / "test_graph.db")
    manager = WorkspaceManager(
        base_dir=base_dir,
        workspaces_dir=base_dir / "workspaces",
        knowledge_store=store,
        analyzer_registry=registry,
        temporal_graph=graph,
    )
    qa_engine = KnowledgeQAEngine(workspace_manager=manager)
    return {
        "tmp_path": tmp_path,
        "registry": registry,
        "store": store,
        "manager": manager,
        "qa_engine": qa_engine,
    }


def test_step1_and_step2_isolated_git_per_workspace(isolated_env):
    """Проверяет, что каждая рабочая область получает собственный изолированный Git-репозиторий (.git)."""
    manager: WorkspaceManager = isolated_env["manager"]

    ws_a = manager.create_or_select_workspace("alpha_ws", name="Первая область")
    ws_b = manager.create_or_select_workspace("beta_ws", name="Вторая область")

    assert Path(ws_a["path"]).joinpath(".git").exists()
    assert Path(ws_b["path"]).joinpath(".git").exists()
    assert ws_a["path"] != ws_b["path"]


@pytest.mark.asyncio
async def test_scenario_a_russian_active_and_passive_questions(isolated_env):
    """Тест A (Русский язык: активный и пассивный залог) для документа 'Мама мыла раму.'."""
    manager: WorkspaceManager = isolated_env["manager"]
    qa_engine: KnowledgeQAEngine = isolated_env["qa_engine"]

    ws = manager.create_or_select_workspace("ru_workspace", name="Русская область")
    ws_id = ws["workspace_id"]

    imp = manager.import_document(
        workspace_id=ws_id,
        document_id="mama.txt",
        content="Мама мыла раму.",
    )
    assert imp["status"] == "indexed"
    assert imp["facts_count"] >= 1
    assert len(imp["commit_hash"]) >= 7

    # 1. Что мыла мама? -> Раму.
    ans1 = await qa_engine.ask(
        question="Что мыла мама?",
        workspace_id=ws_id,
        mode="local_only",
    )
    assert ans1["status"] == "success"
    assert ans1["answer"].lower().rstrip(".") == "раму"
    assert ans1["grammatical_details"]["grammatical_form"] == "accs"

    # 2. Кто мыл раму? -> Мама.
    ans2 = await qa_engine.ask(
        question="Кто мыл раму?",
        workspace_id=ws_id,
        mode="local_only",
    )
    assert ans2["status"] == "success"
    assert ans2["answer"].lower().rstrip(".") == "мама"
    assert ans2["grammatical_details"]["grammatical_form"] == "nomn"

    # 3. Кем была вымыта рама? -> Мамой.
    ans3 = await qa_engine.ask(
        question="Кем была вымыта рама?",
        workspace_id=ws_id,
        mode="local_only",
    )
    assert ans3["status"] == "success"
    assert ans3["answer"].lower().rstrip(".") == "мамой"
    assert ans3["grammatical_details"]["grammatical_form"] == "inst"


@pytest.mark.asyncio
async def test_scenario_b_and_c_hebrew_action(isolated_env):
    """Тест B и Тест C (Иврит: активное действие 'אמא רחצה את המסגרת')."""
    manager: WorkspaceManager = isolated_env["manager"]
    qa_engine: KnowledgeQAEngine = isolated_env["qa_engine"]

    ws = manager.create_or_select_workspace("he_action_ws", name="Hebrew Action")
    ws_id = ws["workspace_id"]

    manager.import_document(
        workspace_id=ws_id,
        document_id="frame_he.txt",
        content="אמא רחצה את המסגרת",
    )

    # מי רחצה את המסגרת? -> אמא
    ans_who = await qa_engine.ask(
        question="מי רחצה את המסגרת?",
        workspace_id=ws_id,
        mode="local_only",
    )
    assert ans_who["status"] == "success"
    assert ans_who["answer"] == "אמא"

    # מה רחצה אמא? -> המסגרת
    ans_what = await qa_engine.ask(
        question="מה רחצה אמא?",
        workspace_id=ws_id,
        mode="local_only",
    )
    assert ans_what["status"] == "success"
    assert ans_what["answer"] in ("המסגרת", "מסגרת")


@pytest.mark.asyncio
async def test_scenario_i_hebrew_possession_dod_moshe(isolated_env):
    """Тест I (Иврит: конструкция обладания 'לדוד משה היתה חווה' и инверсный порядок слов)."""
    manager: WorkspaceManager = isolated_env["manager"]
    qa_engine: KnowledgeQAEngine = isolated_env["qa_engine"]
    registry: AnalyzerRegistry = isolated_env["registry"]

    # Проверка прямого и инверсного порядка слов в анализаторе иврита
    direct_res = registry.analyze_text("לדוד משה היתה חווה", language="he")
    inverted_res = registry.analyze_text("הייתה חווה לדוד משה", language="he")
    assert direct_res["facts"][0]["fact_type"] == "possession"
    assert direct_res["facts"][0]["owner"]["lemma"] == "דוד משה"
    assert direct_res["facts"][0]["possessed_entity"]["lemma"] == "חווה"
    assert inverted_res["facts"][0]["fact_type"] == "possession"
    assert inverted_res["facts"][0]["owner"]["lemma"] == "דוד משה"
    assert inverted_res["facts"][0]["possessed_entity"]["lemma"] == "חווה"

    ws = manager.create_or_select_workspace("he_farm_ws", name="Hebrew Farm")
    ws_id = ws["workspace_id"]

    manager.import_document(
        workspace_id=ws_id,
        document_id="farm.txt",
        content="לדוד משה היתה חווה",
    )

    # 1. מה היה לדוד משה? -> חווה
    q1 = await qa_engine.ask("מה היה לדוד משה?", workspace_id=ws_id, mode="local_only")
    assert q1["status"] == "success"
    assert q1["answer"] == "חווה"

    # 2. למי הייתה חווה? -> לדוד משה
    q2 = await qa_engine.ask("למי הייתה חווה?", workspace_id=ws_id, mode="local_only")
    assert q2["status"] == "success"
    assert q2["answer"] == "לדוד משה"

    # 3. למי הייתה החווה? -> לדוד משה
    q3 = await qa_engine.ask("למי הייתה החווה?", workspace_id=ws_id, mode="local_only")
    assert q3["status"] == "success"
    assert q3["answer"] == "לדוד משה"

    # 4. האם לדוד משה הייתה חווה? -> כן
    q4 = await qa_engine.ask("האם לדוד משה הייתה חווה?", workspace_id=ws_id, mode="local_only")
    assert q4["status"] == "success"
    assert q4["answer"] == "כן"

    # 5. מה היה הקשר בין דוד משה לחווה? -> לדוד משה הייתה חווה
    q5 = await qa_engine.ask("מה היה הקשר בין דוד משה לחווה?", workspace_id=ws_id, mode="local_only")
    assert q5["status"] == "success"
    assert q5["answer"] == "לדוד משה הייתה חווה"


@pytest.mark.asyncio
async def test_yes_no_question_with_mismatched_role_returns_negative(isolated_env):
    """Вопрос «да/нет», где роль из вопроса не совпадает с фактом, должен получать отрицательный ответ.

    Регрессия: «האם הייתה לדוד מושה פרה?» при факте «לדוד מושה היתה חווה» отвечал «כן».
    """
    manager: WorkspaceManager = isolated_env["manager"]
    qa_engine: KnowledgeQAEngine = isolated_env["qa_engine"]

    ws_id = manager.create_or_select_workspace("yes_no_ws", name="Yes/No")["workspace_id"]
    manager.import_document(workspace_id=ws_id, document_id="farm.txt", content="לדוד מושה היתה חווה")
    manager.import_document(workspace_id=ws_id, document_id="mama.txt", content="Мама мыла раму.")

    # Иврит: обладание — несовпадение объекта обладания
    he_neg = await qa_engine.ask("האם הייתה לדוד מושה פרה?", workspace_id=ws_id, mode="local_only")
    assert he_neg["answer"].startswith("לא")
    assert "לדוד מושה היתה חווה" in he_neg["answer"]

    # Иврит: обладание — полное совпадение
    he_pos = await qa_engine.ask("האם הייתה לדוד מושה חווה?", workspace_id=ws_id, mode="local_only")
    assert he_pos["answer"] == "כן"

    # Русский: действие — несовпадение объекта
    ru_neg = await qa_engine.ask("Мыла ли мама машину?", workspace_id=ws_id, mode="local_only")
    assert ru_neg["answer"].startswith("Нет")
    assert "Мама мыла раму" in ru_neg["answer"]

    # Русский: действие — полное совпадение
    ru_pos = await qa_engine.ask("Мыла ли мама раму?", workspace_id=ws_id, mode="local_only")
    assert ru_pos["answer"] == "Да."


@pytest.mark.asyncio
async def test_scenario_d_e_f_g_h_paraphrase_missing_fallback_and_git_stale(isolated_env):
    """Проверяет Тесты D (перефразирование), E (отсутствие факта), F (local_only), G (сбой облака) и H (обновление документа в Git и перевод старых фактов в stale)."""
    manager: WorkspaceManager = isolated_env["manager"]
    qa_engine: KnowledgeQAEngine = isolated_env["qa_engine"]
    store: KnowledgeStore = isolated_env["store"]

    ws = manager.create_or_select_workspace("lifecycle_ws", name="Lifecycle WS")
    ws_id = ws["workspace_id"]

    # Импорт первой редакции документа
    manager.import_document(
        workspace_id=ws_id,
        document_id="mama.txt",
        content="Мама мыла раму.",
    )

    # Тест D: Перефразирование вопроса
    ans_paraphrase = await qa_engine.ask(
        question="Кто очистил оконную раму?",
        workspace_id=ws_id,
        mode="local_only",
    )
    assert ans_paraphrase["status"] == "success"
    assert ans_paraphrase["answer"].lower().rstrip(".") == "мама"

    # Тест E: Отсутствие факта в базе знаний (не выдумывать ответ)
    ans_missing = await qa_engine.ask(
        question="Что готовил папа на ужин?",
        workspace_id=ws_id,
        mode="local_only",
    )
    assert ans_missing["status"] == "insufficient_data"

    # Тест G: Отказоустойчивость при вызове облачного провайдера с несуществующим провайдером
    ans_fallback = await qa_engine.ask(
        question="Что мыла мама?",
        workspace_id=ws_id,
        mode="cloud_enrich",
        provider="unavailable_provider_xyz",
        model="non_existent_model",
    )
    assert ans_fallback["status"] == "success"
    assert ans_fallback["answer"].lower().rstrip(".") == "раму"
    assert ans_fallback["processing"]["cloud_fallback_triggered"] is True

    # Тест H: Изменение документа в Git переводит старые факты в статус stale
    update_res = manager.import_document(
        workspace_id=ws_id,
        document_id="mama.txt",
        content="Папа красил забор.",
    )
    assert update_res["status"] == "indexed"
    assert update_res["version"] == 2

    all_facts = store.get_facts(workspace_id=ws_id, include_stale=True)
    active_facts = [f for f in all_facts if f["status"] != "stale"]
    stale_facts = [f for f in all_facts if f["status"] == "stale"]
    assert len(active_facts) == 1
    assert active_facts[0]["subject"]["lemma"] == "папа"
    assert active_facts[0]["object"]["lemma"] == "забор"
    assert len(stale_facts) >= 1
    assert stale_facts[0]["subject"]["lemma"] == "мама"

    ans_new = await qa_engine.ask(
        question="Что красил папа?",
        workspace_id=ws_id,
        mode="local_only",
    )
    assert ans_new["status"] == "success"
    assert ans_new["answer"].lower().rstrip(".") == "забор"


def test_knowledge_rest_api_endpoints():
    """Проверяет работу REST API эндпоинтов /api/v1/workspaces/seed-demo, /api/v1/facts, /api/v1/ask."""
    client = TestClient(app)

    seed_res = client.post("/api/v1/workspaces/seed-demo")
    assert seed_res.status_code == 200
    seed_data = seed_res.json()
    ws_id = seed_data["workspace"]["workspace_id"]
    assert ws_id == "default"

    ask_ru = client.post(
        "/api/v1/ask",
        json={
            "question": "Кем была вымыта рама?",
            "workspace_id": ws_id,
            "mode": "local_only",
        },
    )
    assert ask_ru.status_code == 200
    assert ask_ru.json()["answer"].lower().rstrip(".") == "мамой"

    ask_he = client.post(
        "/api/v1/ask",
        json={
            "question": "למי הייתה חווה?",
            "workspace_id": ws_id,
            "mode": "local_only",
        },
    )
    assert ask_he.status_code == 200
    assert ask_he.json()["answer"] == "לדוד משה"

    # Тест: Создание и последующее удаление рабочей области через DELETE /api/v1/workspaces/{workspace_id}
    create_test_ws = client.post(
        "/api/v1/workspaces",
        json={"workspace_id": "test_del_ws", "name": "Test Delete WS", "description": "Temp"},
    )
    assert create_test_ws.status_code == 200

    del_res = client.delete("/api/v1/workspaces/test_del_ws")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "ok"
    assert del_res.json()["deleted_workspace_id"] == "test_del_ws"

    # Повторное удаление возвращает 404
    del_404 = client.delete("/api/v1/workspaces/test_del_ws")
    assert del_404.status_code == 404


@pytest.mark.asyncio
async def test_contradiction_filtering_and_negation_in_open_questions(isolated_env):
    """Проверяет защиту от ложноположительных ответов при противоречии субъекта/объекта и учёт отрицания (is_negated)."""
    manager: WorkspaceManager = isolated_env["manager"]
    qa_engine: KnowledgeQAEngine = isolated_env["qa_engine"]

    ws = manager.create_or_select_workspace("precision_ws", name="Precision QA")
    ws_id = ws["workspace_id"]

    manager.import_document(
        workspace_id=ws_id,
        document_id="mama.txt",
        content="Мама мыла раму.",
    )

    # 1. Противоречие по субъекту: в базе "Мама мыла раму", вопрос "Что мыл папа?" не должен возвращать "Раму"
    wrong_subj = await qa_engine.ask("Что мыл папа?", workspace_id=ws_id, mode="local_only")
    assert wrong_subj["status"] == "insufficient_data"

    # 2. Противоречие по объекту: в базе "Мама мыла раму", вопрос "Кто мыл посуду?" не должен возвращать "Мама"
    wrong_obj = await qa_engine.ask("Кто мыл посуду?", workspace_id=ws_id, mode="local_only")
    assert wrong_obj["status"] == "insufficient_data"

    # 3. Отрицательный факт в открытом вопросе
    manager.import_document(
        workspace_id=ws_id,
        document_id="negated.txt",
        content="Папа не красил забор.",
    )
    neg_open = await qa_engine.ask("Что красил папа?", workspace_id=ws_id, mode="local_only")
    assert neg_open["status"] == "success"
    assert "не" in neg_open["answer"].lower()
    assert neg_open["grammatical_details"]["grammatical_form"] == "negated_fact_notice"


@pytest.mark.asyncio
async def test_multilingual_mixed_doc_and_markdown_table_extraction(isolated_env):
    """Проверяет посегментное определение языка в смешанном документе, извлечение фактов из таблиц и очистку FAISS/графа при обновлении."""
    manager: WorkspaceManager = isolated_env["manager"]
    qa_engine: KnowledgeQAEngine = isolated_env["qa_engine"]

    ws = manager.create_or_select_workspace("mixed_ws", name="Mixed & Tables")
    ws_id = ws["workspace_id"]

    # Смешанный документ (русский + иврит + Markdown-таблица)
    mixed_content = (
        "Мама мыла большую раму.\n"
        "לדוד משה היתה חווה.\n\n"
        "| Сотрудник | Должность |\n"
        "| --- | --- |\n"
        "| Алексей | Архитектор |\n"
    )
    manager.import_document(
        workspace_id=ws_id,
        document_id="mixed.md",
        content=mixed_content,
    )

    # Проверка русского предложения с прилагательным ("большую раму")
    ans_ru = await qa_engine.ask("Что мыла мама?", workspace_id=ws_id, mode="local_only")
    assert ans_ru["status"] == "success"
    assert "раму" in ans_ru["answer"].lower()

    # Проверка ивритского предложения из того же документа
    ans_he = await qa_engine.ask("מה היה לדוד משה?", workspace_id=ws_id, mode="local_only")
    assert ans_he["status"] == "success"
    assert ans_he["answer"] == "חווה"

    # Проверка факта, извлечённого из Markdown-таблицы
    ans_tbl = await qa_engine.ask("Что было у Алексея?", workspace_id=ws_id, mode="local_only")
    assert ans_tbl["status"] == "success"
    assert "архитектор" in ans_tbl["answer"].lower()

    # Проверка очистки FAISS-чанков и перевода связей графа в superseded при обновлении документа
    rag = manager.get_faiss_rag(ws_id)
    prefix = f"{ws_id}:mixed.md:"
    chunks_before = [m for m in rag.metadatas if str(m.get("id", "")).startswith(prefix)]
    assert len(chunks_before) >= 1

    manager.import_document(
        workspace_id=ws_id,
        document_id="mixed.md",
        content="Кот пил молоко.",
    )
    chunks_after = [m for m in rag.metadatas if str(m.get("id", "")).startswith(prefix)]
    assert len(chunks_after) == 1
    assert "Кот пил молоко" in chunks_after[0]["text"]

