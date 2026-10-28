# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Core - Git Maintenance Analyzer
# =============================================================================
# Description:
#   Интеллектуальный анализатор состояния Git-репозитория на основе измеряемых
#   метрик (loose objects, pack files, garbage, git fsck) с трехуровневой шкалой
#   принятия решений (НОРМА / НАБЛЮДЕНИЕ / ОБСЛУЖИВАНИЕ) и фиксацией активного
#   репозитория, текущей ветки, HEAD коммита и перечня доступных репозиториев.
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.core.git_maintenance_analyzer import GitMaintenanceAnalyzer
#
#     analyzer = GitMaintenanceAnalyzer()
#     diagnosis = analyzer.diagnose()
#     print(diagnosis.repo_name, diagnosis.current_branch, diagnosis.verdict)
#
# File: git_maintenance_analyzer.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 03:15:00
# =============================================================================

from __future__ import annotations
"""Интеллектуальный анализатор состояния и необходимости обслуживания Git."""

import datetime
import json
import os
import subprocess
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from logger import logger
from header import __root__
from apps.ai_assistant.core.workspace_registry import WorkspaceRegistry, resolve_workspaces_dir

DEFAULT_HISTORY_FILE = __root__ / "apps" / "ai_assistant" / "data" / "git_diagnostics_history.json"


class MaintenanceVerdict(str, Enum):
    """Шкала вердиктов о состоянии репозитория."""
    NORMAL = "NORMAL"                     # Норма (Ничего не делать)
    OBSERVATION = "OBSERVATION"           # Наблюдение (Повторить измерение)
    MAINTENANCE_REQUIRED = "MAINTENANCE"  # Обслуживание (Запустить gc --auto)


class RepoMetrics(BaseModel):
    """Снимок измеряемых показателей Git-репозитория."""
    repo_name: str = Field("", description="Название активного репозитория")
    repo_path: str = Field("", description="Абсолютный путь к рабочей копии")
    current_branch: str = Field("", description="Имя активной ветки")
    current_commit: str = Field("", description="Хэш текущего HEAD коммита")
    commit_message: str = Field("", description="Сообщение последнего коммита")
    is_clean: bool = Field(True, description="Чистая ли рабочая директория")
    loose_count: int = Field(0, description="Число отдельных loose-объектов")
    loose_size_kib: int = Field(0, description="Размер loose-объектов в КиБ")
    in_pack_count: int = Field(0, description="Число упакованных объектов")
    packs_count: int = Field(0, description="Число pack-файлов")
    pack_size_kib: int = Field(0, description="Размер pack-файлов в КиБ")
    prune_packable: int = Field(0, description="Число объектов, пригодных для prune")
    garbage_count: int = Field(0, description="Число мусорных объектов")
    garbage_size_kib: int = Field(0, description="Размер мусорных объектов в КиБ")
    dangling_count: int = Field(0, description="Число висячих ссылок (dangling)")
    connectivity_ok: bool = Field(True, description="Целостность связности объектов")
    maintenance_configured: bool = Field(False, description="Наличие настроек git maintenance")


class DiagnosisResult(BaseModel):
    """Результат комплексной диагностики состояния Git-репозитория."""
    timestamp: str = Field(..., description="Время проведения диагностики")
    repo_name: str = Field(..., description="Название активного репозитория")
    repo_path: str = Field(..., description="Абсолютный путь к активному репозиторию")
    current_branch: str = Field(..., description="Имя активной ветки")
    current_commit: str = Field(..., description="Хэш текущего HEAD коммита")
    verdict: MaintenanceVerdict = Field(..., description="Вердикт состояния (NORMAL/OBSERVATION/MAINTENANCE)")
    verdict_title: str = Field(..., description="Человекопонятный заголовок вердикта на русском")
    action_type: str = Field(..., description="Рекомендуемое действие (none / observe / gc_auto)")
    recommendation: str = Field(..., description="Краткая формулировка рекомендации")
    explanation: str = Field(..., description="Подробное объяснение решения на основе показателей")
    metrics: RepoMetrics = Field(..., description="Собранные метрики")
    available_repos: List[Dict[str, str]] = Field(default_factory=list, description="Список доступных репозиториев")


