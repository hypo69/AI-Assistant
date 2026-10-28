# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant API - Router Knowledge & QA
# =============================================================================
# Description:
#   REST API маршрутизатор мультиязычной системы извлечения знаний, управления
#   рабочими областями (с индивидуальным Git), импорта документов, проверки фактов,
#   FAISS-индексации и интеллектуального поиска ответов (ТЗ раздел 8).
#
# Usage Examples:
#   FastAPI Endpoint:
#     POST /api/v1/workspaces/seed-demo
#     POST /api/v1/documents/import
#     POST /api/v1/ask
#     GET  /api/v1/facts
#     GET  /api/v1/language-modules
#
# File: router_knowledge.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 20:02:00
# =============================================================================

from __future__ import annotations
"""REST API роутер управления рабочими областями, фактами и вопросно-ответной системой."""

import asyncio, json
from fastapi.responses import StreamingResponse
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from logger import logger
from apps.ai_assistant.core.qa_engine import KnowledgeQAEngine
from apps.ai_assistant.core.workspace_manager import WorkspaceManager

router = APIRouter(prefix="/api/v1", tags=["Multilingual Knowledge & Workspaces"])

# Единый экземпляр менеджера рабочих областей и QA-движка
_workspace_manager = WorkspaceManager()
_qa_engine = KnowledgeQAEngine(workspace_manager=_workspace_manager)


def _resolve_target_workspace(workspace_id: Optional[str] = None) -> Optional[str]:
    """Разрешает идентификатор рабочего пространства: переданный -> активный -> первый доступный."""
    if workspace_id:
        return workspace_id
    active = _workspace_manager.store.get_active_workspace_id()
    if active:
        return active
    all_ws = _workspace_manager.list_workspaces()
    if all_ws and all_ws[0].get("workspace_id"):
        return all_ws[0]["workspace_id"]
    return None


class WorkspaceCreateRequest(BaseModel):
    """Запрос на создание или выбор рабочей области."""
    workspace_id: str = Field(..., description="Уникальный идентификатор рабочей области (например, my_docs)")
    name: str = Field(..., description="Отображаемое название рабочей области")
    description: str = Field("", description="Описание рабочей области")
    language: Optional[str] = Field("ru", description="Основной язык рабочего пространства ('he', 'ru', 'en', 'uk')")


class DocumentImportRequest(BaseModel):
    """Запрос на импорт или сохранение документа в рабочей области."""
    workspace_id: Optional[str] = Field(None, description="Идентификатор рабочей области")
    document_id: str = Field(..., description="Имя файла (например, mama.txt или farm.txt)")
    content: str = Field(..., description="Текстовое содержимое документа")
    commit_message: Optional[str] = Field(None, description="Сообщение коммита Git")
    language: Optional[str] = Field(None, description="Язык документа ('ru', 'he', 'en') или автоопределение")
    force_reanalyze: bool = Field(False, description="Принудительно пересчитать факты")


class ReanalyzeRequest(BaseModel):
    """Запрос на повторный анализ документа."""
    workspace_id: Optional[str] = Field(None, description="Идентификатор рабочей области")
    document_id: str = Field(..., description="Идентификатор документа")


class FactStatusUpdateRequest(BaseModel):
    """Запрос на изменение статуса проверки факта."""
    status: str = Field(..., description="Новый статус: extracted, validated, ambiguous, rejected, stale")


class AskQuestionRequest(BaseModel):
    """Запрос на получение грамматически точного ответа по базе знаний (ТЗ п. 8)."""
    question: str = Field(..., description="Вопрос на естественном языке")
    workspace_id: Optional[str] = Field(None, description="Идентификатор рабочей области")
    language: Optional[str] = Field(None, description="Язык вопроса ('ru', 'he', 'en') или автоопределение")
    mode: str = Field("local_first", description="Режим: local_only, local_first, cloud_assist, cloud_enrich")
    provider: Optional[str] = Field("gemini", description="Провайдер из модуля src/ai (gemini, agy, openai, ollama)")
    model: Optional[str] = Field("gemini-3.1-flash-lite", description="Идентификатор модели ИИ")


class RagQueryRequest(BaseModel):
    """Запрос семантического и фактологического поиска RAG по пользовательскому пространству."""
    query: str = Field(..., description="Вопрос или поисковый запрос к базе знаний")
    workspace_id: Optional[str] = Field(None, description="Идентификатор рабочей области (по умолчанию активная)")
    top_k: int = Field(5, ge=1, le=50, description="Количество релевантных источников")
    mode: str = Field("local_first", description="Режим обработки: local_only, local_first, cloud_assist, cloud_enrich")
    provider: Optional[str] = Field(None, description="Провайдер ИИ")
    model: Optional[str] = Field(None, description="Модель ИИ")
    language: Optional[str] = Field(None, description="Язык вопроса ('ru', 'en', 'he') или автоопределение")


class FaissRebuildRequest(BaseModel):
    """Запрос на перестроение индекса FAISS."""
    workspace_id: Optional[str] = Field(None, description="Идентификатор рабочей области")


class LinkSourceRequest(BaseModel):
    """Запрос на связывание файла, папки или Google Таблицы с рабочей областью."""
    target: str = Field(..., description="Путь на диске (файл или папка) или ссылка на Google Таблицу")
    name: Optional[str] = Field(None, description="Отображаемое имя источника")
    auto_watch: bool = Field(True, description="Автоматически отслеживать при синхронизации")


class SyncSourcesRequest(BaseModel):
    """Запрос на синхронизацию связанных источников."""
    force_reanalyze: bool = Field(False, description="Принудительно повторно пересчитать факты")


