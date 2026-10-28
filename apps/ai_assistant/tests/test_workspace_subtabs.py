"""

=============================================================================

Process Name: Test AI Assistant Workspace Subtabs Navigation and URL Routing

=============================================================================

Description:

    Модульные тесты для проверки разметки субменю переключения панелей

    вкладки tab_workspace (Файлы, Документы и факты, Умный поиск QA, Чат),

    структуры контейнеров tab-content, механизма формирования составного URL

    вида http://localhost:8002/#tab-workspace#<panel_id> и отправки раздельных

    API-запросов строго для активной панели.



File: test_workspace_subtabs.py

Package: apps/ai_assistant/tests

Author: hypo69

Copyright: © 2026 hypo69

Updated: 2026-10-25 21:15:00

=============================================================================

"""



from pathlib import Path

import pytest





_WEBGUI_DIR = Path(__file__).resolve().parent.parent / "api" / "webgui"





def test_workspace_subtabs_html_structure() -> None:

    """Проверяет разметку субменю и контейнеров панелей в index.html вкладки tab_workspace."""

    index_html_path = _WEBGUI_DIR / "tab_workspace" / "index.html"

    assert index_html_path.exists(), f"Файл {index_html_path} не найден"

    html = index_html_path.read_text(encoding="utf-8")



    # 1. Проверяем наличие контейнера субменю под заголовком

    assert '<!-- Меню суб-вкладок  -->' in html, "Комментарий меню суб-вкладок не найден"

    assert 'id="workspace-subtabs-nav"' in html, "Контейнер #workspace-subtabs-nav не найден"

    assert 'role="tablist"' in html, "Атрибут role=tablist не найден в субменю"



    # 2. Проверяем наличие кнопок суб-вкладок в стиле верхнего меню

    assert 'id="subtab-ws-step1-btn"' in html, "Кнопка Файлы (Шаг 1) не найдена"

    assert 'id="subtab-ws-step2-btn"' in html, "Кнопка Шаг 2 не найдена"

    assert 'id="subtab-ws-step3-btn"' in html, "Кнопка Шаг 3 не найдена"

    assert 'id="subtab-ws-chat-btn"' in html, "Кнопка Чат не найдена"

    assert 'id="subtab-ws-commits-btn"' in html, "Кнопка Коммиты не найдена"



    assert 'data-panel-id="panel-files"' in html, "data-panel-id='panel-files' не найден"

    assert 'data-panel-id="panel-documents"' in html, "data-panel-id='panel-documents' не найден"

    assert 'data-panel-id="panel-qa"' in html, "data-panel-id='panel-qa' не найден"

    assert 'data-panel-id="panel-chat"' in html, "data-panel-id='panel-chat' не найден"

    assert 'data-panel-id="panel-commits"' in html, "data-panel-id='panel-commits' не найден"



    assert 'data-bs-target="#subpane-ws-step1"' in html, "Target для шага 1 не настроен"

    assert 'data-bs-target="#subpane-ws-step2"' in html, "Target для шага 2 не настроен"

    assert 'data-bs-target="#subpane-ws-step3"' in html, "Target для шага 3 не настроен"

    assert 'data-bs-target="#subpane-ws-chat"' in html, "Target для чата не настроен"

    assert 'data-bs-target="#subpane-ws-commits"' in html, "Target для коммитов не настроен"



    # Кнопки должны иметь класс btn-outline-primary и иконки

    assert 'btn btn-sm btn-outline-primary active' in html, "Активная кнопка Шага 1 не найдена"

    assert 'bi-folder2-open' in html, "Иконка Шага 1 не найдена"

    assert 'bi-file-earmark-code' in html, "Иконка Шага 2 не найдена"

    assert 'bi-chat-dots' in html, "Иконка Шага 3 не найдена"

    assert 'bi-chat-square-text' in html, "Иконка Чата не найдена"

    assert 'bi-git' in html, "Иконка Git не найдена"



    # 3. Проверяем контейнер содержимого суб-панелей

    assert 'id="workspace-subtabs-content"' in html, "Контейнер #workspace-subtabs-content не найден"

    assert 'id="subpane-ws-step1"' in html, "Панель #subpane-ws-step1 не найдена"

    assert 'id="subpane-ws-step2"' in html, "Панель #subpane-ws-step2 не найдена"

    assert 'id="subpane-ws-step3"' in html, "Панель #subpane-ws-step3 не найдена"

    assert 'id="subpane-ws-chat"' in html, "Панель #subpane-ws-chat не найдена"

    assert 'id="subpane-ws-commits"' in html, "Панель #subpane-ws-commits не найдена"



    # 4. Проверяем изоляцию существующих панелей по порядку

    step1_pos = html.find('id="subpane-ws-step1"')

    step2_pos = html.find('id="subpane-ws-step2"')

    step3_pos = html.find('id="subpane-ws-step3"')

    chat_pos = html.find('id="subpane-ws-chat"')

    commits_pos = html.find('id="subpane-ws-commits"')



    assert step1_pos < step2_pos < step3_pos < chat_pos < commits_pos, "Суб-панели расположены не по порядку"



    # Ищем карточки внутри панелей

    files_card = html.find(' id="panel-files"')

    sources_card = html.find(' id="panel-sources"')

    docs_card = html.find(' id="panel-documents"')

    facts_card = html.find(' id="panel-facts"')

    qa_card = html.find(' id="panel-qa"')

    chat_card = html.find(' id="panel-chat"')



    # Панель Файлы: выбор рабочей области и источники

    assert step1_pos < files_card < step2_pos, "panel-files не внутри subpane-ws-step1"

    assert step1_pos < sources_card < step2_pos, "panel-sources не внутри subpane-ws-step1"



    # Проверяем наличие таблицы содержимого папки и опций конвертации

    assert 'id="ws-directory-contents-table-body"' in html

    assert 'name="ws-conv-pdf-mode"' in html

    assert 'name="ws-conv-ocr-mode"' in html

    assert 'name="ws-conv-audio-mode"' in html



    # Шаг 2: документы и факты

    assert step2_pos < docs_card < step3_pos, "panel-documents не внутри subpane-ws-step2"

    assert step2_pos < facts_card < step3_pos, "panel-facts не внутри subpane-ws-step2"



    # Шаг 3: умный поиск QA

    assert step3_pos < qa_card < chat_pos, "panel-qa не внутри subpane-ws-step3"



    # Панель Чат: окно ответа, поле ввода и кнопка отправить

    assert chat_pos < chat_card < commits_pos, "panel-chat не внутри subpane-ws-chat"

    assert 'id="ws-chat-response-window"' in html, "Окно ответа чата не найдено"

    assert 'id="ws-chat-messages"' in html, "Контейнер сообщений чата не найден"

    assert 'id="ws-chat-input"' in html, "Поле ввода чата не найдено"

    assert 'id="ws-chat-send-btn"' in html, "Кнопка отправки чата не найдена"



    # Панель Коммиты: таблица, поиск, обновление

    commits_card = html.find(' id="panel-commits"')

    assert commits_pos < commits_card, "panel-commits не внутри subpane-ws-commits"

    assert 'id="commits-search-input"' in html, "Поле поиска коммитов не найдено"

    assert 'id="commits-refresh-btn"' in html, "Кнопка обновления коммитов не найдена"

    assert 'id="commits-table-body"' in html, "Таблица коммитов не найдена"

    assert 'id="commits-count-badge"' in html, "Бейдж счетчика коммитов не найден"