class GitMaintenanceAnalyzer:
    """Диагностический анализатор состояния репозитория Git."""

    # Пороговые значения мониторинга политики AI-Windows-Admin
    OBSERVATION_LOOSE_COUNT = 2500       # Наблюдение от 2500 объектов
    OBSERVATION_LOOSE_SIZE_KIB = 30720   # Наблюдение от 30 МиБ loose
    MAINTENANCE_LOOSE_COUNT = 6700       # Штатный порог Git GC ~6700 loose objects
    MAINTENANCE_LOOSE_SIZE_KIB = 61440   # Обслуживание от 60 МиБ loose

    def __init__(
        self,
        repo_path: Path | str = ".",
        history_path: Optional[Path | str] = None,
    ) -> None:
        """Инициализирует анализатор репозитория Git.

        Args:
            repo_path: Корневой путь Git-репозитория.
            history_path: Путь к файлу сохранения журнала диагностики.
        """
        self.repo_path = Path(repo_path).resolve()
        self.history_path = Path(history_path).resolve() if history_path else DEFAULT_HISTORY_FILE

    def _resolve_working_repo(self, custom_path: Optional[str | Path] = None) -> Path:
        """Определяет действительный абсолютный путь к целевому репозиторию."""
        if custom_path:
            p = Path(custom_path).resolve()
            if p.exists():
                return p
        return self.repo_path

    def _run_git(
        self,
        args: List[str],
        target_path: Optional[Path] = None,
        timeout_sec: int = 60,
        allow_stderr_fallback: bool = False,
    ) -> str:
        """Синхронно выполняет команду git с таймаутом."""
        cwd_path = Path(target_path or self.repo_path).resolve()
        if not cwd_path.exists() or not cwd_path.is_dir():
            return ""
        cwd = str(cwd_path)
        cmd = ["git"] + args
        git_env = os.environ.copy()
        git_env["GIT_PAGER"] = "cat"
        git_env["PAGER"] = "cat"
        try:
            res = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=git_env,
                timeout=timeout_sec,
            )
            if res.returncode != 0:
                if allow_stderr_fallback:
                    return ((res.stdout or "") + (("\n" + res.stderr) if res.stderr else "")).strip()
                return ""
            output = (res.stdout or "") + (("\n" + res.stderr) if (res.stderr and allow_stderr_fallback) else "")
            return output.strip()
        except Exception as exc:
            logger.warning(f"[GitMaintenanceAnalyzer] Ошибка git {' '.join(cmd)} в {cwd}: {exc}")
            return ""

    def get_repo_meta(self, custom_path: Optional[str | Path] = None) -> Dict[str, Any]:
        """Извлекает метаданные активного репозитория: корень, ветка, HEAD и статус.

        Args:
            custom_path: Опциональный путь к конкретному репозиторию.

        Returns:
            Dict[str, Any]: Словарь с метаданными репозитория.
        """
        target = self._resolve_working_repo(custom_path)
        top_level = self._run_git(["rev-parse", "--show-toplevel"], target_path=target)
        if top_level and Path(top_level).exists():
            real_root = Path(top_level).resolve()
        else:
            real_root = target

        repo_name = real_root.name
        branch = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"], target_path=real_root) or "HEAD"
        commit = self._run_git(["rev-parse", "--short", "HEAD"], target_path=real_root) or "0000000"
        commit_msg = self._run_git(["log", "-1", "--pretty=format:%s"], target_path=real_root)
        porcelain = self._run_git(["status", "--porcelain"], target_path=real_root)
        is_clean = len(porcelain.strip()) == 0

        return {
            "repo_name": repo_name,
            "repo_path": str(real_root).replace("\\", "/"),
            "current_branch": branch,
            "current_commit": commit,
            "commit_message": commit_msg or "Нет коммитов",
            "is_clean": is_clean,
        }

    def get_available_repos(self) -> List[Dict[str, str]]:
        """Находит все доступные Git-репозитории исключительно рабочих пространств из data/workspaces.

        Returns:
            List[Dict[str, str]]: Список репозиториев рабочих пространств.
        """
        repos: List[Dict[str, str]] = []

        # Поиск репозиториев исключительно рабочих пространств из data/workspaces
        for ws in WorkspaceRegistry(resolve_workspaces_dir()).list_workspaces():
            meta = self.get_repo_meta(ws["path"])
            repos.append({
                "id": f"ws-{ws['workspace_id']}",
                "name": f"Workspace: {ws['name']}",
                "path": ws["path"].replace("\\", "/"),
                "branch": meta["current_branch"],
                "commit": meta["current_commit"],
            })

        return repos

    def collect_metrics(self, custom_path: Optional[str | Path] = None) -> RepoMetrics:
        """Снимает текущие измеряемые показатели репозитория.

        Args:
            custom_path: Опциональный путь к конкретному репозиторию.

        Returns:
            RepoMetrics: Модель собранных показателей.
        """
        target = self._resolve_working_repo(custom_path)
        meta = self.get_repo_meta(target)

        # 1. Сбор метрик объектов через git count-objects -v
        raw_count = self._run_git(["count-objects", "-v"], target_path=target, timeout_sec=15)
        parsed: Dict[str, int] = {
            "count": 0,
            "size": 0,
            "in-pack": 0,
            "packs": 0,
            "size-pack": 0,
            "prune-packable": 0,
            "garbage": 0,
            "size-garbage": 0,
        }
        for line in raw_count.splitlines():
            parts = line.split(":", 1)
            if len(parts) == 2:
                k = parts[0].strip().lower()
                v = parts[1].strip()
                if k in parsed:
                    try:
                        parsed[k] = int(v)
                    except ValueError:
                        pass

        # 2. Проверка состояния git maintenance
        maint_cfg = self._run_git(["config", "--get-regexp", r"^maintenance\."], target_path=target, timeout_sec=5)
        maintenance_configured = bool(maint_cfg.strip())

        # 3. Быстрая проверка связности и dangling-объектов
        fsck_out = self._run_git(["fsck", "--connectivity-only"], target_path=target, timeout_sec=20)
        dangling_count = 0
        connectivity_ok = True
        for line in fsck_out.splitlines():
            if line.startswith("dangling "):
                dangling_count += 1
            elif "broken" in line.lower() or "missing" in line.lower() or "error:" in line.lower():
                connectivity_ok = False

        return RepoMetrics(
            repo_name=meta["repo_name"],
            repo_path=meta["repo_path"],
            current_branch=meta["current_branch"],
            current_commit=meta["current_commit"],
            commit_message=meta["commit_message"],
            is_clean=meta["is_clean"],
            loose_count=parsed["count"],
            loose_size_kib=parsed["size"],
            in_pack_count=parsed["in-pack"],
            packs_count=parsed["packs"],
            pack_size_kib=parsed["size-pack"],
            prune_packable=parsed["prune-packable"],
            garbage_count=parsed["garbage"],
            garbage_size_kib=parsed["size-garbage"],
            dangling_count=dangling_count,
            connectivity_ok=connectivity_ok,
            maintenance_configured=maintenance_configured,
        )

    def evaluate(self, metrics: RepoMetrics) -> DiagnosisResult:
        """Оценивает необходимость обслуживания по измеряемым показателям.

        Args:
            metrics: Снимок собранных показателей.

        Returns:
            DiagnosisResult: Вердикт, обоснование и рекомендация.
        """
        now_ts = datetime.datetime.now().isoformat()
        loose_mb = round(metrics.loose_size_kib / 1024, 2)
        pack_mb = round(metrics.pack_size_kib / 1024, 2)
        avail = self.get_available_repos()

        # 1. Проверка условия ТРЕБУЕТСЯ ОБСЛУЖИВАНИЕ (MAINTENANCE)
        if (
            metrics.loose_count >= self.MAINTENANCE_LOOSE_COUNT
            or metrics.loose_size_kib >= self.MAINTENANCE_LOOSE_SIZE_KIB
        ):
            reason_parts = []
            if metrics.loose_count >= self.MAINTENANCE_LOOSE_COUNT:
                reason_parts.append(
                    f"Число loose-объектов ({metrics.loose_count}) достигло порога Git GC ({self.MAINTENANCE_LOOSE_COUNT})"
                )
            if metrics.loose_size_kib >= self.MAINTENANCE_LOOSE_SIZE_KIB:
                reason_parts.append(
                    f"Размер loose-объектов ({loose_mb} МиБ) превысил допустимый лимит ({self.MAINTENANCE_LOOSE_SIZE_KIB // 1024} МиБ)"
                )

            return DiagnosisResult(
                timestamp=now_ts,
                repo_name=metrics.repo_name,
                repo_path=metrics.repo_path,
                current_branch=metrics.current_branch,
                current_commit=metrics.current_commit,
                verdict=MaintenanceVerdict.MAINTENANCE_REQUIRED,
                verdict_title="Требуется обслуживание",
                action_type="gc_auto",
                recommendation="Запустить git gc --auto",
                explanation=f"{'; '.join(reason_parts)}. Рекомендуется штатная упаковка loose-объектов через git gc --auto.",
                metrics=metrics,
                available_repos=avail,
            )

        # 2. Проверка условия НАБЛЮДЕНИЕ (OBSERVATION)
        is_observe_count = metrics.loose_count >= self.OBSERVATION_LOOSE_COUNT
        is_observe_size = metrics.loose_size_kib >= self.OBSERVATION_LOOSE_SIZE_KIB
        has_garbage = metrics.garbage_count > 0 or metrics.prune_packable > 50

        if is_observe_count or is_observe_size or has_garbage or not metrics.connectivity_ok:
            reasons = []
            if is_observe_count:
                reasons.append(f"Loose-объектов: {metrics.loose_count} (порог наблюдения: {self.OBSERVATION_LOOSE_COUNT})")
            if is_observe_size:
                reasons.append(f"Объем loose: {loose_mb} МиБ")
            if has_garbage:
                reasons.append(f"Обнаружен мусор: {metrics.garbage_count} шт / prune: {metrics.prune_packable}")
            if not metrics.connectivity_ok:
                reasons.append("Зафиксированы предупреждения целостности объектов")

            return DiagnosisResult(
                timestamp=now_ts,
                repo_name=metrics.repo_name,
                repo_path=metrics.repo_path,
                current_branch=metrics.current_branch,
                current_commit=metrics.current_commit,
                verdict=MaintenanceVerdict.OBSERVATION,
                verdict_title="Наблюдение",
                action_type="observe",
                recommendation="Повторить измерение",
                explanation=(
                    f"Показатели репозитория {metrics.repo_name} находятся в зоне внимания ({', '.join(reasons)}). "
                    f"Критический порог штатного GC ещё не достигнут. Рекомендуется наблюдать динамику роста."
                ),
                metrics=metrics,
                available_repos=avail,
            )

        # 3. Условие НОРМА (NORMAL)
        return DiagnosisResult(
            timestamp=now_ts,
            repo_name=metrics.repo_name,
            repo_path=metrics.repo_path,
            current_branch=metrics.current_branch,
            current_commit=metrics.current_commit,
            verdict=MaintenanceVerdict.NORMAL,
            verdict_title="Норма",
            action_type="none",
            recommendation="Ничего не делать",
            explanation=(
                f"Репозиторий {metrics.repo_name} ({metrics.current_branch}) компактен и оптимален: loose-объектов {metrics.loose_count} ({loose_mb} МиБ), "
                f"упаковано {pack_mb} МиБ в {metrics.packs_count} пак-файлах. "
                f"Штатная автосборка Git не требуется."
            ),
            metrics=metrics,
            available_repos=avail,
        )

    def diagnose(self, custom_path: Optional[str | Path] = None) -> DiagnosisResult:
        """Выполняет полный цикл: сбор метрик, оценку вердикта и запись в журнал.

        Args:
            custom_path: Опциональный путь к репозиторию.

        Returns:
            DiagnosisResult: Результат диагностики.
        """
        metrics = self.collect_metrics(custom_path)
        diagnosis = self.evaluate(metrics)
        self._record_history(diagnosis)
        return diagnosis

    def _record_history(self, diagnosis: DiagnosisResult, max_records: int = 50) -> None:
        """Сохраняет срез диагностики в локальный журнал истории."""
        try:
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            records: List[Dict[str, Any]] = []
            if self.history_path.exists():
                try:
                    with open(self.history_path, "r", encoding="utf-8") as f:
                        records = json.load(f)
                except Exception:
                    records = []

            records.insert(0, diagnosis.model_dump())
            records = records[:max_records]

            with open(self.history_path, "w", encoding="utf-8") as f:
                json.dump(records, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.warning(f"[GitMaintenanceAnalyzer] Ошибка записи журнала истории: {exc}")

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Возвращает историю предыдущих диагностических срезов."""
        if not self.history_path.exists():
            return []
        try:
            with open(self.history_path, "r", encoding="utf-8") as f:
                records = json.load(f)
            return records[:limit]
        except Exception:
            return []

    def run_gc_auto(self, custom_path: Optional[str | Path] = None) -> Dict[str, Any]:
        """Запускает штатную команду git gc --auto, принимающую решение по встроенным порогам Git.

        Returns:
            Dict[str, Any]: Результат запуска команды и обновленный диагноз.
        """
        target = self._resolve_working_repo(custom_path)
        logger.console(f"[GitMaintenanceAnalyzer] Запуск штатного обслуживания: git gc --auto в {target}...")
        start_ts = datetime.datetime.now()
        output = self._run_git(["gc", "--auto"], target_path=target, timeout_sec=120, allow_stderr_fallback=True)
        elapsed = round((datetime.datetime.now() - start_ts).total_seconds(), 2)

        new_diagnosis = self.diagnose(target)
        return {
            "success": True,
            "command": "git gc --auto",
            "elapsed_sec": elapsed,
            "output": output or "Штатный gc --auto выполнен (условия проверены Git).",
            "diagnosis": new_diagnosis.model_dump(),
        }

    def run_fsck(self, custom_path: Optional[str | Path] = None) -> Dict[str, Any]:
        """Запускает полную проверку доступности и целостности объектов git fsck --full.

        Returns:
            Dict[str, Any]: Результат проверки fsck.
        """
        target = self._resolve_working_repo(custom_path)
        logger.console(f"[GitMaintenanceAnalyzer] Запуск проверки целостности: git fsck --full в {target}...")
        start_ts = datetime.datetime.now()
        output = self._run_git(["fsck", "--full"], target_path=target, timeout_sec=180, allow_stderr_fallback=True)
        elapsed = round((datetime.datetime.now() - start_ts).total_seconds(), 2)

        has_errors = "error:" in output.lower() or "fatal:" in output.lower()
        return {
            "success": not has_errors,
            "elapsed_sec": elapsed,
            "output": output or "Все объекты репозитория целостны.",
            "has_errors": has_errors,
        }


# Глобальный экземпляр анализатора
git_maintenance_analyzer = GitMaintenanceAnalyzer()