class ExtractPreviewRequest(BaseModel):
    """Запрос на предпросмотр извлечения контента из файла или ссылки."""
    target: str = Field(..., description="Путь к файлу на компьютере или URL Google Таблицы")
    language: Optional[str] = Field("ru", description="Язык для аудио транскрибации")


class AddWorkspaceItemsRequest(BaseModel):
    """Запрос на добавление файлов и папок в рабочую область с мгновенным Git-отслеживанием."""
    items: List[str] = Field(..., description="Список путей к файлам или директориям на диске")
    copy_to_workspace: bool = Field(False, description="Копировать файлы в репозиторий рабочей области (True) или следить за файлами на диске без копирования (False, по умолчанию)")
    commit_message: Optional[str] = Field(None, description="Сообщение коммита Git")
    pdf_mode: str = Field("local", description="Режим конвертации PDF: local, model или raw")
    ocr_mode: str = Field("model", description="Режим OCR изображений: local, model или raw")
    audio_mode: str = Field("model", description="Режим транскрибации аудио: model или raw (сохранить сырой аудиофайл)")


class OpenWorkspaceFileRequest(BaseModel):
    """Запрос на открытие файла рабочей области в системном редакторе по умолчанию."""
    rel_path: str = Field(..., description="Относительный путь к файлу внутри рабочей области")


class CreateWorkspaceItemRequest(BaseModel):
    """Запрос на создание нового файла или директории в рабочей области."""
    rel_path: str = Field(..., description="Относительный путь к создаваемому объекту")
    is_dir: bool = Field(False, description="Признак каталога (True для папки, False для файла)")
    content: Optional[str] = Field("", description="Начальный текст файла")


class DeleteWorkspaceItemRequest(BaseModel):
    """Запрос на удаление файла или папки из рабочей области."""
    rel_path: str = Field(..., description="Относительный путь к удаляемому объекту")


class SaveWorkspaceFileContentRequest(BaseModel):
    """Запрос на сохранение текста файла в рабочей области."""
    rel_path: str = Field(..., description="Относительный путь к файлу")
    content: str = Field(..., description="Текстовое содержимое файла")
    commit_message: Optional[str] = Field(None, description="Сообщение коммита Git")


class MoveWorkspaceItemRequest(BaseModel):
    """Запрос на перенос или переименование файла без потери истории и рекомендаций."""
    old_rel_path: str = Field(..., description="Текущий относительный путь к файлу")
    new_rel_path: str = Field(..., description="Новый относительный путь к файлу")
    commit_message: Optional[str] = Field(None, description="Сообщение коммита Git")


class ReviseVirtualTreeRequest(BaseModel):
    """Запрос на ревизию и переоценку виртуальных категорий по содержимому файлов."""
    strategy: str = Field("semantic_domain", description="Стратегия построения категорий: semantic_domain, fact_semantics, entity_centric")
    instruction: str = Field("", description="Дополнительный критерий или правило группировки для модели ИИ")
    use_model: bool = Field(True, description="Использовать ли ИИ-модель (UnifiedChatModel) с fallback на семантический классификатор")
    provider: str = Field("gemini", description="Провайдер модели ИИ")
    model: str = Field("gemini-2.5-flash", description="Имя модели ИИ")


class WorkspaceActivateRequest(BaseModel):
    """Запрос на переключение активного рабочего пространства."""
    workspace_id: str = Field(..., description="Идентификатор рабочей области для активации")


class TelegramScenarioTriggerRequest(BaseModel):
    """Запрос на запуск специального сценария Telegram-бота для рабочего пространства דוד משה."""
    workspace_id: Optional[str] = Field(None, description="Идентификатор рабочего пространства (по умолчанию דוד_משה)")
    trigger_file_name: Optional[str] = Field(None, description="Имя входного файла или сообщения (שיחה בין דוד משה לשמוליק)")
    trigger_source: str = Field("telegram_bot", description="Источник запуска сценария (telegram_bot или webgui)")
    delay_seconds: Optional[float] = Field(None, description="Длительность спиннера в секундах (из config.json по умолчанию 10)")
    wait_for_completion: bool = Field(False, description="Ожидать ли завершения 10-секундной задержки синхронно")


@router.get("/workspaces/telegram-scenario/status", summary="Статус специального сценария Telegram-бота для דוד משה")
async def get_telegram_scenario_status() -> Dict[str, Any]:
    """Возвращает текущее состояние сценария (idle, processing со спиннером или completed с добавленным файлом)."""
    state = await _workspace_manager.scenario_service.get_status(_workspace_manager)
    cfg = _workspace_manager.scenario_service.load_scenario_config()
    return {
        "status": "ok",
        "scenario": state,
        "config": cfg,
    }


@router.post("/workspaces/telegram-scenario/trigger", summary="Запуск специального сценария Telegram-бота (10 сек спиннер -> добавление файла)")
async def trigger_telegram_scenario(req: Optional[TelegramScenarioTriggerRequest] = None) -> Dict[str, Any]:
    """Запускает 10-секундный спиннер и добавляет целевой файл שיחה בין דוד משה לשמוליק.md в рабочую область דוד משה."""
    payload = req or TelegramScenarioTriggerRequest()
    state = await _workspace_manager.scenario_service.trigger_scenario(
        wm=_workspace_manager,
        workspace_id=payload.workspace_id,
        trigger_source=payload.trigger_source,
        trigger_file_name=payload.trigger_file_name,
        delay_seconds=payload.delay_seconds,
        wait_for_completion=payload.wait_for_completion,
    )
    return {
        "status": "ok",
        "scenario": state,
    }


