# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant - Tooltips & i18n Management API Router
# =============================================================================
# Description:
#   API-маршрутизатор для управления всплывающими подсказками (tooltips),
#   их интернационализацией (RU, EN, HE, UK), одноразовым автопереводом и аудитом.
#
# File: router_tooltips.py
# Package: apps.ai_assistant.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 13:50:00
# =============================================================================

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from logger import logger

router = APIRouter(prefix="/api/v1/tooltips", tags=["tooltips"])

WEBGUI_DIR = Path(__file__).resolve().parent.parent / "webgui"
COMMON_DIR = Path(__file__).resolve().parent.parent.parent.parent / "common" / "webgui"
SUPPORTED_LANGS = ["ru", "en", "he", "uk"]
_tooltips_lock = asyncio.Lock()


class TooltipItem(BaseModel):
    """Модель отдельной всплывающей подсказки интерфейса."""
    key: str = Field(..., description="Уникальный идентификатор или i18n-ключ подсказки")
    category: str = Field(default="Навигация", description="Функциональная категория подсказки")
    icon: str = Field(default="💡", description="Иконка подсказки (эмодзи или класс Bootstrap Icons)")
    titles: Dict[str, str] = Field(default_factory=dict, description="Заголовки на поддерживаемых языках")
    summaries: Dict[str, str] = Field(default_factory=dict, description="Описания и подсказки на поддерживаемых языках")
    source: str = Field(default="locale", description="Источник подсказки (kb, locale, title_attr)")
    status: str = Field(default="complete", description="Статус перевода (complete, partial, missing)")


class TooltipUpdateRequest(BaseModel):
    """Модель обновления всплывающей подсказки."""
    category: Optional[str] = Field(default=None)
    icon: Optional[str] = Field(default=None)
    titles: Dict[str, str] = Field(default_factory=dict)
    summaries: Dict[str, str] = Field(default_factory=dict)


class TooltipTranslateRequest(BaseModel):
    """Модель запроса одноразового перевода текста подсказки."""
    text: str = Field(..., description="Исходный текст подсказки")
    source_lang: str = Field(default="ru", description="Исходный язык")
    target_langs: List[str] = Field(default=["en", "he", "uk"], description="Целевые языки")


def _load_locale(lang: str) -> dict:
    """Загружает словарь локализации для указанного языка."""
    if lang not in SUPPORTED_LANGS:
        return {}
    loc_file = WEBGUI_DIR / "locales" / f"{lang}.json"
    if loc_file.exists():
        try:
            return json.loads(loc_file.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"[TooltipsRouter] Ошибка чтения {loc_file}: {e}")
    return {}


