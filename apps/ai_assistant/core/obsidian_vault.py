# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Core - Obsidian Vault Builder
# =============================================================================
# Description:
#   Сервис формирования компактного хранилища Obsidian (Obsidian Vault) прямо
#   внутри папки каждого рабочего пространства (workspaces/<id>/).
#
#   Реализует два режима:
#   1. «На лету» (Auto-Sync): при импорте/обновлении документов или ответах QA
#      обогащает сами .md документы блоком YAML frontmatter, списком фактов и
#      [[wikilinks]], а также синхронно обновляет сводный файл базы знаний
#      `_Knowledge_Base.md` без создания десятков мелких файлов под сущности.
#   2. «Целенаправленная сборка» (On-Demand / Topic Dossier): собирает знания
#      по заданной теме или поисковому запросу в тематический конспект
#      `_Topics/<Тема>.md` и выполняет полную пересборку хранилища.
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.core.obsidian_vault import ObsidianVaultBuilder
#
#     builder = ObsidianVaultBuilder(workspace_manager)
#     builder.sync_document_on_the_fly("default", "mama.txt", "Мама мыла раму.", "abc1234", analysis)
#
# File: obsidian_vault.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-23 19:05:00
# =============================================================================

from __future__ import annotations
"""Генератор и синхронизатор компактного Obsidian Vault внутри рабочей области."""

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from urllib.parse import quote

from logger import logger

if TYPE_CHECKING:
    from apps.ai_assistant.core.workspace_manager import WorkspaceManager

KNOWLEDGE_BASE_FILENAME = "_Knowledge_Base.md"
TOPICS_DIRNAME = "_Topics"
OBSIDIAN_SECTION_START = "<!-- AI-OBSIDIAN-KNOWLEDGE:START -->"
OBSIDIAN_SECTION_END = "<!-- AI-OBSIDIAN-KNOWLEDGE:END -->"


def strip_obsidian_enrichment(raw_markdown: str) -> str:
    """Очищает текст документа от сгенерированного YAML frontmatter и блока фактов Obsidian.

    Позволяет при повторном чтении .md файла с диска извлекать чистый исходный
    текст без дублирования метаданных и секций знаний.

    Args:
        raw_markdown: Полное содержимое .md файла.

    Returns:
        str: Очищенный пользовательский текст документа.
    """
    text = raw_markdown or ""
    # Удаляем наш YAML frontmatter, если в нём есть маркер generator: ai_assistant_obsidian
    if text.startswith("---\n"):
        end_idx = text.find("\n---\n", 4)
        if end_idx != -1:
            frontmatter = text[4:end_idx]
            if "generator: ai_assistant_obsidian" in frontmatter:
                text = text[end_idx + 5 :].lstrip("\n")

    # Удаляем блок автогенерированных знаний в конце файла
    if OBSIDIAN_SECTION_START in text:
        start_pos = text.find(OBSIDIAN_SECTION_START)
        end_pos = text.find(OBSIDIAN_SECTION_END)
        if end_pos != -1:
            text = (text[:start_pos].rstrip() + "\n" + text[end_pos + len(OBSIDIAN_SECTION_END) :].lstrip()).strip()
        else:
            text = text[:start_pos].rstrip()

    return text


def _format_entity_wikilink(entity_dict: Optional[Dict[str, Any]]) -> str:
    """Форматирует сущность в компактный Obsidian wikilink [[лемма|текст]] или [[текст]]."""
    if not entity_dict:
        return "—"
    surface = str(entity_dict.get("text") or entity_dict.get("normalized") or "").strip()
    canonical = str(entity_dict.get("lemma") or entity_dict.get("normalized") or surface).strip()
    if not surface and not canonical:
        return "—"
    if canonical and surface and canonical != surface:
        return f"[[{canonical}|{surface}]]"
    return f"[[{canonical or surface}]]"