@router.get("/workspaces/active", summary="Получение текущего активного рабочего пространства")
async def get_active_workspace() -> Dict[str, Any]:
    """Возвращает метаданные последнего открытого рабочего пространства из конфига."""
    try:
        active_id = _workspace_manager.get_active_workspace_id()
        if not active_id:
            return {"status": "ok", "workspace_id": None, "workspace": None}
        ws = _workspace_manager.get_workspace(active_id)
        if not ws:
            return {"status": "ok", "workspace_id": None, "workspace": None}
        return {
            "status": "ok",
            "workspace_id": active_id,
            "workspace": ws,
        }
    except Exception as exc:
        logger.error(f"[RouterKnowledge] Ошибка получения активного пространства: {exc}")
        return {"status": "ok", "workspace_id": None, "workspace": None}


@router.post("/workspaces/active", summary="Установка активного рабочего пространства")
async def set_active_workspace(req: WorkspaceActivateRequest) -> Dict[str, Any]:
    """Фиксирует выбранное рабочее пространство (папку workspaces/<id>) как последнее активное в конфиге."""
    ws = _workspace_manager.get_workspace(req.workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail=f"Рабочая область '{req.workspace_id}' не найдена")
    _workspace_manager.set_active_workspace(req.workspace_id)
    return {
        "status": "ok",
        "workspace_id": req.workspace_id,
        "workspace": ws,
        "message": f"Рабочая область '{ws.get('name', req.workspace_id)}' успешно активирована",
    }


@router.get("/workspaces", summary="Список рабочих областей")
async def list_workspaces() -> Dict[str, Any]:
    """Возвращает рабочие области, найденные сканированием каталога workspaces/, со статистикой."""
    try:
        workspaces = _workspace_manager.list_workspaces()
        return {"status": "ok", "count": len(workspaces), "workspaces": workspaces}
    except Exception as exc:
        logger.error(f"[RouterKnowledge] Ошибка при получении списка рабочих областей: {exc}")
        try:
            fallback = _workspace_manager.registry.list_workspaces()
            return {"status": "ok", "count": len(fallback), "workspaces": fallback}
        except Exception as inner_exc:
            logger.error(f"[RouterKnowledge] Сбой fallback получения областей: {inner_exc}")
            return {"status": "ok", "count": 0, "workspaces": []}


@router.get("/workspaces/{workspace_id}/folder-status", summary="Статус рабочей папки на диске и Git")
async def get_workspace_folder_status(workspace_id: str) -> Dict[str, Any]:
    """Проверяет физическое наличие папки на диске, наличие .git и количество файлов."""
    status_info = _workspace_manager.check_workspace_folder(workspace_id)
    return {"status": "ok", "folder_status": status_info}


@router.post("/workspaces/{workspace_id}/ensure-folder", summary="Гарантированное создание рабочей папки и Git")
async def ensure_workspace_folder(workspace_id: str) -> Dict[str, Any]:
    """Создаёт папку рабочей области на диске и инициализирует Git-репозиторий при отсутствии."""
    try:
        status_info = _workspace_manager.ensure_workspace_folder(workspace_id)
        return {"status": "ok", "folder_status": status_info}
    except Exception as exc:
        logger.error(f"[RouterKnowledge] Ошибка создания папки рабочей области {workspace_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/workspaces", summary="Создание или выбор рабочей области с Git")
async def create_workspace(req: WorkspaceCreateRequest) -> Dict[str, Any]:
    """Создаёт или открывает рабочую область и инициализирует в ней Git-репозиторий."""
    try:
        ws = _workspace_manager.create_or_select_workspace(
            workspace_id=req.workspace_id,
            name=req.name,
            description=req.description,
            language=req.language or "ru",
        )
        # Если в папке уже есть файлы — сканируем и индексируем их
        scan_info = _workspace_manager.scan_and_index_workspace(ws["workspace_id"])
        return {"status": "ok", "workspace": ws, "scan": scan_info}
    except Exception as exc:
        logger.error(f"[RouterKnowledge] Ошибка создания рабочей области: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/workspaces/{workspace_id}", summary="Удаление рабочего пространства")
async def delete_workspace(workspace_id: str) -> Dict[str, Any]:
    """Удаляет рабочую область и все связанные локальные файлы и историю Git."""
    try:
        res = _workspace_manager.delete_workspace(workspace_id)
        return res
    except FileNotFoundError as fnf:
        raise HTTPException(status_code=404, detail=str(fnf))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        logger.error(f"[RouterKnowledge] Ошибка удаления рабочего пространства {workspace_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


def _open_folder_dialog(initial_dir: Optional[str] = None) -> str:
    """Открывает нативное окно Tkinter для выбора папки на диске."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        folder = filedialog.askdirectory(
            initialdir=initial_dir or None,
            title="Выберите рабочую директорию на компьютере"
        )
        root.destroy()
        return folder or ""
    except Exception as dialog_err:
        logger.warning(f"[browse_folder] Ошибка вызова Tkinter диалога: {dialog_err}")
        return ""


def _open_file_dialog(initial_dir: Optional[str] = None) -> str:
    """Открывает нативное окно Tkinter для выбора файла на диске."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        selected_file = filedialog.askopenfilename(
            initialdir=initial_dir or None,
            title="Выберите файл на компьютере для отслеживания"
        )
        root.destroy()
        return selected_file or ""
    except Exception as dialog_err:
        logger.warning(f"[browse_file] Ошибка вызова Tkinter диалога: {dialog_err}")
        return ""


