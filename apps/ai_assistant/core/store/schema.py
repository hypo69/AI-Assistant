# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Core Store - SQLite Schema DDL
# =============================================================================
# Description:
#   Декларативные SQL-определения схемы таблиц и индексов хранилища знаний
#   KnowledgeStore (ТЗ раздел 7).
#
# File: core/store/schema.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.core.store
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-26 00:19:00
# =============================================================================

from __future__ import annotations
"""Декларативная схема SQLite базы знаний AI Assistant."""

KNOWLEDGE_STORE_DDL = """
CREATE TABLE IF NOT EXISTS documents (
    document_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    host_name TEXT DEFAULT '',
    qualified_path TEXT DEFAULT '',
    title TEXT NOT NULL,
    language TEXT DEFAULT 'ru',
    encoding TEXT DEFAULT 'utf-8',
    current_version INTEGER DEFAULT 1,
    content_hash TEXT NOT NULL,
    commit_hash TEXT DEFAULT '',
    status TEXT DEFAULT 'indexed',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (workspace_id, document_id)
);

CREATE TABLE IF NOT EXISTS document_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    version_num INTEGER NOT NULL,
    commit_hash TEXT DEFAULT '',
    content_hash TEXT NOT NULL,
    raw_content TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS document_chunks (
    chunk_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    version_num INTEGER NOT NULL,
    sentence_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    language TEXT NOT NULL,
    char_start INTEGER DEFAULT 0,
    char_end INTEGER DEFAULT 0,
    content_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS entities (
    entity_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    text TEXT NOT NULL,
    normalized TEXT NOT NULL,
    lemma TEXT NOT NULL,
    entity_type TEXT DEFAULT 'entity',
    language TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS facts (
    fact_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    version_num INTEGER NOT NULL,
    sentence_index INTEGER NOT NULL,
    fact_type TEXT NOT NULL,
    relation TEXT NOT NULL,
    language TEXT NOT NULL,
    subject_json TEXT,
    predicate_json TEXT,
    object_json TEXT,
    owner_json TEXT,
    possessed_json TEXT,
    raw_fact_json TEXT NOT NULL,
    is_negated INTEGER DEFAULT 0,
    confidence REAL DEFAULT 1.0,
    status TEXT DEFAULT 'extracted',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fact_relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id TEXT NOT NULL,
    source_fact_id TEXT NOT NULL,
    target_fact_id TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    provenance TEXT DEFAULT 'analyzer',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fact_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fact_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    commit_hash TEXT DEFAULT '',
    sentence_index INTEGER DEFAULT 0,
    char_start INTEGER DEFAULT 0,
    char_end INTEGER DEFAULT 0,
    quote_text TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS language_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    version_num INTEGER NOT NULL,
    language TEXT NOT NULL,
    analyzer_name TEXT NOT NULL,
    analysis_json TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS embedding_registry (
    workspace_id TEXT PRIMARY KEY,
    model_name TEXT NOT NULL,
    dimension INTEGER NOT NULL,
    index_path TEXT NOT NULL,
    total_vectors INTEGER DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS query_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id TEXT NOT NULL,
    question TEXT NOT NULL,
    language TEXT NOT NULL,
    mode TEXT NOT NULL,
    answer TEXT NOT NULL,
    status TEXT NOT NULL,
    cloud_used INTEGER DEFAULT 0,
    latency_ms REAL DEFAULT 0.0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analysis_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    language TEXT NOT NULL,
    analyzer_name TEXT NOT NULL,
    facts_extracted INTEGER DEFAULT 0,
    duration_ms REAL DEFAULT 0.0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS model_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    model_name TEXT NOT NULL,
    operation TEXT NOT NULL,
    status TEXT NOT NULL,
    latency_ms REAL DEFAULT 0.0,
    prompt_chars INTEGER DEFAULT 0,
    response_chars INTEGER DEFAULT 0,
    error_message TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_facts_ws_status ON facts (workspace_id, status);
CREATE INDEX IF NOT EXISTS idx_facts_doc ON facts (workspace_id, document_id);
CREATE INDEX IF NOT EXISTS idx_facts_lang ON facts (workspace_id, language, fact_type);
CREATE INDEX IF NOT EXISTS idx_doc_versions_ws_doc ON document_versions (workspace_id, document_id, version_num DESC);
CREATE INDEX IF NOT EXISTS idx_doc_chunks_ws_doc ON document_chunks (workspace_id, document_id);
CREATE INDEX IF NOT EXISTS idx_entities_ws_doc ON entities (workspace_id, document_id);
CREATE INDEX IF NOT EXISTS idx_fact_sources_ws_doc ON fact_sources (workspace_id, document_id);
CREATE INDEX IF NOT EXISTS idx_query_history_ws ON query_history (workspace_id, id DESC);
"""
