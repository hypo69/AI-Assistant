# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant - Google OAuth & Account Management Router
# =============================================================================
# Description:
#   FastAPI маршрутизатор аутентификации и авторизации Google OAuth 2.0,
#   проверки профиля (/auth/check), запуска потока авторизации (/auth/google)
#   и управления пулом корпоративных учетных записей Google Workspace.
#
# File: router_auth.py
# Package: apps.ai_assistant.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 19:15:00
# =============================================================================

from __future__ import annotations

"""Маршрутизатор Google OAuth 2.0 авторизации и управления профилями."""

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from header import __root__
from logger import logger
from src.ai.google_accounts_state import (
    DEFAULT_SCOPES,
    _OAUTH_FILES_DIR,
    _TOKENS_DIR,
    delete_google_account,
    get_account_info,
    list_google_accounts,
    load_account_credentials,
    reset_account_status,
    save_google_account,
    set_default_account,
)

router = APIRouter(tags=["Google OAuth & Accounts"])


class GoogleAccountPayload(BaseModel):
    """Полезная нагрузка для создания/добавления Google аккаунта."""
    name: Optional[str] = Field(None, description="Имя аккаунта")
    account_name: Optional[str] = Field(None, description="Алиас имени аккаунта")
    type: Optional[str] = Field("oauth2", description="Тип: oauth2 или service_account")
    account_type: Optional[str] = Field(None, description="Алиас типа аккаунта")
    email: Optional[str] = Field(None, description="Email адрес")
    client_id: Optional[str] = Field(None, description="OAuth2 Client ID")
    client_secret: Optional[str] = Field(None, description="OAuth2 Client Secret")
    credentials_json: Optional[str] = Field(None, description="JSON учетных данных строкой")
    credentials_dict: Optional[Dict[str, Any]] = Field(None, description="JSON учетных данных словарем")
    set_as_default: Optional[bool] = Field(False, description="Установить по умолчанию")


def _get_active_auth_state() -> Dict[str, Any]:
    """Определяет текущий статус аутентификации пользователя через Google."""
    accounts = list_google_accounts()
    default_acc = next((a for a in accounts if a.get("is_default")), accounts[0] if accounts else None)

    has_google = False
    user_email = ""
    user_name = "Гость"
    role = "Guest"

    if default_acc:
        acc_name = default_acc.get("name", "")
        token_rel = default_acc.get("token_file", "")
        token_path = (Path(token_rel) if Path(token_rel).is_absolute() else __root__ / token_rel) if token_rel else (_TOKENS_DIR / f"{acc_name}_token.json")

        if token_path.exists():
            has_google = True
            user_name = acc_name
            user_email = default_acc.get("email") or ""
            role = "Admin"

            # Попытка извлечь email из сохраненного токена, если он не указан
            if not user_email:
                try:
                    with open(token_path, "r", encoding="utf-8") as f:
                        tdata = json.load(f)
                        user_email = tdata.get("account", "")
                except Exception:
                    pass

            if not user_email:
                user_email = f"{acc_name}@gmail.com"

    return {
        "authenticated": has_google,
        "email": user_email,
        "name": user_name if has_google else "Локальный пользователь",
        "picture": None,
        "role": role,
        "is_admin": has_google or True,  # В локальном режиме права администратора
        "has_google": has_google,
        "oauth_enabled": True,
        "accounts": accounts,
    }


# =============================================================================
#  Маршруты статуса и сессии пользователя
# =============================================================================

@router.get("/auth/check", summary="Проверка текущего статуса авторизации")
async def auth_check() -> Dict[str, Any]:
    """Возвращает информацию о текущем пользователе и состоянии Google OAuth."""
    return _get_active_auth_state()


@router.post("/auth/logout", summary="Выход из сессии Google OAuth")
async def auth_logout() -> Dict[str, Any]:
    """Сбрасывает токен текущей авторизации."""
    try:
        accounts = list_google_accounts()
        for acc in accounts:
            token_rel = acc.get("token_file", "")
            if token_rel:
                tp = Path(token_rel) if Path(token_rel).is_absolute() else __root__ / token_rel
                if tp.exists():
                    tp.unlink(missing_ok=True)
        return {"status": "success", "message": "Сессия успешно завершена"}
    except Exception as exc:
        logger.warning(f"[Auth] Ошибка выхода: {exc}")
        return {"status": "error", "message": str(exc)}


# =============================================================================
#  Маршруты потока авторизации Google OAuth 2.0
# =============================================================================