@router.post("/workspaces/browse-folder", summary="Диалоговое окно выбора директории на компьютере")
async def browse_workspace_folder(initial_dir: Optional[str] = Query(None, description="Начальная директория")) -> Dict[str, Any]:
    """Открывает на компьютере системный диалог выбора директории и возвращает выбранный путь."""
    loop = asyncio.get_running_loop()
    try:
        selected_path = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: _open_folder_dialog(initial_dir)),
            timeout=60.0
        )
        if selected_path:
            return {"status": "ok", "path": selected_path}
        return {"status": "cancelled", "path": ""}
    except asyncio.TimeoutError:
        return {"status": "timeout", "path": ""}
    except Exception as exc:
        logger.error(f"[browse_folder] Сбой открытия диалога: {exc}")
        return {"status": "error", "message": str(exc), "path": ""}


@router.post("/workspaces/browse-file", summary="Диалоговое окно выбора файла на компьютере")
async def browse_workspace_file(initial_dir: Optional[str] = Query(None, description="Начальная директория")) -> Dict[str, Any]:
    """Открывает на компьютере системный диалог выбора файла и возвращает выбранный путь."""
    loop = asyncio.get_running_loop()
    try:
        selected_file_path = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: _open_file_dialog(initial_dir)),
            timeout=60.0
        )
        if selected_file_path:
            return {"status": "ok", "path": selected_file_path}
        return {"status": "cancelled", "path": ""}
    except asyncio.TimeoutError:
        return {"status": "timeout", "path": ""}
    except Exception as exc:
        logger.error(f"[browse_file] Сбой открытия диалога: {exc}")
        return {"status": "error", "message": str(exc), "path": ""}


@router.post("/workspaces/seed-demo", summary="Заполнение демо-примерами из ТЗ (RU + HE)")
async def seed_demo(workspace_id: str = Query("default", description="Целевая рабочая область")) -> Dict[str, Any]:
    """Создаёт эталонные документы mama.txt, farm.txt и frame_he.txt, коммитит в Git и извлекает факты."""
    try:
        res = _workspace_manager.seed_demo_workspace(workspace_id=workspace_id)
        return {"status": "ok", **res}
    except Exception as exc:
        logger.error(f"[RouterKnowledge] Ошибка инициализации демо-данных: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/workspaces/{workspace_id}/documents", summary="Список документов рабочей области")
async def list_workspace_documents(workspace_id: str) -> Dict[str, Any]:
    """Возвращает список проиндексированных документов выбранной рабочей области."""
    docs = _workspace_manager.store.list_documents(workspace_id)
    return {"status": "ok", "workspace_id": workspace_id, "count": len(docs), "documents": docs}


@router.get("/workspaces/{workspace_id}/commits", summary="История коммитов Git рабочей области")
async def list_workspace_commits(
    workspace_id: str,
    file_path: Optional[str] = Query(None, description="Фильтр по файлу"),
    limit: int = Query(30, ge=1, le=200),
) -> Dict[str, Any]:
    """Возвращает коммиты индивидуального Git-репозитория рабочей области."""
    commits = await _workspace_manager.get_workspace_commits(workspace_id, file_path=file_path, limit=limit)
    return {"status": "ok", "workspace_id": workspace_id, "count": len(commits), "commits": commits}


@router.post("/documents/import", summary="Импорт/обновление документа с коммитом в Git и извлечением фактов")
async def import_document(req: DocumentImportRequest) -> Dict[str, Any]:
    """Сохраняет файл в рабочей области, создаёт коммит в Git и извлекает структурированные факты."""
    target_ws = _resolve_target_workspace(req.workspace_id)
    if not target_ws:
        raise HTTPException(status_code=400, detail="Рабочее пространство не выбрано")
    try:
        res = _workspace_manager.import_document(
            workspace_id=target_ws,
            document_id=req.document_id,
            content=req.content,
            commit_message=req.commit_message,
            language=req.language,
            force_reanalyze=req.force_reanalyze,
        )
        return res
    except Exception as exc:
        logger.error(f"[RouterKnowledge] Ошибка импорта документа {req.document_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/workspaces/{workspace_id}/sources", summary="Привязка файла, папки или Google Таблицы к рабочей области")
async def link_workspace_source(workspace_id: str, req: LinkSourceRequest) -> Dict[str, Any]:
    """Связывает внешний файл/директорию на компьютере или ссылку Google Таблицы с рабочей областью."""
    try:
        source = _workspace_manager.link_source(
            workspace_id=workspace_id,
            target=req.target,
            name=req.name,
            auto_watch=req.auto_watch,
        )
        return {"status": "ok", "workspace_id": workspace_id, "source": source}
    except Exception as exc:
        logger.error(f"[RouterKnowledge] Ошибка привязки источника {req.target}: {exc}")
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/workspaces/{workspace_id}/sources", summary="Список связанных источников рабочей области")
async def list_workspace_sources(workspace_id: str) -> Dict[str, Any]:
    """Возвращает список всех связанных файлов, папок и Google Таблиц для рабочей области."""
    sources = _workspace_manager.list_sources(workspace_id)
    return {"status": "ok", "workspace_id": workspace_id, "count": len(sources), "sources": sources}


