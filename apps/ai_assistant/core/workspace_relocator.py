# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Core - Workspace File Relocator
# =============================================================================
# Description:
#   Интеллектуальный модуль отслеживания и сверки перемещений файлов без изменений
#   во внешних источниках и внутри рабочей области.
#   Обеспечивает:
#   1. Нативное распознавание переноса в Git (git mv / R100 rename detection)
#      для слепков .extracted_snapshots и локальных файлов.
#   2. Бесшовную перепривязку (relocation) документа по SHA-256 хэшу содержимого
#      в умной рекомендательной системе (SQLite KnowledgeStore, FAISS, TemporalCodeGraph
#      и Obsidian Vault) без дублирования фактов и без потери истории версий.
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.core.workspace_relocator import WorkspaceRelocator
#     relocated_from = WorkspaceRelocator.reconcile_external_move(
#         wm=workspace_manager,
#         ws_path=ws_path,
#         manifest_data=manifest_data,
#         new_doc_id="sub/report.txt",
#         new_snap_rel=".extracted_snapshots/PC_sub_report.txt.snapshot",
#         content="Мама мыла раму.",
#         resolved_host="MYPC",
#     )
#
# File: workspace_relocator.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-26 01:10:00
# =============================================================================

from __future__ import annotations
"""Сверка перемещений файлов в Git и умной рекомендательной системе знаний."""

import json
from pathlib import Path
import shutil
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from logger import logger
from apps.ai_assistant.core.obsidian_vault import strip_obsidian_enrichment
from apps.ai_assistant.core.store.document_fact_repo import compute_sha256

if TYPE_CHECKING:
    from apps.ai_assistant.core.workspace_manager import WorkspaceManager


