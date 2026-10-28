"""
Тесты целостности токенов оформления и отсутствия захардкоженных стилей.

Updated: 2026-10-25 20:35:00
"""

import re
from pathlib import Path
import pytest


COMMON_WEBGUI_DIR = Path("apps/common/webgui")
WEBGUI_DIR = Path("apps/ai_assistant/api/webgui")


def test_variables_css_dark_theme_defaults():
    """Проверяет, что корневые и темные переменные не используют светлый фон #e2e8f0."""
    variables_css = WEBGUI_DIR / "css" / "variables.css"
    assert variables_css.exists(), "variables.css должен существовать"
    content = variables_css.read_text(encoding="utf-8")

    # В :root по умолчанию не должно быть --bs-body-bg: #e2e8f0 или --bg-color: #e2e8f0
    root_match = re.search(r":root\s*,\s*\[data-theme=\"dark\"\][^{]*\{([^}]+)\}", content)
    assert root_match, "Должен существовать блок :root по умолчанию для темной темы"
    root_block = root_match.group(1)

    assert "0b0f19" in root_block.lower(), "Должен использоваться темный цвет #0b0f19 по умолчанию"
    assert "--bs-body-bg:" in root_block, "Должен присутствовать токен --bs-body-bg"
    assert "--bg-color:" in root_block, "Должен присутствовать токен --bg-color"
    assert not re.search(r"--(?:bg-color|bs-body-bg|card-bg|surface-1)\s*:\s*#e2e8f0", root_block, re.IGNORECASE), \
        "Фоновые переменные в блоке по умолчанию не должны содержать светлый цвет #e2e8f0"


def test_no_hardcoded_colors_in_webgui_templates():
    """Проверяет отсутствие явных захардкоженных цветов в HTML шаблонах вкладок."""
    html_files = list(WEBGUI_DIR.glob("**/*.html"))
    assert len(html_files) > 0, "Должны быть найдены HTML-файлы webgui"

    # Паттерн для поиска style="..." с захардкоженными цветами фона и текста
    color_in_style_pattern = re.compile(
        r'style="[^"]*(?:background(?:-color)?|color)\s*:\s*(?:#(?:[0-9a-fA-F]{3,8})|rgba?\([^)]+\))[^"]*"',
        re.IGNORECASE
    )

    violations = []
    for html_file in html_files:
        content = html_file.read_text(encoding="utf-8")
        matches = color_in_style_pattern.findall(content)
        if matches:
            violations.append(f"{html_file}: {matches}")

    assert not violations, f"Обнаружены захардкоженные стили в HTML: {violations}"


def test_theme_dark_slate_has_body_background():
    """Проверяет, что в themes.css для theme-dark-slate явно определен фон body."""
    themes_css = WEBGUI_DIR / "css" / "themes.css"
    assert themes_css.exists(), "themes.css должен существовать"
    content = themes_css.read_text(encoding="utf-8")

    assert 'theme-dark-slate' in content, "В themes.css должна быть тема theme-dark-slate"
    assert 'var(--ui-bg-base' in content, "В themes.css должен использоваться токен var(--ui-bg-base)"


def test_common_webgui_text_muted_bootstrap_override():
    """Проверяет глобальное переопределение text-muted и --bs-secondary-color в apps/common/webgui."""
    overrides_css = COMMON_WEBGUI_DIR / "css" / "overrides.css"
    assert overrides_css.exists(), "overrides.css в common/webgui должен существовать"
    content = overrides_css.read_text(encoding="utf-8")

    # Проверка привязки --bs-secondary-color к токену темы
    assert "--bs-secondary-color: var(--text-muted)" in content, \
        "--bs-secondary-color должен быть привязан к var(--text-muted) в common/overrides.css"

    # Проверка правила для .text-muted
    assert ".text-muted" in content, "Класс .text-muted должен быть переопределен в common/overrides.css"
    assert "color: var(--text-muted) !important" in content, \
        ".text-muted должен использовать color: var(--text-muted) !important"


def test_variables_css_has_bs_secondary_color_mapping():
    """Проверяет наличие маппинга токена --bs-secondary-color в common и app variables.css."""
    for base_dir in [COMMON_WEBGUI_DIR, WEBGUI_DIR]:
        variables_css = base_dir / "css" / "variables.css"
        assert variables_css.exists(), f"{variables_css} должен существовать"
        content = variables_css.read_text(encoding="utf-8")
        assert "--bs-secondary-color:" in content, \
            f"Токен --bs-secondary-color должен быть определен в {variables_css}"


def test_nightview_theme_dark_readable_text_tokens():
    """Проверяет, что тема NightView содержит высококонтрастные темные цвета текста, а не светлые."""
    for base_dir in [COMMON_WEBGUI_DIR, WEBGUI_DIR]:
        themes_css = base_dir / "css" / "themes.css"
        content = themes_css.read_text(encoding="utf-8")
        assert '[data-theme="nightview"]' in content, f"NightView должен быть в {themes_css}"
        # Проверяем, что в NightView заданы темные цвета текста
        assert '--text-color: #18181b' in content, f"--text-color должен быть #18181b в {themes_css}"
        assert '--text-muted: #3f3f46' in content, f"--text-muted должен быть #3f3f46 в {themes_css}"
        assert '--text-silver: #27272a' in content, f"--text-silver должен быть темным антрацитом в {themes_css}"