@router.delete("/workspaces/{workspace_id}/sources/{source_id}", summary="Удаление привязки источника")
async def unlink_workspace_source(workspace_id: str, source_id: str) -> Dict[str, Any]:
    """Удаляет привязку внешнего источника к рабочей области."""
    success = _workspace_manager.unlink_source(workspace_id, source_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Источник '{source_id}' не найден")
    return {"status": "ok", "workspace_id": workspace_id, "source_id": source_id, "deleted": True}


@router.get("/workspaces/{workspace_id}/sources/changes", summary="Инкрементальная проверка изменений во внешних источниках")
async def get_workspace_sources_changes(workspace_id: str) -> Dict[str, Any]:
    """Проверяет mtime и размер всех привязанных файлов/папок без повторного парсинга."""
    return await asyncio.to_thread(_workspace_manager.detect_changed_linked_sources, workspace_id)


@router.post("/workspaces/{workspace_id}/sources/sync", summary="Синхронизация и индексация связанных источников")
async def sync_workspace_sources(workspace_id: str, req: Optional[SyncSourcesRequest] = None) -> Dict[str, Any]:
    """Синхронизирует связанные источники: конвертирует PDF, Excel, Audio, DOCX и индексирует в базе знаний без копирования файлов."""
    try:
        force = req.force_reanalyze if req else False
        report = await _workspace_manager.sync_linked_sources(workspace_id=workspace_id, force_reanalyze=force)
        return report
    except Exception as exc:
        logger.error(f"[RouterKnowledge] Ошибка синхронизации источников {workspace_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/workspaces/{workspace_id}/directory-contents", summary="Содержимое директории, за которой следит Git")
async def get_workspace_directory_contents(workspace_id: str) -> Dict[str, Any]:
    """Возвращает детальное содержимое директории рабочей области со статусом отслеживания Git."""
    try:
        return _workspace_manager.get_directory_contents(workspace_id)
    except Exception as exc:
        logger.error(f"[RouterKnowledge] Ошибка получения содержимого папки {workspace_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/workspaces/{workspace_id}/virtual-tree", summary="Виртуальное дерево всех отслеживаемых файлов по содержимому")
async def get_workspace_virtual_tree(workspace_id: str) -> Dict[str, Any]:
    """Возвращает объединённое виртуальное дерево локальных и внешних файлов, сгруппированное по семантическим категориям содержимого."""
    try:
        return _workspace_manager.get_virtual_tree(workspace_id)
    except Exception as exc:
        logger.error(f"[RouterKnowledge] Ошибка построения виртуального дерева {workspace_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/workspaces/{workspace_id}/virtual-tree/revise", summary="Ревизия и переоценка виртуальных категорий по содержимому")
async def revise_workspace_virtual_tree(
    workspace_id: str,
    req: Optional[ReviseVirtualTreeRequest] = None,
) -> Dict[str, Any]:
    """Переоценивает содержимое всех файлов (локальных и внешних) и перестраивает логику виртуальных категорий."""
    try:
        strategy = req.strategy if req else "semantic_domain"
        instruction = req.instruction if req else ""
        use_model = req.use_model if req is not None else True
        provider = req.provider if req else "gemini"
        model_name = req.model if req else "gemini-2.5-flash"
        return await _workspace_manager.revise_virtual_tree(
            workspace_id=workspace_id,
            strategy=strategy,
            instruction=instruction,
            use_model=use_model,
            provider=provider,
            model_name=model_name,
        )
    except Exception as exc:
        logger.error(f"[RouterKnowledge] Ошибка ревизии виртуального дерева {workspace_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/workspaces/{workspace_id}/open-file", summary="Открытие файла в редакторе по умолчанию у пользователя")
async def open_workspace_file(workspace_id: str, req: OpenWorkspaceFileRequest) -> Dict[str, Any]:
    """Открывает указанный файл рабочей области в ассоциированном приложении / редакторе по умолчанию."""
    try:
        return _workspace_manager.open_workspace_file(workspace_id, req.rel_path)
    except FileNotFoundError as fnf:
        raise HTTPException(status_code=404, detail=str(fnf))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        logger.error(f"[RouterKnowledge] Ошибка открытия файла '{req.rel_path}' в {workspace_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/workspaces/{workspace_id}/items/create", summary="Создание файла или папки с фиксацией в Git")
async def create_workspace_item_endpoint(workspace_id: str, req: CreateWorkspaceItemRequest) -> Dict[str, Any]:
    """Создаёт новый файл или каталог в рабочей области и коммитит изменения в Git."""
    try:
        return _workspace_manager.create_workspace_item(
            workspace_id=workspace_id,
            rel_path=req.rel_path,
            is_dir=req.is_dir,
            content=req.content or "",
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        logger.error(f"[RouterKnowledge] Ошибка создания объекта {req.rel_path} в {workspace_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/workspaces/{workspace_id}/items", summary="Удаление файла или папки с фиксацией в Git")
async def delete_workspace_item_endpoint(
    workspace_id: str,
    rel_path: str = Query(..., description="Относительный путь к удаляемому объекту"),
) -> Dict[str, Any]:
    """Удаляет файл или директорию из рабочей области и сохраняет коммит в Git."""
    try:
        return _workspace_manager.delete_workspace_item(workspace_id=workspace_id, rel_path=rel_path)
    except FileNotFoundError as fnf:
        raise HTTPException(status_code=404, detail=str(fnf))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        logger.error(f"[RouterKnowledge] Ошибка удаления объекта {rel_path} в {workspace_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/workspaces/{workspace_id}/items/move", summary="Перемещение или переименование файла с git mv и сохранением связей базы знаний")
async def move_workspace_item_endpoint(
    workspace_id: str,
    req: MoveWorkspaceItemRequest,
) -> Dict[str, Any]:
    """Перемещает или переименовывает файл с распознаванием Git R100 и бесшовной миграцией фактов и векторов."""
    try:
        return _workspace_manager.move_workspace_item(
            workspace_id=workspace_id,
            old_rel_path=req.old_rel_path,
            new_rel_path=req.new_rel_path,
            commit_message=req.commit_message,
        )
    except FileNotFoundError as fnf:
        raise HTTPException(status_code=404, detail=str(fnf))
    except (ValueError, FileExistsError) as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        logger.error(f"[RouterKnowledge] Ошибка перемещения объекта {req.old_rel_path} -> {req.new_rel_path} в {workspace_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/workspaces/{workspace_id}/file-content", summary="Чтение содержимого файла рабочей области")
async def get_workspace_file_content_endpoint(
    workspace_id: str,
    rel_path: str = Query(..., description="Относительный путь к файлу"),
) -> Dict[str, Any]:
    """Возвращает текущее текстовое содержимое файла из рабочей области."""
    try:
        return _workspace_manager.get_workspace_file_content(workspace_id=workspace_id, rel_path=rel_path)
    except FileNotFoundError as fnf:
        raise HTTPException(status_code=404, detail=str(fnf))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        logger.error(f"[RouterKnowledge] Ошибка чтения содержимого {rel_path} в {workspace_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/workspaces/{workspace_id}/file-content", summary="Сохранение содержимого файла с коммитом в Git")
async def save_workspace_file_content_endpoint(
    workspace_id: str,
    req: SaveWorkspaceFileContentRequest,
) -> Dict[str, Any]:
    """Записывает отредактированный текст в файл рабочей области и создаёт коммит в Git."""
    try:
        return _workspace_manager.save_workspace_file_content(
            workspace_id=workspace_id,
            rel_path=req.rel_path,
            content=req.content,
            commit_message=req.commit_message,
        )
    except FileNotFoundError as fnf:
        raise HTTPException(status_code=404, detail=str(fnf))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        logger.error(f"[RouterKnowledge] Ошибка сохранения файла {req.rel_path} в {workspace_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/workspaces/{workspace_id}/items", summary="Добавление файлов и директорий с немедленным отслеживанием Git")
async def add_workspace_items(workspace_id: str, req: AddWorkspaceItemsRequest) -> Dict[str, Any]:
    """Добавляет директории и/или файлы в рабочую область с опциями конвертации PDF, OCR и аудио."""
    try:
        scen_srv = _workspace_manager.scenario_service
        if scen_srv.is_david_moshe_workspace(workspace_id) and any(scen_srv.is_trigger_file(p) for p in req.items):
            cfg = scen_srv.load_scenario_config()
            target_p = cfg.get("target_file_path")
            # Если пользователь ввёл короткое имя שיחה בין דוד משה לשמוליק без полного пути — запускаем 10-сек сценарий
            from pathlib import Path as _Path
            has_unresolved_trigger = any(
                scen_srv.is_trigger_file(p) and not _Path(str(p).strip()).exists()
                for p in req.items
            )
            if has_unresolved_trigger and target_p:
                scen_state = await scen_srv.trigger_scenario(
                    wm=_workspace_manager,
                    workspace_id=workspace_id,
                    trigger_source="webgui_items",
                    trigger_file_name=req.items[0],
                    wait_for_completion=False,
                )
                return {
                    "status": "scenario_triggered",
                    "workspace_id": workspace_id,
                    "files_added": 1,
                    "scenario": scen_state,
                    "message": f"Запущен сценарий דוד משה (10 сек): {target_p}",
                }

        res = await _workspace_manager.add_items_to_workspace(
            workspace_id=workspace_id,
            paths=req.items,
            copy_to_workspace=req.copy_to_workspace,
            commit_message=req.commit_message,
            pdf_mode=req.pdf_mode,
            ocr_mode=req.ocr_mode,
            audio_mode=req.audio_mode,
        )
        return res
    except Exception as exc:
        logger.error(f"[RouterKnowledge] Ошибка добавления объектов в рабочую область {workspace_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/workspaces/{workspace_id}/files/upload", summary="Загрузка файлов с немедленным отслеживанием Git")
async def upload_workspace_files(
    workspace_id: str,
    files: List[UploadFile] = File(...),
    commit_message: Optional[str] = Form(None),
    pdf_mode: str = Form("local"),
    ocr_mode: str = Form("model"),
    audio_mode: str = Form("model"),
) -> Dict[str, Any]:
    """Загружает файлы в рабочую область с опциями конвертации (PDF, OCR, аудио) и коммитит их в Git."""
    try:
        files_data = []
        for f in files:
            content_bytes = await f.read()
            files_data.append((f.filename or "uploaded_file", content_bytes))

        scen_srv = _workspace_manager.scenario_service
        if scen_srv.is_david_moshe_workspace(workspace_id) and any(scen_srv.is_trigger_file(fn) for fn, _ in files_data):
            trig_name = next((fn for fn, _ in files_data if scen_srv.is_trigger_file(fn)), files_data[0][0])
            scen_state = await scen_srv.trigger_scenario(
                wm=_workspace_manager,
                workspace_id=workspace_id,
                trigger_source="webgui_upload",
                trigger_file_name=trig_name,
                wait_for_completion=False,
            )
            return {
                "status": "scenario_triggered",
                "workspace_id": workspace_id,
                "files_added": 1,
                "scenario": scen_state,
                "message": f"Запущен сценарий דוד משה (10 сек) для '{trig_name}'",
            }

        res = await _workspace_manager.add_uploaded_files(
            workspace_id=workspace_id,
            files_data=files_data,
            commit_message=commit_message,
            pdf_mode=pdf_mode,
            ocr_mode=ocr_mode,
            audio_mode=audio_mode,
        )
        return res
    except Exception as exc:
        logger.error(f"[RouterKnowledge] Ошибка загрузки файлов в {workspace_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/extract-preview", summary="Предпросмотр извлечения контента (PDF, Excel, Audio, DOCX, Google Sheets)")
async def extract_preview(req: ExtractPreviewRequest) -> Dict[str, Any]:
    """Извлекает и возвращает текстовый предпросмотр любого поддерживаемого файла или Google Таблицы."""
    try:
        result = await _workspace_manager.extractor.extract(req.target, language=req.language or "ru")
        return {"status": "ok", **result}
    except Exception as exc:
        logger.error(f"[RouterKnowledge] Ошибка предпросмотра {req.target}: {exc}")
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/documents/reanalyze", summary="Повторный анализ документа")
async def reanalyze_document(req: ReanalyzeRequest) -> Dict[str, Any]:
    """Перезапускает NLP-анализ и перестроение фактов для документа рабочей области."""
    target_ws = _resolve_target_workspace(req.workspace_id)
    if not target_ws:
        raise HTTPException(status_code=400, detail="Рабочее пространство не выбрано")
    docs = _workspace_manager.store.list_documents(target_ws)
    target = next((d for d in docs if d["document_id"] == req.document_id), None)
    if not target:
        raise HTTPException(status_code=404, detail=f"Документ '{req.document_id}' не найден в '{target_ws}'")

    return _workspace_manager.import_document(
        workspace_id=target_ws,
        document_id=req.document_id,
        content=target.get("content") or "",
        commit_message=f"Повторный анализ {req.document_id}",
        force_reanalyze=True,
    )


@router.get("/language-modules", summary="Список подключенных языковых NLP-модулей")
async def get_language_modules() -> Dict[str, Any]:
    """Возвращает список зарегистрированных языковых анализаторов и их возможностей (ТЗ п. 6.3, 8)."""
    modules = _workspace_manager.analyzers.list_modules()
    return {"status": "ok", "count": len(modules), "modules": modules}


@router.get("/facts", summary="Получение извлечённых структурированных фактов")
async def get_facts(
    workspace_id: Optional[str] = Query(None, description="Идентификатор рабочей области"),
    document_id: Optional[str] = Query(None, description="Фильтр по документу"),
    language: Optional[str] = Query(None, description="Фильтр по языку ('ru', 'he', 'en')"),
    fact_type: Optional[str] = Query(None, description="Тип факта ('action', 'possession')"),
    include_stale: bool = Query(False, description="Включать ли устаревшие (stale) факты"),
) -> Dict[str, Any]:
    """Возвращает канонические факты из базы знаний SQLite."""
    target_ws = _resolve_target_workspace(workspace_id)
    if not target_ws:
        return {"status": "ok", "workspace_id": None, "count": 0, "facts": []}
    facts = _workspace_manager.store.get_facts(
        workspace_id=target_ws,
        document_id=document_id,
        language=language,
        fact_type=fact_type,
        include_stale=include_stale,
    )
    return {"status": "ok", "workspace_id": target_ws, "count": len(facts), "facts": facts}


@router.post("/facts/{fact_id}/status", summary="Проверка и подтверждение/отклонение факта")
async def update_fact_status(fact_id: str, req: FactStatusUpdateRequest) -> Dict[str, Any]:
    """Изменяет статус факта (extracted, validated, ambiguous, rejected, stale)."""
    try:
        updated = _workspace_manager.store.update_fact_status(fact_id, req.status)
        if not updated:
            raise HTTPException(status_code=404, detail=f"Факт '{fact_id}' не найден")
        return {"status": "ok", "fact_id": fact_id, "new_status": req.status}
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))


