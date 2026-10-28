# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Core - Workspace Manager
# =============================================================================
# Description:
#   Менеджер изолированных рабочих областей (Workspaces).
#   Каждая рабочая область — подпапка корневого каталога data/ с собственным Git (.git)
#   и настройками в .workspace/config.json (реестр WorkspaceRegistry, без БД);
#   при импорте/изменении документов фиксирует коммит, извлекает факты через
#   NLP-анализаторы в SQLite (KnowledgeStore), обновляет векторный индекс FAISS
#   с очисткой устаревших чанков и инвалидирует старые связи в графе WikiLLM.
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.core.workspace_manager import WorkspaceManager
#
#     wm = WorkspaceManager()
#     wm.seed_demo_workspace()
#
# File: workspace_manager.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 20:38:00
# =============================================================================

from __future__ import annotations
"""Управление рабочими областями, изолированными Git-репозиториями и конвейером индексации."""

import json
import os
from pathlib import Path
import re
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple

from logger import logger
from src.ai.rag.text_rag import TextRAG
from src.utils.convertors.excel import excel2text
from src.utils.pdf import extract_pdf_text
from apps.ai_assistant.core.content_extractor import ContentExtractor
from apps.ai_assistant.core.git_history_engine import GitHistoryEngine
from apps.ai_assistant.core.knowledge_store import KnowledgeStore
from apps.ai_assistant.core.nlp_analyzers import AnalyzerRegistry
from apps.ai_assistant.core.obsidian_vault import ObsidianVaultBuilder, strip_obsidian_enrichment
from apps.ai_assistant.core.temporal_code_graph import TemporalCodeGraph
from apps.ai_assistant.core.wikillm_version_linker import WikiLLMVersionLinker
from apps.ai_assistant.core.workspace_registry import (
    WORKSPACE_META_DIR,
    WorkspaceRegistry,
    format_host_qualified_path,
    generate_workspace_readme,
    get_current_host_name,
    normalize_workspace_language,
    parse_host_qualified_path,
    parse_workspace_readme,
    resolve_workspaces_dir,
)

SUPPORTED_EXTENSIONS = {
    ".txt", ".md", ".json", ".csv", ".tsv", ".log", ".py", ".yaml", ".yml",
    ".pdf", ".xlsx", ".xls", ".docx", ".wav", ".mp3", ".ogg", ".m4a", ".flac",
}


