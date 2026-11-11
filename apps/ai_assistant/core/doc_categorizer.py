# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant - Smart Document Categorizer & RAG Engine
# =============================================================================
# Description:
#   Движок обнаружения, интеллектуальной категоризации и RAG-поиска
#   по локальным документам пользователя с поддержкой Human-in-the-Loop.
#
# Usage Examples:
#   from apps.ai_assistant.core.doc_categorizer import doc_categorizer_service
#   doc_categorizer_service.start_scan(mode="auto")
#
# File: doc_categorizer.py
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 19:56:00
# =============================================================================

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from header import __root__
from logger import logger

SUPPORTED_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx",
    ".txt", ".md", ".rtf", ".csv", ".odt", ".png", ".jpg", ".jpeg"
}

SYSTEM_EXCLUDE_DIRS = {
    "windows", "program files", "program files (x86)", "appdata",
    "node_modules", ".git", ".venv", "venv", "$recycle.bin",
    "system volume information", "cache", "site-packages"
}

DEFAULT_CATEGORIES: Dict[str, Dict[str, Any]] = {
    "finance": {
        "title": "Финансы и Бухгалтерия",
        "icon": "bi-receipt-cutoff",
        "color": "primary",
        "keywords": ["счет", "инвойс", "invoice", "акт", "чек", "оплата", "квитанция", "налог", "декларация", "statement", "bill"]
    },
    "legal": {
        "title": "Юриспруденция и Договоры",
        "icon": "bi-journal-text",
        "color": "info",
        "keywords": ["договор", "contract", "соглашение", "agreement", "nda", "доверенность", "акт приема", "оферта", "юрист", "устав"]
    },
    "personal": {
        "title": "Личные документы",
        "icon": "bi-person-badge",
        "color": "success",
        "keywords": ["паспорт", "passport", "диплом", "свидетельство", "страховка", "полис", "снилс", "инн", "резюме", "cv", "медицин"]
    },
    "work": {
        "title": "Работа и Проекты",
        "icon": "bi-briefcase",
        "color": "warning",
        "keywords": ["тз", "спецификация", "проект", "отчет", "report", "presentation", "roadmap", "аналитика", "brief", "план"]
    },
    "education": {
        "title": "Обучение и Знания",
        "icon": "bi-mortarboard",
        "color": "purple",
        "keywords": ["лекция", "конспект", "книга", "учебник", "статья", "paper", "методичка", "курс", "tutorial", "шпаргалка"]
    },
    "archive": {
        "title": "Архив и Черновики",
        "icon": "bi-archive",
        "color": "secondary",
        "keywords": ["черновик", "draft", "копия", "temp", "old", "backup", "архив", "лог", "выгрузка"]
    }
}


