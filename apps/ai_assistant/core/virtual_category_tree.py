# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Core - Virtual Category Tree
# =============================================================================
# Description:
#   Движок построения виртуального семантического дерева файлов рабочей области
#   (включая внешние файлы на диске, отслеживаемые Git без копирования в рабочую
#   папку). Формирует динамическую иерархию виртуальных категорий на основе
#   оценки содержимого файлов, извлечённых фактов и сущностей, а также выполняет
#   ревизию (переоценку содержимого и логики построения категорий) с помощью
#   модели ИИ или корпусного семантического анализатора.
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.core.virtual_category_tree import VirtualCategoryTreeEngine
#     engine = VirtualCategoryTreeEngine(workspace_manager)
#     tree = engine.get_virtual_tree("default")
#     revised = await engine.revise_taxonomy("default", strategy="entity_centric")
#
# File: virtual_category_tree.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 18:38:00
# =============================================================================

from __future__ import annotations
"""Построение виртуального дерева категорий по содержимому файлов и ревизия таксономии моделью."""

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from logger import logger
from apps.ai_assistant.core.workspace_relocator import WorkspaceRelocator

if TYPE_CHECKING:
    from apps.ai_assistant.core.workspace_manager import WorkspaceManager


# Ключевые семантические домены для оценки содержимого с поддержкой мультиязычности
SEMANTIC_DOMAIN_RULES: List[Dict[str, Any]] = [
    {
        "id": "domestic",
        "category": {
            "ru": "Быт и семейные сцены / Повседневные действия",
            "he": "חיי יומיום ומשפחה / פעולות שגרתיות",
            "en": "Daily Life & Family / Everyday Actions",
            "uk": "Побут і сімейні сцени / Повсякденні дії",
        },
        "keywords": {"мама", "рама", "мыть", "мыла", "дом", "семья", "окно", "אמא", "מסגרת", "רחצה", "לשטוף", "שטפה", "בית", "משפחה", "חלון", "mother", "frame", "wash"},
        "rationale": {
            "ru": "В тексте описываются бытовые действия, субъекты семьи и предметы домашнего обихода.",
            "he": "הטקסט מתאר פעולות יומיומיות, בני משפחה וחפצי בית.",
            "en": "The text describes household activities, family members, and domestic objects.",
            "uk": "У тексті описуються побутові дії, члени сім'ї та предмети домашнього вжитку.",
        },
    },
    {
        "id": "farming_ownership",
        "category": {
            "ru": "Имущество и хозяйство / Фермерство и владение",
            "he": "נכסים ומשק / חקלאות ובעלות",
            "en": "Property & Estate / Farming & Ownership",
            "uk": "Майно і господарство / Фермерство та володіння",
        },
        "keywords": {"ферма", "давид", "моше", "корова", "земля", "сад", "иметь", "חווה", "דוד", "משה", "היתה", "הייתה", "פרה", "אדמה", "בעלות", "farm", "david", "moshe", "cow", "land"},
        "rationale": {
            "ru": "Содержание посвящено владению имуществом, фермерскому хозяйству и принадлежности объектов.",
            "he": "התוכן עוסק בבעלות על נכסים, חקלאות ושיוך אובייקטים.",
            "en": "Content focuses on property ownership, agriculture, and entity possession.",
            "uk": "Зміст присвячений володінню майном, фермерському господарству та приналежності об'єктів.",
        },
    },
    {
        "id": "tech_docs",
        "category": {
            "ru": "Техническая документация / Архитектура и код",
            "he": "תיעוד טכני / ארכיטקטורה וקוד",
            "en": "Technical Documentation / Architecture & Code",
            "uk": "Технічна документація / Архітектура та код",
        },
        "keywords": {"api", "git", "python", "sqlite", "faiss", "модуль", "сервер", "класс", "функция", "архитектура", "тест", "код", "אלגוריתם", "קוד", "קלאס", "algorithm"},
        "rationale": {
            "ru": "Техническое описание программной архитектуры, исходного кода или инфраструктуры.",
            "he": "תיאור טכני של ארכיטקטורת תוכנה, קוד מקור או תשתית.",
            "en": "Technical description of software architecture, source code, or infrastructure.",
            "uk": "Технічний опис програмної архітектури, вихідного коду або інфраструктури.",
        },
    },
    {
        "id": "analytics",
        "category": {
            "ru": "Аналитика и отчёты / Финансы и таблицы",
            "he": "אנליטיקה ודוחות / פיננסים וטבלאות",
            "en": "Analytics & Reports / Finance & Spreadsheets",
            "uk": "Аналітика та звіти / Фінанси і таблиці",
        },
        "keywords": {"отчет", "отчёт", "бюджет", "таблица", "сумма", "доход", "расход", "баланс", "квартал", "excel", "csv", "sheet", "דו\"ח", "דוח", "תקציב", "טבלה", "מאזן", "report", "budget"},
        "rationale": {
            "ru": "Структурированные табличные данные, финансовые показатели или аналитическая сводка.",
            "he": "נתונים טבלאיים מובנים, מדדים פיננסיים או סיכום אנליטי.",
            "en": "Structured tabular data, financial metrics, or analytical summaries.",
            "uk": "Структуровані табличні данные, фінансові показники або аналітичне зведення.",
        },
    },
]


