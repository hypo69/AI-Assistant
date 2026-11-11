# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Core - Watchdog PDF Pipeline
# =============================================================================
# Description:
#   Конвейер автоматической обработки PDF-файлов для наблюдателя watchdog:
#   1. Отправляет новый или изменённый PDF-файл в Paperless-ngx для OCR и разбора
#      (с резервным fallback на ContentExtractor при недоступности Paperless).
#   2. Преобразует результат Paperless в структурированный Markdown (.md).
#   3. Изучает смысл документа и структуру каталогов рабочей области с помощью
#      модели Gemini (UnifiedChatModel), подбирая подходящую папку назначения.
#   4. Формулирует осмысленное название Git-коммита на основе изменений и фиксирует
#      итоговый .md файл в рабочей области, БД знаний, FAISS и Git.
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.core.watchdog_pdf_pipeline import WatchdogPdfPipeline
#
#     pipeline = WatchdogPdfPipeline(workspace_manager)
#     result = await pipeline.process_pdf(ws_id="default", ws_path=ws_path, file_path=pdf_path)
#
# File: watchdog_pdf_pipeline.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-11 23:42:30
# =============================================================================

from __future__ import annotations
"""Конвейер обработки PDF через Paperless-ngx, семантического размещения Gemini и Git-коммита."""

import asyncio
import difflib
import json
from pathlib import Path
import re
from typing import Any, Callable, Dict, List, Optional, Tuple, TYPE_CHECKING

try:
    from src.config import ai_cfg
except Exception:
    ai_cfg = None

from logger import logger
from apps.ai_assistant.core.doc_categorizer import DEFAULT_CATEGORIES
from apps.ai_assistant.core.obsidian_vault import strip_obsidian_enrichment
from apps.ai_assistant.core.paperless_connector import PaperlessConnector, PaperlessError

if TYPE_CHECKING:
    from apps.ai_assistant.core.workspace_manager import WorkspaceManager

_RESERVED_DIR_NAMES = {
    ".git",
    ".workspace",
    ".obsidian",
    ".extracted_snapshots",
    "faiss_indices",
    "_topics",
    "_notes",
    "_entities",
    "assets",
    "__pycache__",
    "node_modules",
}

_INVALID_SEGMENT_CHARS_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


def _read_provider_model(providers_obj: Any, provider_key: str) -> Optional[Tuple[str, str]]:
    """Извлекает (provider, model) для включённого провайдера из ai_cfg.providers."""
    if not providers_obj:
        return None
    sec = providers_obj.get(provider_key) if isinstance(providers_obj, dict) else getattr(providers_obj, provider_key, None)
    if not sec:
        return None
    enabled = sec.get("enabled") if isinstance(sec, dict) else getattr(sec, "enabled", True)
    if enabled is False:
        return None
    model = (
        (sec.get("default_model") or sec.get("model") or "")
        if isinstance(sec, dict)
        else (getattr(sec, "default_model", "") or getattr(sec, "model", "") or "")
    )
    model_str = str(model).strip()
    return (provider_key, model_str) if model_str else None


def resolve_gemini_candidates(cfg_obj: Any = None) -> List[Tuple[str, str]]:
    """Возвращает упорядоченный список (provider, model) семейства Gemini из конфигурации."""
    cfg = cfg_obj if cfg_obj is not None else ai_cfg
    candidates: List[Tuple[str, str]] = []
    seen: set[Tuple[str, str]] = set()

    if cfg is not None:
        providers = getattr(cfg, "providers", None)
        def_prov = str(getattr(cfg, "default_provider", "") or "").strip().lower()
        def_model = str(getattr(cfg, "default_model", "") or "").strip()

        # Если системный провайдер по умолчанию из семейства Gemini — ставим его первым
        if def_prov in {"gemini", "agy", "gemini_cli"} and def_model:
            pair = (def_prov, def_model)
            candidates.append(pair)
            seen.add(pair)

        for key in ("gemini", "agy", "gemini_cli"):
            pair = _read_provider_model(providers, key)
            if pair and pair not in seen:
                candidates.append(pair)
                seen.add(pair)

    return candidates


