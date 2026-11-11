# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Tests - Demo Scenario Pack
# =============================================================================
# Description:
#   Тесты пакета демо-сценария דוד משה: Obsidian-версия транскрипта и текст для Paperless.
#
# File: test_demo_scenario_pack.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 00:12:00
# =============================================================================

from __future__ import annotations
"""Тесты DemoScenarioPack."""

from pathlib import Path

import pytest

from apps.ai_assistant.core.demo_scenario_pack import DemoScenarioPack

PACK_DIR = Path(__file__).resolve().parents[1] / "demo_scenarios" / "david_moshe"
SAMPLE = "**שמוליק:** זינה — **8.3** ליטר.\n\n---\n\n### שלב 1\n* **דּוֹד משה** — קונה"


@pytest.fixture(name="pack")
def pack_fixture() -> DemoScenarioPack:
    """Загружает реальный пакет сценария."""
    return DemoScenarioPack.load(PACK_DIR)


def test_obsidian_transcript_has_wikilinks_and_frontmatter(pack: DemoScenarioPack) -> None:
    """Имена участников превращаются в wikilinks, в frontmatter попадают аудио и paperless_id."""
    out = pack.render_obsidian_transcript(SAMPLE, "t", "assets/call.mp3", 7)
    assert out.startswith("---\ntitle:")
    assert "paperless_id: 7" in out
    assert "![[assets/call.mp3]]" in out
    assert "[[שמוליק]]" in out and "[[זינה]]" in out
    assert "[[דוד משה|דּוֹד משה]]" in out
    assert "[[[[" not in out


def test_plain_text_for_paperless_has_no_markdown(pack: DemoScenarioPack) -> None:
    """Текст для Paperless очищается от разметки Markdown."""
    plain = pack.render_plain_text(SAMPLE)
    assert "**" not in plain and "###" not in plain and "---" not in plain


def test_all_pack_notes_exist(pack: DemoScenarioPack) -> None:
    """Все заметки из pack.json присутствуют на диске."""
    for note in pack.data["notes"]:
        assert (PACK_DIR / "notes" / note["src"]).is_file()
