# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Common WebGUI Static Files Handler
# =============================================================================
# Description:
#   Универсальный статический обработчик FastAPI для объединения нескольких
#   каталогов WebGUI с поддержкой динамического приоритета по Referer
#   и каскадного поиска в общем репозитории apps/common/webgui.
#
# File: static_files.py
# Project: ai-windows-admin
# Package: apps.common.webgui
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-11 19:55:00
# =============================================================================

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Any, Optional
from fastapi.staticfiles import StaticFiles
from starlette.responses import HTMLResponse, Response

from apps.common.webgui.i18n_renderer import (
    detect_language_from_scope,
    render_i18n_placeholders,
)


class SmartMultiDirStaticFiles(StaticFiles):
    """Статический файловый обработчик с объединением каталогов.

    Позволяет прозрачно раздавать статические ассеты из каталога конкретного
    приложения с автоматическим fallback на общий каталог apps/common/webgui.
    """

    def __init__(self, *directories: Path | str, **kwargs: Any) -> None:
        """Инициализация обработчика со списком директорий.

        Args:
            *directories: Пути к директориям в порядке приоритета.
            **kwargs: Дополнительные параметры для Starlette StaticFiles.
        """
        valid_dirs = [Path(d).resolve() for d in directories if d]
        first_dir = valid_dirs[0] if valid_dirs else Path(".")
        super().__init__(directory=str(first_dir), **kwargs)
        self.directories: list[Path] = valid_dirs

    def lookup_path(self, path: str) -> tuple[str, Optional[os.stat_result]]:
        """Поиск файла по цепочке директорий в заданном порядке.

        Args:
            path: Относительный путь к запрашиваемому файлу.

        Returns:
            tuple[str, Optional[os.stat_result]]: Полный путь к файлу и его stat,
            либо пустая строка и None в случае отсутствия файла.
        """
        clean_rel = (path or "").replace("\x00", "").lstrip("/\\")
        for directory in self.directories:
            if not directory.exists():
                continue
            dir_resolved = directory.resolve()
            try:
                candidate = (dir_resolved / clean_rel).resolve()
                candidate.relative_to(dir_resolved)
            except (ValueError, OSError):
                continue
            full_path = str(candidate)
            try:
                return full_path, os.stat(full_path)
            except (FileNotFoundError, NotADirectoryError, OSError):
                continue
        return "", None

    async def get_response(self, path: str, scope: Any) -> Response:
        """Формирует HTTP-ответ со статическим файлом с SSR-подстановкой i18n для HTML.

        Args:
            path: Запрашиваемый путь к файлу.
            scope: ASGI scope запроса.

        Returns:
            Response: Ответ со статическим или SSR-отрендеренным файлом.
        """
        lower_path = (path or "").lower()
        method = str(scope.get("method", "GET")).upper()
        if method in ("GET", "HEAD") and lower_path.endswith((".html", ".htm")):
            full_path, stat_result = self.lookup_path(path)
            if full_path and stat_result and stat.S_ISREG(stat_result.st_mode):
                raw_html = Path(full_path).read_text(encoding="utf-8")
                if "{{" in raw_html or "<html" in raw_html.lower():
                    lang = detect_language_from_scope(scope)
                    rendered = render_i18n_placeholders(raw_html, lang, self.directories)
                    headers = {
                        "Cache-Control": "no-cache",
                        "Vary": "Cookie, Accept-Language",
                        "Content-Language": lang,
                    }
                    if method == "HEAD":
                        encoded = rendered.encode("utf-8")
                        headers["Content-Length"] = str(len(encoded))
                        return Response(
                            content=b"",
                            status_code=200,
                            media_type="text/html; charset=utf-8",
                            headers=headers,
                        )
                    return HTMLResponse(content=rendered, status_code=200, headers=headers)

        response = await super().get_response(path, scope)

        if lower_path.endswith((".js", ".mjs", ".css", ".html", ".json")):
            response.headers["Cache-Control"] = "no-cache"

        return response