class WorkspaceRelocator:
    """Координирует отслеживание перемещений файлов между Git и базой знаний."""

    @staticmethod
    def compute_clean_hash(content: str) -> str:
        """Вычисляет канонический SHA-256 хэш очищенного текста документа."""
        return compute_sha256(strip_obsidian_enrichment(content))

    @classmethod
    def find_moved_manifest_entry(
        cls,
        ws_path: Path,
        manifest_data: Dict[str, Any],
        new_doc_id: str,
        content_hash: str,
        content_len: int,
        resolved_host: str,
    ) -> Optional[str]:
        """Ищет в .tracked_sources.json прежний путь файла, который был перенесён без изменений.

        Файл считается перенесённым, если:
        1. Его прежний ключ (old_doc_id) отличается от new_doc_id на том же хосте.
        2. По старому пути (file_path) файл на диске больше не существует.
        3. Хэш содержимого (content_hash) или слепок .snapshot полностью совпадает.
        """
        host_upper = resolved_host.upper()
        for old_doc_id, meta in list(manifest_data.items()):
            if old_doc_id == new_doc_id:
                continue
            entry_host = str(meta.get("host_name") or resolved_host).upper()
            if entry_host != host_upper:
                continue

            old_fp_str = str(meta.get("file_path") or "")
            if old_fp_str and Path(old_fp_str).exists():
                # Старый файл всё ещё на месте — значит это копия, а не перенос
                continue

            saved_hash = meta.get("content_hash")
            if saved_hash and saved_hash == content_hash:
                return old_doc_id

            # Fallback для старых записей манифеста без поля content_hash: проверяем слепок
            snap_rel = meta.get("snapshot")
            if snap_rel:
                snap_path = ws_path / str(snap_rel)
                if snap_path.exists() and snap_path.is_file():
                    try:
                        snap_text = snap_path.read_text(encoding="utf-8", errors="replace")
                        if cls.compute_clean_hash(snap_text) == content_hash:
                            return old_doc_id
                    except Exception:
                        pass

            # Проверка по длине контента, если слепок уже перемещён
            if not saved_hash and int(meta.get("content_length", -1)) == content_len and content_len > 0:
                return old_doc_id

        return None

    @classmethod
    def reconcile_external_move(
        cls,
        wm: WorkspaceManager,
        ws_path: Path,
        manifest_data: Dict[str, Any],
        new_doc_id: str,
        new_snap_rel: str,
        content: str,
        resolved_host: str,
    ) -> Optional[str]:
        """Выполняет git mv слепка и обновляет манифест при переносе внешнего файла без изменений.

        Returns:
            Идентификатор прежнего документа (old_doc_id), если обнаружен перенос, иначе None.
        """
        content_hash = cls.compute_clean_hash(content)
        old_doc_id = cls.find_moved_manifest_entry(
            ws_path=ws_path,
            manifest_data=manifest_data,
            new_doc_id=new_doc_id,
            content_hash=content_hash,
            content_len=len(content),
            resolved_host=resolved_host,
        )
        if not old_doc_id:
            return None

        old_meta = manifest_data.pop(old_doc_id, {})
        old_snap_rel = str(old_meta.get("snapshot") or "")
        new_snap_path = ws_path / new_snap_rel
        new_snap_path.parent.mkdir(parents=True, exist_ok=True)

        if old_snap_rel and old_snap_rel != new_snap_rel:
            old_snap_path = ws_path / old_snap_rel
            if old_snap_path.exists():
                # Пробуем штатный git mv, чтобы индекс Git сразу зафиксировал R100 rename
                mv_out = wm._run_git(ws_path, ["mv", "-f", old_snap_rel, new_snap_rel])
                if not new_snap_path.exists():
                    try:
                        shutil.move(str(old_snap_path), str(new_snap_path))
                        wm._run_git(ws_path, ["rm", "-f", "--cached", old_snap_rel])
                    except Exception as mv_exc:
                        logger.debug(f"[WorkspaceRelocator] Fallback перемещения слепка ({mv_out}): {mv_exc}")

        logger.info(
            f"[WorkspaceRelocator] Обнаружен перенос файла без изменений: "
            f"'{old_doc_id}' -> '{new_doc_id}' (SHA-256: {content_hash[:12]})"
        )
        return old_doc_id

    @classmethod
    def migrate_subsystems_on_move(
        cls,
        wm: WorkspaceManager,
        workspace_id: str,
        old_doc_id: str,
        new_doc_id: str,
        commit_hash: str,
        original_path: Optional[str] = None,
        host_name: Optional[str] = None,
        qualified_path: Optional[str] = None,
    ) -> None:
        """Обновляет FAISS-векторы и темпоральный граф при перемещении документа без пересчёта NLP."""
        if not old_doc_id or old_doc_id == new_doc_id:
            return

        # 1. Обновление метаданных в векторном индексе FAISS без потери эмбеддингов
        try:
            rag = wm.get_faiss_rag(workspace_id)
            old_prefix = f"{workspace_id}:{old_doc_id}:"
            new_prefix = f"{workspace_id}:{new_doc_id}:"
            updated_any = False
            deduped_metas: List[Dict[str, Any]] = []
            seen_ids = set()

            for meta in rag.metadatas:
                m_id = str(meta.get("id", ""))
                if m_id.startswith(old_prefix):
                    suffix = m_id[len(old_prefix):]
                    new_id = f"{new_prefix}{suffix}"
                    meta["id"] = new_id
                    meta["document_id"] = new_doc_id
                    if commit_hash:
                        meta["commit_hash"] = commit_hash
                    if original_path:
                        meta["original_path"] = original_path
                    if host_name:
                        meta["host_name"] = host_name
                    if qualified_path:
                        meta["qualified_path"] = qualified_path
                    updated_any = True
                    if new_id not in seen_ids:
                        seen_ids.add(new_id)
                        deduped_metas.append(meta)
                else:
                    if m_id not in seen_ids:
                        seen_ids.add(m_id)
                        deduped_metas.append(meta)

            if updated_any:
                rag.metadatas = deduped_metas
                rag._save()
        except Exception as faiss_exc:
            logger.warning(f"[WorkspaceRelocator] Ошибка миграции FAISS для {old_doc_id} -> {new_doc_id}: {faiss_exc}")

        # 2. Перепривязка в темпоральном графе знаний (TemporalCodeGraph)
        try:
            if commit_hash:
                active_links = wm.graph.get_active_links(source_id=old_doc_id)
                wm.graph.supersede_links_by_source(source_id=old_doc_id, invalidating_commit=commit_hash)
                for lnk in active_links:
                    wm.graph.add_link(
                        source_id=new_doc_id,
                        target_id=lnk.target_id,
                        relation_type=lnk.relation_type,
                        valid_from=commit_hash,
                        confidence=lnk.confidence,
                        provenance=lnk.provenance,
                    )
                wm.graph.add_link(
                    source_id=new_doc_id,
                    target_id=old_doc_id,
                    relation_type="relocated_from",
                    valid_from=commit_hash,
                    confidence=1.0,
                    provenance="workspace_relocator",
                )
        except Exception as graph_exc:
            logger.warning(f"[WorkspaceRelocator] Ошибка миграции графа для {old_doc_id} -> {new_doc_id}: {graph_exc}")

    @classmethod
    def cleanup_deleted_external_sources(
        cls,
        wm: WorkspaceManager,
        workspace_id: str,
        ws_path: Path,
        active_doc_ids: set[str],
        current_host: str,
    ) -> List[str]:
        """Очищает по-настоящему удалённые внешние файлы (которые не были перенесены в другое место)."""
        manifest_file = ws_path / ".tracked_sources.json"
        if not manifest_file.exists():
            return []

        try:
            manifest_data: Dict[str, Any] = json.loads(manifest_file.read_text(encoding="utf-8"))
        except Exception:
            return []

        removed_docs: List[str] = []
        host_upper = current_host.upper()

        for doc_id, meta in list(manifest_data.items()):
            if doc_id in active_doc_ids:
                continue
            entry_host = str(meta.get("host_name") or current_host).upper()
            if entry_host != host_upper:
                continue
            fp_str = str(meta.get("file_path") or "")
            if fp_str and not Path(fp_str).exists():
                # Файл отсутствует на диске и не был сопоставлен ни с одним новым файлом при синхронизации
                manifest_data.pop(doc_id, None)
                snap_rel = meta.get("snapshot")
                if snap_rel and (ws_path / str(snap_rel)).exists():
                    wm._run_git(ws_path, ["rm", "-f", str(snap_rel)])
                wm.store.mark_document_deleted(workspace_id=workspace_id, document_id=doc_id)
                removed_docs.append(doc_id)

        if removed_docs:
            manifest_file.write_text(json.dumps(manifest_data, indent=2, ensure_ascii=False), encoding="utf-8")
            wm._run_git(ws_path, ["add", ".tracked_sources.json"])
            if wm._run_git(ws_path, ["status", "--porcelain"]):
                wm._run_git(
                    ws_path,
                    ["commit", "-m", f"Очистка удалённых внешних файлов: {', '.join(removed_docs[:5])}"],
                )

        return removed_docs