@router.get("/auth/google", response_class=HTMLResponse, summary="Точка входа авторизации Google OAuth")
async def auth_google_page(next: str = "/") -> HTMLResponse:
    """Отображает интерактивную страницу запуска OAuth потока в браузере."""
    html_content = f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <title>Google OAuth Авторизация — AI Assistant</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
  <style>
    body {{
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      background: #111827;
      color: #f3f4f6;
      font-family: system-ui, -apple-system, sans-serif;
      margin: 0;
      padding: 1rem;
    }}
    .auth-box {{
      width: 100%;
      max-width: 440px;
      background: #1f2937;
      border: 1px solid #374151;
      border-radius: 14px;
      padding: 2rem;
      text-align: center;
      box-shadow: 0 10px 25px rgba(0,0,0,0.5);
    }}
    .google-badge {{
      width: 60px;
      height: 60px;
      border-radius: 50%;
      background: #ffffff;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 4px 12px rgba(0,0,0,0.2);
      margin-bottom: 1.25rem;
    }}
  </style>
</head>
<body>
  <div class="auth-box">
    <div class="google-badge">
      <svg width="32" height="32" viewBox="0 0 24 24">
        <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
        <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
        <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"/>
        <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"/>
      </svg>
    </div>
    <h4 class="fw-bold mb-2">Google OAuth Авторизация</h4>
    <p class="text-secondary small mb-4" id="auth-status-desc">
      Запуск локального сервера авторизации... В вашем браузере откроется окно выбора аккаунта Google.
    </p>

    <div class="d-flex justify-content-center mb-4">
      <div class="spinner-border text-primary" role="status" id="auth-spinner">
        <span class="visually-hidden">Загрузка...</span>
      </div>
    </div>

    <div class="alert alert-danger d-none py-2 small mb-3" id="auth-error-box"></div>

    <div class="d-flex gap-2 justify-content-center">
      <button class="btn btn-primary btn-sm px-3 fw-semibold" id="btn-trigger-oauth" type="button">
        <i class="bi bi-box-arrow-up-right me-1"></i> Запустить авторизацию
      </button>
      <a href="{next}" class="btn btn-outline-secondary btn-sm px-3">
        Назад к приложению
      </a>
    </div>
  </div>

  <script>
    const nextUrl = {json.dumps(next)};
    const desc = document.getElementById('auth-status-desc');
    const spinner = document.getElementById('auth-spinner');
    const errBox = document.getElementById('auth-error-box');
    const btn = document.getElementById('btn-trigger-oauth');

    async function runOAuth() {{
      btn.disabled = true;
      spinner.classList.remove('d-none');
      errBox.classList.add('d-none');
      desc.textContent = 'Ожидание подтверждения в окне Google... Пожалуйста, выберите ваш аккаунт Google и разрешите доступ.';

      try {{
        const resp = await fetch('/api/v1/auth/google/login', {{ method: 'POST' }});
        const data = await resp.json();

        if (data.status === 'success') {{
          desc.innerHTML = '<span class="text-success fw-bold">✓ Авторизация успешно выполнена!</span> Перенаправление...';
          spinner.classList.add('d-none');
          setTimeout(() => {{ window.location.href = nextUrl; }}, 800);
        }} else {{
          throw new Error(data.message || 'Ошибка авторизации');
        }}
      }} catch (err) {{
        spinner.classList.add('d-none');
        btn.disabled = false;
        errBox.textContent = err.message;
        errBox.classList.remove('d-none');
        desc.textContent = 'Не удалось завершить авторизацию. Попробуйте еще раз или проверьте настройки Google Cloud Console.';
      }}
    }}

    btn.addEventListener('click', runOAuth);
    // Автоматический запуск при первой загрузке страницы
    window.addEventListener('load', () => {{
      setTimeout(runOAuth, 400);
    }});
  </script>
