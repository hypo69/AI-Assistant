# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Core - Demo Scenario Pack
# =============================================================================
# Description:
#   Применение «пакета» демо-сценария к рабочему пространству: жёстко заданная
#   логика обогащения транскрипта для Obsidian (frontmatter, wikilinks, заметки
#   сущностей) и для Paperless-ngx (текстовая версия с тегами, корреспондентом
#   и типом документа). Данные пакета лежат в demo_scenarios/<id>/pack.json.
#
# Usage Examples:
#   pack = DemoScenarioPack.load(pack_dir)
#   result = await pack.apply(wm, "דוד_משה", transcript_text, "assets/call.mp3", "דוד משה")
#
# File: demo_scenario_pack.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 00:10:00
# =============================================================================

from __future__ import annotations
"""Пакет демо-сценария: обогащение транскрипта для Obsidian и Paperless."""

import asyncio
import json
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, TYPE_CHECKING

from logger import logger

if TYPE_CHECKING:
    from apps.ai_assistant.core.workspace_manager import WorkspaceManager

_HEBREW_RANGE = "\u0590-\u05FF"


@dataclass(frozen=True)
class DemoScenarioPack:
    """Неизменяемое описание пакета демо-сценария (pack.json + каталог заметок)."""

    pack_dir: Path
    data: Dict[str, Any]

    @classmethod
    def load(cls, pack_dir: Path) -> "DemoScenarioPack":
        """Загружает pack.json из каталога пакета.

        Raises:
            FileNotFoundError: Если pack.json отсутствует.
        """
        pack_file = Path(pack_dir) / "pack.json"
        if not pack_file.is_file():
            raise FileNotFoundError(f"Не найден pack.json демо-сценария: {pack_file}")
        return cls(Path(pack_dir), json.loads(pack_file.read_text(encoding="utf-8")))

    @property
    def transcript_dest_dir(self) -> str:
        """Каталог внутри рабочей области, куда помещается транскрипт."""
        return str(self.data["transcript"]["dest_dir"])

    def render_obsidian_transcript(self, text: str, title: str, audio_rel: str, paperless_id: Optional[int]) -> str:
        """Формирует Obsidian-версию транскрипта: frontmatter, вложение аудио, wikilinks, связанные заметки."""
        cfg = self.data["transcript"]["obsidian"]
        links: Dict[str, str] = cfg["wikilinks"]
        terms = sorted(links, key=len, reverse=True)
        pattern = re.compile(
            rf"(?<![{_HEBREW_RANGE}\[|])(?:{'|'.join(re.escape(t) for t in terms)})(?![{_HEBREW_RANGE}\]|])"
        )

        def _link(match: "re.Match[str]") -> str:
            shown = match.group(0)
            target = links[shown]
            return f"[[{target}]]" if shown == target else f"[[{target}|{shown}]]"

        linked = pattern.sub(_link, text)
        front = [
            "---",
            f'title: "{title}"',
            "type: transcript",
            "language: he",
            f'audio: "[[{audio_rel}]]"',
            "tags:",
            *[f"  - {t}" for t in cfg["tags"]],
        ]
        if paperless_id is not None:
            front.append(f"paperless_id: {paperless_id}")
        front.append("---")
        related = " · ".join(f"[[{n}]]" for n in cfg["related"])
        return "\n".join(front) + f"\n\n![[{audio_rel}]]\n\n{linked.rstrip()}\n\n---\n**קשור:** {related}\n"

    @staticmethod
    def render_plain_text(text: str) -> str:
        """Очищает Markdown до простого текста для OCR/индексации Paperless."""
        plain = re.sub(r"\*\*|^#+\s*|^[*\-]\s+", "", text, flags=re.MULTILINE)
        return re.sub(r"^---\s*$\n?", "", plain, flags=re.MULTILINE).strip() + "\n"

    def _ingest_paperless_sync(self, text: str, workspace_id: str, workspace_name: str) -> Optional[int]:
        """Загружает текстовую версию транскрипта в Paperless с метаданными; None, если сервис недоступен."""
        from apps.ai_assistant.core.paperless_connector import PaperlessConnector, PaperlessError

        meta = self.data["paperless"]
        try:
            connector = PaperlessConnector.from_config()
            if not connector.ping():
                logger.warning("[DemoScenarioPack] Paperless недоступен, пропускаю загрузку транскрипта")
                return None
            with tempfile.TemporaryDirectory() as tmp:
                tmp_file = Path(tmp) / meta["file_name"]
                tmp_file.write_text(self.render_plain_text(text), encoding="utf-8")
                res = connector.ingest_file(
                    file_path=tmp_file,
                    workspace_id=workspace_id,
                    workspace_name=workspace_name,
                    title=meta["title"],
                    extra_tags=meta.get("extra_tags"),
                    correspondent=meta.get("correspondent"),
                    document_type=meta.get("document_type"),
                )
            return int(res["paperless_id"]) if res and res.get("paperless_id") else None
        except (PaperlessError, OSError) as exc:
            logger.warning(f"[DemoScenarioPack] Ошибка загрузки в Paperless: {exc}")
            return None

    async def apply(
        self,
        wm: WorkspaceManager,
        workspace_id: str,
        transcript_text: str,
        audio_rel: str,
        workspace_name: str,
        transcript_name: str,
    ) -> Dict[str, Any]:
        """Применяет пакет: Paperless -> Obsidian-транскрипт -> заметки сущностей.

        Args:
            wm: Менеджер рабочих областей.
            workspace_id: Идентификатор рабочей области.
            transcript_text: Исходный Markdown транскрипта.
            audio_rel: Относительный путь аудиофайла в рабочей области (assets/...).
            workspace_name: Читаемое имя рабочей области (имя тега Paperless).
            transcript_name: Имя файла транскрипта (определяет заметку в transcripts/).

        Returns:
            Словарь: ``transcript_rel`` (путь внутри области), ``paperless_id`` (или None), ``notes`` (список путей).
        """
        paperless_id: Optional[int] = None
        if self.data.get("paperless", {}).get("enabled"):
            paperless_id = await asyncio.to_thread(
                self._ingest_paperless_sync, transcript_text, workspace_id, workspace_name
            )

        transcript_rel = f"{self.transcript_dest_dir}/{transcript_name}"
        title = Path(transcript_name).stem
        wm.import_document(
            workspace_id=workspace_id,
            document_id=transcript_rel,
            content=self.render_obsidian_transcript(transcript_text, title, audio_rel, paperless_id),
            commit_message=f"Демо-сценарий: транскрипт {transcript_name} (Obsidian)",
            language="he",
            paperless_id=paperless_id,
        )

        notes = []
        for note in self.data["notes"]:
            src = self.pack_dir / "notes" / note["src"]
            wm.import_document(
                workspace_id=workspace_id,
                document_id=note["dest"],
                content=src.read_text(encoding="utf-8"),
                commit_message=f"Демо-сценарий: заметка {note['dest']}",
                language="he",
            )
            notes.append(note["dest"])
        return {"transcript_rel": transcript_rel, "paperless_id": paperless_id, "notes": notes}