class DocumentCategorizerService:
    """Сервис обнаружения, категоризации и семантического поиска документов."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        """Инициализирует сервис и локальную базу данных SQLite."""
        self._db_path = db_path or (__root__ / "data" / "doc_categorizer.db")
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._scan_thread: Optional[threading.Thread] = None
        self._is_scanning = False
        self._scan_stats = {
            "total_found": 0,
            "processed": 0,
            "classified": 0,
            "uncertain": 0,
            "current_file": ""
        }
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Создает подключение к локальной SQLite базе данных."""
        conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Создает схемы таблиц и виртуальную таблицу FTS5 для RAG-поиска."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    file_name TEXT NOT NULL,
                    file_path TEXT NOT NULL UNIQUE,
                    file_size INTEGER NOT NULL,
                    extension TEXT NOT NULL,
                    hash_sha256 TEXT,
                    category TEXT,
                    subcategory TEXT,
                    confidence REAL DEFAULT 0.0,
                    status TEXT NOT NULL, -- 'classified', 'uncertain', 'pending'
                    summary TEXT,
                    content_preview TEXT,
                    created_at TEXT NOT NULL,
                    modified_at TEXT NOT NULL,
                    indexed_at TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS classification_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern TEXT NOT NULL,
                    target_category TEXT NOT NULL,
                    rule_type TEXT NOT NULL, -- 'name_regex', 'path_contains'
                    created_at TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
                    id UNINDEXED,
                    file_name,
                    content_preview,
                    summary,
                    category
                )
            """)
            conn.commit()

    def get_status(self) -> Dict[str, Any]:
        """Возвращает текущий статус сканирования и статистику базы данных."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM documents")
            total_docs = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM documents WHERE status = 'classified'")
            classified_count = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM documents WHERE status = 'uncertain'")
            uncertain_count = cur.fetchone()[0]

            cur.execute("SELECT category, COUNT(*) as cnt FROM documents GROUP BY category")
            category_counts = {row["category"] or "unassigned": row["cnt"] for row in cur.fetchall()}

        return {
            "is_scanning": self._is_scanning,
            "scan_stats": self._scan_stats,
            "total_documents": total_docs,
            "classified_count": classified_count,
            "uncertain_count": uncertain_count,
            "categories": category_counts,
            "default_categories": DEFAULT_CATEGORIES
        }

    def start_scan(self, mode: str = "auto", custom_path: Optional[str] = None) -> bool:
        """Запускает процесс сканирования документов в фоновом потоке."""
        with self._lock:
            if self._is_scanning:
                return False
            self._is_scanning = True
            self._scan_stats = {
                "total_found": 0,
                "processed": 0,
                "classified": 0,
                "uncertain": 0,
                "current_file": ""
            }

        target_dirs: List[Path] = []
        if mode == "explicit" and custom_path:
            p = Path(custom_path)
            if p.exists() and p.is_dir():
                target_dirs.append(p)
        else:
            # Автоматический режим поиска в стандартных директориях Windows
            user_profile = Path(os.environ.get("USERPROFILE", Path.home()))
            for candidate in ["Documents", "Downloads", "Desktop", "OneDrive"]:
                cand_dir = user_profile / candidate
                if cand_dir.exists() and cand_dir.is_dir():
                    target_dirs.append(cand_dir)

        self._scan_thread = threading.Thread(
            target=self._run_scan_worker,
            args=(target_dirs,),
            daemon=True
        )
        self._scan_thread.start()
        return True

    def _run_scan_worker(self, target_dirs: List[Path]) -> None:
        """Фоновый воркер поиска и классификации документов."""
        try:
            logger.console(f"[DocCategorizer] Запуск сканирования директорий: {[str(d) for d in target_dirs]}")
            rules = self._load_rules()

            for base_dir in target_dirs:
                for root, dirs, files in os.walk(base_dir):
                    # Исключение системных каталогов
                    dirs[:] = [
                        d for d in dirs
                        if d.lower() not in SYSTEM_EXCLUDE_DIRS and not d.startswith(".")
                    ]

                    for f in files:
                        ext = Path(f).suffix.lower()
                        if ext not in SUPPORTED_EXTENSIONS:
                            continue

                        full_path = Path(root) / f
                        self._scan_stats["total_found"] += 1
                        self._scan_stats["current_file"] = f
                        self._process_single_file(full_path, rules)
                        self._scan_stats["processed"] += 1

        except Exception as exc:
            logger.warning(f"[DocCategorizer] Ошибка во время сканирования: {exc}")
        finally:
            with self._lock:
                self._is_scanning = False
                self._scan_stats["current_file"] = ""
            logger.console("[DocCategorizer] Фоновое сканирование успешно завершено.")

    def _load_rules(self) -> List[sqlite3.Row]:
        """Загружает пользовательские правила фильтрации из базы данных."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT pattern, target_category, rule_type FROM classification_rules")
            return cur.fetchall()

    def _process_single_file(self, path: Path, rules: List[Any]) -> None:
        """Вычисляет метаданные, категорию и сохраняет документ в RAG-базу."""
        try:
            stat = path.stat()
            file_name = path.name
            path_str = str(path.resolve())

            # Первичная проверка существующих правил пользователя
            assigned_cat: Optional[str] = None
            for rule in rules:
                pat = rule["pattern"].lower()
                if rule["rule_type"] == "path_contains" and pat in path_str.lower():
                    assigned_cat = rule["target_category"]
                    break
                elif rule["rule_type"] == "name_regex" and re.search(pat, file_name, re.IGNORECASE):
                    assigned_cat = rule["target_category"]
                    break

            confidence = 0.95 if assigned_cat else 0.0
            if not assigned_cat:
                assigned_cat, confidence = self._classify_heuristically(file_name, path_str)

            status = "classified" if confidence >= 0.75 else "uncertain"
            if status == "classified":
                self._scan_stats["classified"] += 1
            else:
                self._scan_stats["uncertain"] += 1

            doc_id = hashlib.sha1(path_str.encode("utf-8")).hexdigest()[:16]
            preview = self._extract_preview(path)
            now_iso = datetime.now().isoformat()

            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO documents (
                        id, file_name, file_path, file_size, extension,
                        category, confidence, status, content_preview,
                        created_at, modified_at, indexed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(file_path) DO UPDATE SET
                        file_size=excluded.file_size,
                        category=excluded.category,
                        confidence=excluded.confidence,
                        status=excluded.status,
                        content_preview=excluded.content_preview,
                        indexed_at=excluded.indexed_at
                """, (
                    doc_id, file_name, path_str, stat.st_size, path.suffix.lower(),
                    assigned_cat, confidence, status, preview,
                    datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    now_iso
                ))
                # Обновление FTS5 индекса
                cur.execute("DELETE FROM documents_fts WHERE id = ?", (doc_id,))
                cur.execute("""
                    INSERT INTO documents_fts (id, file_name, content_preview, summary, category)
                    VALUES (?, ?, ?, ?, ?)
                """, (doc_id, file_name, preview, "", assigned_cat or ""))
                conn.commit()

        except Exception as exc:
            logger.debug(f"[DocCategorizer] Ошибка обработки файла {path.name}: {exc}")

    def _classify_heuristically(self, name: str, path_str: str) -> Tuple[Optional[str], float]:
        """Определяет категорию документа и рассчитывает балл уверенности."""
        parent_name = Path(path_str).parent.name
        raw_text = f"{name} {parent_name}".lower()
        tokens = set(re.split(r'[\s_\-\.\/\\]+', raw_text))

        best_cat: Optional[str] = None
        best_score = 0.0

        for cat_key, meta in DEFAULT_CATEGORIES.items():
            matches = 0
            for kw in meta["keywords"]:
                kw_lower = kw.lower()
                if len(kw_lower) <= 4:
                    if kw_lower in tokens:
                        matches += 1
                else:
                    if any(kw_lower in t or t.startswith(kw_lower) for t in tokens):
                        matches += 1

            if matches > 0:
                score = min(0.95, 0.55 + (matches * 0.25))
                if score > best_score:
                    best_score = score
                    best_cat = cat_key

        if best_cat and best_score >= 0.75:
            return best_cat, best_score
        return best_cat, (best_score if best_score > 0 else 0.30)

    def _extract_preview(self, path: Path) -> str:
        """Извлекает текстовое превью из файла для первичного RAG-поиска."""
        ext = path.suffix.lower()
        if ext in {".txt", ".md", ".csv", ".json", ".log"}:
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    return f.read(500)
            except Exception:
                return ""
        return f"Документ: {path.name} ({ext.upper()})"

    def get_uncertain_documents(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Возвращает документы, требующие решения пользователя."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, file_name, file_path, file_size, extension,
                       category, confidence, content_preview, modified_at
                FROM documents
                WHERE status = 'uncertain'
                ORDER BY confidence ASC
                LIMIT ?
            """, (limit,))
            rows = cur.fetchall()
            return [dict(r) for r in rows]

    def resolve_uncertain(
        self,
        doc_id: str,
        category: str,
        create_rule: bool = False,
        rule_pattern: Optional[str] = None
    ) -> bool:
        """Применяет выбор пользователя к спорному документу и опционально создает правило."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE documents
                SET category = ?, confidence = 1.0, status = 'classified'
                WHERE id = ?
            """, (category, doc_id))

            if create_rule and rule_pattern:
                cur.execute("""
                    INSERT INTO classification_rules (pattern, target_category, rule_type, created_at)
                    VALUES (?, ?, 'path_contains', ?)
                """, (rule_pattern, category, datetime.now().isoformat()))

                # Автоматически перекатегоризуем похожие документы по новому правилу
                cur.execute("""
                    UPDATE documents
                    SET category = ?, confidence = 0.95, status = 'classified'
                    WHERE file_path LIKE ? AND status = 'uncertain'
                """, (category, f"%{rule_pattern}%"))

            conn.commit()
            return True

    def list_documents(
        self,
        category: Optional[str] = None,
        status: Optional[str] = None,
        query: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Возвращает пагинированный список документов с фильтрами."""
        where_clauses = ["1=1"]
        params: List[Any] = []

        if category:
            where_clauses.append("category = ?")
            params.append(category)
        if status:
            where_clauses.append("status = ?")
            params.append(status)
        if query:
            where_clauses.append("(file_name LIKE ? OR content_preview LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%"])

        where_sql = " AND ".join(where_clauses)

        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(f"SELECT COUNT(*) FROM documents WHERE {where_sql}", tuple(params))
            total = cur.fetchone()[0]

            cur.execute(f"""
                SELECT id, file_name, file_path, file_size, extension,
                       category, confidence, status, content_preview, modified_at
                FROM documents
                WHERE {where_sql}
                ORDER BY modified_at DESC
                LIMIT ? OFFSET ?
            """, tuple(params + [limit, offset]))
            items = [dict(r) for r in cur.fetchall()]

        return {"total": total, "items": items, "limit": limit, "offset": offset}

    def search_rag(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Выполняет полнотекстовый и фактологический поиск по проиндексированным документам."""
        if not query or not query.strip():
            return []

        clean_q = re.sub(r'[^a-zA-Zа-яА-Я0-9\s]', ' ', query).strip()
        if not clean_q:
            return []

        fts_query = " OR ".join(clean_q.split())

        with self._get_connection() as conn:
            cur = conn.cursor()
            try:
                cur.execute("""
                    SELECT d.id, d.file_name, d.file_path, d.category,
                           d.confidence, d.content_preview, snippet(documents_fts, 1, '<b>', '</b>', '...', 15) as match_snippet
                    FROM documents_fts f
                    JOIN documents d ON f.id = d.id
                    WHERE documents_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                """, (fts_query, limit))
                return [dict(r) for r in cur.fetchall()]
            except Exception as exc:
                logger.debug(f"[DocCategorizer] Ошибка FTS поиска: {exc}")
                # Fallback на LIKE поиск
                cur.execute("""
                    SELECT id, file_name, file_path, category, confidence, content_preview
                    FROM documents
                    WHERE file_name LIKE ? OR content_preview LIKE ?
                    LIMIT ?
                """, (f"%{clean_q}%", f"%{clean_q}%", limit))
                return [dict(r) for r in cur.fetchall()]


doc_categorizer_service = DocumentCategorizerService()