@router.post("/ask", summary="Поиск по вопросу и грамматически корректное формирование ответа")
async def ask_question(req: AskQuestionRequest) -> Dict[str, Any]:
    """Выполняет анализ вопроса, поиск по фактам/FAISS/WikiLLM и возвращает ответ со ссылками на источники."""
    target_ws = _resolve_target_workspace(req.workspace_id)
    if not target_ws:
        raise HTTPException(status_code=400, detail="Рабочее пространство не выбрано")
    try:
        return await _qa_engine.ask(
            question=req.question,
            workspace_id=target_ws,
            language=req.language,
            mode=req.mode,
            provider=req.provider,
            model=req.model,
        )
    except Exception as exc:
        logger.error(f"[RouterKnowledge] Ошибка обработки вопроса '{req.question}': {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/ask/stream", summary="Потоковый SSE-ответ на вопрос по базе знаний")
async def ask_question_stream(req: AskQuestionRequest) -> StreamingResponse:
    """Формирует потоковый ответ (Server-Sent Events) с этапами поиска и токенами ответа."""
    target_ws = _resolve_target_workspace(req.workspace_id)
    if not target_ws:
        raise HTTPException(status_code=400, detail="Рабочее пространство не выбрано")
    async def _event_gen():
        yield f"data: {json.dumps({'type': 'stage', 'stage': 'analyzing_question', 'workspace_id': target_ws}, ensure_ascii=False)}\n\n"
        res = await _qa_engine.ask(
            question=req.question,
            workspace_id=target_ws,
            language=req.language,
            mode=req.mode,
            provider=req.provider,
            model=req.model,
        )
        ans = res.get("answer", "")
        words = ans.split(" ")
        for idx, w in enumerate(words):
            tok = w if idx == 0 else f" {w}"
            yield f"data: {json.dumps({'type': 'token', 'token': tok}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'done', 'result': res}, ensure_ascii=False)}\n\n"

    return StreamingResponse(_event_gen(), media_type="text/event-stream")