def _atomic_write_text(file_path: Path, content: str) -> None:
    """Атомарно записывает текстовый файл через временный файл .tmp и os.replace()."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = file_path.with_suffix(f"{file_path.suffix}.tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, file_path)


def _save_locale(lang: str, data: dict) -> None:
    """Атомарно сохраняет словарь локализации в WebGUI и синхронизирует в common."""
    if lang not in SUPPORTED_LANGS:
        return
    loc_file = WEBGUI_DIR / "locales" / f"{lang}.json"
    content = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    _atomic_write_text(loc_file, content)

    common_file = COMMON_DIR / "locales" / f"{lang}.json"
    if common_file.parent.exists():
        _atomic_write_text(common_file, content)


def _get_nested(dict_obj: dict, key_path: str) -> Optional[str]:
    """Извлекает значение по точечному пути ключа."""
    cur = dict_obj
    for part in key_path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return str(cur) if cur is not None else None


def _set_nested(dict_obj: dict, key_path: str, value: str) -> None:
    """Устанавливает значение по точечному пути ключа."""
    parts = key_path.split(".")
    cur = dict_obj
    for part in parts[:-1]:
        if part not in cur or not isinstance(cur[part], dict):
            cur[part] = {}
        cur = cur[part]
    cur[parts[-1]] = value


def _sync_collect_tooltips() -> dict:
    """Синхронно агрегирует все всплывающие подсказки из локалей."""
    locales = {lang: _load_locale(lang) for lang in SUPPORTED_LANGS}
    items_map: Dict[str, TooltipItem] = {}

    # 1. Считываем базу знаний tooltips.kb
    for lang in SUPPORTED_LANGS:
        kb_dict = locales[lang].get("tooltips", {}).get("kb", {})
        for k, v in kb_dict.items():
            if not isinstance(v, dict):
                continue
            if k not in items_map:
                items_map[k] = TooltipItem(
                    key=k,
                    category=v.get("category", "База знаний"),
                    icon="🔍" if "rag" in k else "💡",
                    source="kb"
                )
            if "title" in v and v["title"]:
                items_map[k].titles[lang] = v["title"]
            if "summary" in v and v["summary"]:
                items_map[k].summaries[lang] = v["summary"]

    # 2. Считываем заголовки titles.* и titles.ide.*
    for lang in SUPPORTED_LANGS:
        titles_sec = locales[lang].get("titles", {})
        for grp, val in titles_sec.items():
            if isinstance(val, dict):
                for subk, text in val.items():
                    full_key = f"titles.{grp}.{subk}"
                    if full_key not in items_map:
                        items_map[full_key] = TooltipItem(
                            key=full_key,
                            category=f"Интерфейс ({grp})",
                            icon="🔘",
                            source="title_attr"
                        )
                    if text:
                        items_map[full_key].titles[lang] = str(text)
                        items_map[full_key].summaries[lang] = str(text)

    # 3. Рассчитываем статусы
    tooltips_list: List[dict] = []
    complete_count = 0
    partial_count = 0

    for item in items_map.values():
        langs_with_title = [l for l in SUPPORTED_LANGS if item.titles.get(l)]
        if len(langs_with_title) == len(SUPPORTED_LANGS):
            item.status = "complete"
            complete_count += 1
        elif len(langs_with_title) > 0:
            item.status = "partial"
            partial_count += 1
        else:
            item.status = "missing"
            partial_count += 1
        tooltips_list.append(item.model_dump())

    # Сортировка по ключу
    tooltips_list.sort(key=lambda x: x["key"])

    return {
        "tooltips": tooltips_list,
        "stats": {
            "total": len(tooltips_list),
            "complete": complete_count,
            "partial": partial_count,
            "completeness_pct": round(complete_count / len(tooltips_list) * 100, 1) if tooltips_list else 0
        }
    }


@router.get("", response_model=dict)
async def get_all_tooltips() -> dict:
    """
    Возвращает объединенный каталог всех всплывающих подсказок интерфейса,
    статистику перевода и данные для аудита.
    """
    return await asyncio.to_thread(_sync_collect_tooltips)


def _sync_update_tooltip(key: str, payload: TooltipUpdateRequest) -> None:
    """Синхронно обновляет словари локализации для выбранного ключа подсказки."""
    locales = {lang: _load_locale(lang) for lang in SUPPORTED_LANGS}
    is_kb = not key.startswith("titles.") and not key.startswith("workspace.") and not key.startswith("obsidian.")

    for lang in SUPPORTED_LANGS:
        t_val = payload.titles.get(lang)
        s_val = payload.summaries.get(lang) or t_val

        if is_kb:
            if "tooltips" not in locales[lang]:
                locales[lang]["tooltips"] = {}
            if "kb" not in locales[lang]["tooltips"]:
                locales[lang]["tooltips"]["kb"] = {}
            if key not in locales[lang]["tooltips"]["kb"]:
                locales[lang]["tooltips"]["kb"][key] = {}

            if t_val:
                locales[lang]["tooltips"]["kb"][key]["title"] = t_val
            if s_val:
                locales[lang]["tooltips"]["kb"][key]["summary"] = s_val
            if payload.category:
                locales[lang]["tooltips"]["kb"][key]["category"] = payload.category
        else:
            if t_val:
                _set_nested(locales[lang], key, t_val)

        _save_locale(lang, locales[lang])


@router.put("/{key}", response_model=dict)
async def update_tooltip(key: str, payload: TooltipUpdateRequest) -> dict:
    """
    Обновляет переводы и свойства всплывающей подсказки в словарях всех языков.
    """
    if not key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Не указан ключ подсказки")

    async with _tooltips_lock:
        await asyncio.to_thread(_sync_update_tooltip, key, payload)

    logger.info(f"[TooltipsRouter] Подсказка '{key}' успешно обновлена.")
    return {"status": "ok", "key": key}


@router.post("/translate", response_model=dict)
async def auto_translate_tooltip(payload: TooltipTranslateRequest) -> dict:
    """
    Выполняет одноразовый перевод текста подсказки на поддерживаемые языки.
    """
    src_text = payload.text.strip()
    if not src_text:
        return {"translations": {}}

    results: Dict[str, str] = {}

    # Терминологический словарь быстрых замен для типовых подсказок
    dict_en = {
        "Рабочая область": "Workspace",
        "Создать": "Create",
        "Открыть": "Open",
        "Удалить": "Delete",
        "Сохранить": "Save",
        "Обновить": "Refresh",
        "Просмотр": "View",
        "История коммитов": "Git Commits History",
        "Сравнение": "Diff Analysis",
        "Шкала времени": "Timeline",
        "Интеллектуальный чат": "Smart Chat",
        "Граф знаний": "Knowledge Graph",
        "Каталог моделей": "Models Catalog",
        "Поиск RAG": "RAG Search",
        "Контур верификации": "Verification Circuit",
        "Плагины": "Plugins",
        "Настройки": "Settings",
        "Развернуть": "Expand",
        "Свернуть": "Collapse"
    }

    dict_he = {
        "Рабочая область": "מרחב עבודה",
        "Создать": "צור",
        "Открыть": "פתח",
        "Удалить": "מחק",
        "Сохранить": "שמור",
        "Обновить": "רענן",
        "Просмотр": "צפייה",
        "История коммитов": "היסטוריית גרסאות Git",
        "Сравнение": "השוואת גרסאות",
        "Шкала времени": "ציר זמן",
        "Интеллектуальный чат": "צ'אט חכם",
        "Граф знаний": "גרף ידע",
        "Каталог моделей": "קטלוג מודלים",
        "Поиск RAG": "חיפוש RAG",
        "Контур верификации": "אימות שלמות",
        "Плагины": "תוספים",
        "Настройки": "הגדרות",
        "Развернуть": "הרחב",
        "Свернуть": "כווץ"
    }

    dict_uk = {
        "Рабочая область": "Робочий простір",
        "Создать": "Створити",
        "Открыть": "Відкрити",
        "Удалить": "Видалити",
        "Сохранить": "Зберегти",
        "Обновить": "Оновити",
        "Просмотр": "Перегляд",
        "История коммитов": "Історія комітів Git",
        "Сравнение": "Порівняння версій",
        "Шкала времени": "Хронологія",
        "Интеллектуальный чат": "Розумний чат",
        "Граф знаний": "Граф знань",
        "Каталог моделей": "Каталог моделей",
        "Поиск RAG": "Пошук RAG",
        "Контур верификации": "Контур верифікації",
        "Плагины": "Плагіни",
        "Настройки": "Налаштування",
        "Развернуть": "Розгорнути",
        "Свернуть": "Згорнути"
    }

    for lang in payload.target_langs:
        if lang == payload.source_lang:
            results[lang] = src_text
            continue

        if lang == "en":
            t = src_text
            for k, v in dict_en.items():
                t = t.replace(k, v)
            results["en"] = t
        elif lang == "he":
            t = src_text
            for k, v in dict_he.items():
                t = t.replace(k, v)
            results["he"] = t
        elif lang == "uk":
            t = src_text
            for k, v in dict_uk.items():
                t = t.replace(k, v)
            results["uk"] = t
        else:
            results[lang] = src_text

    return {"translations": results}
