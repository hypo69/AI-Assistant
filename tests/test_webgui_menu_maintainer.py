"""
=============================================================================
Process Name: Test WebGUI Menu Maintainer Skill and Auditor Tool
=============================================================================
Description:
  Тесты для навыка webgui-menu-maintainer и утилиты аудита menu_auditor.py.
  Проверяют корректность детекции меню, проверки статических тултипов без LLM,
  проверки i18n ключей, двухуровневой маршрутизации, локального menu_config.json,
  автоисправления (--fix) и полное соответствие всех вкладок WebGUI каноническому стандарту.

File: test_webgui_menu_maintainer.py
Project: ai-assistant
Package: tests
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-11-01 13:35:00
=============================================================================
"""

import json
import sys
from pathlib import Path
import pytest

AUDITOR_PATH = Path(__file__).resolve().parent.parent / ".agents" / "skills" / "webgui-menu-maintainer" / "scripts"
if str(AUDITOR_PATH) not in sys.path:
    sys.path.insert(0, str(AUDITOR_PATH))

from menu_auditor import WebGUIMenuAuditor


def test_menu_auditor_on_mock_tab(tmp_path):
    """Проверяет аудит меню на временной вкладке с валидной разметкой."""
    tab_dir = tmp_path / "tab_mock"
    tab_dir.mkdir()

    html_content = """
    <!-- Блок меню переключения панелей на вкладке. Выбранная панель добавляется в url -->
    <div id="mock-subtabs-nav" role="tablist">
      <button class="btn btn-sm btn-outline-primary active" id="btn-1" 
              data-bs-toggle="pill" data-panel-id="panel-1" 
              data-i18n-title="mockBtnTitle" title="Просмотр панели 1">
        <span data-i18n="mockBtnLabel">Панель 1</span>
      </button>
    </div>
    <div id="mock-blocks-nav">
      <button class="btn btn-outline-secondary" id="btn-block-a" 
              data-block-id="block-a" data-i18n-title="mockBlockTitle" title="Блок А">
        <span data-i18n="mockBlockLabel">Блок А</span>
      </button>
    </div>
    """

    js_content = """
    export function updateUrlWithPanel(panelId, blockId) {
        history.replaceState(null, null, `#tab-mock#${panelId}#block-${blockId}`);
    }
    """

    (tab_dir / "index.html").write_text(html_content, encoding="utf-8")
    (tab_dir / "main.js").write_text(js_content, encoding="utf-8")

    mock_config = {
        "tab_id": "tab-mock",
        "draggable": True,
        "subtabs": {"nav_id": "mock-subtabs-nav", "items": [{"id": "panel-1"}]}
    }
    (tab_dir / "menu_config.json").write_text(json.dumps(mock_config), encoding="utf-8")

    auditor = WebGUIMenuAuditor(root_dir=tmp_path)
    auditor.ru_dict = {
        "mockBtnTitle": "Просмотр панели 1",
        "mockBlockTitle": "Блок А"
    }

    result = auditor.audit_tab(tab_dir)

    assert result["has_menu"] is True
    assert len(result["issues"]) == 0, f"Ошибки аудита: {result['issues']}"
    assert any("Обязательный комментарий" in p for p in result["passed"])
    assert any("Статический тултип" in p for p in result["passed"])
    assert any("Синхронизация с URL" in p for p in result["passed"])
    assert any("menu_config.json" in p for p in result["passed"])


def test_menu_auditor_detects_missing_tooltips(tmp_path):
    """Проверяет, что аудитор фиксирует отсутствие тултипов и вызовов модели."""
    tab_dir = tmp_path / "tab_broken"
    tab_dir.mkdir()

    html_content = """
    <div id="broken-subtabs-nav" role="tablist">
      <button class="btn btn-sm btn-outline-primary" id="btn-1" data-bs-toggle="pill" data-panel-id="panel-1">
        <span>Панель без подсказки</span>
      </button>
    </div>
    """

    js_content = """// Main logic without url routing"""

    (tab_dir / "index.html").write_text(html_content, encoding="utf-8")
    (tab_dir / "main.js").write_text(js_content, encoding="utf-8")

    auditor = WebGUIMenuAuditor(root_dir=tmp_path)
    result = auditor.audit_tab(tab_dir)

    assert result["has_menu"] is True
    assert len(result["issues"]) > 0
    # Проверяем предупреждение о тултипе
    assert any("не имеет статического тултипа" in iss for iss in result["issues"])
    # Проверяем предупреждение о menu_config.json
    assert any("отсутствует локальный menu_config.json" in iss for iss in result["issues"])


def test_menu_auditor_fix_mode(tmp_path):
    """Проверяет режим автоматического исправления (--fix) на сломанной вкладке."""
    # Создаем структуру locales
    locales_dir = tmp_path / "apps" / "ai_assistant" / "api" / "webgui" / "locales"
    locales_dir.mkdir(parents=True)
    for lang in ["ru", "en", "he", "uk"]:
        (locales_dir / f"{lang}.json").write_text("{}", encoding="utf-8")

    # Создаем сломанную вкладку: без комментария, с nav-link, без тултипов, без роутинга и menu_config.json
    tab_dir = tmp_path / "apps" / "ai_assistant" / "api" / "webgui" / "tab_sample"
    tab_dir.mkdir(parents=True)

    html_content = """
    <div class="container-fluid">
      <ul class="nav nav-tabs" id="sampleTabNav" role="tablist">
        <li class="nav-item">
          <button class="nav-link active" data-bs-target="#pane-one" data-bs-toggle="tab" id="btn-tab-one">
            <span>Первая секция</span>
          </button>
        </li>
      </ul>
      <div class="tab-content">
        <div class="tab-pane active" id="pane-one">Контент</div>
      </div>
    </div>
    """
    js_content = """export function initSample() { console.log('init'); }"""

    (tab_dir / "index.html").write_text(html_content, encoding="utf-8")
    (tab_dir / "main.js").write_text(js_content, encoding="utf-8")

    auditor = WebGUIMenuAuditor(root_dir=tmp_path)

    # До фикса: есть замечания
    before_audit = auditor.audit_tab(tab_dir)
    assert len(before_audit["issues"]) > 0

    # Запускаем фикс
    fix_res = auditor.fix_tab(tab_dir)
    assert fix_res["fixed"] is True
    assert len(fix_res["changes"]) > 0

    # После фикса: 0 замечаний
    after_audit = auditor.audit_tab(tab_dir)
    assert len(after_audit["issues"]) == 0, f"Остались ошибки после fix: {after_audit['issues']}"
    assert (tab_dir / "menu_config.json").is_file()

    fixed_html = (tab_dir / "index.html").read_text(encoding="utf-8")
    assert "Блок меню переключения панелей" in fixed_html
    assert "btn btn-sm btn-outline-primary" in fixed_html
    assert "data-bs-toggle=\"pill\"" in fixed_html
    assert "data-i18n-title=" in fixed_html


def test_all_webgui_menus_compliance():
    """Проверяет, что ВСЕ существующие вкладки WebGUI строго соответствуют каноническому стандарту."""
    auditor = WebGUIMenuAuditor()
    results = auditor.run_audit()
    failed_tabs = {}

    for r in results:
        if r["has_menu"] and r["issues"]:
            failed_tabs[r["tab"]] = r["issues"]

    assert not failed_tabs, f"Вкладки WebGUI не соответствуют стандарту меню: {json.dumps(failed_tabs, indent=2, ensure_ascii=False)}"