def test_workspace_subtabs_routing_and_url_builder() -> None:

    """Проверяет утилиты формирования URL вида #tab-workspace#<panel_id> в common/ui_utils.js."""

    utils_path = _WEBGUI_DIR / "tab_workspace" / "common" / "ui_utils.js"

    assert utils_path.exists(), f"Файл {utils_path} не найден"

    content = utils_path.read_text(encoding="utf-8")



    assert "export const TAB_ID = 'tab-workspace';" in content

    assert "function isWorkspaceTabActive(" in content

    assert "function normalizeSubTabId(" in content

    assert "function getActiveSubTabId(" in content

    assert "function getPanelFromHash(" in content

    assert "function updateUrlWithPanel(" in content



    # Проверяем формирование хеша с префиксом вкладки

    assert "#${TAB_ID}#${canonical}" in content

    assert "history.replaceState" in content





def test_workspace_subtabs_isolated_api_fetching() -> None:

    """Проверяет логику раздельных API-запросов и слушателей в tab_workspace/main.js."""

    main_js_path = _WEBGUI_DIR / "tab_workspace" / "main.js"

    assert main_js_path.exists(), f"Файл {main_js_path} не найден"

    content = main_js_path.read_text(encoding="utf-8")



    # Проверяем экспорт функций управления субпанелями

    assert "function switchWorkspaceSubTab(" in content, "Функция switchWorkspaceSubTab не найдена"

    assert "function getActiveWorkspaceSubTabId(" in content, "Функция getActiveWorkspaceSubTabId не найдена"

    assert "function fetchActiveSubTabOnly(" in content, "Функция fetchActiveSubTabOnly не найдена"



    assert "window.switchWorkspaceSubTab = switchWorkspaceSubTab;" in content

    assert "window.getActiveWorkspaceSubTabId = getActiveWorkspaceSubTabId;" in content

    assert "window.getWorkspacePanelFromHash = getPanelFromHash;" in content

    assert "window.updateWorkspaceUrlWithPanel = updateUrlWithPanel;" in content

    assert "window.fetchActiveWorkspaceSubTab = fetchActiveSubTabOnly;" in content



    # Проверяем раздельные API-запросы для каждой суб-панели

    assert "panel-files" in content

    assert "loadWorkspaces()" in content

    assert "loadSources(wsId, force)" in content



    assert "activeSub === 'panel-documents'" in content

    assert "loadDocuments(wsId, force)" in content

    assert "loadWorkspaceCommits(wsId, force)" in content

    assert "loadFacts(wsId, force)" in content



    # Проверяем интеграцию панели чата

    assert "panel-chat" in content

    assert "initChatPanel" in content



    # Проверяем привязку слушателей к кнопкам навигации и хешу URL

    assert "workspace-subtabs-nav" in content, "Селектор субменю не найден в main.js"

    assert "shown.bs.tab" in content, "Обработка shown.bs.tab не найдена в main.js"

    assert "hashchange" in content, "Обработка события hashchange не найдена в main.js"





def test_top_workspace_dropdown_integration() -> None:

    """Проверяет интеграцию перехода к документам в top_workspace_dropdown.js."""

    dropdown_js_path = _WEBGUI_DIR / "js" / "top_workspace_dropdown.js"

    assert dropdown_js_path.exists(), f"Файл {dropdown_js_path} не найден"

    content = dropdown_js_path.read_text(encoding="utf-8")



    assert "window.switchWorkspaceSubTab('step2')" in content, "top_workspace_dropdown.js не переключает на step2"





def test_tab_core_panel_active_matching() -> None:

    """Проверяет распознавание группированных панелей tab-workspace в tab-core.js."""

    tab_core_path = _WEBGUI_DIR / "js" / "tab-core.js"

    assert tab_core_path.exists(), f"Файл {tab_core_path} не найден"

    content = tab_core_path.read_text(encoding="utf-8")



    assert "tab-workspace" in content

    assert "cleanActive.includes('commit')" in content

    assert "cleanActive.includes('chat')" in content

    assert "cleanActive.includes('document')" in content

    assert "cleanActive.includes('file')" in content

    assert "cleanActive.includes('qa')" in content

