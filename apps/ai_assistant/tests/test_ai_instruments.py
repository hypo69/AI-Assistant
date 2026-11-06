# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Assistant Tests - AI Instruments Test Suite
# =============================================================================
# Description:
#   Модульные TDD тесты для базы инструментов цепочек размышлений
#   (AIInstrumentsStorage, AIInstrumentsService, DatabaseInstrumentTool,
#   Markdown Adapter и синхронизация toolchain_tools.md).
#
# File: test_ai_instruments.py
# Project: ai-assistant
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-03 16:35:00
# =============================================================================

from __future__ import annotations

"""Тестирование функциональности базы инструментов цепочек размышлений."""

import asyncio
import json
import pytest
from pathlib import Path

from apps.ai_assistant.core.ai_instruments import (
    AIInstrument,
    AIInstrumentCreate,
    AIInstrumentsService,
    AIInstrumentsStorage,
    DatabaseInstrumentTool,
    load_reasoning_tools,
    load_markdown_tools,
    save_markdown_tools,
    parse_instruments_from_markdown,
    serialize_instruments_to_markdown,
)


@pytest.fixture
def temp_storage(tmp_path: Path) -> AIInstrumentsStorage:
    """Фикстура изолированного хранилища SQLite и Markdown во временном каталоге."""
    db_file = tmp_path / "test_instruments.db"
    md_file = tmp_path / "data" / "apps" / "ai_assistent" / "toolchain_tools.md"
    return AIInstrumentsStorage(db_path=db_file, engine="sqlite", md_path=md_file)


@pytest.fixture
def service(temp_storage: AIInstrumentsStorage) -> AIInstrumentsService:
    """Фикстура сервиса инструментов."""
    return AIInstrumentsService(storage=temp_storage)


def test_storage_save_and_get(temp_storage: AIInstrumentsStorage):
    """Проверка сохранения и извлечения инструмента из базы данных."""
    inst = AIInstrument(
        tool_id="test_calc_hash",
        name="Тестовый расчет хеша",
        tool_type="python",
        command="print('hash_ok')",
        description="Инструмент верификации хеша",
        target_entity="file:hash",
        parameters_schema={"type": "object"},
        risk_level="safe",
        author_agent="cot_planner",
        tags=["#test", "#hash"],
    )
    saved = temp_storage.save_instrument(inst)
    assert saved.tool_id == "test_calc_hash"

    loaded = temp_storage.get_instrument("test_calc_hash")
    assert loaded is not None
    assert loaded.name == "Тестовый расчет хеша"
    assert loaded.target_entity == "file:hash"
    assert loaded.execution_count == 0


def test_storage_list_and_search(temp_storage: AIInstrumentsStorage):
    """Проверка фильтрации и поиска по каталогу инструментов."""
    inst1 = AIInstrument(
        tool_id="inst_1",
        name="Поиск по SQLite",
        tool_type="python",
        command="select 1",
        description="Чтение таблиц базы данных",
        target_entity="database:sqlite",
    )
    inst2 = AIInstrument(
        tool_id="inst_2",
        name="Пинг сетевого сокета",
        tool_type="powershell",
        command="Test-NetConnection",
        description="Проверка доступности порта",
        target_entity="network:port",
    )
    temp_storage.save_instrument(inst1)
    temp_storage.save_instrument(inst2)

    all_items = temp_storage.list_instruments(limit=10)
    assert len(all_items) >= 2

    py_items = temp_storage.list_instruments(tool_type="python")
    assert any(it.tool_id == "inst_1" for it in py_items)

    found = temp_storage.search_instruments("сокета")
    assert len(found) >= 1
    assert any(it.tool_id == "inst_2" for it in found)


