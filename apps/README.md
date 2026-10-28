# 📦 Приложения платформы (`/apps`)

**Статус:** ✅ Активно  
**Автор:** hypo69  
**Updated:** 2026-10-26 00:35:00  

---

## 📋 Назначение

Директория `/apps` содержит прикладные подсистемы и общие интерфейсные модули проекта:

```text
apps/
├── ai_assistant/     # Мультиязычная система управления знаниями, Git-областями, RAG, FAISS и WikiLLM
└── common/           # Общие компоненты WebGUI (модальный ИИ-ассистент, редактор тем, палитры)
```

---

## 🚀 Состав пакетов

| Пакет | Описание | Документация |
|---|---|---|
| **[`apps/ai_assistant`](ai_assistant/README.md)** | Основное приложение платформы: изолированные рабочие области Git, слежение за файлами на месте (`copy_to_workspace = False`), носимый USB-режим с привязкой к имени компьютера (`\\<HOST>\<PATH>`), мультиязычный NLP (`ru`/`he`/`en`) с разрешением кореференции местоимений, база знаний SQLite + FAISS + WikiLLM + Obsidian Vault и IDE-интерфейс (WebGUI / Electron / WebView2). | [`ai_assistant/README.md`](ai_assistant/README.md)<br>[`TECHNICAL_SPECIFICATION.md`](ai_assistant/TECHNICAL_SPECIFICATION.md) |
| **[`apps/common`](common/webgui/README.md)** | Разделяемые фронтенд-модули дизайн-системы: универсальное модальное окно [`ai_modal_dialog`](common/webgui/ai_modal_dialog/README.md), визуальный редактор тем [`tab_theme_editor`](common/webgui/tab_theme_editor/README.md) и набор JSON-тем [`themes`](common/webgui/themes/README.md). | [`common/webgui/README.md`](common/webgui/README.md) |