def format_paperless_markdown(
    file_name: str,
    content: str,
    paperless_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Преобразует результат OCR-обработки Paperless-ngx в чистый Markdown (.md)."""
    clean_text = (content or "").strip()
    meta = metadata or {}
    raw_title = str(meta.get("title") or "").strip()
    title = raw_title or Path(file_name).stem

    if not clean_text:
        return f"# {title}\n\n*(Текст не распознан при обработке {file_name})*\n"

    lines: List[str] = []
    first_non_empty = next((ln.strip() for ln in clean_text.splitlines() if ln.strip()), "")
    if not first_non_empty.startswith("# "):
        lines.append(f"# {title}")
        lines.append("")

    if paperless_id is not None:
        meta_parts = [f"Paperless ID: `#{paperless_id}`", f"Файл: `{file_name}`"]
        created = str(meta.get("created_date") or meta.get("created") or "").strip()
        if created:
            meta_parts.append(f"Дата: `{created[:10]}`")
        lines.append("> " + " • ".join(meta_parts))
        lines.append("")

    lines.append(clean_text)
    return "\n".join(lines).rstrip() + "\n"


def sanitize_target_dir(raw_dir: str, fallback_dir: str = "Документы") -> str:
    """Нормализует относительный путь папки назначения, защищая от Path Traversal и служебных каталогов."""
    cleaned = str(raw_dir or "").replace("\\", "/").strip().strip("/")
    safe_segments: List[str] = []
    for part in cleaned.split("/"):
        raw_seg = part.strip()
        if not raw_seg or raw_seg in {".", ".."}:
            continue
        if raw_seg.startswith((".", "_")) or raw_seg.lower() in _RESERVED_DIR_NAMES:
            continue
        seg = _INVALID_SEGMENT_CHARS_RE.sub("_", raw_seg).strip(" .")
        seg = re.sub(r"\s+", " ", seg)
        if not seg or seg.startswith((".", "_")) or seg.lower() in _RESERVED_DIR_NAMES:
            continue
        safe_segments.append(seg[:60])
        if len(safe_segments) >= 3:
            break
    return "/".join(safe_segments) if safe_segments else fallback_dir


def sanitize_commit_message(raw_message: str, fallback: str) -> str:
    """Приводит сообщение Git-коммита к компактной однострочной форме."""
    one_line = re.sub(r"\s+", " ", str(raw_message or "")).strip().strip("\"'`")
    if not one_line:
        return fallback
    return one_line[:160]


class WatchdogPdfPipeline:
    """Конвейер: PDF -> Paperless (.md) -> семантическое размещение Gemini -> Git commit."""

    def __init__(
        self,
        workspace_manager: WorkspaceManager,
        paperless_factory: Optional[Callable[[], PaperlessConnector]] = None,
        chat_model_factory: Optional[Callable[..., Any]] = None,
        suppress_callback: Optional[Callable[[Path, float], None]] = None,
    ) -> None:
        """Инициализирует конвейер с явным внедрением зависимостей (DI).

        Args:
            workspace_manager: Экземпляр WorkspaceManager.
            paperless_factory: Фабрика клиента PaperlessConnector (по умолчанию PaperlessConnector.from_config).
            chat_model_factory: Фабрика модели UnifiedChatModel для анализа Gemini.
            suppress_callback: Функция подавления эхо-событий watchdog при записи .md.
        """
        self.wm = workspace_manager
        self.paperless_factory = paperless_factory or PaperlessConnector.from_config
        self.chat_model_factory = chat_model_factory
        self.suppress_callback = suppress_callback

    def _collect_workspace_folders(self, ws_path: Path, max_folders: int = 80) -> List[Dict[str, Any]]:
        """Сканирует пользовательские подкаталоги рабочей области для контекста Gemini."""
        folders: List[Dict[str, Any]] = []
        ws_resolved = ws_path.resolve()
        if not ws_resolved.is_dir():
            return folders

        for current in sorted(ws_resolved.rglob("*")):
            if not current.is_dir():
                continue
            try:
                rel = current.relative_to(ws_resolved)
            except ValueError:
                continue
            parts = rel.parts
            if not parts or len(parts) > 3:
                continue
            if any(p.startswith((".", "_")) or p.lower() in _RESERVED_DIR_NAMES for p in parts):
                continue

            sample_files = [
                f.name for f in sorted(current.iterdir())
                if f.is_file() and not f.name.startswith(".") and f.suffix.lower() in {".md", ".txt"}
            ][:5]
            folders.append({
                "path": "/".join(parts),
                "sample_files": sample_files,
            })
            if len(folders) >= max_folders:
                break

        return folders

    async def _ingest_via_paperless(
        self,
        file_path: Path,
        workspace_id: str,
        workspace_name: str,
    ) -> Tuple[Optional[int], str, Dict[str, Any], str]:
        """Отправляет PDF в Paperless-ngx и возвращает (paperless_id, md_text, metadata, source_kind)."""
        def _sync_ingest() -> Optional[Dict[str, Any]]:
            connector = self.paperless_factory()
            try:
                if not connector.ping():
                    return None
                return connector.ingest_file(
                    file_path=file_path,
                    workspace_id=workspace_id,
                    workspace_name=workspace_name,
                    title=file_path.name,
                )
            finally:
                connector.close()

        try:
            ingest_res = await asyncio.to_thread(_sync_ingest)
            if ingest_res and ingest_res.get("paperless_id"):
                pid = int(ingest_res["paperless_id"])
                raw_text = str(ingest_res.get("content") or "")
                meta = dict(ingest_res.get("metadata") or {})
                md_text = format_paperless_markdown(
                    file_name=file_path.name,
                    content=raw_text,
                    paperless_id=pid,
                    metadata=meta,
                )
                logger.console(
                    f"[WatchdogPdfPipeline] Paperless-ngx обработал '{file_path.name}' "
                    f"(ID: #{pid}, символов: {len(raw_text)})."
                )
                return pid, md_text, meta, "paperless"
        except (PaperlessError, OSError, ValueError) as exc:
            logger.warning(
                f"[WatchdogPdfPipeline] Paperless недоступен для '{file_path.name}', "
                f"выполняется резервное извлечение: {exc}"
            )

        extracted = await self.wm.extractor.extract(file_path, pdf_mode="model")
        fallback_text = str(extracted.get("text") or "").strip()
        md_fallback = format_paperless_markdown(file_name=file_path.name, content=fallback_text)
        return None, md_fallback, {}, "extractor_fallback"

    def _build_chat_model(self, system_instruction: str, provider: str, model: str) -> Any:
        """Создаёт экземпляр UnifiedChatModel через фабрику DI или напрямую."""
        if self.chat_model_factory:
            return self.chat_model_factory(
                system_instruction=system_instruction,
                provider=provider,
                model=model,
            )
        from src.ai.orchestration.unified_chat import UnifiedChatModel

        return UnifiedChatModel(
            system_instruction=system_instruction,
            provider=provider,
            model=model,
        )

    def _find_existing_md_diff(self, ws_path: Path, stem: str, new_md: str) -> Tuple[Optional[str], str]:
        """Ищет существующий <stem>.md в рабочей области и формирует текстовый diff при обновлении."""
        ws_resolved = ws_path.resolve()
        for candidate in ws_resolved.rglob(f"{stem}.md"):
            try:
                rel = candidate.relative_to(ws_resolved)
            except ValueError:
                continue
            if any(p.startswith((".", "_")) or p.lower() in _RESERVED_DIR_NAMES for p in rel.parts[:-1]):
                continue
            try:
                old_clean = strip_obsidian_enrichment(candidate.read_text(encoding="utf-8", errors="replace"))
                diff_lines = list(
                    difflib.unified_diff(
                        old_clean.splitlines(),
                        new_md.splitlines(),
                        fromfile=f"a/{rel.as_posix()}",
                        tofile=f"b/{rel.as_posix()}",
                        lineterm="",
                        n=2,
                    )
                )
                return rel.parent.as_posix() if rel.parent != Path(".") else "", "\n".join(diff_lines[:80])
            except Exception:
                return None, ""
        return None, ""

    def _fallback_decision(
        self,
        file_name: str,
        md_content: str,
        existing_folders: List[Dict[str, Any]],
        existing_dir: Optional[str],
        ws_lang: str,
    ) -> Dict[str, str]:
        """Детерминированный резервный выбор папки и названия коммита при недоступности Gemini."""
        text_lower = f"{file_name}\n{md_content[:4000]}".lower()
        chosen_dir = existing_dir or ""

        if not chosen_dir:
            # 1. Пробуем сопоставить с существующими папками рабочей области
            best_folder = ""
            best_score = 0
            for f_info in existing_folders:
                f_path = str(f_info.get("path") or "")
                words = [w for w in re.findall(r"[\w\u0590-\u05FF]{3,}", f_path.lower())]
                score = sum(1 for w in words if w in text_lower)
                if score > best_score:
                    best_score = score
                    best_folder = f_path
            if best_folder:
                chosen_dir = best_folder

        if not chosen_dir:
            # 2. Сопоставление со словарём категорий DEFAULT_CATEGORIES из doc_categorizer
            best_cat_title = ""
            best_hits = 0
            for cat_data in DEFAULT_CATEGORIES.values():
                hits = sum(1 for kw in cat_data.get("keywords", []) if kw in text_lower)
                if hits > best_hits:
                    best_hits = hits
                    best_cat_title = str(cat_data.get("title") or "")
            if best_cat_title:
                chosen_dir = best_cat_title

        fallback_root = {"en": "Documents", "he": "מסמכים", "uk": "Документи"}.get(ws_lang, "Документы")
        safe_dir = sanitize_target_dir(chosen_dir, fallback_dir=fallback_root)
        action_word = "Обновлён" if existing_dir is not None else "Добавлен"
        first_heading = next(
            (ln.lstrip("# ").strip() for ln in md_content.splitlines() if ln.strip() and not ln.strip().startswith(">")),
            Path(file_name).stem,
        )
        msg = sanitize_commit_message(
            f"{action_word} документ «{first_heading[:70]}» в раздел «{safe_dir}»",
            fallback=f"{action_word} Markdown для {file_name}",
        )
        return {
            "target_dir": safe_dir,
            "commit_message": msg,
            "evaluated_by": "local_fallback",
        }

    async def _analyze_with_gemini(
        self,
        workspace_id: str,
        ws_info: Dict[str, Any],
        file_name: str,
        md_content: str,
        paperless_meta: Dict[str, Any],
        existing_folders: List[Dict[str, Any]],
        existing_dir: Optional[str],
        diff_snippet: str,
    ) -> Dict[str, str]:
        """Изучает документ через Gemini и возвращает (target_dir, commit_message, evaluated_by)."""
        ws_lang = str(ws_info.get("language") or "ru").strip().lower()
        ws_name = str(ws_info.get("name") or workspace_id)
        ws_desc = str(ws_info.get("description") or "")

        fallback = self._fallback_decision(
            file_name=file_name,
            md_content=md_content,
            existing_folders=existing_folders,
            existing_dir=existing_dir,
            ws_lang=ws_lang,
        )

        candidates = resolve_gemini_candidates()
        if not candidates:
            return fallback

        lang_titles = {
            "ru": "Русский",
            "en": "English",
            "he": "עברית (Hebrew)",
            "uk": "Українська",
        }
        target_lang_title = lang_titles.get(ws_lang, "Русский")

        sys_prompt = (
            "Ты — интеллектуальный архитектор базы знаний. "
            "Изучи смысл Markdown-документа, полученного после OCR-обработки PDF в Paperless-ngx, "
            "проанализируй существующие папки рабочей области и реши:\n"
            "1. `target_dir`: наиболее подходящая по смыслу папка внутри рабочей области "
            "(выбери существующую из списка, если она подходит по теме, либо предложи короткую логичную папку "
            "или путь вида 'Раздел/Подраздел'). Не используй служебные имена (.git, .workspace, assets, _Topics).\n"
            "2. `commit_message`: краткое, содержательное сообщение git-коммита на основе изменений и сути документа "
            f"(строго на языке: {target_lang_title}, одной строкой до 120 символов, без префикса 'Watchdog:').\n"
            "Верни СТРОГО валидный JSON-объект вида:\n"
            '{"target_dir": "Раздел/Подраздел", "commit_message": "Добавлен ..."}'
        )

        excerpt = md_content[:6000]
        if len(md_content) > 7500:
            excerpt += "\n\n...[пропущено]...\n\n" + md_content[-1500:]

        meta_summary = {
            k: paperless_meta.get(k)
            for k in ("id", "title", "created_date", "correspondent", "document_type", "tags")
            if paperless_meta.get(k) is not None
        }
        user_payload = {
            "workspace": {"id": workspace_id, "name": ws_name, "description": ws_desc, "language": target_lang_title},
            "existing_folders": existing_folders[:40],
            "pdf_file": file_name,
            "is_update": existing_dir is not None,
            "previous_dir": existing_dir,
            "diff_snippet": diff_snippet[:2500] if diff_snippet else "",
            "paperless_metadata": meta_summary,
            "markdown_content": excerpt,
        }
        user_prompt = json.dumps(user_payload, ensure_ascii=False, indent=2)

        for provider, model_name in candidates:
            try:
                chat = self._build_chat_model(sys_prompt, provider=provider, model=model_name)
                raw_resp = await asyncio.wait_for(
                    chat.ask(q=user_prompt, attempts=2, temperature=0.1),
                    timeout=45.0,
                )
                if not raw_resp:
                    continue
                cleaned = raw_resp.strip()
                match = re.search(r"\{[\s\S]*\}", cleaned)
                if match:
                    cleaned = match.group(0)
                parsed = json.loads(cleaned)
                if isinstance(parsed, dict) and (parsed.get("target_dir") or parsed.get("commit_message")):
                    safe_dir = sanitize_target_dir(
                        str(parsed.get("target_dir") or ""),
                        fallback_dir=fallback["target_dir"],
                    )
                    commit_msg = sanitize_commit_message(
                        str(parsed.get("commit_message") or ""),
                        fallback=fallback["commit_message"],
                    )
                    return {
                        "target_dir": safe_dir,
                        "commit_message": commit_msg,
                        "evaluated_by": f"{provider}/{model_name}",
                    }
            except Exception as exc:
                logger.info(f"[WatchdogPdfPipeline] Модель {provider}/{model_name} не ответила: {exc}")
                continue

        return fallback

    async def process_pdf(
        self,
        ws_id: str,
        ws_path: Path,
        file_path: Path,
        auto_git_commit: bool = True,
    ) -> Dict[str, Any]:
        """Выполняет полный цикл обработки добавленного PDF-файла и возвращает отчёт."""
        ws_info = self.wm.get_workspace(ws_id) or {"workspace_id": ws_id, "name": ws_id, "language": "ru"}
        ws_name = str(ws_info.get("name") or ws_id)

        paperless_id, md_content, paperless_meta, ocr_source = await self._ingest_via_paperless(
            file_path=file_path,
            workspace_id=ws_id,
            workspace_name=ws_name,
        )

        existing_folders = self._collect_workspace_folders(ws_path)
        existing_dir, diff_snippet = self._find_existing_md_diff(ws_path, file_path.stem, md_content)

        decision = await self._analyze_with_gemini(
            workspace_id=ws_id,
            ws_info=ws_info,
            file_name=file_path.name,
            md_content=md_content,
            paperless_meta=paperless_meta,
            existing_folders=existing_folders,
            existing_dir=existing_dir,
            diff_snippet=diff_snippet,
        )

        target_dir = decision["target_dir"]
        commit_message = decision["commit_message"]
        target_rel_doc = f"{target_dir}/{file_path.stem}.md" if target_dir else f"{file_path.stem}.md"

        if self.suppress_callback:
            self.suppress_callback(ws_path, 6.0)

        import_res = await asyncio.to_thread(
            self.wm.import_document,
            workspace_id=ws_id,
            document_id=target_rel_doc,
            content=md_content,
            commit_message=commit_message if auto_git_commit else None,
            paperless_id=paperless_id,
        )

        logger.console(
            f"[WatchdogPdfPipeline] PDF '{file_path.name}' -> '{target_rel_doc}' "
            f"(source={ocr_source}, gemini={decision['evaluated_by']}, commit='{commit_message}')"
        )
        return {
            "status": "ok",
            "action": "pdf_paperless_gemini_committed",
            "document_id": target_rel_doc,
            "target_dir": target_dir,
            "paperless_id": paperless_id,
            "ocr_source": ocr_source,
            "evaluated_by": decision["evaluated_by"],
            "commit_message": commit_message,
            "commit_hash": import_res.get("commit_hash", ""),
        }
