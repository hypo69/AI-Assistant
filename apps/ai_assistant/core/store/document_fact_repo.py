# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Core Store - Document & Fact Repo
# =============================================================================
# Description:
#   Управление таблицами documents, document_versions, document_chunks,
#   entities, facts, fact_sources и language_analysis в SQLite.
#   Обеспечивает автоматический перевод прежних фактов в статус 'stale'.
#
# File: core/store/document_fact_repo.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.core.store
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-27 22:20:00
# =============================================================================

from __future__ import annotations
"""Репозиторий управления документами, версиями, сущностями и фактами."""

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

from apps.ai_assistant.core.store.workspace_repo import get_utc_now_iso
from apps.ai_assistant.core.workspace_registry import get_current_host_name, parse_host_qualified_path


def compute_sha256(text: str) -> str:
    """Вычисляет хэш SHA-256 для строки текста."""
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


class DocumentFactRepoMixin:
    """Миксин операций с документами, чанками, сущностями и фактами."""

    VALID_FACT_STATUSES = {"extracted", "validated", "ambiguous", "rejected", "stale"}

    def relocate_document(
        self,
        workspace_id: str,
        old_document_id: str,
        new_document_id: str,
        new_file_path: str,
        commit_hash: str = "",
        host_name: Optional[str] = None,
        qualified_path: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Перепривязывает документ, его версии, чанки, сущности и факты на новый путь без потери истории."""
        if not old_document_id or old_document_id == new_document_id:
            return None

        now = get_utc_now_iso()
        resolved_host, clean_file_path, resolved_qualified = parse_host_qualified_path(
            new_file_path, default_host=host_name
        )
        final_qualified = qualified_path or resolved_qualified
        conn = self._get_conn(workspace_id=workspace_id)
        try:
            cur = conn.execute(
                "SELECT * FROM documents WHERE workspace_id = ? AND document_id = ?",
                (workspace_id, old_document_id),
            )
            old_doc = cur.fetchone()
            if not old_doc:
                return None

            cur_version = int(old_doc["current_version"] or 1)
            eff_commit = commit_hash or str(old_doc["commit_hash"] or "")
            old_chunk_prefix = f"{workspace_id}:{old_document_id}:"
            new_chunk_prefix = f"{workspace_id}:{new_document_id}:"

            with conn:
                # 1. Удаляем случайный дубликат на целевом document_id, если он был
                conn.execute(
                    "DELETE FROM documents WHERE workspace_id = ? AND document_id = ?",
                    (workspace_id, new_document_id),
                )
                # 2. Обновляем основную запись документа
                conn.execute(
                    """
                    UPDATE documents
                    SET document_id = ?, file_path = ?, host_name = ?, qualified_path = ?,
                        title = ?, commit_hash = ?, status = 'indexed', updated_at = ?
                    WHERE workspace_id = ? AND document_id = ?
                    """,
                    (
                        new_document_id,
                        clean_file_path,
                        resolved_host,
                        final_qualified,
                        Path(new_document_id).name,
                        eff_commit,
                        now,
                        workspace_id,
                        old_document_id,
                    ),
                )
                # 3. Переносим историю версий
                conn.execute(
                    "UPDATE document_versions SET document_id = ? WHERE workspace_id = ? AND document_id = ?",
                    (new_document_id, workspace_id, old_document_id),
                )
                # 4. Переносим чанки с обновлением префикса chunk_id
                chunk_rows = conn.execute(
                    "SELECT chunk_id FROM document_chunks WHERE workspace_id = ? AND document_id = ?",
                    (workspace_id, old_document_id),
                ).fetchall()
                for c_row in chunk_rows:
                    old_cid = str(c_row["chunk_id"])
                    new_cid = (
                        f"{new_chunk_prefix}{old_cid[len(old_chunk_prefix):]}"
                        if old_cid.startswith(old_chunk_prefix)
                        else old_cid
                    )
                    conn.execute(
                        "UPDATE document_chunks SET chunk_id = ?, document_id = ? WHERE chunk_id = ?",
                        (new_cid, new_document_id, old_cid),
                    )
                # 5. Переносим сущности
                ent_rows = conn.execute(
                    "SELECT entity_id FROM entities WHERE workspace_id = ? AND document_id = ?",
                    (workspace_id, old_document_id),
                ).fetchall()
                for e_row in ent_rows:
                    old_eid = str(e_row["entity_id"])
                    new_eid = (
                        f"{new_chunk_prefix}{old_eid[len(old_chunk_prefix):]}"
                        if old_eid.startswith(old_chunk_prefix)
                        else old_eid
                    )
                    conn.execute(
                        "UPDATE entities SET entity_id = ?, document_id = ? WHERE entity_id = ?",
                        (new_eid, new_document_id, old_eid),
                    )
                # 6. Переносим факты (сохраняя их статус extracted/validated!) и обновляем source в raw_fact_json
                fact_rows = conn.execute(
                    "SELECT fact_id, raw_fact_json FROM facts WHERE workspace_id = ? AND document_id = ?",
                    (workspace_id, old_document_id),
                ).fetchall()
                for f_row in fact_rows:
                    fid = f_row["fact_id"]
                    try:
                        raw_obj = json.loads(f_row["raw_fact_json"])
                        if isinstance(raw_obj.get("source"), dict):
                            raw_obj["source"]["document_id"] = new_document_id
                        raw_obj["document_id"] = new_document_id
                        new_raw_json = json.dumps(raw_obj, ensure_ascii=False)
                    except Exception:
                        new_raw_json = f_row["raw_fact_json"]
                    conn.execute(
                        "UPDATE facts SET document_id = ?, raw_fact_json = ? WHERE fact_id = ?",
                        (new_document_id, new_raw_json, fid),
                    )
                # 7. Переносим источники фактов и прогоны анализа
                conn.execute(
                    "UPDATE fact_sources SET document_id = ?, commit_hash = ? WHERE workspace_id = ? AND document_id = ?",
                    (new_document_id, eff_commit, workspace_id, old_document_id),
                )
                conn.execute(
                    "UPDATE language_analysis SET document_id = ? WHERE workspace_id = ? AND document_id = ?",
                    (new_document_id, workspace_id, old_document_id),
                )
                conn.execute(
                    "UPDATE analysis_runs SET document_id = ? WHERE workspace_id = ? AND document_id = ?",
                    (new_document_id, workspace_id, old_document_id),
                )

            active_facts = self.get_facts(workspace_id=workspace_id, document_id=new_document_id, include_stale=False)
            return {
                "status": "relocated_unchanged",
                "previous_document_id": old_document_id,
                "document_id": new_document_id,
                "version": cur_version,
                "commit_hash": eff_commit,
                "language": old_doc["language"],
                "facts_count": len(active_facts),
                "facts": active_facts,
            }
        finally:
            self._close_conn(conn)

    def mark_document_deleted(self, workspace_id: str, document_id: str) -> bool:
        """Помечает удалённый внешний документ и переводит его факты в статус 'stale'."""
        conn = self._get_conn(workspace_id=workspace_id)
        try:
            with conn:
                conn.execute(
                    "UPDATE facts SET status = 'stale' WHERE workspace_id = ? AND document_id = ? AND status != 'stale'",
                    (workspace_id, document_id),
                )
                cur = conn.execute(
                    "DELETE FROM documents WHERE workspace_id = ? AND document_id = ?",
                    (workspace_id, document_id),
                )
                conn.execute(
                    "DELETE FROM document_chunks WHERE workspace_id = ? AND document_id = ?",
                    (workspace_id, document_id),
                )
                return cur.rowcount > 0
        finally:
            self._close_conn(conn)

    def store_document_and_facts(
        self,
        workspace_id: str,
        document_id: str,
        file_path: str,
        raw_content: str,
        commit_hash: str,
        analysis_result: Dict[str, Any],
        duration_ms: float = 0.0,
        force_reanalyze: bool = False,
        host_name: Optional[str] = None,
        qualified_path: Optional[str] = None,
        relocated_from: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Сохраняет документ, версию, чанки и извлечённые факты с автораспознаванием переноса файла."""
        now = get_utc_now_iso()
        content_hash = compute_sha256(raw_content)
        language = analysis_result.get("language", "ru")
        analyzer_name = analysis_result.get("analyzer", "DefaultAnalyzer")
        resolved_host, clean_file_path, resolved_qualified = parse_host_qualified_path(file_path, default_host=host_name)
        final_qualified = qualified_path or resolved_qualified
        conn = self._get_conn(workspace_id=workspace_id)
        try:
            # Если явно передан источник перемещения или обнаружен идентичный content_hash у перемещённого файла
            candidate_old_id = relocated_from
            if not candidate_old_id and not force_reanalyze:
                cand_rows = conn.execute(
                    """
                    SELECT document_id, file_path, host_name
                    FROM documents
                    WHERE workspace_id = ? AND content_hash = ? AND document_id != ?
                    """,
                    (workspace_id, content_hash, document_id),
                ).fetchall()
                for c_row in cand_rows:
                    old_fp = str(c_row["file_path"] or "")
                    old_host = str(c_row["host_name"] or resolved_host).upper()
                    if old_host == resolved_host.upper() and old_fp and not Path(old_fp).exists():
                        candidate_old_id = str(c_row["document_id"])
                        break

            if candidate_old_id and candidate_old_id != document_id and not force_reanalyze:
                relocated_res = self.relocate_document(
                    workspace_id=workspace_id,
                    old_document_id=candidate_old_id,
                    new_document_id=document_id,
                    new_file_path=clean_file_path,
                    commit_hash=commit_hash,
                    host_name=resolved_host,
                    qualified_path=final_qualified,
                )
                if relocated_res:
                    return relocated_res

            cur = conn.execute(
                "SELECT current_version, content_hash FROM documents WHERE workspace_id = ? AND document_id = ?",
                (workspace_id, document_id),
            )
            existing = cur.fetchone()

            if existing and existing["content_hash"] == content_hash and not force_reanalyze:
                active_facts = self.get_facts(workspace_id=workspace_id, document_id=document_id, include_stale=False)
                return {
                    "status": "unchanged_deduplicated",
                    "document_id": document_id,
                    "version": existing["current_version"],
                    "facts_count": len(active_facts),
                    "facts": active_facts,
                }

            new_version = (int(existing["current_version"]) + 1) if existing else 1

            with conn:
                conn.execute(
                    """
                    UPDATE facts
                    SET status = 'stale'
                    WHERE workspace_id = ? AND document_id = ? AND status != 'stale'
                    """,
                    (workspace_id, document_id),
                )
                conn.execute(
                    "DELETE FROM document_chunks WHERE workspace_id = ? AND document_id = ?",
                    (workspace_id, document_id),
                )
                conn.execute(
                    "DELETE FROM entities WHERE workspace_id = ? AND document_id = ?",
                    (workspace_id, document_id),
                )

                conn.execute(
                    """
                    INSERT INTO documents (
                        document_id, workspace_id, file_path, host_name, qualified_path, title, language, encoding,
                        current_version, content_hash, commit_hash, status, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'utf-8', ?, ?, ?, 'indexed', ?)
                    ON CONFLICT(workspace_id, document_id) DO UPDATE SET
                        file_path = excluded.file_path,
                        host_name = excluded.host_name,
                        qualified_path = excluded.qualified_path,
                        language = excluded.language,
                        current_version = excluded.current_version,
                        content_hash = excluded.content_hash,
                        commit_hash = excluded.commit_hash,
                        status = 'indexed',
                        updated_at = excluded.updated_at
                    """,
                    (
                        document_id,
                        workspace_id,
                        clean_file_path,
                        resolved_host,
                        final_qualified,
                        Path(document_id).name,
                        language,
                        new_version,
                        content_hash,
                        commit_hash,
                        now,
                    ),
                )

                conn.execute(
                    """
                    INSERT INTO document_versions (
                        workspace_id, document_id, version_num, commit_hash, content_hash, raw_content, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (workspace_id, document_id, new_version, commit_hash, content_hash, raw_content, now),
                )

                for sent in analysis_result.get("sentences", []):
                    s_idx = int(sent.get("sentence_index", 0))
                    s_text = sent.get("text", "")
                    chunk_id = f"{workspace_id}:{document_id}:v{new_version}:s{s_idx}"
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO document_chunks (
                            chunk_id, workspace_id, document_id, version_num, sentence_index,
                            text, language, char_start, char_end, content_hash
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            chunk_id,
                            workspace_id,
                            document_id,
                            new_version,
                            s_idx,
                            s_text,
                            language,
                            int(sent.get("char_start", 0)),
                            int(sent.get("char_end", len(s_text))),
                            compute_sha256(s_text),
                        ),
                    )

                for idx, ent in enumerate(analysis_result.get("entities", [])):
                    ent_id = f"{workspace_id}:{document_id}:ent:{idx}:{ent.get('normalized', '')}"
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO entities (
                            entity_id, workspace_id, document_id, text, normalized, lemma, entity_type, language
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            ent_id,
                            workspace_id,
                            document_id,
                            ent.get("text", ""),
                            ent.get("normalized", ""),
                            ent.get("lemma", ""),
                            ent.get("entity_type", "entity"),
                            ent.get("language", language),
                        ),
                    )

                saved_facts: List[Dict[str, Any]] = []
                for idx, fact in enumerate(analysis_result.get("facts", [])):
                    fact_id = f"fact_{uuid.uuid4().hex[:12]}"
                    src = fact.get("source", {})
                    s_idx = int(src.get("sentence_index", idx))
                    fact_copy = dict(fact)
                    fact_copy["fact_id"] = fact_id
                    fact_copy["version_num"] = new_version
                    fact_copy["status"] = "extracted"
                    fact_copy["commit_hash"] = commit_hash

                    conn.execute(
                        """
                        INSERT INTO facts (
                            fact_id, workspace_id, document_id, version_num, sentence_index,
                            fact_type, relation, language, subject_json, predicate_json,
                            object_json, owner_json, possessed_json, raw_fact_json,
                            is_negated, confidence, status, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'extracted', ?)
                        """,
                        (
                            fact_id,
                            workspace_id,
                            document_id,
                            new_version,
                            s_idx,
                            fact.get("fact_type", "action"),
                            fact.get("relation", ""),
                            fact.get("language", language),
                            json.dumps(fact.get("subject"), ensure_ascii=False) if fact.get("subject") else None,
                            json.dumps(fact.get("predicate"), ensure_ascii=False) if fact.get("predicate") else None,
                            json.dumps(fact.get("object"), ensure_ascii=False) if fact.get("object") else None,
                            json.dumps(fact.get("owner"), ensure_ascii=False) if fact.get("owner") else None,
                            json.dumps(fact.get("possessed_entity"), ensure_ascii=False) if fact.get("possessed_entity") else None,
                            json.dumps(fact_copy, ensure_ascii=False),
                            1 if fact.get("is_negated") else 0,
                            float(fact.get("confidence", 0.95)),
                            now,
                        ),
                    )

                    conn.execute(
                        """
                        INSERT INTO fact_sources (
                            fact_id, workspace_id, document_id, commit_hash,
                            sentence_index, char_start, char_end, quote_text
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            fact_id,
                            workspace_id,
                            document_id,
                            commit_hash,
                            s_idx,
                            int(src.get("char_start", 0)),
                            int(src.get("char_end", 0)),
                            src.get("quote", ""),
                        ),
                    )
                    saved_facts.append(fact_copy)

                conn.execute(
                    """
                    INSERT INTO language_analysis (
                        workspace_id, document_id, version_num, language,
                        analyzer_name, analysis_json, confidence, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        workspace_id,
                        document_id,
                        new_version,
                        language,
                        analyzer_name,
                        json.dumps(analysis_result, ensure_ascii=False),
                        float(analysis_result.get("confidence", 0.9)),
                        now,
                    ),
                )

                conn.execute(
                    """
                    INSERT INTO analysis_runs (
                        workspace_id, document_id, language, analyzer_name,
                        facts_extracted, duration_ms, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        workspace_id,
                        document_id,
                        language,
                        analyzer_name,
                        len(saved_facts),
                        duration_ms,
                        now,
                    ),
                )

            return {
                "status": "indexed",
                "document_id": document_id,
                "version": new_version,
                "commit_hash": commit_hash,
                "language": language,
                "facts_count": len(saved_facts),
                "facts": saved_facts,
            }
        finally:
            self._close_conn(conn)

    def get_facts(
        self,
        workspace_id: str,
        document_id: Optional[str] = None,
        language: Optional[str] = None,
        fact_type: Optional[str] = None,
        include_stale: bool = False,
    ) -> List[Dict[str, Any]]:
        """Возвращает структурированные факты рабочей области с фильтрацией."""
        conn = self._get_conn(workspace_id=workspace_id)
        try:
            clauses = ["workspace_id = ?"]
            params: List[Any] = [workspace_id]
            if not include_stale:
                clauses.append("status NOT IN ('stale', 'rejected')")
            if document_id:
                clauses.append("document_id = ?")
                params.append(document_id)
            if language:
                clauses.append("language = ?")
                params.append(language)
            if fact_type:
                clauses.append("fact_type = ?")
                params.append(fact_type)

            sql = f"SELECT * FROM facts WHERE {' AND '.join(clauses)} ORDER BY created_at DESC"
            cur = conn.execute(sql, params)
            results: List[Dict[str, Any]] = []
            for row in cur.fetchall():
                raw = json.loads(row["raw_fact_json"])
                raw["fact_id"] = row["fact_id"]
                raw["status"] = row["status"]
                raw["version_num"] = row["version_num"]
                raw["document_id"] = row["document_id"]
                results.append(raw)
            return results
        finally:
            self._close_conn(conn)

    def update_fact_status(self, fact_id: str, status: str, workspace_id: Optional[str] = None) -> bool:
        """Обновляет статус проверки факта (extracted, validated, ambiguous, rejected, stale)."""
        if status not in self.VALID_FACT_STATUSES:
            raise ValueError(f"Недопустимый статус факта: {status}")
        conn = self._get_conn(workspace_id=workspace_id)
        try:
            with conn:
                cur = conn.execute("UPDATE facts SET status = ? WHERE fact_id = ?", (status, fact_id))
                return cur.rowcount > 0
        finally:
            self._close_conn(conn)

    def list_documents(self, workspace_id: str) -> List[Dict[str, Any]]:
        """Возвращает список документов рабочей области с числом активных фактов."""
        conn = self._get_conn(workspace_id=workspace_id)
        try:
            cur = conn.execute(
                """
                SELECT d.*,
                    (SELECT COUNT(*) FROM facts f WHERE f.workspace_id = d.workspace_id AND f.document_id = d.document_id AND f.status != 'stale') AS active_facts_count,
                    (SELECT raw_content FROM document_versions dv WHERE dv.workspace_id = d.workspace_id AND dv.document_id = d.document_id ORDER BY dv.version_num DESC LIMIT 1) AS content
                FROM documents d
                WHERE d.workspace_id = ?
                ORDER BY d.updated_at DESC
                """,
                (workspace_id,),
            )
            rows = [dict(r) for r in cur.fetchall()]
            for item in rows:
                h_name, loc_p, qual_p = parse_host_qualified_path(
                    str(item.get("file_path", "")),
                    default_host=item.get("host_name") or None,
                )
                item["host_name"] = item.get("host_name") or h_name
                item["qualified_path"] = item.get("qualified_path") or qual_p
            return rows
        finally:
            self._close_conn(conn)

    def list_entities(self, workspace_id: str, query: Optional[str] = None) -> List[Dict[str, Any]]:
        """Возвращает сущности рабочей области."""
        conn = self._get_conn(workspace_id=workspace_id)
        try:
            if query:
                q_like = f"%{query.strip()}%"
                cur = conn.execute(
                    """
                    SELECT * FROM entities
                    WHERE workspace_id = ? AND (text LIKE ? OR normalized LIKE ? OR lemma LIKE ?)
                    """,
                    (workspace_id, q_like, q_like, q_like),
                )
            else:
                cur = conn.execute("SELECT * FROM entities WHERE workspace_id = ?", (workspace_id,))
            return [dict(r) for r in cur.fetchall()]
        finally:
            self._close_conn(conn)

    def get_document_chunks(
        self,
        workspace_id: str,
        document_id: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """Возвращает чанки документов рабочей области для инспекции и семантического анализа RAG.

        Args:
            workspace_id: Идентификатор рабочей области.
            document_id: Опциональный фильтр по документу.
            limit: Максимальное количество чанков.

        Returns:
            Список словарей с метаданными и текстом чанков.
        """
        conn = self._get_conn(workspace_id=workspace_id)
        try:
            clauses = ["c.workspace_id = ?"]
            params: List[Any] = [workspace_id]
            if document_id:
                clauses.append("c.document_id = ?")
                params.append(document_id)
            params.append(limit)
            sql = f"""
                SELECT c.chunk_id, c.workspace_id, c.document_id, c.version_num,
                       c.sentence_index, c.text, c.language, c.char_start, c.char_end,
                       c.content_hash, d.title, d.file_path, d.host_name, d.qualified_path
                FROM document_chunks c
                LEFT JOIN documents d ON d.workspace_id = c.workspace_id AND d.document_id = c.document_id
                WHERE {' AND '.join(clauses)}
                ORDER BY c.rowid DESC
                LIMIT ?
            """
            cur = conn.execute(sql, params)
            rows = [dict(r) for r in cur.fetchall()]
            for item in rows:
                h_name, loc_p, qual_p = parse_host_qualified_path(
                    str(item.get("file_path", "")),
                    default_host=item.get("host_name") or None,
                )
                item["host_name"] = item.get("host_name") or h_name
                item["qualified_path"] = item.get("qualified_path") or qual_p
            return rows
        finally:
            self._close_conn(conn)