def _format_fact_line(fact: Dict[str, Any], include_doc_link: bool = False) -> str:
    """Форматирует структурированный факт в строку списка с [[wikilinks]]."""
    f_type = fact.get("fact_type", "action")
    lang = fact.get("language", "ru")
    is_neg = bool(fact.get("is_negated"))
    doc_id = fact.get("document_id") or fact.get("source", {}).get("document_id", "")
    doc_stem = Path(doc_id).stem if doc_id else ""
    doc_ref = f" *(источник: [[{doc_stem}|{doc_id}]])*" if (include_doc_link and doc_id) else ""

    if f_type == "possession":
        owner_link = _format_entity_wikilink(fact.get("owner"))
        poss_link = _format_entity_wikilink(fact.get("possessed_entity"))
        rel_label = "не владеет (not has)" if is_neg else "владеет (`has`)"
        return f"- 🏠 **Принадлежность ({lang}):** {owner_link} — *{rel_label}* → {poss_link}{doc_ref}"

    subj_link = _format_entity_wikilink(fact.get("subject"))
    pred = fact.get("predicate") or {}
    pred_text = pred.get("text") or pred.get("lemma") or fact.get("relation") or "действие"
    pred_lemma = pred.get("lemma") or pred_text
    neg_prefix = "НЕ " if is_neg else ""
    obj_link = _format_entity_wikilink(fact.get("object"))
    return (
        f"- ⚡ **Действие ({lang}):** {subj_link} — *{neg_prefix}{pred_text}* "
        f"(`{pred_lemma}`) → {obj_link}{doc_ref}"
    )