def test_storage_record_execution_and_delete(temp_storage: AIInstrumentsStorage):
    """Проверка счетчика исполнений и удаления инструмента."""
    inst = AIInstrument(
        tool_id="inst_run_cnt",
        name="Счетчик запусков",
        command="echo 1",
    )
    temp_storage.save_instrument(inst)
    temp_storage.record_execution("inst_run_cnt")

    loaded = temp_storage.get_instrument("inst_run_cnt")
    assert loaded is not None
    assert loaded.execution_count == 1
    assert loaded.last_executed_at is not None

    deleted = temp_storage.delete_instrument("inst_run_cnt")
    assert deleted is True
    assert temp_storage.get_instrument("inst_run_cnt") is None


def test_service_seed_default_instruments(service: AIInstrumentsService):
    """Проверка инициализации базового каталога инструментов."""
    seeded = service.seed_default_instruments(force=True)
    assert len(seeded) >= 5
    assert any(it.tool_id == "inst_calc_file_hash" for it in seeded)


def test_service_extract_from_text(service: AIInstrumentsService):
    """Проверка извлечения инструментов из цепочки размышлений."""
    reasoning_text = """
    Шаг 1: Для подсчета строк файла воспользуемся Python скриптом:
    ```python
    import sys
    print("Total rows: 42")
    ```

    Шаг 2: Проверим сетевой сокет:
    ```powershell
    Get-Process -Name svchost
    ```
    """
    extracted = service.extract_and_save_from_text(
        text=reasoning_text,
        target_entity="reasoning:step",
        title_prefix="Авто-инструмент",
    )
    assert len(extracted) == 2
    types = [it.tool_type for it in extracted]
    assert "python" in types
    assert "powershell" in types


def test_service_execute_instrument_python(service: AIInstrumentsService):
    """Проверка выполнения изолированного Python инструмента."""
    item = AIInstrumentCreate(
        tool_id="inst_py_sum",
        name="Тест суммирования",
        tool_type="python",
        command="a = {val_a}\nb = {val_b}\nprint(a + b)",
    )
    service.save_instrument(item)
    res = service.execute_instrument("inst_py_sum", parameters={"val_a": 10, "val_b": 25})
    assert res["success"] is True
    assert "35" in res["stdout"]

    inst = service.get_instrument("inst_py_sum")
    assert inst is not None
    assert inst.execution_count == 1


def test_service_csv_export_and_import(service: AIInstrumentsService, tmp_path: Path):
    """Проверка экспорта и импорта каталога в CSV."""
    service.save_instrument(AIInstrumentCreate(tool_id="c1", name="Команда 1", command="print(1)"))
    service.save_instrument(AIInstrumentCreate(tool_id="c2", name="Команда 2", command="print(2)"))

    csv_file = tmp_path / "tools.csv"
    count = service.export_to_csv(csv_file)
    assert count >= 2
    assert csv_file.is_file()

    storage2 = AIInstrumentsStorage(
        db_path=tmp_path / "db2.db",
        engine="sqlite",
        md_path=tmp_path / "tools2.md",
    )
    service2 = AIInstrumentsService(storage=storage2)
    imported = service2.import_from_csv(csv_file)
    assert len(imported) >= 2
    assert service2.get_instrument("c1") is not None


@pytest.mark.asyncio
async def test_database_instrument_tool_adapter(service: AIInstrumentsService):
    """Проверка асинхронного адаптера DatabaseInstrumentTool для цепочек размышлений."""
    item = AIInstrumentCreate(
        tool_id="inst_cot_test",
        name="Инструмент CoT",
        tool_type="python",
        command="import json\nprint(json.dumps({'res': 'ok_cot'}))",
    )
    service.save_instrument(item)

    tools = load_reasoning_tools(storage=service.storage)
    matching = [t for t in tools if t.name == "inst_cot_test"]
    assert len(matching) == 1

    tool = matching[0]
    assert tool.title == "Инструмент CoT"
    res = await tool.execute()
    assert res["success"] is True
    assert "ok_cot" in res["stdout"]