</body>
</html>"""
    return HTMLResponse(content=html_content)


@router.post("/api/v1/auth/google/login", summary="Запуск OAuth consent flow")
async def api_auth_google_login(account_name: Optional[str] = None) -> Dict[str, Any]:
    """Выполняет интерактивный OAuth flow через локальный сервер (InstalledAppFlow)."""
    try:
        acc = account_name or "davidka"
        creds = await asyncio.to_thread(load_account_credentials, acc)
        if not creds:
            return {
                "status": "error",
                "message": f"Не удалось получить учетные данные для '{acc}'. Проверьте наличие credentials.json в src/secrets.",
            }

        return {
            "status": "success",
            "account": acc,
            "message": "Авторизация Google OAuth успешно подтверждена и токен сохранен.",
            "scopes": list(creds.scopes or DEFAULT_SCOPES),
        }
    except Exception as exc:
        logger.error(f"[Auth] Ошибка в процессе OAuth авторизации: {exc}")
        return {"status": "error", "message": str(exc)}


# =============================================================================
#  Маршруты управления пулом учетных записей Google Workspace
# =============================================================================

@router.get("/api/v1/auth/google-accounts", summary="Список аккаунтов Google")
async def list_accounts_endpoint() -> Dict[str, Any]:
    """Возвращает список всех зарегистрированных Google аккаунтов в пуле."""
    try:
        raw_accounts = list_google_accounts()
        accounts = []
        for acc in raw_accounts:
            item = dict(acc)
            token_str = item.get("token_file", "")
            if token_str:
                tp = Path(token_str)
                token_path = tp if tp.is_absolute() else __root__ / tp
                item["has_token"] = token_path.exists()
            else:
                item["has_token"] = False
            accounts.append(item)
        return {"status": "success", "accounts": accounts}
    except Exception as exc:
        logger.error(f"[Auth] Ошибка получения списка аккаунтов: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/api/v1/auth/google-accounts", summary="Создать Google аккаунт")
async def create_account_endpoint(payload: GoogleAccountPayload) -> Dict[str, Any]:
    """Создает или обновляет аккаунт Google в пуле."""
    acc_name = (payload.account_name or payload.name or "").strip()
    if not acc_name:
        raise HTTPException(status_code=400, detail="Имя аккаунта обязательно для заполнения")

    acc_type = (payload.account_type or payload.type or "oauth2").strip().lower()
    creds_data: Any = None

    if payload.credentials_dict:
        creds_data = payload.credentials_dict
    elif payload.credentials_json:
        try:
            creds_data = json.loads(payload.credentials_json)
        except Exception:
            creds_data = payload.credentials_json
    elif payload.client_id and payload.client_secret:
        creds_data = {
            "installed": {
                "client_id": payload.client_id.strip(),
                "client_secret": payload.client_secret.strip(),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }
    else:
        raise HTTPException(status_code=400, detail="Предоставьте файл JSON ключа или Client ID/Secret")

    res = save_google_account(
        account_name=acc_name,
        credentials_path_or_dict=creds_data,
        account_type=acc_type,
        email=payload.email or "",
        set_as_default=bool(payload.set_as_default),
    )
    if not res:
        raise HTTPException(status_code=500, detail="Не удалось сохранить аккаунт в пуле")

    return {"status": "success", "account": get_account_info(acc_name)}


@router.post("/api/v1/auth/google-accounts/upload", summary="Загрузить credentials.json")
async def upload_credentials_endpoint(
    account_name: Optional[str] = Form(None),
    account_type: Optional[str] = Form("oauth2"),
    email: Optional[str] = Form(""),
    set_as_default: Optional[str] = Form("false"),
    file: UploadFile = File(...),
) -> Dict[str, Any]:
    """Загрузка файла client_secrets или service_account JSON."""
    try:
        content = await file.read()
        try:
            creds_dict = json.loads(content.decode("utf-8"))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Файл не содержит валидный JSON: {exc}")

        detected_type = "service_account" if creds_dict.get("type") == "service_account" else (account_type or "oauth2")
        acc_name = (account_name or "").strip()
        if not acc_name:
            filename = file.filename or "credentials.json"
            acc_name = Path(filename).stem.removesuffix("_secret").removesuffix("_credentials")
            if not acc_name:
                acc_name = "default"

        is_default = str(set_as_default).lower() in ("true", "1", "yes")

        res = save_google_account(
            account_name=acc_name,
            credentials_path_or_dict=creds_dict,
            account_type=detected_type,
            email=email or "",
            set_as_default=is_default,
        )
        if not res:
            raise HTTPException(status_code=500, detail="Не удалось сохранить аккаунт из файла")

        return {"status": "success", "account_name": acc_name, "account": get_account_info(acc_name)}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"[Auth] Ошибка загрузки файла: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/api/v1/auth/google-accounts/{name}/set-default", summary="Назначить аккаунт по умолчанию")
@router.post("/api/v1/auth/google-accounts/{name}/default", summary="Назначить аккаунт по умолчанию (алиас)")
async def set_default_endpoint(name: str) -> Dict[str, Any]:
    """Назначает выбранный аккаунт по умолчанию."""
    res = set_default_account(name)
    if not res:
        raise HTTPException(status_code=404, detail=f"Аккаунт '{name}' не найден")
    return {"status": "success", "default_account": name}


@router.post("/api/v1/auth/google-accounts/{name}/reset-status", summary="Сбросить статус исчерпания")
async def reset_status_endpoint(name: str) -> Dict[str, Any]:
    """Сбрасывает статус исчерпания квоты в активный."""
    res = reset_account_status(name)
    if not res:
        raise HTTPException(status_code=404, detail=f"Аккаунт '{name}' не найден")
    return {"status": "success", "name": name}


@router.post("/api/v1/auth/google-accounts/{name}/test", summary="Тест валидности токена")
async def test_account_endpoint(name: str) -> Dict[str, Any]:
    """Проверяет аутентификацию и валидность токена Google аккаунта."""
    info = get_account_info(name)
    if not info:
        return {"status": "error", "name": name, "message": f"Аккаунт '{name}' не найден"}

    token_rel = info.get("token_file", "")
    token_path = (Path(token_rel) if Path(token_rel).is_absolute() else __root__ / token_rel) if token_rel else (_TOKENS_DIR / f"{name}_token.json")

    if not token_path.exists():
        return {
            "status": "warning",
            "name": name,
            "message": "Учетные данные загружены, но токен OAuth 2.0 еще не создан. Нажмите 'Войти через Google'.",
        }

    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        creds = Credentials.from_authorized_user_file(str(token_path), DEFAULT_SCOPES)
        if creds.valid:
            return {"status": "success", "name": name, "message": "OAuth 2.0 токен валиден и активен", "scopes": list(creds.scopes or DEFAULT_SCOPES)}

        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                with open(token_path, "w", encoding="utf-8") as tf:
                    tf.write(creds.to_json())
                return {"status": "success", "name": name, "message": "Токен успешно обновлен через Refresh Token", "scopes": list(creds.scopes or DEFAULT_SCOPES)}
            except Exception as ref_err:
                return {"status": "warning", "name": name, "message": f"Срок токена истек, требуется повторная авторизация: {ref_err}"}

        return {"status": "warning", "name": name, "message": "Токен недействителен, требуется авторизация"}
    except Exception as exc:
        return {"status": "error", "name": name, "message": f"Ошибка верификации токена: {exc}"}


@router.delete("/api/v1/auth/google-accounts/{name}", summary="Удалить аккаунт из пула")
async def delete_account_endpoint(name: str) -> Dict[str, Any]:
    """Удаляет учетную запись Google из пула."""
    res = delete_google_account(name)
    if not res:
        raise HTTPException(status_code=404, detail=f"Аккаунт '{name}' не найден")
    return {"status": "success", "message": f"Аккаунт '{name}' удален"}


@router.post("/api/v1/auth/telegram/token", summary="Генерация кода для привязки Telegram к аккаунту")
async def generate_telegram_link_code() -> Dict[str, Any]:
    """Генерирует одноразовый 8-значный код привязки к Telegram-боту."""
    from src.user_manager import user_manager
    user = user_manager.get_user_by_id(1)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    token = user_manager.generate_telegram_link_token(user["id"])
    return {
        "status": "success",
        "token": token,
        "expires_in_seconds": 900,
        "instructions": f"Отправьте боту команду: /link {token}",
    }


@router.get("/api/v1/auth/telegram/status", summary="Статус привязки Telegram-аккаунта")
async def get_telegram_link_status() -> Dict[str, Any]:
    """Возвращает информацию о текущей привязке Telegram."""
    from src.user_manager import user_manager
    user = user_manager.get_user_by_id(1)
    if not user:
        return {"status": "error", "linked": False}
    return {
        "status": "success",
        "linked": bool(user.get("telegram_id")),
        "telegram_id": user.get("telegram_id"),
        "telegram_username": user.get("telegram_username"),
        "user_id": user.get("id"),
        "user_name": user.get("name"),
    }


@router.post("/api/v1/auth/telegram/unlink", summary="Отвязка Telegram-аккаунта")
async def unlink_telegram_code() -> Dict[str, Any]:
    """Отвязывает Telegram-аккаунт от текущего профиля."""
    from src.user_manager import user_manager
    user_manager.unlink_telegram_account(1)
    return {"status": "success", "message": "Telegram-аккаунт успешно отвязан"}