class WorkspaceManager:
    """Управляет жизненным циклом рабочих областей, их Git-репозиториями и индексацией знаний."""

    def __init__(
        self,
        base_dir: Path | str = "data/ai_assistant",
        knowledge_store: Optional[KnowledgeStore] = None,
        analyzer_registry: Optional[AnalyzerRegistry] = None,
        temporal_graph: Optional[TemporalCodeGraph] = None,
        content_extractor: Optional[ContentExtractor] = None,
        workspaces_dir: Optional[Path | str] = None,
    ) -> None:
        """Инициализирует менеджер рабочих областей с явным внедрением зависимостей (DI)."""
        p = Path(base_dir)
        # Если передан дефолтный относительный путь, проверяем единое хранилище в корне репозитория AI-TC
        if str(base_dir) == "data/ai_assistant" and not p.is_absolute():
            repo_root_data = Path(__file__).resolve().parent.parent.parent.parent / "data" / "ai_assistant"
            if repo_root_data.exists() and (repo_root_data / "knowledge_store.db").exists():
                p = repo_root_data
        self.base_dir = p.resolve()

        # Каталог рабочих пространств: явный параметр или config.json приложения
        self.workspaces_dir = Path(workspaces_dir).resolve() if workspaces_dir else resolve_workspaces_dir()
        self.registry = WorkspaceRegistry(self.workspaces_dir)

        self.faiss_dir = self.base_dir / "faiss_indices"
        # Директории индексов и БД создаются изолированно внутри каждого рабочего пространства (.workspace/)
        fallback_store = self.base_dir / "knowledge_store.db"
        self.store = knowledge_store or KnowledgeStore(
            db_path=fallback_store,
            workspaces_dir=self.workspaces_dir,
        )
        self.analyzers = analyzer_registry or AnalyzerRegistry()
        fallback_graph = self.base_dir / "temporal_graph.db"
        self.graph = temporal_graph or TemporalCodeGraph(
            db_path=fallback_graph,
            workspaces_dir=self.workspaces_dir,
        )
        self.wiki_linker = WikiLLMVersionLinker(
            db_path=":memory:",
            temporal_graph=self.graph,
        )
        self.extractor = content_extractor or ContentExtractor()
        self.obsidian = ObsidianVaultBuilder(self)
        self._rag_instances: Dict[str, TextRAG] = {}
        self._stores: Dict[str, KnowledgeStore] = {}
        self._graphs: Dict[str, TemporalCodeGraph] = {}

        # Автоматическая миграция существующих глобальных БД в локальные директории пространств
        try:
            self.migrate_legacy_databases_to_workspaces()
        except Exception as exc:
            logger.debug(f"[WorkspaceManager] Начальная проверка миграции БД: {exc}")

    def get_workspace_db_path(self, workspace_id: str) -> Path:
        """Возвращает путь к SQLite базе знаний внутри рабочего пространства."""
        ws_path = self.registry.workspace_path(workspace_id)
        db_dir = ws_path / WORKSPACE_META_DIR
        db_dir.mkdir(parents=True, exist_ok=True)
        return db_dir / "knowledge_store.db"

    def get_workspace_graph_path(self, workspace_id: str) -> Path:
        """Возвращает путь к SQLite темпорального графа внутри рабочего пространства."""
        ws_path = self.registry.workspace_path(workspace_id)
        db_dir = ws_path / WORKSPACE_META_DIR
        db_dir.mkdir(parents=True, exist_ok=True)
        return db_dir / "temporal_graph.db"

    def get_workspace_store(self, workspace_id: str) -> KnowledgeStore:
        """Возвращает изолированный экземпляр KnowledgeStore для конкретного рабочего пространства."""
        if workspace_id not in self._stores:
            db_path = self.get_workspace_db_path(workspace_id)
            self._stores[workspace_id] = KnowledgeStore(db_path=db_path)
        return self._stores[workspace_id]

    def get_workspace_graph(self, workspace_id: str) -> TemporalCodeGraph:
        """Возвращает изолированный экземпляр TemporalCodeGraph для конкретного рабочего пространства."""
        if workspace_id not in self._graphs:
            graph_path = self.get_workspace_graph_path(workspace_id)
            self._graphs[workspace_id] = TemporalCodeGraph(db_path=graph_path)
        return self._graphs[workspace_id]

    def migrate_legacy_databases_to_workspaces(self) -> None:
        """Переносит записи существующих рабочих пространств из глобальных БД в локальные .workspace/."""
        import sqlite3
        legacy_store_path = self.base_dir / "knowledge_store.db"
        if not legacy_store_path.exists():
            alt = Path("data/ai_assistant/knowledge_store.db").resolve()
            if alt.exists():
                legacy_store_path = alt

        legacy_graph_path = self.base_dir / "temporal_graph.db"
        if not legacy_graph_path.exists():
            alt = Path("data/ai_assistant/temporal_graph.db").resolve()
            if alt.exists():
                legacy_graph_path = alt

        for ws in self.registry.list_workspaces():
            ws_id = ws["workspace_id"]
            ws_meta = Path(ws["path"]) / WORKSPACE_META_DIR
            ws_meta.mkdir(parents=True, exist_ok=True)

            ws_db = ws_meta / "knowledge_store.db"
            if not ws_db.exists() and legacy_store_path.exists():
                try:
                    target_store = KnowledgeStore(db_path=ws_db)
                    src_conn = sqlite3.connect(str(legacy_store_path))
                    src_conn.row_factory = sqlite3.Row
                    dst_conn = sqlite3.connect(str(ws_db))
                    tables = [
                        "documents", "document_versions", "document_chunks", "entities",
                        "facts", "fact_relations", "fact_sources", "language_analysis",
                        "embedding_registry", "query_history", "analysis_runs", "model_usage", "app_settings"
                    ]
                    with dst_conn:
                        for tbl in tables:
                            try:
                                rows = src_conn.execute(f"SELECT * FROM {tbl} WHERE workspace_id = ?", (ws_id,)).fetchall()
                                if rows:
                                    cols = [c[0] for c in src_conn.execute(f"SELECT * FROM {tbl} LIMIT 0").description]
                                    placeholders = ", ".join(["?"] * len(cols))
                                    col_names = ", ".join(cols)
                                    for r in rows:
                                        dst_conn.execute(
                                            f"INSERT OR IGNORE INTO {tbl} ({col_names}) VALUES ({placeholders})",
                                            tuple(r)
                                        )
                            except Exception:
                                pass
                    src_conn.close()
                    dst_conn.close()
                    logger.info(f"[WorkspaceManager] Перенесена SQLite база знаний для '{ws_id}' в {ws_db}")
                except Exception as exc:
                    logger.warning(f"[WorkspaceManager] Ошибка переноса SQLite для '{ws_id}': {exc}")

            ws_graph = ws_meta / "temporal_graph.db"
            if not ws_graph.exists() and legacy_graph_path.exists():
                try:
                    target_graph = TemporalCodeGraph(db_path=ws_graph)
                    src_conn = sqlite3.connect(str(legacy_graph_path))
                    dst_conn = sqlite3.connect(str(ws_graph))
                    with dst_conn:
                        rows = src_conn.execute("SELECT * FROM temporal_evidence_links").fetchall()
                        if rows:
                            cols = [c[0] for c in src_conn.execute("SELECT * FROM temporal_evidence_links LIMIT 0").description]
                            placeholders = ", ".join(["?"] * len(cols))
                            col_names = ", ".join(cols)
                            for r in rows:
                                dst_conn.execute(
                                    f"INSERT OR IGNORE INTO temporal_evidence_links ({col_names}) VALUES ({placeholders})",
                                    tuple(r)
                                )
                    src_conn.close()
                    dst_conn.close()
                    logger.info(f"[WorkspaceManager] Перенесён SQLite граф для '{ws_id}' в {ws_graph}")
                except Exception as exc:
                    logger.warning(f"[WorkspaceManager] Ошибка переноса графа для '{ws_id}': {exc}")

    def get_workspace_faiss_dir(self, workspace_id: str) -> Path:
        """Возвращает путь к каталогу хранения векторного индекса FAISS внутри рабочего пространства."""
        ws_path = self.registry.workspace_path(workspace_id)
        faiss_dir = ws_path / WORKSPACE_META_DIR / "faiss_indices"
        faiss_dir.mkdir(parents=True, exist_ok=True)
        return faiss_dir

    def get_faiss_rag(self, workspace_id: str) -> TextRAG:
        """Возвращает или создаёт экземпляр FAISS TextRAG для указанной рабочей области внутри её директории."""
        if workspace_id not in self._rag_instances:
            ws_faiss_dir = self.get_workspace_faiss_dir(workspace_id)
            idx_path = ws_faiss_dir / f"ws_{workspace_id}"

            # Автоматическая миграция из централизованного каталога при наличии
            if not idx_path.with_suffix(".faiss").exists() and not idx_path.with_suffix(".json").exists():
                legacy_dirs = [
                    self.faiss_dir,
                    self.base_dir / "faiss_indices",
                    Path("apps/ai_assistant/data/ai_assistant/faiss_indices").resolve(),
                    Path("data/ai_assistant/faiss_indices").resolve(),
                ]
                for l_dir in legacy_dirs:
                    if not l_dir.exists():
                        continue
                    l_faiss = l_dir / f"ws_{workspace_id}.faiss"
                    l_json = l_dir / f"ws_{workspace_id}.json"
                    if l_faiss.exists() or l_json.exists():
                        try:
                            import shutil
                            if l_faiss.exists():
                                shutil.copy2(l_faiss, idx_path.with_suffix(".faiss"))
                            if l_json.exists():
                                shutil.copy2(l_json, idx_path.with_suffix(".json"))
                            logger.info(
                                f"[WorkspaceManager] Перенесён FAISS индекс '{workspace_id}' из {l_dir} в {ws_faiss_dir}"
                            )
                            break
                        except Exception as exc:
                            logger.warning(
                                f"[WorkspaceManager] Ошибка переноса FAISS индекса для '{workspace_id}' из {l_dir}: {exc}"
                            )

            self._rag_instances[workspace_id] = TextRAG(db_path=idx_path, dimension=256)
        return self._rag_instances[workspace_id]

    def _run_git(self, repo_path: Path, args: List[str]) -> str:
        """Выполняет команду git в каталоге рабочей области без вызова интерактивного пейджера."""
        try:
            env = os.environ.copy()
            env["GIT_PAGER"] = "cat"
            env["GIT_TERMINAL_PROMPT"] = "0"
            res = subprocess.run(
                ["git", "--no-pager"] + args,
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=15,
                env=env,
            )
            return res.stdout.strip()
        except Exception as exc:
            logger.warning(f"[WorkspaceManager] Ошибка вызова git {args} в {repo_path}: {exc}")
            return ""

    def get_active_workspace_id_from_config(self) -> Optional[str]:
        """Читает последнее открытое рабочее пространство из config.json.

        Returns:
            Optional[str]: ID рабочего пространства, если оно задано и директория существует.
        """
        cfg_path = Path(__file__).resolve().parent.parent / "config.json"
        if cfg_path.exists():
            try:
                data = json.loads(cfg_path.read_text(encoding="utf-8"))
                active_ws = data.get("active_workspace") or data.get("last_active_workspace")
                if active_ws:
                    active_ws = str(active_ws).strip()
                    import unicodedata
                    from urllib.parse import unquote
                    clean_id = unicodedata.normalize("NFC", unquote(active_ws))
                    if (self.workspaces_dir / clean_id).is_dir():
                        return clean_id
                    for p in self.workspaces_dir.iterdir():
                        if p.is_dir() and unicodedata.normalize("NFC", p.name).lower() == clean_id.lower():
                            return p.name
            except Exception as exc:
                logger.warning(f"[WorkspaceManager] Ошибка чтения active_workspace из config.json: {exc}")
        return None

    def set_active_workspace_in_config(self, workspace_id: str) -> None:
        """Сохраняет последнее открытое рабочее пространство в apps/ai_assistant/config.json.

        Args:
            workspace_id: Идентификатор активного рабочего пространства.
        """
        clean_id = (workspace_id or "").strip()
        cfg_path = Path(__file__).resolve().parent.parent / "config.json"
        if cfg_path.exists():
            try:
                data = json.loads(cfg_path.read_text(encoding="utf-8"))
                data["active_workspace"] = clean_id
                data["last_active_workspace"] = clean_id
                cfg_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                logger.info(f"[WorkspaceManager] В config.json сохранён active_workspace: '{clean_id}'")
            except Exception as exc:
                logger.warning(f"[WorkspaceManager] Ошибка сохранения active_workspace в config.json: {exc}")

    def get_active_workspace_id(self) -> Optional[str]:
        """Возвращает последнее открытое рабочее пространство из конфига или БД."""
        cfg_active = self.get_active_workspace_id_from_config()
        if cfg_active:
            return cfg_active
        try:
            store_active = self.store.get_active_workspace_id()
            if store_active:
                import unicodedata
                clean_store = unicodedata.normalize("NFC", str(store_active).strip())
                if (self.workspaces_dir / clean_store).is_dir():
                    return clean_store
                for p in self.workspaces_dir.iterdir():
                    if p.is_dir() and unicodedata.normalize("NFC", p.name).lower() == clean_store.lower():
                        return p.name
        except Exception:
            pass
        return None

    def set_active_workspace(self, workspace_id: str) -> bool:
        """Фиксирует выбранное рабочее пространство как активное в конфиге, БД и electron_state.json."""
        self.set_active_workspace_in_config(workspace_id)
        try:
            from header import __root__
            el_state_path = __root__ / "data" / "electron_state.json"
            if el_state_path.parent.exists():
                el_state = {"active_workspace_id": workspace_id, "updated_at": _utc_now_iso()}
                el_state_path.write_text(json.dumps(el_state, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass
        try:
            return self.store.set_active_workspace(workspace_id)
        except Exception as exc:
            logger.warning(f"[WorkspaceManager] Ошибка сохранения активного пространства в БД: {exc}")
            return True

    def _ensure_git_repo(
        self,
        ws_path: Path,
        name: str = "",
        description: str = "",
        language: str = "ru",
    ) -> str:
        """Инициализирует индивидуальный Git-репозиторий в папке рабочей области, создаёт каталог assets/ и README.md."""
        ws_path.mkdir(parents=True, exist_ok=True)
        # Гарантируем наличие каталога assets для исходников, загруженных в пространство
        assets_dir = ws_path / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)

        git_dir = ws_path / ".git"
        is_new_repo = not git_dir.exists()
        if is_new_repo:
            self._run_git(ws_path, ["init"])
            self._run_git(ws_path, ["config", "user.name", "AI-Assistant"])
            self._run_git(ws_path, ["config", "user.email", "ai-assistant@local"])
            self._run_git(ws_path, ["config", "core.quotepath", "false"])
            self._run_git(ws_path, ["config", "diff.renames", "true"])
            self._run_git(ws_path, ["config", "status.renames", "true"])

        # Гарантируем наличие файла README.md с первой строкой lang=<language> и главами
        self.registry.ensure_workspace_readme(
            ws_path,
            name=name,
            description=description,
            language=language,
        )

        # Удаляем assets из индекса Git, если каталог случайно был зафиксирован ранее
        if not is_new_repo:
            if self._run_git(ws_path, ["ls-files", "assets"]):
                self._run_git(ws_path, ["rm", "-r", "--cached", "--ignore-unmatch", "assets"])
                self._run_git(ws_path, ["commit", "-m", "Git: исключение директории assets из репозитория"])

        # Создаём .gitignore по умолчанию (каталог assets/ и бинарные медиафайлы исключены из Git)
        gitignore_path = ws_path / ".gitignore"
        default_gitignore = (
            "# AI Windows Admin - Workspace Git Ignore\n"
            "# Временные файлы и системные кэши\n"
            "~*\n"
            "*.tmp\n"
            "__pycache__/\n"
            ".DS_Store\n"
            "Thumbs.db\n\n"
            "# Каталог исходников исключен из Git\n"
            "assets/\n\n"
            "# PDF и медиафайлы по умолчанию (хранятся только конвертированные .md)\n"
            "*.pdf\n"
            "*.png\n"
            "*.jpg\n"
            "*.jpeg\n"
            "*.bmp\n"
            "*.webp\n"
            "*.tiff\n"
            "*.gif\n"
            "*.wav\n"
            "*.mp3\n"
            "*.ogg\n"
            "*.m4a\n"
            "*.flac\n"
            "*.aac\n"
            "*.mp4\n"
            "*.avi\n"
            "*.mkv\n"
            "*.mov\n\n"
            "# Исключения: сохранять конвертированные companion .md и текстовые файлы\n"
            "!*.md\n"
            "!*.txt\n"
        )
        if not gitignore_path.exists():
            try:
                gitignore_path.write_text(default_gitignore, encoding="utf-8")
                self._run_git(ws_path, ["add", ".gitignore", "README.md"])
                self._run_git(ws_path, ["commit", "-m", "Git: начальная конфигурация .gitignore и README.md"])
            except Exception as ign_err:
                logger.warning(f"[WorkspaceManager] Не удалось записать .gitignore в {ws_path}: {ign_err}")
        else:
            try:
                current_gi = gitignore_path.read_text(encoding="utf-8")
                if "assets/" not in current_gi:
                    new_gi = current_gi.rstrip("\n") + "\n\n# Каталог исходников исключен из Git\nassets/\n"
                    gitignore_path.write_text(new_gi, encoding="utf-8")
                    self._run_git(ws_path, ["add", ".gitignore"])
                    self._run_git(ws_path, ["commit", "-m", "Git: исключение каталога assets из репозитория"])
            except Exception as ign_upd_err:
                logger.warning(f"[WorkspaceManager] Не удалось обновить .gitignore в {ws_path}: {ign_upd_err}")

            # Проверяем, зафиксирован ли README.md в репозитории
            untracked = self._run_git(ws_path, ["status", "--porcelain", "README.md"])
            if untracked:
                self._run_git(ws_path, ["add", "README.md"])
                self._run_git(ws_path, ["commit", "-m", "Git: добавление README.md рабочего пространства"])

        head = self._run_git(ws_path, ["rev-parse", "HEAD"])
        return head if head and not head.startswith("fatal") else ""

    def create_or_select_workspace(
        self,
        workspace_id: str,
        name: str,
        description: str = "",
        language: str = "ru",
    ) -> Dict[str, Any]:
        """Создаёт или выбирает рабочую область data/workspaces/<id>, инициализирует Git, assets/, README.md и config.json."""
        # Очистка идентификатора: поддержка Unicode-букв и цифр, схлопывание разделителей
        clean_id = re.sub(r"[^\w\-]+", "_", workspace_id.strip()).strip("_") or "default"
        ws_path = self.registry.workspace_path(clean_id)
        ws_path.mkdir(parents=True, exist_ok=True)
        (ws_path / "assets").mkdir(parents=True, exist_ok=True)
        self._ensure_git_repo(ws_path, name=name or clean_id, description=description, language=language)
        saved = self.registry.save_workspace(clean_id, name=name or clean_id, description=description, language=language)
        self.set_active_workspace(clean_id)
        return saved

    def get_workspace(self, workspace_id: str) -> Optional[Dict[str, Any]]:
        """Возвращает описание рабочей области из файлового реестра или None."""
        return self.registry.get_workspace(workspace_id)

    def delete_workspace(self, workspace_id: str) -> Dict[str, Any]:
        """Удаляет рабочую область, сбрасывает связанные кэши и переключает активную область.

        Args:
            workspace_id: Идентификатор удаляемого рабочего пространства.

        Returns:
            Dict[str, Any]: Результат с удаленным ID и новым активным ID пространства.
        """
        clean_id = (workspace_id or "").strip()
        if not clean_id:
            raise ValueError("Идентификатор рабочего пространства не может быть пустым")

        # Очищаем кэшированные инстансы из памяти
        self._stores.pop(clean_id, None)
        self._graphs.pop(clean_id, None)
        self._rag_instances.pop(clean_id, None)

        # Удаляем директорию через файловый реестр
        self.registry.delete_workspace(clean_id)

        # Проверяем и обновляем активное пространство
        active_id = self.store.get_active_workspace_id() or self.get_active_workspace_id()
        next_active_id = active_id

        if active_id == clean_id:
            remaining = self.list_workspaces()
            if remaining:
                next_active_id = remaining[0]["workspace_id"]
                self.store.set_active_workspace(next_active_id)
                self.set_active_workspace_in_config(next_active_id)
            else:
                next_active_id = None
                self.set_active_workspace_in_config("")
                try:
                    self.store.set_active_workspace("")
                except Exception:
                    pass

        logger.info(f"[WorkspaceManager] Рабочее пространство '{clean_id}' удалено, активное теперь '{next_active_id}'")
        return {
            "status": "ok",
            "deleted_workspace_id": clean_id,
            "active_workspace_id": next_active_id or "",
        }

    def list_workspaces(self) -> List[Dict[str, Any]]:
        """Возвращает список рабочих пространств из data/workspaces с отметкой активного."""
        active_id = self.get_active_workspace_id()
        try:
            raw_list = self.registry.list_workspaces()
        except Exception as exc:
            logger.error(f"[WorkspaceManager] Ошибка сканирования реестра рабочих пространств: {exc}")
            return []

        workspaces: List[Dict[str, Any]] = []
        for ws in raw_list:
            ws_id = ws.get("workspace_id", "")
            workspaces.append({
                **ws,
                "is_active": (ws_id == active_id) if active_id else False,
            })
        return workspaces

    def _get_or_create_workspace(self, workspace_id: str) -> Tuple[Dict[str, Any], Path]:
        """Возвращает описание и путь рабочей области, создавая её при отсутствии."""
        ws = self.registry.get_workspace(workspace_id) or self.create_or_select_workspace(workspace_id, name=workspace_id)
        return ws, Path(ws["path"])

    def _update_faiss_and_graph_for_doc(
        self,
        workspace_id: str,
        doc_id: str,
        commit_hash: str,
        commit_message: Optional[str],
        analysis: Dict[str, Any],
        original_path: Optional[str] = None,
        host_name: Optional[str] = None,
        qualified_path: Optional[str] = None,
    ) -> None:
        """Обновляет векторный индекс FAISS (с очисткой прежних чанков документа) и граф связей WikiLLM."""
        rag = self.get_faiss_rag(workspace_id)
        doc_prefix = f"{workspace_id}:{doc_id}:"
        # Удаляем устаревшие предложения прежней версии документа из индекса FAISS
        rag.metadatas = [m for m in rag.metadatas if not str(m.get("id", "")).startswith(doc_prefix)]

        rag_docs: List[Dict[str, Any]] = []
        for sent in analysis.get("sentences", []):
            s_idx = sent.get("sentence_index", 0)
            s_text = sent.get("text", "")
            if s_text:
                meta: Dict[str, Any] = {
                    "workspace_id": workspace_id,
                    "document_id": doc_id,
                    "sentence_index": s_idx,
                    "commit_hash": commit_hash,
                    "language": analysis.get("language", "ru"),
                }
                if original_path:
                    meta["original_path"] = original_path
                if host_name:
                    meta["host_name"] = host_name
                if qualified_path:
                    meta["qualified_path"] = qualified_path
                rag_docs.append({
                    "id": f"{doc_prefix}s{s_idx}",
                    "text": s_text,
                    "meta": meta,
                })

        if rag_docs:
            rag.add_documents(rag_docs)
        else:
            rag._rebuild_index()
            rag._save()

        self.store.update_embedding_registry(
            workspace_id=workspace_id,
            model_name="TextRAG-FAISS-256",
            dimension=rag.dimension,
            index_path=str(rag.index_file),
            total_vectors=rag.count(),
        )

        if commit_hash:
            # Мягко инвалидируем прежние связи документа в темпоральном графе перед записью новых
            self.graph.supersede_links_by_source(source_id=doc_id, invalidating_commit=commit_hash)
            self.wiki_linker.auto_link_commit(
                commit_hash=commit_hash,
                files=[doc_id],
                message=commit_message or f"Индексация {doc_id}",
            )
            for ent in analysis.get("entities", []):
                norm_ent = ent.get("normalized", "")
                if norm_ent:
                    self.graph.add_link(
                        source_id=doc_id,
                        target_id=norm_ent,
                        relation_type="documents",
                        valid_from=commit_hash,
                        confidence=0.95,
                        provenance="nlp_analyzer",
                    )

    def _persist_and_index_doc(
        self,
        workspace_id: str,
        doc_id: str,
        file_path_str: str,
        content: str,
        commit_hash: str,
        commit_message: Optional[str],
        language: Optional[str],
        force_reanalyze: bool,
        t0: float,
        original_path: Optional[str] = None,
        host_name: Optional[str] = None,
        qualified_path: Optional[str] = None,
        relocated_from: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Единый метод сохранения проанализированного документа в SQLite, FAISS, графе и компактном Obsidian Vault."""
        from apps.ai_assistant.core.workspace_relocator import WorkspaceRelocator

        clean_content = strip_obsidian_enrichment(content)
        analysis = self.analyzers.analyze_text(clean_content, document_id=doc_id, language=language)
        duration_ms = (time.perf_counter() - t0) * 1000.0
        resolved_host, _, resolved_qual = parse_host_qualified_path(file_path_str, default_host=host_name)
        final_qual = qualified_path or resolved_qual
        store_res = self.store.store_document_and_facts(
            workspace_id=workspace_id,
            document_id=doc_id,
            file_path=file_path_str,
            raw_content=clean_content,
            commit_hash=commit_hash,
            analysis_result=analysis,
            duration_ms=duration_ms,
            force_reanalyze=force_reanalyze,
            host_name=resolved_host,
            qualified_path=final_qual,
            relocated_from=relocated_from,
        )
        prev_doc_id = store_res.get("previous_document_id") or relocated_from
        if store_res.get("status") == "relocated_unchanged" and prev_doc_id:
            WorkspaceRelocator.migrate_subsystems_on_move(
                wm=self,
                workspace_id=workspace_id,
                old_doc_id=str(prev_doc_id),
                new_doc_id=doc_id,
                commit_hash=commit_hash,
                original_path=original_path,
                host_name=resolved_host,
                qualified_path=final_qual,
            )
        else:
            if prev_doc_id and prev_doc_id != doc_id:
                WorkspaceRelocator.migrate_subsystems_on_move(
                    wm=self,
                    workspace_id=workspace_id,
                    old_doc_id=str(prev_doc_id),
                    new_doc_id=doc_id,
                    commit_hash=commit_hash,
                    original_path=original_path,
                    host_name=resolved_host,
                    qualified_path=final_qual,
                )
            self._update_faiss_and_graph_for_doc(
                workspace_id=workspace_id,
                doc_id=doc_id,
                commit_hash=commit_hash,
                commit_message=commit_message,
                analysis=analysis,
                original_path=original_path,
                host_name=resolved_host,
                qualified_path=final_qual,
            )
        # Мгновенная («на лету») синхронизация компактной заметки Obsidian и _Knowledge_Base.md
        obsidian_md_path: Optional[Path] = None
        try:
            obsidian_md_path = self.obsidian.sync_document_on_the_fly(
                workspace_id=workspace_id,
                doc_id=doc_id,
                clean_content=clean_content,
                commit_hash=commit_hash,
                analysis=analysis,
                version_num=int(store_res.get("version") or 1),
                original_path=final_qual if original_path else file_path_str,
            )
            ws_info = self.registry.get_workspace(workspace_id)
            if ws_info and obsidian_md_path:
                ws_p = Path(ws_info["path"])
                self._run_git(ws_p, ["add", "."])
                if self._run_git(ws_p, ["status", "--porcelain"]):
                    self._run_git(ws_p, ["commit", "-m", f"Obsidian auto-sync: {doc_id}"])
        except Exception as obs_exc:
            logger.warning(f"[WorkspaceManager] Предупреждение синхронизации Obsidian для {doc_id}: {obs_exc}")

        res = {
            **store_res,
            "workspace_id": workspace_id,
            "document_id": doc_id,
            "analysis": analysis,
            "duration_ms": round(duration_ms, 2),
        }
        if obsidian_md_path:
            res["obsidian_note_path"] = str(obsidian_md_path)
        if original_path:
            res["original_path"] = original_path
        return res

    def import_document(
        self,
        workspace_id: str,
        document_id: str,
        content: str,
        commit_message: Optional[str] = None,
        language: Optional[str] = None,
        force_reanalyze: bool = False,
    ) -> Dict[str, Any]:
        """Импортирует или обновляет документ в рабочей области, коммитит в Git и индексирует знания."""
        t0 = time.perf_counter()
        _, ws_path = self._get_or_create_workspace(workspace_id)
        self._ensure_git_repo(ws_path)

        clean_rel = str(document_id).strip().replace("\\", "/").lstrip("/")
        rel_parts = [p for p in clean_rel.split("/") if p and p not in (".", "..")]
        safe_doc_id = "/".join(rel_parts) if rel_parts else Path(document_id).name
        file_full_path = ws_path / safe_doc_id
        file_full_path.parent.mkdir(parents=True, exist_ok=True)
        file_full_path.write_text(content, encoding="utf-8")

        is_in_assets = safe_doc_id.startswith("assets/") or (len(rel_parts) > 0 and rel_parts[0] == "assets")
        if not is_in_assets:
            self._run_git(ws_path, ["add", safe_doc_id])
            if self._run_git(ws_path, ["status", "--porcelain", safe_doc_id]):
                self._run_git(ws_path, ["commit", "-m", commit_message or f"Обновление документа {safe_doc_id}"])

        commit_hash = self._run_git(ws_path, ["rev-parse", "HEAD"])
        if commit_hash.startswith("fatal"):
            commit_hash = "HEAD"

        return self._persist_and_index_doc(
            workspace_id=workspace_id,
            doc_id=safe_doc_id,
            file_path_str=str(file_full_path),
            content=content,
            commit_hash=commit_hash,
            commit_message=commit_message,
            language=language,
            force_reanalyze=force_reanalyze,
            t0=t0,
        )

    def _extract_file_sync(self, fpath: Path) -> str:
        """Синхронно извлекает текст из локального файла рабочей области (включая PDF, Excel, DOCX, CSV, медиа)."""
        suffix = fpath.suffix.lower()
        if suffix == ".pdf":
            return extract_pdf_text(fpath) or f"*(Пустой PDF: {fpath.name})*"
        if suffix in (".xlsx", ".xls"):
            return excel2text(fpath)
        if suffix == ".docx":
            return self.extractor._extract_docx(fpath)
        if suffix in (".csv", ".tsv"):
            return self.extractor._extract_csv(fpath)
        if suffix in (".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tiff", ".gif"):
            try:
                from PIL import Image
                with Image.open(fpath) as img:
                    return f"# Изображение: {fpath.name}\n\n- **Формат:** {img.format}\n- **Разрешение:** {img.size[0]}x{img.size[1]} px\n- **Цветовая модель:** {img.mode}"
            except Exception:
                return f"# Изображение: {fpath.name}"
        if suffix in (".wav", ".mp3", ".ogg", ".m4a", ".flac", ".aac"):
            return f"# Аудиозапись: {fpath.name}\n\n*(Файл аудио в рабочей области Git)*"
        return self.extractor._extract_plain_text(fpath)

    def scan_and_index_workspace(self, workspace_id: str) -> Dict[str, Any]:
        """Сканирует все поддерживаемые файлы в папке рабочей области и индексирует их."""
        ws = self.registry.get_workspace(workspace_id)
        if not ws:
            raise ValueError(f"Рабочая область '{workspace_id}' не найдена")

        ws_path = Path(ws["path"])
        if not ws_path.exists():
            return {"workspace_id": workspace_id, "indexed_files": 0, "files": []}

        indexed_files: List[str] = []
        for fpath in sorted(ws_path.iterdir()):
            if (
                fpath.is_file()
                and fpath.suffix.lower() in SUPPORTED_EXTENSIONS
                and not fpath.name.startswith("~")
                and not fpath.name.startswith(".")
                and not ObsidianVaultBuilder.is_reserved_obsidian_file(fpath.name)
            ):
                # Если в папке есть и исходный файл (например, mama.txt), и сгенерированный mama.md — индексируем оригинал
                if fpath.suffix.lower() == ".md" and (ws_path / f"{fpath.stem}.txt").exists():
                    continue
                try:
                    raw_text = strip_obsidian_enrichment(self._extract_file_sync(fpath))
                    self.import_document(
                        workspace_id=workspace_id,
                        document_id=fpath.name,
                        content=raw_text,
                        commit_message=f"Авто-сканирование {fpath.name}",
                    )
                    indexed_files.append(fpath.name)
                except Exception as exc:
                    logger.warning(f"[WorkspaceManager] Ошибка импорта {fpath}: {exc}")

        return {
            "workspace_id": workspace_id,
            "indexed_files": len(indexed_files),
            "files": indexed_files,
        }

    def index_document_from_source(
        self,
        workspace_id: str,
        document_id: str,
        content: str,
        file_path: str,
        commit_message: Optional[str] = None,
        language: Optional[str] = None,
        force_reanalyze: bool = False,
        host_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Индексирует документ из связанного внешнего источника БЕЗ копирования оригинала, сохраняя полный путь с именем ПК."""
        t0 = time.perf_counter()
        _, ws_path = self._get_or_create_workspace(workspace_id)
        self._ensure_git_repo(ws_path)

        resolved_host, clean_local_path, qualified_path = parse_host_qualified_path(file_path, default_host=host_name)

        manifest_file = ws_path / ".tracked_sources.json"
        manifest_data: Dict[str, Any] = {}
        if manifest_file.exists():
            try:
                manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
            except Exception:
                manifest_data = {}

        # Если одноимённый файл уже отслеживается с ДРУГОГО компьютера на этой же флешке — разделяем по имени ПК
        existing_entry = manifest_data.get(document_id)
        if existing_entry and existing_entry.get("host_name") and existing_entry["host_name"].upper() != resolved_host.upper():
            document_id = f"{resolved_host}/{document_id}"

        # Сохраняем текстовый слепок в скрытой служебной директории .extracted_snapshots для реального git diff
        from apps.ai_assistant.core.workspace_relocator import WorkspaceRelocator

        snapshots_dir = ws_path / ".extracted_snapshots"
        snapshots_dir.mkdir(parents=True, exist_ok=True)
        safe_snap_name = "".join(c if c.isalnum() or c in ("_", "-", ".") else "_" for c in f"{resolved_host}_{document_id}") + ".snapshot"
        new_snap_rel = f".extracted_snapshots/{safe_snap_name}"
        snap_file = snapshots_dir / safe_snap_name

        # Проверяем, не был ли этот файл перенесён без изменений из другой папки/пути
        relocated_from = WorkspaceRelocator.reconcile_external_move(
            wm=self,
            ws_path=ws_path,
            manifest_data=manifest_data,
            new_doc_id=document_id,
            new_snap_rel=new_snap_rel,
            content=content,
            resolved_host=resolved_host,
        )
        content_hash = WorkspaceRelocator.compute_clean_hash(content)
        snap_file.write_text(content, encoding="utf-8")

        src_mtime = 0.0
        src_size = 0
        try:
            fp_obj = Path(clean_local_path)
            if fp_obj.exists() and fp_obj.is_file():
                st = fp_obj.stat()
                src_mtime = st.st_mtime
                src_size = st.st_size
        except Exception:
            pass

        entry_payload: Dict[str, Any] = {
            "host_name": resolved_host,
            "file_path": str(clean_local_path),
            "qualified_path": qualified_path,
            "snapshot": new_snap_rel,
            "updated_at": time.time(),
            "content_length": len(content),
            "content_hash": content_hash,
            "source_mtime": src_mtime,
            "source_size": src_size,
        }
        if relocated_from:
            entry_payload["moved_from"] = relocated_from
        manifest_data[document_id] = entry_payload
        manifest_file.write_text(json.dumps(manifest_data, indent=2, ensure_ascii=False), encoding="utf-8")

        if relocated_from:
            self._run_git(ws_path, ["add", "-A", ".tracked_sources.json", ".extracted_snapshots"])
            default_commit_msg = f"Перемещение источника без изменений ({resolved_host}): {relocated_from} -> {document_id}"
        else:
            self._run_git(ws_path, ["add", ".tracked_sources.json", new_snap_rel])
            default_commit_msg = f"Синхронизация источника ({resolved_host}): {document_id}"

        if self._run_git(ws_path, ["status", "--porcelain", ".tracked_sources.json", ".extracted_snapshots"]):
            self._run_git(ws_path, ["commit", "-m", commit_message or default_commit_msg])

        commit_hash = self._run_git(ws_path, ["rev-parse", "HEAD"])
        if commit_hash.startswith("fatal"):
            commit_hash = "HEAD"

        return self._persist_and_index_doc(
            workspace_id=workspace_id,
            doc_id=document_id,
            file_path_str=str(clean_local_path),
            content=content,
            commit_hash=commit_hash,
            commit_message=commit_message or default_commit_msg,
            language=language,
            force_reanalyze=force_reanalyze,
            t0=t0,
            original_path=qualified_path,
            host_name=resolved_host,
            qualified_path=qualified_path,
            relocated_from=relocated_from,
        )

    def link_source(
        self,
        workspace_id: str,
        target: str,
        name: Optional[str] = None,
        auto_watch: bool = True,
        host_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Связывает файл, директорию на компьютере или ссылку Google Таблицы с рабочей областью с фиксацией имени ПК."""
        target_str = target.strip()
        if not target_str:
            raise ValueError("Путь или ссылка на источник не могут быть пустыми")

        self._get_or_create_workspace(workspace_id)
        resolved_host, clean_local_path, _ = parse_host_qualified_path(target_str, default_host=host_name)

        if self.extractor.is_google_sheet_target(target_str):
            source_type = "google_sheet"
            disp_name = name or f"Google Таблица: {target_str[:40]}"
            clean_local_path = target_str
        else:
            is_cur_host = (resolved_host.upper() == get_current_host_name().upper())
            p = Path(clean_local_path)
            if is_cur_host:
                p = p.resolve()
                if not p.exists():
                    raise FileNotFoundError(f"Файл или директория не найдены на диске: {p}")
                source_type = "directory" if p.is_dir() else "file"
                clean_local_path = str(p)
            else:
                source_type = "file" if p.suffix else "directory"
            disp_name = name or p.name or clean_local_path

        return self.registry.add_source(
            workspace_id=workspace_id,
            source_type=source_type,
            source_path=clean_local_path,
            name=disp_name,
            auto_watch=auto_watch,
            host_name=resolved_host,
        )

    def list_sources(self, workspace_id: str) -> List[Dict[str, Any]]:
        """Возвращает список всех привязанных источников для рабочей области."""
        return self.registry.list_sources(workspace_id)

    def unlink_source(self, workspace_id: str, source_id: str) -> bool:
        """Удаляет привязку источника из рабочей области."""
        return self.registry.delete_source(workspace_id, source_id)

    def detect_changed_linked_sources(self, workspace_id: str) -> Dict[str, Any]:
        """Инкрементально проверяет изменения во всех привязанных файлах и папках по mtime и размеру без повторного парсинга."""
        _, ws_path = self._get_or_create_workspace(workspace_id)
        manifest_file = ws_path / ".tracked_sources.json"
        manifest: Dict[str, Any] = {}
        if manifest_file.exists():
            try:
                manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
            except Exception:
                manifest = {}

        cur_host = get_current_host_name()
        sources = self.registry.list_sources(workspace_id)
        changed_files: List[str] = []
        new_files: List[str] = []
        missing_files: List[str] = []
        unchanged_files: List[str] = []
        other_host_files: List[str] = []

        seen_doc_ids: set[str] = set()
        new_file_stats: Dict[str, Tuple[float, int, Path]] = {}

        for src in sources:
            if not src.get("auto_watch", 1):
                continue
            src_type = src["source_type"]
            src_path = src["source_path"]
            src_host = (src.get("host_name") or cur_host).upper()
            qual_path = src.get("qualified_path") or format_host_qualified_path(src_path, src_host)
            is_cur_host = (src_host == cur_host.upper())

            if src_type == "file":
                p = Path(src_path)
                if not p.exists() or not p.is_file():
                    if not is_cur_host:
                        other_host_files.append(qual_path)
                    else:
                        missing_files.append(src_path)
                    continue
                doc_id = p.name
                seen_doc_ids.add(doc_id)
                entry = manifest.get(doc_id) or manifest.get(f"{src_host}/{doc_id}")
                st = p.stat()
                if not entry:
                    new_files.append(doc_id)
                    new_file_stats[doc_id] = (st.st_mtime, st.st_size, p)
                elif abs(float(entry.get("source_mtime", 0.0)) - st.st_mtime) > 1e-3 or int(entry.get("source_size", -1)) != st.st_size:
                    changed_files.append(doc_id)
                else:
                    unchanged_files.append(doc_id)
            elif src_type == "directory":
                dir_path = Path(src_path)
                if not dir_path.exists() or not dir_path.is_dir():
                    if not is_cur_host:
                        other_host_files.append(qual_path)
                    else:
                        missing_files.append(src_path)
                    continue
                for f in sorted(dir_path.rglob("*")):
                    if f.is_file() and self.extractor.is_supported_file(f) and not f.name.startswith("~") and not f.name.startswith("."):
                        rel_name = str(f.relative_to(dir_path)).replace("\\", "/")
                        seen_doc_ids.add(rel_name)
                        entry = manifest.get(rel_name) or manifest.get(f"{src_host}/{rel_name}")
                        st = f.stat()
                        if not entry:
                            new_files.append(rel_name)
                            new_file_stats[rel_name] = (st.st_mtime, st.st_size, f)
                        elif abs(float(entry.get("source_mtime", 0.0)) - st.st_mtime) > 1e-3 or int(entry.get("source_size", -1)) != st.st_size:
                            changed_files.append(rel_name)
                        else:
                            unchanged_files.append(rel_name)

        moved_files: List[Dict[str, str]] = []
        for old_doc_id, meta in manifest.items():
            if old_doc_id in seen_doc_ids:
                continue
            entry_host = str(meta.get("host_name") or cur_host).upper()
            if entry_host != cur_host.upper():
                continue
            old_fp = Path(str(meta.get("file_path") or ""))
            if not old_fp.exists():
                matched_new: Optional[str] = None
                old_size = int(meta.get("source_size", -1))
                for cand_new_id, (n_mtime, n_size, _) in list(new_file_stats.items()):
                    if old_size >= 0 and n_size == old_size:
                        matched_new = cand_new_id
                        del new_file_stats[cand_new_id]
                        break
                if matched_new:
                    moved_files.append({"from": old_doc_id, "to": matched_new})
                elif old_doc_id not in missing_files:
                    missing_files.append(old_doc_id)

        return {
            "workspace_id": workspace_id,
            "current_host": cur_host,
            "has_changes": bool(changed_files or new_files or missing_files or moved_files),
            "changed_files": changed_files,
            "new_files": new_files,
            "moved_files": moved_files,
            "missing_files": missing_files,
            "unchanged_files": unchanged_files,
            "other_host_files": other_host_files,
        }

    async def sync_linked_sources(
        self,
        workspace_id: str,
        force_reanalyze: bool = False,
        pdf_mode: str = "local",
        ocr_mode: str = "model",
        audio_mode: str = "model",
        commit_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Синхронизирует и индексирует все связанные файлы, директории и Google Таблицы без их копирования."""
        from apps.ai_assistant.core.workspace_relocator import WorkspaceRelocator

        _, ws_path = self._get_or_create_workspace(workspace_id)
        sources = self.registry.list_sources(workspace_id)
        total_indexed = 0
        results_by_source: List[Dict[str, Any]] = []
        active_doc_ids: set[str] = set()
        relocated_files: List[Dict[str, str]] = []

        for src in sources:
            if not src.get("auto_watch", 1):
                continue

            src_id = src["source_id"]
            src_type = src["source_type"]
            src_path = src["source_path"]
            src_host = src.get("host_name") or get_current_host_name()
            qual_path = src.get("qualified_path") or format_host_qualified_path(src_path, src_host)
            is_cur_host = (src_host.upper() == get_current_host_name().upper())
            indexed_in_source = 0
            errors: List[str] = []
            other_host_skipped = False

            try:
                if src_type == "google_sheet":
                    extracted = await self.extractor.extract(
                        src_path,
                        pdf_mode=pdf_mode,
                        ocr_mode=ocr_mode,
                        audio_mode=audio_mode,
                    )
                    idx_res = self.index_document_from_source(
                        workspace_id=workspace_id,
                        document_id=extracted["document_id"],
                        content=extracted["text"],
                        file_path=src_path,
                        commit_message=commit_message or f"Индексация Google Таблицы {extracted['title']}",
                        force_reanalyze=force_reanalyze,
                        host_name=src_host,
                    )
                    active_doc_ids.add(idx_res.get("document_id", extracted["document_id"]))
                    indexed_in_source += 1
                    total_indexed += 1
                elif src_type == "file":
                    p = Path(src_path)
                    if p.exists() and p.is_file():
                        extracted = await self.extractor.extract(
                            p,
                            pdf_mode=pdf_mode,
                            ocr_mode=ocr_mode,
                            audio_mode=audio_mode,
                        )
                        idx_res = self.index_document_from_source(
                            workspace_id=workspace_id,
                            document_id=p.name,
                            content=extracted["text"],
                            file_path=str(p),
                            commit_message=commit_message or f"Индексация связанного файла {p.name}",
                            force_reanalyze=force_reanalyze,
                            host_name=src_host,
                        )
                        active_doc_ids.add(idx_res.get("document_id", p.name))
                        if idx_res.get("previous_document_id"):
                            relocated_files.append({
                                "from": str(idx_res["previous_document_id"]),
                                "to": str(idx_res["document_id"]),
                            })
                        indexed_in_source += 1
                        total_indexed += 1
                    elif not is_cur_host:
                        other_host_skipped = True
                    else:
                        errors.append(f"Файл недоступен: {qual_path}")
                elif src_type == "directory":
                    dir_path = Path(src_path)
                    if dir_path.exists() and dir_path.is_dir():
                        for f in sorted(dir_path.rglob("*")):
                            if f.is_file() and self.extractor.is_supported_file(f) and not f.name.startswith("~") and not f.name.startswith("."):
                                try:
                                    extracted = await self.extractor.extract(
                                        f,
                                        pdf_mode=pdf_mode,
                                        ocr_mode=ocr_mode,
                                        audio_mode=audio_mode,
                                    )
                                    rel_name = str(f.relative_to(dir_path)).replace("\\", "/")
                                    idx_res = self.index_document_from_source(
                                        workspace_id=workspace_id,
                                        document_id=rel_name,
                                        content=extracted["text"],
                                        file_path=str(f),
                                        commit_message=commit_message or f"Индексация связанного файла {rel_name}",
                                        force_reanalyze=force_reanalyze,
                                        host_name=src_host,
                                    )
                                    active_doc_ids.add(idx_res.get("document_id", rel_name))
                                    if idx_res.get("previous_document_id"):
                                        relocated_files.append({
                                            "from": str(idx_res["previous_document_id"]),
                                            "to": str(idx_res["document_id"]),
                                        })
                                    indexed_in_source += 1
                                    total_indexed += 1
                                except Exception as file_exc:
                                    logger.warning(f"[sync_linked_sources] Ошибка обработки файла {f}: {file_exc}")
                                    errors.append(f"{f.name}: {file_exc}")
                    elif not is_cur_host:
                        other_host_skipped = True
                    else:
                        errors.append(f"Директория недоступна: {qual_path}")

                status_val = "other_host" if other_host_skipped else ("error" if errors else "active")
                self.registry.update_source_status(
                    workspace_id=workspace_id,
                    source_id=src_id,
                    status=status_val,
                    item_count=indexed_in_source if not other_host_skipped else int(src.get("item_count", 0)),
                    error_message="; ".join(errors),
                )
                results_by_source.append({
                    "source_id": src_id,
                    "name": src["name"],
                    "source_type": src_type,
                    "host_name": src_host,
                    "qualified_path": qual_path,
                    "status": status_val,
                    "indexed_items": indexed_in_source,
                    "errors": errors,
                })
            except Exception as exc:
                logger.error(f"[sync_linked_sources] Ошибка синхронизации источника {src_path}: {exc}")
                self.registry.update_source_status(workspace_id, src_id, status="error", error_message=str(exc))
                results_by_source.append({
                    "source_id": src_id,
                    "name": src["name"],
                    "source_type": src_type,
                    "indexed_items": 0,
                    "errors": [str(exc)],
                })

        deleted_docs = WorkspaceRelocator.cleanup_deleted_external_sources(
            wm=self,
            workspace_id=workspace_id,
            ws_path=ws_path,
            active_doc_ids=active_doc_ids,
            current_host=get_current_host_name(),
        )

        return {
            "status": "ok",
            "workspace_id": workspace_id,
            "total_indexed": total_indexed,
            "relocated_files": relocated_files,
            "deleted_files": deleted_docs,
            "sources": results_by_source,
        }

    def rebuild_faiss_index(self, workspace_id: str) -> Dict[str, Any]:
        """Полностью перестраивает векторный индекс FAISS из первичных данных SQLite (ТЗ п. 8, 9.3)."""
        rag = self.get_faiss_rag(workspace_id)
        rag.clear()
        docs = self.store.list_documents(workspace_id)
        total_chunks = 0
        for d in docs:
            content = d.get("content") or ""
            doc_id = d["document_id"]
            commit_hash = d.get("commit_hash", "")
            analysis = self.analyzers.analyze_text(content, document_id=doc_id, language=d.get("language"))
            batch = [
                {
                    "id": f"{workspace_id}:{doc_id}:s{sent.get('sentence_index', 0)}",
                    "text": sent.get("text", ""),
                    "meta": {
                        "workspace_id": workspace_id,
                        "document_id": doc_id,
                        "sentence_index": sent.get("sentence_index", 0),
                        "commit_hash": commit_hash,
                        "language": d.get("language", "ru"),
                    },
                }
                for sent in analysis.get("sentences", [])
                if sent.get("text", "")
            ]
            if batch:
                total_chunks += rag.add_documents(batch)

        self.store.update_embedding_registry(
            workspace_id=workspace_id,
            model_name="TextRAG-FAISS-256",
            dimension=rag.dimension,
            index_path=str(rag.index_file),
            total_vectors=rag.count(),
        )
        return {
            "status": "rebuilt",
            "workspace_id": workspace_id,
            "total_vectors": rag.count(),
            "chunks_indexed": total_chunks,
        }

    def seed_demo_workspace(self, workspace_id: str = "default") -> Dict[str, Any]:
        """Создаёт демонстрационную рабочую область с эталонными документами из ТЗ (RU + HE)."""
        ws = self.create_or_select_workspace(
            workspace_id=workspace_id,
            name="Демо-область (RU + HE: Мама мыла раму / Ферма Давида Моше)",
            description="Эталонная рабочая область с отслеживанием Git, RAG, FAISS и WikiLLM",
        )
        demo_docs = [
            ("mama.txt", "Мама мыла раму.", "ru", "Добавлен документ mama.txt (Мама мыла раму)"),
            ("farm.txt", "לדוד משה היתה חווה", "he", "Добавлен документ farm.txt (Ферма Давида Моше)"),
            ("frame_he.txt", "אמא רחצה את המסגרת", "he", "Добавлен документ frame_he.txt (Мама мыла раму на иврите)"),
        ]
        for doc_id, text, lang, msg in demo_docs:
            self.import_document(
                workspace_id=workspace_id,
                document_id=doc_id,
                content=text,
                commit_message=msg,
                language=lang,
                force_reanalyze=True,
            )

        return {
            "workspace": self.registry.get_workspace(workspace_id) or ws,
            "imported_documents": len(demo_docs),
            "documents": self.store.list_documents(workspace_id),
            "facts": self.store.get_facts(workspace_id=workspace_id),
        }

    async def get_workspace_commits(
        self,
        workspace_id: str,
        file_path: Optional[str] = None,
        limit: int = 30,
    ) -> List[Dict[str, Any]]:
        """Возвращает историю коммитов Git конкретной рабочей области."""
        ws = self.registry.get_workspace(workspace_id)
        if not ws:
            return []
        engine = GitHistoryEngine(repo_path=ws["path"])
        commits = await engine.get_file_history(file_path=file_path, limit=limit)
        return [c.model_dump() for c in commits]

    @property
    def items_tracker(self) -> Any:
        """Возвращает экземпляр трекера добавления и Git-отслеживания файлов и папок."""
        if not hasattr(self, "_items_tracker") or self._items_tracker is None:
            from apps.ai_assistant.core.workspace_items_tracker import WorkspaceItemsTracker
            self._items_tracker = WorkspaceItemsTracker(self)
        return self._items_tracker

    @property
    def scenario_service(self) -> Any:
        """Возвращает сервис специального сценария Telegram-бота для рабочего пространства דוד משה."""
        if not hasattr(self, "_scenario_service") or self._scenario_service is None:
            from apps.ai_assistant.core.telegram_workspace_scenario import TelegramWorkspaceScenarioService
            self._scenario_service = TelegramWorkspaceScenarioService()
        return self._scenario_service

    async def add_items_to_workspace(
        self,
        workspace_id: str,
        paths: List[str],
        copy_to_workspace: bool = False,
        commit_message: Optional[str] = None,
        pdf_mode: str = "local",
        ocr_mode: str = "model",
        audio_mode: str = "model",
    ) -> Dict[str, Any]:
        """Добавляет файлы и/или папки в рабочую область и немедленно начинает отслеживание Git (по умолчанию без копирования)."""
        return await self.items_tracker.add_disk_items(
            workspace_id=workspace_id,
            paths=paths,
            copy_to_workspace=copy_to_workspace,
            commit_message=commit_message,
            pdf_mode=pdf_mode,
            ocr_mode=ocr_mode,
            audio_mode=audio_mode,
        )

    async def add_uploaded_files(
        self,
        workspace_id: str,
        files_data: List[Tuple[str, bytes]],
        commit_message: Optional[str] = None,
        pdf_mode: str = "local",
        ocr_mode: str = "model",
        audio_mode: str = "model",
    ) -> Dict[str, Any]:
        """Загружает файлы в рабочую область и немедленно фиксирует их в Git."""
        return await self.items_tracker.add_uploaded_files(
            workspace_id=workspace_id,
            files_data=files_data,
            commit_message=commit_message,
            pdf_mode=pdf_mode,
            ocr_mode=ocr_mode,
            audio_mode=audio_mode,
        )

    def get_directory_contents(self, workspace_id: str) -> Dict[str, Any]:
        """Возвращает детальное содержимое директории рабочей области, за которой следит Git."""
        return self.items_tracker.get_directory_contents(workspace_id)

    def check_workspace_folder(self, workspace_id: str) -> Dict[str, Any]:
        """Проверяет физическое наличие папки на диске и статус Git-репозитория."""
        return self.items_tracker.check_workspace_folder(workspace_id)

    def ensure_workspace_folder(self, workspace_id: str) -> Dict[str, Any]:
        """Создаёт рабочую папку на диске и инициализирует Git-репозиторий."""
        return self.items_tracker.ensure_workspace_folder(workspace_id)

    def open_workspace_file(self, workspace_id: str, rel_path: str) -> Dict[str, Any]:
        """Открывает файл рабочей области в ассоциированном приложении / редакторе по умолчанию."""
        return self.items_tracker.open_workspace_file(workspace_id, rel_path)

    def create_workspace_item(
        self,
        workspace_id: str,
        rel_path: str,
        is_dir: bool = False,
        content: str = "",
    ) -> Dict[str, Any]:
        """Создает файл или директорию в рабочей области с авто-коммитом в Git."""
        from apps.ai_assistant.core.workspace_file_ops import WorkspaceFileOps
        return WorkspaceFileOps.create_item(
            wm=self,
            workspace_id=workspace_id,
            rel_path=rel_path,
            is_dir=is_dir,
            content=content,
        )

    def delete_workspace_item(self, workspace_id: str, rel_path: str) -> Dict[str, Any]:
        """Удаляет файл или директорию из рабочей области с коммитом в Git."""
        from apps.ai_assistant.core.workspace_file_ops import WorkspaceFileOps
        return WorkspaceFileOps.delete_item(wm=self, workspace_id=workspace_id, rel_path=rel_path)

    def get_workspace_file_content(self, workspace_id: str, rel_path: str) -> Dict[str, Any]:
        """Считывает текстовое содержимое файла из рабочей области."""
        from apps.ai_assistant.core.workspace_file_ops import WorkspaceFileOps
        return WorkspaceFileOps.get_content(wm=self, workspace_id=workspace_id, rel_path=rel_path)

    def save_workspace_file_content(
        self,
        workspace_id: str,
        rel_path: str,
        content: str,
        commit_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Сохраняет текстовое содержимое файла в рабочей области с авто-коммитом в Git."""
        from apps.ai_assistant.core.workspace_file_ops import WorkspaceFileOps
        return WorkspaceFileOps.save_content(
            wm=self,
            workspace_id=workspace_id,
            rel_path=rel_path,
            content=content,
            commit_message=commit_message,
        )

    def move_workspace_item(
        self,
        workspace_id: str,
        old_rel_path: str,
        new_rel_path: str,
        commit_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Перемещает или переименовывает файл в рабочей области через git mv и перепривязывает в базе знаний."""
        from apps.ai_assistant.core.workspace_file_ops import WorkspaceFileOps
        return WorkspaceFileOps.move_item(
            wm=self,
            workspace_id=workspace_id,
            old_rel_path=old_rel_path,
            new_rel_path=new_rel_path,
            commit_message=commit_message,
        )

    @property
    def virtual_tree_engine(self) -> Any:
        """Возвращает экземпляр движка виртуального дерева категорий по содержимому."""
        if not hasattr(self, "_virtual_tree_engine") or self._virtual_tree_engine is None:
            from apps.ai_assistant.core.virtual_category_tree import VirtualCategoryTreeEngine
            self._virtual_tree_engine = VirtualCategoryTreeEngine(self)
        return self._virtual_tree_engine

    def get_virtual_tree(self, workspace_id: str) -> Dict[str, Any]:
        """Возвращает виртуальное дерево всех отслеживаемых файлов (локальных и внешних) по категориям содержимого."""
        return self.virtual_tree_engine.get_virtual_tree(workspace_id)

    async def revise_virtual_tree(
        self,
        workspace_id: str,
        strategy: str = "semantic_domain",
        instruction: str = "",
        use_model: bool = True,
        provider: str = "gemini",
        model_name: str = "gemini-2.5-flash",
    ) -> Dict[str, Any]:
        """Выполняет ревизию содержимого всех файлов и перестраивает логику виртуальных категорий."""
        return await self.virtual_tree_engine.revise_taxonomy(
            workspace_id=workspace_id,
            strategy=strategy,
            instruction=instruction,
            use_model=use_model,
            provider=provider,
            model_name=model_name,
        )