class ObsidianVaultBuilder:
    """Управляет компактным Obsidian Vault внутри папки рабочего пространства (`workspaces/<id>/`)."""

    def __init__(self, workspace_manager: WorkspaceManager) -> None:
        """Инициализирует построитель хранилища Obsidian с внедрением WorkspaceManager."""
        self.wm = workspace_manager

    @staticmethod
    def is_reserved_obsidian_file(filename_or_relpath: str) -> bool:
        """Проверяет, является ли файл служебным сводным индексом или конспектом Obsidian."""
        norm = str(filename_or_relpath).replace("\\", "/").lstrip("/")
        name = Path(norm).name
        if name == KNOWLEDGE_BASE_FILENAME:
            return True
        if norm.startswith(f"{TOPICS_DIRNAME}/") or f"/{TOPICS_DIRNAME}/" in f"/{norm}":
            return True
        return False

    def ensure_vault_config(self, ws_path: Path) -> None:
        """Инициализирует минимальную конфигурацию `.obsidian/app.json` для открытия папки как Vault."""
        obs_dir = ws_path / ".obsidian"
        obs_dir.mkdir(parents=True, exist_ok=True)
        app_json = obs_dir / "app.json"
        if not app_json.exists():
            default_obs_cfg = {
                "alwaysUpdateLinks": True,
                "newFileLocation": "root",
                "attachmentFolderPath": "attachments",
                "showFrontmatter": True,
                "strictLineBreaks": False,
            }
            try:
                app_json.write_text(
                    json.dumps(default_obs_cfg, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
            except Exception as exc:
                logger.warning(f"[ObsidianVault] Ошибка создания .obsidian/app.json в {ws_path}: {exc}")

    def build_obsidian_uri(self, ws_path: Path, note_name: Optional[str] = None) -> str:
        """Формирует протокольную ссылку `obsidian://open?path=...` для открытия Vault или заметки."""
        target_path = (ws_path / note_name) if note_name else ws_path
        encoded_path = quote(str(target_path.resolve()), safe="")
        return f"obsidian://open?path={encoded_path}"

    def _resolve_doc_md_path(self, ws_path: Path, doc_id: str) -> Path:
        """Определяет путь к компактному .md файлу документа внутри рабочей области."""
        clean_rel = str(doc_id).replace("\\", "/").lstrip("/")
        rel_path = Path(clean_rel)
        if rel_path.suffix.lower() == ".md":
            return ws_path / rel_path
        if rel_path.suffix.lower() in (".txt", ".csv", ".tsv", ".json", ".docx", ".xlsx", ".xls"):
            return ws_path / rel_path.with_suffix(".md")
        return ws_path / f"{clean_rel}.md"

    def render_compact_document_markdown(
        self,
        workspace_id: str,
        doc_id: str,
        clean_content: str,
        commit_hash: str,
        language: str,
        facts: List[Dict[str, Any]],
        entities: List[Dict[str, Any]],
        version_num: int = 1,
        original_path: Optional[str] = None,
    ) -> str:
        """Формирует компактный .md документ с YAML frontmatter, исходным текстом и блоком фактов."""
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        entity_names = sorted({
            str(e.get("lemma") or e.get("normalized") or e.get("text") or "").strip()
            for e in entities
            if str(e.get("lemma") or e.get("normalized") or e.get("text") or "").strip()
        })
        tags = ["knowledge", f"lang/{language}", f"ws/{workspace_id}"]
        if facts:
            tags.append("has-facts")

        frontmatter_lines = [
            "---",
            "generator: ai_assistant_obsidian",
            f"title: \"{Path(doc_id).stem}\"",
            f"document_id: {doc_id}",
            f"workspace_id: {workspace_id}",
            f"language: {language}",
            f"version: {version_num}",
            f"git_commit: {(commit_hash or 'HEAD')[:12]}",
            f"facts_count: {len(facts)}",
            f"updated_at: \"{now_iso}\"",
        ]
        if original_path:
            safe_orig = str(original_path).replace("\\", "/")
            frontmatter_lines.append(f"source_path: \"{safe_orig}\"")
        frontmatter_lines.append("tags:")
        for t in tags:
            frontmatter_lines.append(f"  - {t}")
        if entity_names:
            frontmatter_lines.append("entities:")
            for ent_name in entity_names[:25]:
                safe_ent = ent_name.replace('"', "'")
                frontmatter_lines.append(f"  - \"{safe_ent}\"")
        frontmatter_lines.append("---")

        section_lines = [
            OBSIDIAN_SECTION_START,
            "",
            "---",
            f"### 🧠 Извлечённые знания (Obsidian · [[{Path(KNOWLEDGE_BASE_FILENAME).stem}|Сводная база знаний]])",
            "",
        ]

        if facts:
            section_lines.append("#### 📌 Структурированные факты:")
            for f in facts:
                section_lines.append(_format_fact_line(f, include_doc_link=False))
            section_lines.append("")
        else:
            section_lines.append("*Структурированных фактов (action / possession) в этой ревизии не выделено.*\n")

        if entity_names:
            links_str = " · ".join(f"[[{name}]]" for name in entity_names[:30])
            section_lines.append(f"**Связанные сущности:** {links_str}")
            section_lines.append("")

        section_lines.append(OBSIDIAN_SECTION_END)

        body = clean_content.strip()
        return "\n".join(frontmatter_lines) + "\n\n" + body + "\n\n" + "\n".join(section_lines) + "\n"

    def sync_document_on_the_fly(
        self,
        workspace_id: str,
        doc_id: str,
        clean_content: str,
        commit_hash: str,
        analysis: Dict[str, Any],
        version_num: int = 1,
        original_path: Optional[str] = None,
    ) -> Optional[Path]:
        """Мгновенно («на лету») обновляет компактный .md файл документа и сводную базу знаний."""
        if self.is_reserved_obsidian_file(doc_id):
            return None

        ws = self.wm.registry.get_workspace(workspace_id)
        if not ws:
            return None
        ws_path = Path(ws["path"])
        self.ensure_vault_config(ws_path)

        # Для бинарных/медиа файлов в режиме raw (без извлечённого текста) не создаём побочный .md
        if not (clean_content or "").strip() and Path(doc_id).suffix.lower() not in (".md", ".txt"):
            self.rebuild_knowledge_base_index(workspace_id)
            return None

        language = analysis.get("language", "ru")
        facts = self.wm.store.get_facts(workspace_id=workspace_id, document_id=doc_id, include_stale=False)
        if not facts and analysis.get("facts"):
            facts = analysis.get("facts", [])
        entities = analysis.get("entities", [])

        md_target = self._resolve_doc_md_path(ws_path, doc_id)
        md_target.parent.mkdir(parents=True, exist_ok=True)
        enriched_md = self.render_compact_document_markdown(
            workspace_id=workspace_id,
            doc_id=doc_id,
            clean_content=clean_content,
            commit_hash=commit_hash,
            language=language,
            facts=facts,
            entities=entities,
            version_num=version_num,
            original_path=original_path,
        )
        md_target.write_text(enriched_md, encoding="utf-8")
        self.rebuild_knowledge_base_index(workspace_id)
        return md_target

    def rebuild_knowledge_base_index(self, workspace_id: str) -> Path:
        """Генерирует/обновляет единый компактный сводный файл `_Knowledge_Base.md` в корне рабочей области."""
        ws, ws_path = self.wm._get_or_create_workspace(workspace_id)
        self.ensure_vault_config(ws_path)

        docs = self.wm.store.list_documents(workspace_id)
        active_facts = self.wm.store.get_facts(workspace_id=workspace_id, include_stale=False)
        entities = self.wm.store.list_entities(workspace_id=workspace_id)
        metrics = self.wm.store.get_metrics(workspace_id=workspace_id)
        recent_queries = metrics.get("recent_queries", [])

        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        ws_name = ws.get("name") or workspace_id
        git_head = (ws.get("git_head") or "HEAD")[:8]

        lines: List[str] = [
            "---",
            "generator: ai_assistant_obsidian",
            f"title: \"Сводная база знаний — {ws_name}\"",
            f"workspace_id: {workspace_id}",
            f"git_head: {git_head}",
            f"documents_count: {len(docs)}",
            f"active_facts_count: {len(active_facts)}",
            f"updated_at: \"{now_iso}\"",
            "tags:",
            "  - obsidian-moc",
            "  - knowledge-base",
            f"  - ws/{workspace_id}",
            "---",
            "",
            f"# 🧠 Сводная база знаний: {ws_name}",
            "",
            f"> [!INFO] Компактный Obsidian Vault рабочего пространства `{workspace_id}`",
            f"> Документов: **{len(docs)}** | Активных фактов: **{len(active_facts)}** | Сущностей: **{len(entities)}** | Git HEAD: `{git_head}`",
            "",
            "## 📄 Документы рабочей области",
            "",
        ]

        if docs:
            lines.append("| Документ | Язык | Версия | Активных фактов | Git ревизия |")
            lines.append("| --- | --- | --- | --- | --- |")
            for d in docs:
                d_id = d["document_id"]
                if self.is_reserved_obsidian_file(d_id):
                    continue
                md_name = self._resolve_doc_md_path(ws_path, d_id).relative_to(ws_path).as_posix()
                link_target = md_name[:-3] if md_name.endswith(".md") else md_name
                c_short = (d.get("commit_hash") or "HEAD")[:8]
                lines.append(
                    f"| [[{link_target}]] (`{d_id}`) | `{d.get('language', 'ru')}` | v{d.get('current_version', 1)} "
                    f"| {d.get('active_facts_count', 0)} | `{c_short}` |"
                )
            lines.append("")
        else:
            lines.append("*В рабочей области пока нет проиндексированных документов.*\n")

        # Секция всех активных фактов, сгруппированных компактно
        lines.append("## 📌 Извлечённые канонические факты")
        lines.append("")
        if active_facts:
            for f in active_facts:
                lines.append(_format_fact_line(f, include_doc_link=True))
            lines.append("")
        else:
            lines.append("*Факты ещё не извлечены.*\n")

        # Mermaid-диаграмма связей знаний (для визуализации прямо в Obsidian)
        lines.append("## 🕸 Семантический граф связей (Mermaid)")
        lines.append("")
        lines.append("```mermaid")
        lines.append("flowchart LR")
        if active_facts:
            for idx, f in enumerate(active_facts[:25]):
                f_type = f.get("fact_type", "action")
                if f_type == "possession":
                    src_txt = (f.get("owner") or {}).get("lemma") or (f.get("owner") or {}).get("text") or "Owner"
                    dst_txt = (f.get("possessed_entity") or {}).get("lemma") or (f.get("possessed_entity") or {}).get("text") or "Item"
                    rel_txt = "владеет" if not f.get("is_negated") else "не владеет"
                else:
                    src_txt = (f.get("subject") or {}).get("lemma") or (f.get("subject") or {}).get("text") or "Subject"
                    dst_txt = (f.get("object") or {}).get("lemma") or (f.get("object") or {}).get("text") or "Object"
                    rel_txt = (f.get("predicate") or {}).get("lemma") or (f.get("predicate") or {}).get("text") or "action"
                safe_src = re.sub(r'["\[\]\(\)]', "", str(src_txt))
                safe_dst = re.sub(r'["\[\]\(\)]', "", str(dst_txt))
                safe_rel = re.sub(r'["\[\]\(\)]', "", str(rel_txt))
                lines.append(f'    N{idx}_S["{safe_src}"] -->|"{safe_rel}"| N{idx}_O["{safe_dst}"]')
        else:
            lines.append('    Empty["Нет активных связей"]')
        lines.append("```")
        lines.append("")

        # Компактный индекс сущностей (без создания отдельных файлов под каждую сущность)
        lines.append("## 🏷 Индекс сущностей и понятий")
        lines.append("")
        if entities:
            unique_ents: Dict[str, Dict[str, Any]] = {}
            for e in entities:
                key = str(e.get("lemma") or e.get("normalized") or e.get("text") or "").strip()
                if key and key not in unique_ents:
                    unique_ents[key] = e
            ent_badges = [
                f"[[{k}]] (`{v.get('entity_type', 'entity')}`, {v.get('language', 'ru')})"
                for k, v in sorted(unique_ents.items())
            ]
            lines.append(" · ".join(ent_badges))
            lines.append("")
        else:
            lines.append("*Сущности не найдены.*\n")

        # Тематические конспекты (_Topics), если они были собраны
        topics_dir = ws_path / TOPICS_DIRNAME
        if topics_dir.exists() and topics_dir.is_dir():
            topic_files = sorted(topics_dir.glob("*.md"))
            if topic_files:
                lines.append("## 🎯 Целенаправленно собранные тематические конспекты")
                lines.append("")
                for tf in topic_files:
                    lines.append(f"- [[{TOPICS_DIRNAME}/{tf.stem}|{tf.stem}]]")
                lines.append("")

        # История проверенных вопросов и ответов QA («на лету»)
        lines.append("## 💬 Ответы ИИ и проверенные знания (QA)")
        lines.append("")
        valid_queries = [q for q in recent_queries if q.get("status") == "success"]
        if valid_queries:
            for q_item in valid_queries[:15]:
                q_str = q_item.get("question", "")
                a_str = q_item.get("answer", "")
                q_lang = q_item.get("language", "ru")
                lines.append(f"- **В ({q_lang}):** *{q_str}* → **О:** **{a_str}**")
            lines.append("")
        else:
            lines.append("*Задайте вопрос во вкладке «Вопрос-Ответ (QA)» или «Чат», и ответы автоматически появятся здесь.*\n")

        kb_path = ws_path / KNOWLEDGE_BASE_FILENAME
        kb_path.write_text("\n".join(lines), encoding="utf-8")
        return kb_path

    def build_workspace_vault(
        self,
        workspace_id: str,
        commit_to_git: bool = True,
    ) -> Dict[str, Any]:
        """Целенаправленно пересобирает все компактные .md документы и `_Knowledge_Base.md` в рабочей области."""
        ws, ws_path = self.wm._get_or_create_workspace(workspace_id)
        self.ensure_vault_config(ws_path)

        docs = self.wm.store.list_documents(workspace_id)
        enriched_files: List[str] = []

        for d in docs:
            doc_id = d["document_id"]
            if self.is_reserved_obsidian_file(doc_id):
                continue
            raw_content = strip_obsidian_enrichment(d.get("content") or "")
            if not raw_content.strip() and Path(doc_id).suffix.lower() not in (".md", ".txt"):
                continue
            commit_hash = d.get("commit_hash") or "HEAD"
            lang = d.get("language") or "ru"
            ver = int(d.get("current_version") or 1)
            facts = self.wm.store.get_facts(workspace_id=workspace_id, document_id=doc_id, include_stale=False)
            all_ents = self.wm.store.list_entities(workspace_id=workspace_id)
            doc_ents = [e for e in all_ents if e.get("document_id") == doc_id]

            md_path = self._resolve_doc_md_path(ws_path, doc_id)
            md_path.parent.mkdir(parents=True, exist_ok=True)
            rendered = self.render_compact_document_markdown(
                workspace_id=workspace_id,
                doc_id=doc_id,
                clean_content=raw_content,
                commit_hash=commit_hash,
                language=lang,
                facts=facts,
                entities=doc_ents,
                version_num=ver,
                original_path=d.get("file_path"),
            )
            md_path.write_text(rendered, encoding="utf-8")
            enriched_files.append(str(md_path.relative_to(ws_path)).replace("\\", "/"))

        kb_path = self.rebuild_knowledge_base_index(workspace_id)

        if commit_to_git:
            self.wm._run_git(ws_path, ["add", "."])
            if self.wm._run_git(ws_path, ["status", "--porcelain"]):
                self.wm._run_git(ws_path, ["commit", "-m", "Obsidian Vault: синхронизация компактной базы знаний (.md)"])

        head = self.wm._run_git(ws_path, ["rev-parse", "HEAD"])
        return {
            "status": "ok",
            "workspace_id": workspace_id,
            "vault_path": str(ws_path),
            "knowledge_base_file": str(kb_path),
            "obsidian_uri": self.build_obsidian_uri(ws_path, KNOWLEDGE_BASE_FILENAME),
            "documents_enriched": len(enriched_files),
            "enriched_files": enriched_files,
            "git_head": head[:8] if head and not head.startswith("fatal") else "HEAD",
        }

    def compile_topic_note(
        self,
        workspace_id: str,
        topic: str,
        query: Optional[str] = None,
        commit_to_git: bool = True,
    ) -> Dict[str, Any]:
        """Целенаправленно собирает знания по теме или поисковому запросу в заметку `_Topics/<Тема>.md`.

        Отбирает все релевантные факты из SQLite, семантические совпадения из FAISS
        и связанные документы рабочей области, формируя компактный тематический конспект Obsidian.
        """
        clean_topic = topic.strip() or "Тематический_срез"
        search_q = (query or clean_topic).strip()
        ws, ws_path = self.wm._get_or_create_workspace(workspace_id)
        self.ensure_vault_config(ws_path)

        topics_dir = ws_path / TOPICS_DIRNAME
        topics_dir.mkdir(parents=True, exist_ok=True)
        safe_filename = re.sub(r"[^\w\-]+", "_", clean_topic).strip("_") or "Topic"
        note_path = topics_dir / f"{safe_filename}.md"

        # 1. Отбираем релевантные факты по ключевым словам темы/запроса
        all_facts = self.wm.store.get_facts(workspace_id=workspace_id, include_stale=False)
        keywords = [w.lower() for w in re.findall(r"\w+", search_q) if len(w) >= 2]

        matched_facts: List[Dict[str, Any]] = []
        for f in all_facts:
            blob = json.dumps(f, ensure_ascii=False).lower()
            if not keywords or any(kw in blob for kw in keywords):
                matched_facts.append(f)

        # Если по строгому фильтру ничего не нашлось, включаем все активные факты области
        if not matched_facts and all_facts:
            matched_facts = all_facts[:15]

        # 2. Семантический поиск чанков в FAISS
        faiss_hits: List[Dict[str, Any]] = []
        try:
            rag = self.wm.get_faiss_rag(workspace_id)
            faiss_hits = rag.search(search_q, top_k=6)
        except Exception as exc:
            logger.debug(f"[ObsidianVault] Ошибка поиска FAISS для темы '{clean_topic}': {exc}")

        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        referenced_docs = sorted({
            f.get("document_id") or f.get("source", {}).get("document_id", "")
            for f in matched_facts
            if (f.get("document_id") or f.get("source", {}).get("document_id", ""))
        })

        lines: List[str] = [
            "---",
            "generator: ai_assistant_obsidian",
            f"title: \"Тема: {clean_topic}\"",
            f"topic: \"{clean_topic}\"",
            f"query: \"{search_q}\"",
            f"workspace_id: {workspace_id}",
            f"facts_matched: {len(matched_facts)}",
            f"created_at: \"{now_iso}\"",
            "tags:",
            "  - obsidian-topic",
            "  - knowledge-dossier",
            f"  - ws/{workspace_id}",
            "---",
            "",
            f"# 🎯 Тематический конспект: {clean_topic}",
            "",
            f"← Вернуться в [[{Path(KNOWLEDGE_BASE_FILENAME).stem}|Сводную базу знаний ({KNOWLEDGE_BASE_FILENAME})]]",
            "",
            f"> [!SUMMARY] Целенаправленная выборка знаний по запросу: `{search_q}`",
            f"> Найдено фактов: **{len(matched_facts)}** | Семантических фрагментов (FAISS): **{len(faiss_hits)}**",
            "",
            "## 📌 Собранные факты по теме",
            "",
        ]

        if matched_facts:
            for f in matched_facts:
                lines.append(_format_fact_line(f, include_doc_link=True))
            lines.append("")
        else:
            lines.append("*Подходящих фактов не обнаружено.*\n")

        lines.append("## 🔍 Контекстные фрагменты и цитаты (RAG / FAISS)")
        lines.append("")
        if faiss_hits:
            for h in faiss_hits:
                meta = h.get("meta") or {}
                d_id = meta.get("document_id", "документ")
                d_stem = Path(d_id).stem
                quote_txt = h.get("text", "").strip()
                if quote_txt:
                    lines.append(f"> «{quote_txt}» — из [[{d_stem}|{d_id}]] *(предложение #{meta.get('sentence_index', 0)})*")
                    lines.append("")
        else:
            lines.append("*Семантических совпадений в FAISS не найдено.*\n")

        if referenced_docs:
            lines.append("## 📂 Первоисточники")
            lines.append("")
            for rd in referenced_docs:
                lines.append(f"- [[{Path(rd).stem}|{rd}]]")
            lines.append("")

        note_path.write_text("\n".join(lines), encoding="utf-8")

        # Обновляем сводный индекс, чтобы новая тема появилась в _Knowledge_Base.md
        self.rebuild_knowledge_base_index(workspace_id)

        if commit_to_git:
            self.wm._run_git(ws_path, ["add", "."])
            if self.wm._run_git(ws_path, ["status", "--porcelain"]):
                self.wm._run_git(ws_path, ["commit", "-m", f"Obsidian Topic: собран конспект '{clean_topic}'"])

        return {
            "status": "ok",
            "workspace_id": workspace_id,
            "topic": clean_topic,
            "query": search_q,
            "note_path": str(note_path),
            "obsidian_uri": self.build_obsidian_uri(ws_path, f"{TOPICS_DIRNAME}/{note_path.name}"),
            "facts_count": len(matched_facts),
            "faiss_chunks_count": len(faiss_hits),
        }

    def get_vault_status(self, workspace_id: str) -> Dict[str, Any]:
        """Возвращает состояние компактного Obsidian Vault в указанной рабочей области."""
        ws = self.wm.registry.get_workspace(workspace_id)
        if not ws:
            ws, ws_path = self.wm._get_or_create_workspace(workspace_id)
        else:
            ws_path = Path(ws["path"])

        kb_path = ws_path / KNOWLEDGE_BASE_FILENAME
        if not kb_path.exists():
            self.rebuild_knowledge_base_index(workspace_id)

        topics_dir = ws_path / TOPICS_DIRNAME
        topics = [p.name for p in sorted(topics_dir.glob("*.md"))] if topics_dir.exists() else []
        md_files = [
            p.name
            for p in sorted(ws_path.glob("*.md"))
            if not p.name.startswith("~")
        ]

        return {
            "status": "ok",
            "workspace_id": workspace_id,
            "vault_path": str(ws_path),
            "knowledge_base_file": str(kb_path),
            "knowledge_base_exists": kb_path.exists(),
            "obsidian_configured": (ws_path / ".obsidian" / "app.json").exists(),
            "obsidian_uri": self.build_obsidian_uri(ws_path, KNOWLEDGE_BASE_FILENAME),
            "markdown_files_count": len(md_files),
            "markdown_files": md_files,
            "topics_count": len(topics),
            "topics": topics,
        }