def test_markdown_adapter_serialize_and_parse(tmp_path: Path):
    """Проверка сериализации в Markdown и последующего парсинга."""
    test_inst = AIInstrument(
        tool_id="inst_md_test",
        name="Markdown Тест",
        tool_type="python",
        command="print('md_parsed')",
        description="Проверка формата Markdown",
        target_entity="test:md",
        parameters_schema={"type": "object", "properties": {"arg": {"type": "string"}}},
        risk_level="safe",
        author_agent="reasoning_chain",
        tags=["#md", "#test"],
        execution_count=5,
    )
    md_text = serialize_instruments_to_markdown([test_inst])
    assert "## `inst_md_test`" in md_text
    assert "Markdown Тест" in md_text
    assert "print('md_parsed')" in md_text

    parsed_list = parse_instruments_from_markdown(md_text)
    assert len(parsed_list) == 1
    p = parsed_list[0]
    assert p.tool_id == "inst_md_test"
    assert p.name == "Markdown Тест"
    assert p.command == "print('md_parsed')"
    assert p.execution_count == 5
    assert p.parameters_schema.get("type") == "object"


def test_storage_markdown_file_sync(tmp_path: Path):
    """Проверка автоматической синхронизации в Markdown файл toolchain_tools.md."""
    md_file = tmp_path / "data" / "apps" / "ai_assistent" / "toolchain_tools.md"
    storage = AIInstrumentsStorage(
        db_path=tmp_path / "sqlite.db",
        engine="sqlite",
        md_path=md_file,
    )
    assert md_file.is_file(), "Файл toolchain_tools.md должен быть создан автоматически"

    # Проверяем, что в файле есть стандартные инструменты
    loaded_from_md = load_markdown_tools(md_file)
    assert len(loaded_from_md) >= 5

    # Сохраняем новый инструмент
    new_inst = AIInstrument(
        tool_id="inst_new_sync",
        name="Синхронизированный инструмент",
        command="print('sync_test')",
    )
    storage.save_instrument(new_inst)

    # Проверяем обновление файла на диске
    updated_from_md = load_markdown_tools(md_file)
    assert any(it.tool_id == "inst_new_sync" for it in updated_from_md)


def test_search_and_google_instruments_presence_and_execution(service: AIInstrumentsService, tmp_path: Path):
    """Проверка регистрации инструментов поиска и исполнения локального поиска."""
    # 1. Проверяем наличие всех 7 инструментов поиска в хранилище
    expected_tools = [
        "inst_search_files_and_dirs",
        "inst_google_drive_search",
        "inst_google_mail_search",
        "inst_google_contacts_search",
        "inst_google_calendar_search",
        "inst_google_sheets_search",
        "inst_google_docs_search",
    ]
    for tid in expected_tools:
        inst = service.storage.get_instrument(tid)
        assert inst is not None, f"Инструмент {tid} должен быть зарегистрирован в хранилище"
        assert inst.tool_type == "python"

    # 2. Проверяем исполнение инструмента локального поиска файлов и папок
    test_dir = tmp_path / "search_test_sandbox"
    test_dir.mkdir(parents=True, exist_ok=True)
    sub_dir = test_dir / "reports"
    sub_dir.mkdir(parents=True, exist_ok=True)
    f1 = test_dir / "data_2026.csv"
    f1.write_text("a,b,c", encoding="utf-8")
    f2 = sub_dir / "annual_report.pdf"
    f2.write_text("pdf dummy content", encoding="utf-8")

    res = service.execute_instrument(
        "inst_search_files_and_dirs",
        {
            "root_path": str(test_dir),
            "pattern": "*report*",
            "entry_type": "all",
            "max_results": 10,
            "case_sensitive": False,
        },
    )
    assert res["success"] is True
    parsed_out = json.loads(res["stdout"])
    assert parsed_out["count"] >= 1
    found_names = [it["name"] for it in parsed_out["results"]]
    assert "reports" in found_names or "annual_report.pdf" in found_names

