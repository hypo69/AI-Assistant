# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Core - Workspace Registry
# =============================================================================
# Description:
#   Файловый реестр рабочих пространств без базы данных.
#   Рабочее пространство — подпапка каталога workspaces/, содержащая .git.
#   Настройки пространства (имя, описание, дата создания, привязанные источники)
#   хранятся в служебном файле <ws>/.workspace/config.json, который создаётся
#   автоматически при первом сканировании и исключается из Git через
#   .git/info/exclude.
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.core.workspace_registry import WorkspaceRegistry
#
#     registry = WorkspaceRegistry(Path("apps/ai_assistant/data/workspaces"))
#     for ws in registry.list_workspaces():
#         print(ws["workspace_id"], ws["name"])
#
# File: workspace_registry.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 20:00:00
# =============================================================================

from __future__ import annotations
"""Файловый реестр рабочих пространств на основе сканирования каталога workspaces/."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import re
import shutil
import socket
import stat
from typing import Any, Dict, List, Optional, Tuple
import uuid

from logger import logger

WORKSPACE_META_DIR = ".workspace"
WORKSPACE_CONFIG_FILE = "config.json"

SYSTEM_DATA_DIRS = {
    "ai_assistant", "chromium", "rag", "rag_index", "telegram_rag",
    "users", "windows_wikillm", "workspaces", "cache", "logs", "temp", "tmp"
}

_HOST_PREFIX_RE = re.compile(r"^(?:\\\\|//)([^\\/]+)[\\/]([A-Za-z]:[\\/].*)$")
_HOST_COLON_RE = re.compile(r"^([A-Za-z0-9_.\-]+)::(.+)$")


def normalize_workspace_language(language: Optional[str] = None) -> str:
    """Нормализует код языка рабочего пространства ('en', 'ru', 'he', 'ua')."""
    raw = (language or "ru").strip().lower()
    if raw in ("uk", "ukr", "ua", "ukrainian"):
        return "ua"
    if raw in ("ru", "rus", "russian"):
        return "ru"
    if raw in ("he", "heb", "hebrew", "iw"):
        return "he"
    if raw in ("en", "eng", "english"):
        return "en"
    return raw or "ru"


def generate_workspace_readme(
    name: str,
    description: str = "",
    language: Optional[str] = "ru",
) -> str:
    """Формирует содержимое файла README.md с языковой меткой lang=<lang> и главами Название и Описание.

    Args:
        name: Название рабочего пространства.
        description: Описание рабочего пространства.
        language: Язык рабочего пространства (en, ru, he, ua).

    Returns:
        str: Текст файла README.md в формате Markdown.
    """
    lang = normalize_workspace_language(language)
    locales = {
        "ru": {
            "title_default": "Рабочее пространство",
            "desc_header": "Описание",
            "desc_default": "Рабочее пространство создано в AI Windows Admin.",
        },
        "en": {
            "title_default": "Workspace",
            "desc_header": "Description",
            "desc_default": "Workspace created in AI Windows Admin.",
        },
        "he": {
            "title_default": "מרחב עבודה",
            "desc_header": "תיאור",
            "desc_default": "מרחב עבודה נוצר ב-AI Windows Admin.",
        },
        "ua": {
            "title_default": "Робочий простір",
            "desc_header": "Опис",
            "desc_default": "Робочий простір створено в AI Windows Admin.",
        },
    }
    loc = locales.get(lang, locales["en"])
    ws_title = (name or "").strip() or loc["title_default"]
    ws_desc = (description or "").strip() or loc["desc_default"]

    return (
        f"lang={lang}\n\n"
        f"# {ws_title}\n\n"
        f"## {loc['desc_header']}\n"
        f"{ws_desc}\n"
    )


def parse_workspace_readme(readme_path: Path) -> Dict[str, str]:
    """Извлекает язык, название и описание из файла README.md рабочего пространства.

    Args:
        readme_path: Путь к файлу README.md.

    Returns:
        Dict[str, str]: Словарь с ключами 'language', 'name', 'description'.
    """
    result = {"language": "ru", "name": "", "description": ""}
    if not readme_path.is_file():
        return result
    try:
        content = readme_path.read_text(encoding="utf-8")
        lines = [line.strip() for line in content.splitlines()]
        # Первая строка: lang=...
        for line in lines:
            if line.lower().startswith("lang="):
                result["language"] = normalize_workspace_language(line.split("=", 1)[1].strip())
                break
        # Заголовок первого уровня '# ...'
        for line in lines:
            if line.startswith("# "):
                result["name"] = line[2:].strip()
                break
        # Секция '## ...'
        desc_lines: List[str] = []
        capturing = False
        for line in lines:
            if line.startswith("## "):
                capturing = True
                continue
            elif capturing and line.startswith("#"):
                break
            elif capturing and line:
                desc_lines.append(line)
        if desc_lines:
            result["description"] = "\n".join(desc_lines).strip()
    except Exception as exc:
        logger.warning(f"[WorkspaceRegistry] Ошибка чтения {readme_path}: {exc}")
    return result


def get_current_host_name() -> str:
    """Возвращает нормализованное имя текущего компьютера для носимого (USB) режима."""
    raw = os.environ.get("COMPUTERNAME") or platform.node() or socket.gethostname() or "LOCALHOST"
    return raw.strip().upper()


def parse_host_qualified_path(raw_target: str, default_host: Optional[str] = None) -> Tuple[str, str, str]:
    """Разбирает путь и возвращает кортеж (host_name, local_path, qualified_path с именем ПК)."""
    s = str(raw_target or "").strip()
    host = (default_host or get_current_host_name()).strip().upper()
    if not s or s.lower().startswith(("http://", "https://")):
        return host, s, s

    m_unc = _HOST_PREFIX_RE.match(s)
    if m_unc:
        parsed_host = m_unc.group(1).strip().upper()
        local_p = m_unc.group(2).strip()
        return parsed_host, local_p, f"\\\\{parsed_host}\\{local_p}"

    m_col = _HOST_COLON_RE.match(s)
    if m_col:
        parsed_host = m_col.group(1).strip().upper()
        local_p = m_col.group(2).strip()
        return parsed_host, local_p, f"\\\\{parsed_host}\\{local_p}"

    return host, s, f"\\\\{host}\\{s}"


def format_host_qualified_path(local_path: str | Path, host_name: Optional[str] = None) -> str:
    """Формирует полный путь файла или папки, включая имя компьютера (\\\\<HOST>\\<PATH>)."""
    return parse_host_qualified_path(str(local_path), default_host=host_name)[2]



def _utc_now_iso() -> str:
    """Возвращает текущее время UTC в формате ISO 8601."""
    return datetime.now(timezone.utc).isoformat()


def resolve_workspaces_dir() -> Path:
    """Определяет каталог рабочих пространств из config.json приложения ai_assistant.

    Returns:
        Path: Абсолютный путь к каталогу workspaces (`storage.workspaces_dir`
        или `git.workspaces_dir`; по умолчанию `data/workspaces` в корне проекта).
    """
    app_dir = Path(__file__).resolve().parent.parent
    cfg_file = app_dir / "config.json"
    cfg_ws_dir = ""
    if cfg_file.exists():
        try:
            cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
            cfg_ws_dir = cfg.get("storage", {}).get("workspaces_dir") or cfg.get("git", {}).get("workspaces_dir") or ""
        except Exception as exc:
            logger.warning(f"[WorkspaceRegistry] Ошибка чтения config.json: {exc}")
    raw_str = (cfg_ws_dir or "data/workspaces").strip()
    if raw_str.replace("\\", "/").rstrip("/") == "data":
        raw_str = "data/workspaces"
    ws_path = Path(raw_str)
    if ws_path.is_absolute():
        ws_path.mkdir(parents=True, exist_ok=True)
        return ws_path

    # Корневой каталог проекта
    from header import __root__
    root_ws = (__root__ / ws_path).resolve()
    app_ws = (app_dir / ws_path).resolve()

    root_ws.mkdir(parents=True, exist_ok=True)
    return root_ws


def _read_git_head(ws_path: Path) -> str:
    """Читает хеш HEAD напрямую из каталога .git без вызова git.

    Returns:
        str: Полный хеш коммита или пустая строка, если коммитов ещё нет.
    """
    git_dir = ws_path / ".git"
    try:
        head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
        if not head.startswith("ref:"):
            return head
        ref = head[4:].strip()
        ref_file = git_dir / ref
        if ref_file.exists():
            return ref_file.read_text(encoding="utf-8").strip()
        packed = git_dir / "packed-refs"
        if packed.exists():
            for line in packed.read_text(encoding="utf-8").splitlines():
                if line.endswith(f" {ref}"):
                    return line.split(" ", 1)[0]
    except Exception:
        pass
    return ""


class WorkspaceRegistry:
    """Реестр рабочих пространств: сканирует каталог и управляет файлами .workspace/config.json."""

    def __init__(self, workspaces_dir: Path) -> None:
        """Инициализирует реестр с явно переданным каталогом рабочих пространств.

        Args:
            workspaces_dir: Каталог, подпапки которого являются рабочими пространствами.
        """
        self.workspaces_dir = Path(workspaces_dir).resolve()
        self.workspaces_dir.mkdir(parents=True, exist_ok=True)
        self._migrate_workspaces_from_legacy_data()

    def _migrate_workspaces_from_legacy_data(self) -> None:
        """Автоматически переносит рабочие пространства из корневого каталога data/ в data/workspaces/."""
        parent_dir = self.workspaces_dir.parent
        if not parent_dir.exists() or parent_dir == self.workspaces_dir or parent_dir.name.lower() != "data":
            return
        try:
            for item in list(parent_dir.iterdir()):
                if not item.is_dir() or item.name.startswith((".", "~")):
                    continue
                if item.name.lower() in SYSTEM_DATA_DIRS:
                    continue
                if (item / ".git").exists() or (item / WORKSPACE_META_DIR).exists():
                    target_path = self.workspaces_dir / item.name
                    if not target_path.exists():
                        logger.info(f"[WorkspaceRegistry] Миграция рабочего пространства '{item.name}' из {item} в {target_path}")
                        shutil.move(str(item), str(target_path))
                    else:
                        logger.debug(f"[WorkspaceRegistry] Рабочее пространство '{item.name}' уже существует в {target_path}")
                    target_assets = (self.workspaces_dir / item.name) / "assets"
                    target_assets.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            logger.warning(f"[WorkspaceRegistry] Ошибка автоматической миграции workspaces из data/: {exc}")

    # ------------------------------------------------------------------
    # Служебные операции с config.json
    # ------------------------------------------------------------------

    def workspace_path(self, workspace_id: str) -> Path:
        """Возвращает путь к папке рабочего пространства (папка может не существовать)."""
        return self.workspaces_dir / workspace_id

    def _config_file(self, ws_path: Path) -> Path:
        """Возвращает путь к служебному файлу настроек пространства."""
        return ws_path / WORKSPACE_META_DIR / WORKSPACE_CONFIG_FILE

    def _exclude_meta_from_git(self, ws_path: Path) -> None:
        """Добавляет служебные каталоги (.workspace/, .obsidian/, faiss_indices/, *.faiss, *.db) в локальный .git/info/exclude."""
        exclude_file = ws_path / ".git" / "info" / "exclude"
        lines_to_exclude = [f"{WORKSPACE_META_DIR}/", "assets/", ".obsidian/", "faiss_indices/", "*.faiss", "*.db", "*.db-wal", "*.db-shm"]
        try:
            exclude_file.parent.mkdir(parents=True, exist_ok=True)
            current = exclude_file.read_text(encoding="utf-8") if exclude_file.exists() else ""
            existing = set(current.splitlines())
            added = [ln for ln in lines_to_exclude if ln not in existing]
            if added:
                exclude_file.write_text(
                    current.rstrip("\n") + ("\n" if current else "") + "\n".join(added) + "\n",
                    encoding="utf-8",
                )
        except Exception as exc:
            logger.warning(f"[WorkspaceRegistry] Не удалось исключить служебные каталоги из Git в {ws_path}: {exc}")

    def _write_config(self, ws_path: Path, cfg: Dict[str, Any]) -> None:
        """Сохраняет настройки пространства в .workspace/config.json."""
        cfg_file = self._config_file(ws_path)
        cfg_file.parent.mkdir(parents=True, exist_ok=True)
        cfg_file.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
        self._exclude_meta_from_git(ws_path)

    def _load_config(self, ws_path: Path) -> Dict[str, Any]:
        """Читает настройки пространства; при отсутствии файла создаёт его со значениями по умолчанию."""
        cfg_file = self._config_file(ws_path)
        if cfg_file.exists():
            try:
                cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
                if isinstance(cfg, dict):
                    cfg.setdefault("sources", [])
                    cfg.setdefault("language", "ru")
                    return cfg
            except Exception as exc:
                logger.warning(f"[WorkspaceRegistry] Повреждён {cfg_file}, будет пересоздан: {exc}")
        cfg = {
            "name": ws_path.name,
            "description": "",
            "language": "ru",
            "created_at": _utc_now_iso(),
            "sources": [],
        }
        self._write_config(ws_path, cfg)
        return cfg

    def _describe(self, ws_path: Path, cfg: Dict[str, Any]) -> Dict[str, Any]:
        """Формирует публичное описание рабочего пространства."""
        return {
            "workspace_id": ws_path.name,
            "name": cfg.get("name") or ws_path.name,
            "description": cfg.get("description", ""),
            "language": cfg.get("language") or "ru",
            "created_at": cfg.get("created_at", ""),
            "path": str(ws_path),
            "git_head": _read_git_head(ws_path),
        }

    def _is_workspace_dir(self, p: Path) -> bool:
        """Признак рабочего пространства: подпапка с .git, имя не начинается с '.' или '~' и не является системным каталогом."""
        return (
            p.is_dir()
            and not p.name.startswith((".", "~"))
            and p.name.lower() not in SYSTEM_DATA_DIRS
            and (p / ".git").exists()
        )

    # ------------------------------------------------------------------
    # Рабочие пространства
    # ------------------------------------------------------------------

    def ensure_workspace_readme(
        self,
        ws_path: Path,
        name: str = "",
        description: str = "",
        language: Optional[str] = None,
    ) -> Path:
        """Создаёт файл README.md в каталоге рабочего пространства, если он отсутствует.

        Args:
            ws_path: Путь к каталогу рабочего пространства.
            name: Название рабочего пространства.
            description: Описание рабочего пространства.
            language: Код языка рабочего пространства.

        Returns:
            Path: Путь к созданному файлу README.md.
        """
        readme_path = ws_path / "README.md"
        if not readme_path.exists():
            cfg = self._load_config(ws_path)
            eff_name = name or cfg.get("name") or ws_path.name
            eff_desc = description or cfg.get("description", "")
            eff_lang = language or cfg.get("language") or "ru"
            content = generate_workspace_readme(eff_name, eff_desc, eff_lang)
            readme_path.write_text(content, encoding="utf-8")
            logger.info(f"[WorkspaceRegistry] Создан файл README.md для '{ws_path.name}' (lang={normalize_workspace_language(eff_lang)})")
        return readme_path

    def list_workspaces(self) -> List[Dict[str, Any]]:
        """Возвращает список рабочих пространств быстрым чтением содержимого каталога data/workspaces.

        Returns:
            List[Dict[str, Any]]: Отсортированный по workspace_id список описаний.
        """
        workspaces = []
        if not self.workspaces_dir.exists():
            return []
        for p in sorted(self.workspaces_dir.iterdir(), key=lambda x: x.name.lower()):
            if not self._is_workspace_dir(p):
                continue
            readme_file = p / "README.md"
            meta = parse_workspace_readme(readme_file) if readme_file.exists() else {}
            cfg_data = self._load_config(p)

            ws_name = meta.get("name") or cfg_data.get("name") or p.name
            ws_desc = meta.get("description") or cfg_data.get("description") or ""
            ws_lang = meta.get("language") or cfg_data.get("language") or "ru"

            workspaces.append({
                "workspace_id": p.name,
                "name": ws_name,
                "description": ws_desc,
                "language": ws_lang,
                "created_at": cfg_data.get("created_at", ""),
                "path": str(p),
                "git_head": _read_git_head(p),
                "has_git": True,
            })
        return workspaces

    def get_workspace(self, workspace_id: str) -> Optional[Dict[str, Any]]:
        """Возвращает описание рабочего пространства или None, если папки с .git нет."""
        if not workspace_id:
            return None
        ws_path = self.workspace_path(workspace_id)
        if not self._is_workspace_dir(ws_path):
            return None
        readme_file = ws_path / "README.md"
        meta = parse_workspace_readme(readme_file) if readme_file.exists() else {}
        cfg = self._load_config(ws_path)
        return {
            "workspace_id": ws_path.name,
            "name": meta.get("name") or cfg.get("name") or ws_path.name,
            "description": meta.get("description") or cfg.get("description", ""),
            "language": meta.get("language") or cfg.get("language") or "ru",
            "created_at": cfg.get("created_at", ""),
            "path": str(ws_path),
            "git_head": _read_git_head(ws_path),
            "has_git": True,
        }

    def save_workspace(
        self,
        workspace_id: str,
        name: str,
        description: str = "",
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Записывает имя, описание и язык в config.json и README.md существующей папки пространства.

        Args:
            workspace_id: Идентификатор (имя папки) рабочего пространства.
            name: Отображаемое имя.
            description: Описание (пустая строка сохраняет прежнее значение).
            language: Основной язык рабочего пространства ('he', 'ru', 'en', 'ua').

        Returns:
            Dict[str, Any]: Обновлённое описание пространства.
        """
        ws_path = self.workspace_path(workspace_id)
        if not ws_path.is_dir():
            raise FileNotFoundError(f"Папка рабочего пространства не найдена: {ws_path}")
        (ws_path / "assets").mkdir(parents=True, exist_ok=True)
        norm_lang = normalize_workspace_language(language) if language else None
        cfg = self._load_config(ws_path)
        cfg["name"] = name or cfg.get("name") or workspace_id
        if description:
            cfg["description"] = description
        if norm_lang:
            cfg["language"] = norm_lang
        self._write_config(ws_path, cfg)

        # Синхронизация README.md
        readme_file = ws_path / "README.md"
        if readme_file.exists():
            parsed = parse_workspace_readme(readme_file)
            eff_lang = norm_lang or parsed.get("language") or cfg.get("language") or "ru"
            eff_name = name or parsed.get("name") or cfg.get("name") or workspace_id
            eff_desc = description if description else (parsed.get("description") or cfg.get("description", ""))
            readme_file.write_text(generate_workspace_readme(eff_name, eff_desc, eff_lang), encoding="utf-8")
        else:
            self.ensure_workspace_readme(ws_path, name=name, description=description, language=norm_lang)

        return self.get_workspace(workspace_id) or self._describe(ws_path, cfg)

    def delete_workspace(self, workspace_id: str) -> bool:
        """Удаляет рабочее пространство и его директорию с диска.

        Args:
            workspace_id: Идентификатор рабочего пространства.

        Returns:
            bool: True в случае успешного удаления.

        Raises:
            ValueError: При попытке path traversal или недопустимом имени.
            FileNotFoundError: Если директория пространства не найдена.
        """
        if not workspace_id or str(workspace_id).strip().startswith((".", "~")):
            raise ValueError(f"Недопустимый идентификатор рабочего пространства: {workspace_id}")

        clean_id = str(workspace_id).strip()
        if clean_id.lower() in SYSTEM_DATA_DIRS:
            raise ValueError(f"Запрещено удалять системный каталог: {clean_id}")
        ws_path = (self.workspaces_dir / clean_id).resolve()
        resolved_root = self.workspaces_dir.resolve()

        if not str(ws_path).startswith(str(resolved_root)) or ws_path == resolved_root:
            raise ValueError(f"Попытка выхода за пределы каталога рабочих пространств: {workspace_id}")

        if not ws_path.exists() or not ws_path.is_dir():
            raise FileNotFoundError(f"Папка рабочего пространства не найдена: {ws_path}")

        def _handle_remove_readonly(func: Any, path: str, exc: Any) -> None:
            try:
                os.chmod(path, stat.S_IWRITE)
                func(path)
            except Exception as err:
                logger.warning(f"[WorkspaceRegistry] Не удалось удалить файл/папку {path}: {err}")

        shutil.rmtree(ws_path, onerror=_handle_remove_readonly)
        logger.info(f"[WorkspaceRegistry] Рабочее пространство '{clean_id}' успешно удалено с диска: {ws_path}")
        return True

    # ------------------------------------------------------------------
    # Привязанные источники
    # ------------------------------------------------------------------

    def list_sources(self, workspace_id: str) -> List[Dict[str, Any]]:
        """Возвращает привязанные источники пространства с информацией об имени компьютера (новые первыми)."""
        ws_path = self.workspace_path(workspace_id)
        if not ws_path.is_dir():
            return []
        cur_host = get_current_host_name()
        sources = self._load_config(ws_path).get("sources", [])
        enriched: List[Dict[str, Any]] = []
        for s in sources:
            item = dict(s)
            raw_path = str(item.get("source_path", ""))
            s_host, local_p, qual_p = parse_host_qualified_path(raw_path, default_host=item.get("host_name"))
            item["host_name"] = s_host
            item["source_path"] = local_p
            item["qualified_path"] = item.get("qualified_path") or qual_p
            item["is_current_host"] = (s_host.upper() == cur_host.upper())
            enriched.append(item)
        return sorted(enriched, key=lambda s: s.get("created_at", ""), reverse=True)

    def add_source(
        self,
        workspace_id: str,
        source_type: str,
        source_path: str,
        name: str,
        auto_watch: bool = True,
        host_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Добавляет внешний источник (файл, папку или Google Таблицу) с привязкой к имени компьютера в config.json.

        Returns:
            Dict[str, Any]: Запись созданного источника с полями host_name и qualified_path.
        """
        ws_path = self.workspace_path(workspace_id)
        cfg = self._load_config(ws_path)
        now = _utc_now_iso()
        resolved_host, clean_local_path, qualified_path = parse_host_qualified_path(source_path, default_host=host_name)
        source = {
            "source_id": f"src_{uuid.uuid4().hex[:12]}",
            "workspace_id": workspace_id,
            "source_type": source_type,
            "host_name": resolved_host,
            "source_path": clean_local_path,
            "qualified_path": qualified_path,
            "is_current_host": (resolved_host.upper() == get_current_host_name().upper()),
            "name": name,
            "auto_watch": bool(auto_watch),
            "last_scanned_at": "",
            "item_count": 0,
            "status": "linked",
            "error_message": "",
            "created_at": now,
            "updated_at": now,
        }
        cfg["sources"].append(source)
        self._write_config(ws_path, cfg)
        return source

    def delete_source(self, workspace_id: str, source_id: str) -> bool:
        """Удаляет источник из config.json пространства.

        Returns:
            bool: True, если источник найден и удалён.
        """
        ws_path = self.workspace_path(workspace_id)
        if not ws_path.is_dir():
            return False
        cfg = self._load_config(ws_path)
        before = len(cfg["sources"])
        cfg["sources"] = [s for s in cfg["sources"] if s.get("source_id") != source_id]
        if len(cfg["sources"]) == before:
            return False
        self._write_config(ws_path, cfg)
        return True

    def update_source_status(
        self,
        workspace_id: str,
        source_id: str,
        status: str = "active",
        item_count: int = 0,
        error_message: str = "",
    ) -> bool:
        """Обновляет статус и результат последнего сканирования источника.

        Returns:
            bool: True, если источник найден и обновлён.
        """
        ws_path = self.workspace_path(workspace_id)
        if not ws_path.is_dir():
            return False
        cfg = self._load_config(ws_path)
        now = _utc_now_iso()
        for src in cfg["sources"]:
            if src.get("source_id") == source_id:
                src.update(
                    status=status,
                    item_count=item_count,
                    error_message=error_message,
                    last_scanned_at=now,
                    updated_at=now,
                )
                self._write_config(ws_path, cfg)
                return True
        return False