class VirtualCategoryTreeEngine:
    """Управляет виртуальным деревом файлов по содержимому и ревизией категорий моделью."""

    def __init__(
        self,
        workspace_manager: WorkspaceManager,
        chat_model_factory: Optional[Callable[..., Any]] = None,
    ) -> None:
        """Инициализирует движок виртуальных категорий с явным внедрением зависимостей."""
        self.wm = workspace_manager
        self.chat_model_factory = chat_model_factory

    def _taxonomy_file_path(self, ws_path: Path) -> Path:
        """Возвращает путь к файлу хранения виртуальной таксономии и истории ревизий."""
        meta_dir = ws_path / ".workspace"
        meta_dir.mkdir(parents=True, exist_ok=True)
        return meta_dir / "virtual_taxonomy.json"

    def _load_taxonomy_state(self, ws_path: Path) -> Dict[str, Any]:
        """Загружает сохранённое состояние виртуальных категорий и историю ревизий."""
        t_file = self._taxonomy_file_path(ws_path)
        if t_file.exists():
            try:
                return json.loads(t_file.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning(f"[VirtualCategoryTree] Ошибка чтения {t_file}: {exc}")
        return {
            "revision_num": 1,
            "strategy": "semantic_domain",
            "revised_at": datetime.now(timezone.utc).isoformat(),
            "evaluated_by": "content_semantic_analyzer",
            "taxonomy_logic": (
                "Иерархия строится на основе семантической оценки текста, извлечённых "
                "фактов (действия / владение) и ключевых сущностей независимо от физической папки файла."
            ),
            "by_rel_path": {},
            "by_content_hash": {},
            "revision_history": [],
        }

    def _save_taxonomy_state(self, ws_path: Path, state: Dict[str, Any]) -> None:
        """Сохраняет состояние виртуальных категорий и историю ревизий на диск."""
        t_file = self._taxonomy_file_path(ws_path)
        try:
            t_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning(f"[VirtualCategoryTree] Ошибка сохранения {t_file}: {exc}")

    def _is_primary_content_item(
        self,
        ws_path: Path,
        item: Dict[str, Any],
        indexed_doc_ids: set[str],
    ) -> bool:
        """Проверяет, является ли элемент первичным пользовательским файлом (исключая служебные файлы .gitignore, .obsidian и авто-сводки Obsidian)."""
        if item.get("is_dir"):
            return False
        rel_path = str(item.get("rel_path") or "").replace("\\", "/")
        name = str(item.get("name") or Path(rel_path).name)
        if not rel_path or name.startswith(".") or ".obsidian/" in f"{rel_path}/" or rel_path.startswith(".obsidian/"):
            return False
        if name in ("_Knowledge_Base.md", "_Index.md") or rel_path.startswith(("_Entities/", "_Topics/")):
            return False
        if item.get("source_mode") == "linked":
            return True
        # Если это сгенерированная заметка Obsidian (.md), которая не является первичным документом в SQLite
        if name.endswith(".md") and rel_path not in indexed_doc_ids and name not in indexed_doc_ids:
            return False
        return True

    def _read_item_content(self, ws_path: Path, item: Dict[str, Any], docs_map: Dict[str, Dict[str, Any]]) -> str:
        """Извлекает текстовое содержимое файла (из БД знаний, слепка .extracted_snapshots или диска)."""
        rel_path = str(item.get("rel_path") or "")
        name = str(item.get("name") or "")
        for key in (rel_path, name):
            if key in docs_map and docs_map[key].get("content"):
                return str(docs_map[key]["content"])

        # Проверяем манифест внешних источников и их текстовые слепки
        manifest_file = ws_path / ".tracked_sources.json"
        if manifest_file.exists():
            try:
                manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
                entry = manifest.get(rel_path) or manifest.get(name)
                if entry and entry.get("snapshot"):
                    snap_p = ws_path / str(entry["snapshot"])
                    if snap_p.exists() and snap_p.is_file():
                        return snap_p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                pass

        # Если это локальный текстовый файл в рабочей директории
        local_cand = ws_path / rel_path
        if local_cand.exists() and local_cand.is_file():
            try:
                raw = local_cand.read_bytes()
                if b"\x00" not in raw[:4096]:
                    return raw.decode("utf-8", errors="replace")
            except Exception:
                pass

        # Если это внешний текстовый файл на текущем ПК
        ext_cand_str = item.get("local_path")
        if ext_cand_str:
            ext_cand = Path(str(ext_cand_str))
            if ext_cand.exists() and ext_cand.is_file() and ext_cand.suffix.lower() in {".txt", ".md", ".csv", ".json", ".py", ".log"}:
                try:
                    return ext_cand.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    pass
        return ""

    def _evaluate_single_file(
        self,
        item: Dict[str, Any],
        content: str,
        doc_facts: List[Dict[str, Any]],
        strategy: str = "semantic_domain",
        custom_instruction: str = "",
        workspace_lang: str = "ru",
    ) -> Dict[str, Any]:
        """Оценивает содержимое файла, его факты и леммы и определяет виртуальную категорию на целевом языке."""
        text_lower = content.lower()
        tokens = set(re.findall(r"[\w\u0590-\u05FF]+", text_lower))

        # Извлекаем субъекты, объекты и предикаты из канонических фактов документа
        fact_types = {f.get("fact_type", "action") for f in doc_facts}
        actors: List[str] = []
        objects: List[str] = []
        predicates: List[str] = []
        langs = {f.get("language") for f in doc_facts if f.get("language")}

        for f in doc_facts:
            if f.get("fact_type") == "possession":
                owner = f.get("owner") or {}
                poss = f.get("possessed_entity") or {}
                if owner.get("lemma") or owner.get("text"):
                    actors.append(str(owner.get("lemma") or owner.get("text")))
                if poss.get("lemma") or poss.get("text"):
                    objects.append(str(poss.get("lemma") or poss.get("text")))
            else:
                subj = f.get("subject") or {}
                obj = f.get("object") or {}
                pred = f.get("predicate") or {}
                if subj.get("lemma") or subj.get("text"):
                    actors.append(str(subj.get("lemma") or subj.get("text")))
                if obj.get("lemma") or obj.get("text"):
                    objects.append(str(obj.get("lemma") or obj.get("text")))
                if pred.get("lemma") or pred.get("text"):
                    predicates.append(str(pred.get("lemma") or pred.get("text")))

        # Определяем язык текста
        has_hebrew = any("\u0590" <= ch <= "\u05FF" for ch in content)
        has_cyrillic = any("\u0400" <= ch <= "\u04FF" for ch in content)
        lang_code = "he" if has_hebrew else ("ru" if has_cyrillic else (next(iter(langs), "en")))
        lang_label = {"ru": "RU", "he": "HE", "en": "EN", "uk": "UK"}.get(lang_code, lang_code.upper())

        # Целевой язык для формирования таксономии и описаний (язык рабочего пространства)
        target_lang = (workspace_lang or lang_code or "ru").strip().lower()
        if target_lang not in ("ru", "he", "en", "uk"):
            target_lang = "en"

        possession_tag = {"he": "בעלות", "ru": "владение", "en": "possession", "uk": "володіння"}.get(target_lang, "владение")
        action_tag = {"he": "פעולה", "ru": "действие", "en": "action", "uk": "дія"}.get(target_lang, "действие")

        tags: List[str] = []
        for x in actors + predicates + objects:
            clean_x = x.strip()
            if clean_x and clean_x not in tags:
                tags.append(clean_x)
        for ft in sorted(fact_types):
            tags.append(possession_tag if ft == "possession" else action_tag)
        tags.append(lang_label)

        # Выбираем логику построения категорий в зависимости от активной стратегии ревизии
        default_cats = {
            "he": ("מאגר ידע כללי / מסמכים ללא סיווג", "הקטגוריה נקבעה על פי ניתוח בסיסי של תוכן הקובץ."),
            "en": ("General Knowledge Base / Uncategorized Documents", "Category assigned based on basic content analysis."),
            "uk": ("Загальна база знань / Некатегоризовані документи", "Категорія призначена на основі базового аналізу вмісту."),
            "ru": ("Общая база знаний / Некатегоризированные документы", "Категория назначена на основе базового анализа содержимого."),
        }
        category_path, rationale = default_cats.get(target_lang, default_cats["ru"])
        confidence = 0.78

        if strategy == "fact_semantics":
            if "possession" in fact_types and "action" in fact_types:
                cat_tpls = {
                    "he": (f"אונטולוגיית עובדות / מעורב (פעולות ובעלות) [{lang_label}]", "במסמך זוהו עובדות של ביצוע פעולות לצד בעלות על אובייקטים."),
                    "en": (f"Fact Ontology / Mixed (Actions & Possession) [{lang_label}]", "Document contains both action occurrences and object possessions."),
                    "uk": (f"Онтологія фактів / Змішані (Дії та Володіння) [{lang_label}]", "У документі виявлено як факти вчинення дій, так і факти володіння об'єктами."),
                    "ru": (f"Онтология фактов / Смешанные (Действия и Владение) [{lang_label}]", "В документе обнаружены как факты совершения действий, так и факты владения объектами."),
                }
                category_path, rationale = cat_tpls.get(target_lang, cat_tpls["ru"])
                confidence = 0.94
            elif "possession" in fact_types:
                owner_lbl = actors[0].capitalize() if actors else ("בעלים" if target_lang == "he" else "Субъекты")
                cat_tpls = {
                    "he": (f"אונטולוגיית בעלות (Possession) / בעלים: {owner_lbl}", f"מבנה הטקסט מבטא יחס שיוך/בעלות (גורם: {', '.join(actors) or 'לא צוין'})."),
                    "en": (f"Possession Ontology / Owner: {owner_lbl}", f"Text structure conveys ownership relation (subject: {', '.join(actors) or 'unspecified'})."),
                    "uk": (f"Онтологія володіння (Possession) / Власник: {owner_lbl}", f"Структура тексту виражає відношення належності/володіння (суб'єкт: {', '.join(actors) or 'не вказано'})."),
                    "ru": (f"Онтология владения (Possession) / Владелец: {owner_lbl}", f"Структура текста выражает отношение принадлежности/владения (субъект: {', '.join(actors) or 'не указан'})."),
                }
                category_path, rationale = cat_tpls.get(target_lang, cat_tpls["ru"])
                confidence = 0.95
            elif "action" in fact_types:
                pred_lbl = predicates[0].capitalize() if predicates else ("תהליכים" if target_lang == "he" else "Процессы")
                cat_tpls = {
                    "he": (f"אונטולוגיית פעולות (Action) / תהליך: {pred_lbl}", f"מבנה הטקסט מתאר פעולה פעילה על אובייקט ({', '.join(objects) or 'אובייקט'})."),
                    "en": (f"Action Ontology / Process: {pred_lbl}", f"Text structure describes active action upon entity ({', '.join(objects) or 'object'})."),
                    "uk": (f"Онтологія дій (Action) / Процес: {pred_lbl}", f"Структура тексту описує активну дію над об'єктом ({', '.join(objects) or 'об\'єкт'})."),
                    "ru": (f"Онтология действий (Action) / Процесс: {pred_lbl}", f"Структура текста описывает активное действие над объектом ({', '.join(objects) or 'объект'})."),
                }
                category_path, rationale = cat_tpls.get(target_lang, cat_tpls["ru"])
                confidence = 0.95
            else:
                cat_tpls = {
                    "he": (f"חומרי עזר / טקסטים תיאוריים [{lang_label}]", "בטקסט אין פרדיקטים מובהקים של פעולה או בעלות; שויך לחומרי עזר."),
                    "en": (f"Reference Materials / Descriptive Texts [{lang_label}]", "Text lacks explicit action or possession predicates; categorized as reference."),
                    "uk": (f"Довідкові матеріали / Описові тексти [{lang_label}]", "У тексті немає явних предикатів дії або володіння; віднесено до довідкових матеріалів."),
                    "ru": (f"Справочные материалы / Описательные тексты [{lang_label}]", "В тексте нет явных предикатов действия или владения; отнесён к справочным материалам."),
                }
                category_path, rationale = cat_tpls.get(target_lang, cat_tpls["ru"])
                confidence = 0.80

        elif strategy == "entity_centric":
            primary_actor = actors[0].capitalize() if actors else None
            primary_obj = objects[0].capitalize() if objects else None
            if primary_actor:
                sub_group_map = {
                    "he": f"אובייקט: {primary_obj}" if primary_obj else "חומרים קשורים",
                    "en": f"Object: {primary_obj}" if primary_obj else "Related materials",
                    "uk": f"Об'єкт: {primary_obj}" if primary_obj else "Пов'язані матеріали",
                    "ru": f"Объект: {primary_obj}" if primary_obj else "Связанные материалы",
                }
                sub_group = sub_group_map.get(target_lang, sub_group_map["ru"])
                dossier_prefix = {"he": "תיקי ישויות", "en": "Entity Dossiers", "uk": "Досьє суб'єктів", "ru": "Досье субъектов"}.get(target_lang, "Досье субъектов")
                category_path = f"{dossier_prefix} / {primary_actor} / {sub_group}"
                rationale_map = {
                    "he": f"המסמך קובץ סביב הדמות הראשית או הבעלים «{primary_actor}».",
                    "en": f"Document grouped around primary entity or owner «{primary_actor}».",
                    "uk": f"Документ згруповано навколо головної дійової особи або власника «{primary_actor}».",
                    "ru": f"Документ сгруппирован вокруг главного действующего лица или владельца «{primary_actor}».",
                }
                rationale = rationale_map.get(target_lang, rationale_map["ru"])
                confidence = 0.93
            elif tokens:
                top_word = sorted(tokens, key=lambda w: len(w), reverse=True)[0].capitalize()
                prefix = {"he": "אובייקטים נושאיים / קונספט:", "en": "Thematic Concepts / Concept:", "uk": "Тематичні об'єкти / Концепт:", "ru": "Тематические объекты / Концепт:"}.get(target_lang, "Тематические объекты / Концепт:")
                category_path = f"{prefix} {top_word}"
                rat_tpl = {"he": f"קובץ לפי מושג המפתח בטקסט «{top_word}».", "en": f"Grouped by primary text concept «{top_word}».", "uk": f"Згруповано за ключовим поняттям тексту «{top_word}».", "ru": f"Сгруппировано по ключевому понятию текста «{top_word}»."}
                rationale = rat_tpl.get(target_lang, rat_tpl["ru"])
                confidence = 0.82

        else:
            # Стратегия по умолчанию (semantic_domain) или с пользовательским фокусом
            best_rule = None
            best_hits = 0
            for rule in SEMANTIC_DOMAIN_RULES:
                hits = len(tokens & rule["keywords"]) + sum(
                    1 for kw in rule["keywords"] if kw in text_lower
                )
                if hits > best_hits:
                    best_hits = hits
                    best_rule = rule

            if best_rule and best_hits > 0:
                rule_cat = best_rule["category"]
                rule_rat = best_rule["rationale"]
                category_path = (rule_cat.get(target_lang) or rule_cat.get("ru")) if isinstance(rule_cat, dict) else str(rule_cat)
                rationale = (rule_rat.get(target_lang) or rule_rat.get("ru")) if isinstance(rule_rat, dict) else str(rule_rat)
                confidence = min(0.98, 0.80 + 0.05 * best_hits)
            elif "possession" in fact_types:
                possession_paths = {
                    "he": ("נכסים ומשק / אובייקטים בבעלות", "נקבע לפי סמנטיקה של בעלות על נכסים בעובדות שחולצו."),
                    "en": ("Property & Assets / Possessed Entities", "Identified by ownership semantics in extracted facts."),
                    "uk": ("Майно і господарство / Об'єкти володіння", "Визначено за семантикою володіння майном у витягнутих фактах."),
                    "ru": ("Имущество и хозяйство / Объекты владения", "Определено по семантике обладания имуществом в извлечённых фактах."),
                }
                category_path, rationale = possession_paths.get(target_lang, possession_paths["ru"])
                confidence = 0.88
            elif "action" in fact_types:
                action_paths = {
                    "he": ("אירועים ותהליכים / פעולות אקטיביות", "נקבע על פי קיומן של פעולות נושא-מושא בטקסט."),
                    "en": ("Events & Processes / Active Actions", "Identified by subject-object action predicates in text."),
                    "uk": ("Події та процеси / Активні дії", "Визначено за наявністю суб'єктно-об'єктних дій у тексті."),
                    "ru": ("События и процессы / Активные действия", "Определено по наличию субъектно-объектных действий в тексте."),
                }
                category_path, rationale = action_paths.get(target_lang, action_paths["ru"])
                confidence = 0.88
            elif content.strip():
                first_words = [w for w in re.findall(r"[\w\u0590-\u05FF]{3,}", content)][:2]
                topic_lbl = " ".join(first_words).capitalize() if first_words else ("הערות" if target_lang == "he" else "Заметки")
                prefix = {"he": f"חומרים נושאיים ({lang_label})", "en": f"Thematic Materials ({lang_label})", "uk": f"Тематичні матеріали ({lang_label})", "ru": f"Тематические материалы ({lang_label})"}.get(target_lang, f"Тематические материалы ({lang_label})")
                category_path = f"{prefix} / {topic_lbl}"
                rat_prefix = {"he": f"חלוקה נושאית אוטומטית לפי מונחי מפתח בטקסט ({lang_label}).", "en": f"Automatic topical classification by key terms ({lang_label}).", "uk": f"Автоматична тематична рубрикація за ключовими термінами тексту ({lang_label}).", "ru": f"Автоматическая тематическая рубрикация по ключевым терминам текста ({lang_label})."}.get(target_lang, f"Автоматическая тематическая рубрикация по ключевым терминам текста ({lang_label}).")
                rationale = rat_prefix
                confidence = 0.81

            if custom_instruction.strip():
                instr_clean = custom_instruction.strip()
                # Если инструкция задаёт приоритетную ось классификации, отражаем её в надкатегории и обосновании
                short_axis = instr_clean[:42].strip().rstrip(".,;:")
                category_path = f"{short_axis} / {category_path.split('/')[-1].strip()}"
                rev_prefix = {"he": f"הוערך מחדש לפי קריטריון הרוויזיה «{instr_clean}»: {rationale}", "en": f"Re-evaluated by revision criterion «{instr_clean}»: {rationale}", "uk": f"Переоцінено за критерієм ревізії «{instr_clean}»: {rationale}", "ru": f"Переоценено по критерию ревизии «{instr_clean}»: {rationale}"}.get(target_lang, f"Переоценено по критерию ревизии «{instr_clean}»: {rationale}")
                rationale = rev_prefix

        preview_line = " ".join(content.strip().splitlines()[:2]).strip()
        if len(preview_line) > 140:
            preview_line = preview_line[:137] + "..."
        default_file_labels = {
            "he": f"קובץ {item.get('name', '')} ({item.get('size_formatted', '0 B')})",
            "en": f"File {item.get('name', '')} ({item.get('size_formatted', '0 B')})",
            "uk": f"Файл {item.get('name', '')} ({item.get('size_formatted', '0 B')})",
            "ru": f"Файл {item.get('name', '')} ({item.get('size_formatted', '0 B')})",
        }
        summary = preview_line or default_file_labels.get(target_lang, default_file_labels["ru"])

        return {
            "virtual_category": category_path,
            "semantic_summary": summary,
            "semantic_tags": tags[:6],
            "confidence": round(confidence, 2),
            "classification_rationale": rationale,
            "language": lang_code,
        }

    def get_virtual_tree(self, workspace_id: str) -> Dict[str, Any]:
        """Собирает полное виртуальное дерево всех файлов (локальных и внешних), отслеживаемых Git."""
        _, ws_path = self.wm._get_or_create_workspace(workspace_id)
        ws_info = self.wm.get_workspace(workspace_id) or {}
        ws_lang = str(ws_info.get("language") or "ru").strip().lower()
        dir_info = self.wm.get_directory_contents(workspace_id)
        raw_items = dir_info.get("items", [])

        docs_list = self.wm.store.list_documents(workspace_id)
        docs_map: Dict[str, Dict[str, Any]] = {d["document_id"]: d for d in docs_list}
        indexed_doc_ids = set(docs_map.keys())
        all_facts = self.wm.store.get_facts(workspace_id=workspace_id, include_stale=False)
        facts_by_doc: Dict[str, List[Dict[str, Any]]] = {}
        for f in all_facts:
            did = str(f.get("document_id") or "")
            facts_by_doc.setdefault(did, []).append(f)

        state = self._load_taxonomy_state(ws_path)
        strategy = state.get("strategy", "semantic_domain")
        custom_instruction = state.get("custom_instruction", "")
        by_rel_path: Dict[str, Any] = state.get("by_rel_path", {})
        by_hash: Dict[str, Any] = state.get("by_content_hash", {})
        state_dirty = False

        enriched_items: List[Dict[str, Any]] = []
        categories_counter: Dict[str, int] = {}

        for item in raw_items:
            if item.get("is_dir"):
                # Физические папки сохраняем для режима просмотра физических директорий
                enriched_items.append({
                    **item,
                    "virtual_category": "",
                    "virtual_path": item.get("rel_path", ""),
                })
                continue

            if not self._is_primary_content_item(ws_path, item, indexed_doc_ids):
                continue

            rel_path = str(item.get("rel_path") or item.get("name") or "")
            content = self._read_item_content(ws_path, item, docs_map)
            content_hash = item.get("content_hash") or (
                WorkspaceRelocator.compute_clean_hash(content) if content else ""
            )
            doc_facts = (
                facts_by_doc.get(rel_path)
                or facts_by_doc.get(Path(rel_path).name)
                or []
            )

            # 1. Если файл был перенесён без изменений — находим его оценку по content_hash!
            cached_eval = None
            if content_hash and content_hash in by_hash:
                cached_eval = by_hash[content_hash]
                if rel_path not in by_rel_path:
                    by_rel_path[rel_path] = cached_eval
                    state_dirty = True
            elif rel_path in by_rel_path:
                cached_eval = by_rel_path[rel_path]

            if not cached_eval:
                cached_eval = self._evaluate_single_file(
                    item=item,
                    content=content,
                    doc_facts=doc_facts,
                    strategy=strategy,
                    custom_instruction=custom_instruction,
                    workspace_lang=ws_lang,
                )
                by_rel_path[rel_path] = cached_eval
                if content_hash:
                    by_hash[content_hash] = cached_eval
                state_dirty = True

            v_default = {
                "he": "מאגר ידע כללי / מסמכים",
                "en": "General Knowledge Base / Documents",
                "uk": "Загальна база знань / Документи",
                "ru": "Общая база знаний / Документы",
            }.get(ws_lang, "Общая база знаний / Документы")
            v_cat = str(cached_eval.get("virtual_category") or v_default)
            v_path = f"{v_cat}/{item.get('name') or Path(rel_path).name}"
            categories_counter[v_cat] = categories_counter.get(v_cat, 0) + 1

            enriched_items.append({
                **item,
                "content_hash": content_hash,
                "virtual_category": v_cat,
                "virtual_path": v_path,
                "semantic_summary": cached_eval.get("semantic_summary", ""),
                "semantic_tags": cached_eval.get("semantic_tags", []),
                "confidence": cached_eval.get("confidence", 0.85),
                "classification_rationale": cached_eval.get("classification_rationale", ""),
                "facts_count": len(doc_facts),
            })

        if state_dirty:
            state["by_rel_path"] = by_rel_path
            state["by_content_hash"] = by_hash
            self._save_taxonomy_state(ws_path, state)

        categories_summary = [
            {"category_path": k, "files_count": v}
            for k, v in sorted(categories_counter.items(), key=lambda x: x[0])
        ]

        return {
            **dir_info,
            "items": enriched_items,
            "virtual_taxonomy": {
                "revision_num": state.get("revision_num", 1),
                "strategy": strategy,
                "custom_instruction": custom_instruction,
                "revised_at": state.get("revised_at", ""),
                "evaluated_by": state.get("evaluated_by", "content_semantic_analyzer"),
                "taxonomy_logic": state.get("taxonomy_logic", ""),
                "total_categories": len(categories_summary),
                "categories": categories_summary,
                "revision_history": state.get("revision_history", [])[-10:],
            },
        }

    async def _try_model_taxonomy_revision(
        self,
        workspace_id: str,
        files_digest: List[Dict[str, Any]],
        strategy: str,
        instruction: str,
        provider: str,
        model_name: str,
        workspace_lang: str = "ru",
    ) -> Optional[Dict[str, Any]]:
        """Запрашивает у ИИ-модели (UnifiedChatModel) ревизию содержимого файлов и перестройку виртуальных категорий."""
        if not files_digest:
            return None

        lang_titles = {
            "he": "עברית (Hebrew)",
            "en": "English",
            "uk": "Українська (Ukrainian)",
            "ru": "Русский (Russian)",
        }
        target_lang_title = lang_titles.get(workspace_lang, "Русский (Russian)")

        sys_prompt = (
            f"Ты — архитектор базы знаний и рекомендательной системы. "
            f"Проведи ревизию содержимого всех отслеживаемых файлов (локальных и внешних) и "
            f"построй иерархическое дерево виртуальных категорий (формат категории: 'Раздел / Подраздел'). "
            f"ВАЖНОЕ ТРЕБОВАНИЕ ЯЗЫКА: Все названия категорий ('Раздел / Подраздел'), объяснение логики (taxonomy_logic), "
            f"краткая суть (semantic_summary), обоснования (classification_rationale) и теги (semantic_tags) "
            f"ДОЛЖНЫ БЫТЬ СТРОГО НА ЯЗЫКЕ: {target_lang_title}. Не смешивай языки!\n"
            f"Верни СТРОГО валидный JSON-объект вида:\n"
            "{\n"
            f'  "taxonomy_logic": "Объяснение логики на языке {target_lang_title}",\n'
            '  "assignments": {\n'
            '    "<rel_path>": {\n'
            '      "virtual_category": "Раздел / Подраздел",\n'
            '      "semantic_summary": "Краткая суть содержимого",\n'
            '      "semantic_tags": ["тег1", "тег2"],\n'
            '      "confidence": 0.95,\n'
            '      "classification_rationale": "Почему файл отнесён в эту категорию"\n'
            "    }\n"
            "  }\n"
            "}"
        )
        user_prompt = (
            f"Целевой язык пространства: {target_lang_title}\n"
            f"Стратегия ревизии: {strategy}\n"
            f"Дополнительное указание: {instruction or 'Построй наиболее осмысленные категории по сути контента и фактов'}\n\n"
            f"Файлы для переоценки:\n{json.dumps(files_digest, ensure_ascii=False, indent=2)}"
        )

        t0 = time.perf_counter()
        try:
            if self.chat_model_factory:
                chat = self.chat_model_factory(
                    system_instruction=sys_prompt,
                    provider=provider,
                    model=model_name,
                )
            else:
                from src.ai.orchestration.unified_chat import UnifiedChatModel

                chat = UnifiedChatModel(
                    system_instruction=sys_prompt,
                    provider=provider,
                    model=model_name,
                )

            raw_resp = await chat.ask(q=user_prompt, attempts=1, temperature=0.1)
            lat = (time.perf_counter() - t0) * 1000.0
            if not raw_resp:
                return None

            # Извлекаем JSON-блок из ответа модели
            cleaned = raw_resp.strip()
            if "```" in cleaned:
                match = re.search(r"\{[\s\S]*\}", cleaned)
                if match:
                    cleaned = match.group(0)
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict) and isinstance(parsed.get("assignments"), dict):
                self.wm.store.log_model_usage(
                    workspace_id=workspace_id,
                    provider=provider,
                    model_name=model_name,
                    operation="virtual_tree_revision",
                    status="success",
                    latency_ms=lat,
                    prompt_chars=len(user_prompt),
                    response_chars=len(raw_resp),
                )
                return parsed
        except Exception as exc:
            logger.info(
                f"[VirtualCategoryTree] Облачная модель ({provider}/{model_name}) недоступна для ревизии: {exc}. "
                "Применяется локальный корпусный семантический анализатор."
            )
        return None

    async def revise_taxonomy(
        self,
        workspace_id: str,
        strategy: str = "semantic_domain",
        instruction: str = "",
        use_model: bool = True,
        provider: str = "gemini",
        model_name: str = "gemini-2.5-flash",
    ) -> Dict[str, Any]:
        """Выполняет ревизию: переоценивает содержимое всех файлов и перестраивает виртуальные категории."""
        _, ws_path = self.wm._get_or_create_workspace(workspace_id)
        dir_info = self.wm.get_directory_contents(workspace_id)
        raw_items = [i for i in dir_info.get("items", []) if not i.get("is_dir")]

        docs_list = self.wm.store.list_documents(workspace_id)
        docs_map: Dict[str, Dict[str, Any]] = {d["document_id"]: d for d in docs_list}
        indexed_doc_ids = set(docs_map.keys())
        raw_items = [i for i in raw_items if self._is_primary_content_item(ws_path, i, indexed_doc_ids)]
        all_facts = self.wm.store.get_facts(workspace_id=workspace_id, include_stale=False)
        facts_by_doc: Dict[str, List[Dict[str, Any]]] = {}
        for f in all_facts:
            did = str(f.get("document_id") or "")
            facts_by_doc.setdefault(did, []).append(f)

        state = self._load_taxonomy_state(ws_path)
        prev_rev = int(state.get("revision_num", 1))
        new_rev = prev_rev + 1

        files_digest: List[Dict[str, Any]] = []
        local_evaluations: Dict[str, Dict[str, Any]] = {}
        hash_map: Dict[str, str] = {}

        ws_info = self.wm.get_workspace(workspace_id) or {}
        ws_lang = str(ws_info.get("language") or "ru").strip().lower()

        for item in raw_items:
            rel_path = str(item.get("rel_path") or item.get("name") or "")
            content = self._read_item_content(ws_path, item, docs_map)
            c_hash = item.get("content_hash") or (
                WorkspaceRelocator.compute_clean_hash(content) if content else ""
            )
            if c_hash:
                hash_map[rel_path] = c_hash
            doc_facts = (
                facts_by_doc.get(rel_path)
                or facts_by_doc.get(Path(rel_path).name)
                or []
            )
            eval_res = self._evaluate_single_file(
                item=item,
                content=content,
                doc_facts=doc_facts,
                strategy=strategy,
                custom_instruction=instruction,
                workspace_lang=ws_lang,
            )
            local_evaluations[rel_path] = eval_res
            files_digest.append({
                "rel_path": rel_path,
                "source_mode": item.get("source_mode", "local"),
                "content_excerpt": content[:400],
                "facts_count": len(doc_facts),
                "detected_tags": eval_res.get("semantic_tags", []),
            })

        model_result: Optional[Dict[str, Any]] = None
        if use_model and files_digest:
            model_result = await self._try_model_taxonomy_revision(
                workspace_id=workspace_id,
                files_digest=files_digest,
                strategy=strategy,
                instruction=instruction,
                provider=provider,
                model_name=model_name,
                workspace_lang=ws_lang,
            )

        new_by_rel: Dict[str, Any] = {}
        new_by_hash: Dict[str, Any] = {}

        if model_result and isinstance(model_result.get("assignments"), dict):
            evaluated_by = f"model_revision:{provider}/{model_name}"
            taxonomy_logic = str(
                model_result.get("taxonomy_logic")
                or f"Ревизия #{new_rev} выполнена моделью {provider}/{model_name} (стратегия: {strategy})."
            )
            model_assigns = model_result["assignments"]
            for rel_path, fallback_eval in local_evaluations.items():
                m_item = model_assigns.get(rel_path)
                if isinstance(m_item, dict) and m_item.get("virtual_category"):
                    merged = {
                        **fallback_eval,
                        "virtual_category": str(m_item["virtual_category"]).strip(),
                        "semantic_summary": str(m_item.get("semantic_summary") or fallback_eval["semantic_summary"]),
                        "semantic_tags": list(m_item.get("semantic_tags") or fallback_eval["semantic_tags"]),
                        "confidence": float(m_item.get("confidence", 0.95)),
                        "classification_rationale": str(
                            m_item.get("classification_rationale") or fallback_eval["classification_rationale"]
                        ),
                    }
                else:
                    merged = fallback_eval
                new_by_rel[rel_path] = merged
                if rel_path in hash_map:
                    new_by_hash[hash_map[rel_path]] = merged
        else:
            evaluated_by = f"semantic_reclassifier:{strategy}"
            strategy_descriptions = {
                "semantic_domain": "Категории перестроены по смысловым и предметным областям содержимого файлов (быт, хозяйство/имущество, техника, аналитика).",
                "fact_semantics": "Категории перестроены по грамматической и онтологической структуре фактов: разделены процессы/действия (Action) и отношения владения (Possession).",
                "entity_centric": "Категории перестроены вокруг ключевых субъектов, владельцев и главных сущностей, извлечённых из текстов.",
            }
            base_desc = strategy_descriptions.get(
                strategy,
                "Категории переоценены на основе полного анализа текстов, сущностей и фактов.",
            )
            if instruction.strip():
                base_desc += f" Применено правило ревизии: «{instruction.strip()}»."
            taxonomy_logic = f"Ревизия #{new_rev}: {base_desc}"

            for rel_path, eval_res in local_evaluations.items():
                new_by_rel[rel_path] = eval_res
                if rel_path in hash_map:
                    new_by_hash[hash_map[rel_path]] = eval_res

        now_iso = datetime.now(timezone.utc).isoformat()
        history = list(state.get("revision_history", []))
        history.append({
            "revision_num": new_rev,
            "revised_at": now_iso,
            "strategy": strategy,
            "instruction": instruction,
            "evaluated_by": evaluated_by,
            "files_evaluated": len(new_by_rel),
            "categories_count": len({v["virtual_category"] for v in new_by_rel.values()}),
            "taxonomy_logic": taxonomy_logic,
        })

        new_state = {
            "revision_num": new_rev,
            "strategy": strategy,
            "custom_instruction": instruction,
            "revised_at": now_iso,
            "evaluated_by": evaluated_by,
            "taxonomy_logic": taxonomy_logic,
            "by_rel_path": new_by_rel,
            "by_content_hash": new_by_hash,
            "revision_history": history[-20:],
        }
        self._save_taxonomy_state(ws_path, new_state)
        logger.info(
            f"[VirtualCategoryTree] Выполнена ревизия #{new_rev} виртуального дерева в '{workspace_id}' "
            f"(стратегия={strategy}, файлов={len(new_by_rel)})"
        )
        return self.get_virtual_tree(workspace_id)
