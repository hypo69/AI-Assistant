# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant - Package Init
# =============================================================================
# Description:
#   Пакет AI Assistant: модуль умной истории версий на основе Git, WikiLLM и RAG.
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant import SmartHistoryOrchestrator, init_router
#
# File: __init__.py
# Project: ai-windows-admin
# Package: apps.ai_assistant
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 09:48:00
# =============================================================================

from __future__ import annotations
"""Пакет модуля AI Assistant с координатором умной истории версий."""

from apps.ai_assistant.git_adapter import GitAdapter
from apps.ai_assistant.models import (
    DiffHunk,
    FileChange,
    FileRevision,
    GitCommitInfo,
    HistoryDocumentChunk,
    IndexingStatus,
    KnowledgeLink,
    QueryRequest,
    QueryResponse,
)
from apps.ai_assistant.core.ai_diff_summarizer import AIDiffSummarizer
from apps.ai_assistant.core.git_history_engine import GitHistoryEngine
from apps.ai_assistant.core.query_orchestrator import QueryOrchestrator
from apps.ai_assistant.core.rag_faiss_engine import RAGFaissEngine
from apps.ai_assistant.core.temporal_code_graph import TemporalCodeGraph
from apps.ai_assistant.core.wikillm_version_linker import WikiLLMVersionLinker
from apps.ai_assistant.main import app
from apps.ai_assistant.orchestrator import SmartHistoryOrchestrator
from apps.ai_assistant.rag_retriever import SmartHistoryRAGRetriever
from apps.ai_assistant.router import init_router, router
from apps.ai_assistant.wiki_adapter import WikiAdapter

__all__ = [
    "GitAdapter",
    "WikiAdapter",
    "SmartHistoryRAGRetriever",
    "SmartHistoryOrchestrator",
    "GitHistoryEngine",
    "TemporalCodeGraph",
    "RAGFaissEngine",
    "WikiLLMVersionLinker",
    "AIDiffSummarizer",
    "QueryOrchestrator",
    "app",
    "GitCommitInfo",
    "FileChange",
    "DiffHunk",
    "FileRevision",
    "KnowledgeLink",
    "HistoryDocumentChunk",
    "QueryRequest",
    "QueryResponse",
    "IndexingStatus",
    "router",
    "init_router",
]