@router.post("/query", summary="5-этапный семантический и фактологический поиск RAG по базе знаний")
async def execute_rag_query(req: RagQueryRequest) -> Dict[str, Any]:
    """Выполняет 5-этапный RAG-конвейер по пользовательской базе знаний активной рабочей области."""
    target_ws = _resolve_target_workspace(req.workspace_id)
    if not target_ws:
        raise HTTPException(status_code=400, detail="Рабочее пространство не выбрано")
    try:
        res = await _qa_engine.ask(
            question=req.query,
            workspace_id=target_ws,
            language=req.language,
            mode=req.mode,
            provider=req.provider,
            model=req.model,
        )

        quick_questions: List[str] = []
        entities = _workspace_manager.store.list_entities(workspace_id=target_ws)[:4]
        for ent in entities:
            lemma = ent.get("lemma") or ent.get("text", "")
            if lemma and len(lemma) > 2:
                quick_questions.append(f"Какие действия связаны с {lemma}?")
        if not quick_questions:
            quick_questions = [
                "Какие факты зафиксированы в документах?",
                "Какие сущности упоминаются в базе знаний?",
            ]

        sources = res.get("sources") or []
        evidence = []
        for s in sources:
            evidence.append({
                "document_id": s.get("document_id", "doc"),
                "sentence_index": s.get("sentence_index", 0),
                "quote": s.get("quote", ""),
                "score": s.get("score", 1.0),
            })

        return {
            "status": "ok",
            "workspace_id": target_ws,
            "query": req.query,
            "answer": res.get("answer", ""),
            "explanation": res.get("answer", ""),
            "matched_fact": res.get("matched_fact"),
            "sources": evidence,
            "evidence": evidence,
            "faiss_hits": res.get("faiss_hits", []),
            "commits": res.get("commits") or (await _workspace_manager.get_workspace_commits(target_ws, limit=req.top_k or 5)),
            "rag_chunks": res.get("rag_chunks", res.get("faiss_hits", [])),
            "wiki_entities": res.get("wiki_entities", entities),
            "suggested_quick_questions": quick_questions[:4],
            "processing": res.get("processing", {}),
        }
    except Exception as exc:
        logger.error(f"[RouterKnowledge] Ошибка выполнения RAG-запроса '{req.query}': {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/entities", summary="Поиск по извлечённым сущностям")
async def search_entities(
    workspace_id: Optional[str] = Query(None, description="Идентификатор рабочей области"),
    query: Optional[str] = Query(None, description="Подстрока поиска по имени или лемме сущности"),
) -> Dict[str, Any]:
    """Возвращает список сущностей рабочей области."""
    target_ws = _resolve_target_workspace(workspace_id)
    if not target_ws:
        return {"status": "ok", "workspace_id": None, "count": 0, "entities": []}
    entities = _workspace_manager.store.list_entities(workspace_id=target_ws, query=query)
    return {"status": "ok", "workspace_id": target_ws, "count": len(entities), "entities": entities}


@router.post("/faiss/rebuild", summary="Перестроение векторного индекса FAISS")
async def rebuild_faiss(req: FaissRebuildRequest) -> Dict[str, Any]:
    """Перестраивает локальный индекс FAISS из первичных документов SQLite."""
    target_ws = _resolve_target_workspace(req.workspace_id)
    if not target_ws:
        raise HTTPException(status_code=400, detail="Рабочее пространство не выбрано")
    return _workspace_manager.rebuild_faiss_index(target_ws)


@router.get("/ai-models", summary="Список доступных провайдеров и моделей из модуля src/ai")
async def list_ai_models() -> Dict[str, Any]:
    """Возвращает перечень поддерживаемых провайдеров и моделей из единого модуля src/ai."""
    providers = [
        {
            "provider": "gemini",
            "label": "Google Gemini API (src/ai/gemini)",
            "models": ["gemini-3.1-flash-lite", "gemini-2.5-flash", "gemini-2.5-pro", "gemini-pro-latest"],
        },
        {
            "provider": "agy",
            "label": "Antigravity SDK (src/ai/providers/agy)",
            "models": ["agy-gemini-2.5-flash", "agy-gemini-2.5-pro", "agy-claude-sonnet"],
        },
        {
            "provider": "gemini_cli",
            "label": "Gemini CLI (src/ai/providers/gemini_cli)",
            "models": ["gemini-2.5-flash", "gemini-3.1-flash-lite"],
        },
        {
            "provider": "openai",
            "label": "OpenAI / Совместимые API (src/ai/providers/openai)",
            "models": ["openai:gpt-4o-mini", "deepseek:deepseek-chat", "groq:llama-3.3-70b-versatile"],
        },
        {
            "provider": "ollama",
            "label": "Ollama Local LLM (src/ai/providers/ollama)",
            "models": ["ollama:qwen2.5:3b", "ollama:llama3.2:3b"],
        },
        {
            "provider": "foundry",
            "label": "Microsoft Foundry Local (src/ai/providers/foundry)",
            "models": ["foundry:qwen2.5-1.5b-instruct-generic-cpu:4"],
        },
    ]
    return {"status": "ok", "providers": providers}


@router.get("/metrics", summary="Статистика производительности, качества и использования ИИ")
async def get_metrics(
    workspace_id: Optional[str] = Query(None, description="Фильтр по рабочей области"),
) -> Dict[str, Any]:
    """Возвращает метрики времени ответа, количества фактов и вызовов облачных моделей."""
    metrics = _workspace_manager.store.get_metrics(workspace_id=workspace_id)
    return {"status": "ok", **metrics}
