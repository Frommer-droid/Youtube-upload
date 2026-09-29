"""OAuth 2.0 Desktop Application для YouTube Data API (ТЗ, разделы 12-15).

Модуль отвечает только за: загрузку/сохранение credentials, refresh,
запуск OAuth в браузере, удаление token.json и создание клиента API.
OAuth-логика не размещена в GUI.
"""

from __future__ import annotations

import json
import logging

from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from . import config

logger = logging.getLogger("youtube_uploader.auth")

NO_CLIENT_SECRET_MSG = (
    "Не найден файл OAuth client_secret.json.\n\n"
    "Откройте инструкцию SETUP_GOOGLE.md и выполните первоначальную настройку."
)

REAUTH_MSG = (
    "Сеанс авторизации Google завершился.\n\n"
    "Повторите авторизацию: откроется браузер Google."
)

AUTH_FAILED_MSG = (
    "Не удалось авторизоваться в Google.\n\nПовторите авторизацию."
)


class AuthError(Exception):
    """Ошибка авторизации с человекочитаемым сообщением."""

    def __init__(self, message: str, detail: str | None = None):
        super().__init__(message)
        self.message = message
        self.detail = detail


def client_secret_exists() -> bool:
    return config.client_secret_path().is_file()


def load_credentials() -> Credentials | None:
    """Прочитать token.json. Повреждённый файл считается отсутствующим."""
    path = config.token_path()
    if not path.is_file():
        return None
    try:
        creds = Credentials.from_authorized_user_file(
            str(path), scopes=config.SCOPES
        )
        return creds
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        logger.warning("Повреждённый token.json: %s", exc)
        return None


def save_credentials(creds: Credentials) -> None:
    path = config.token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.loads(creds.to_json())
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh)
    logger.info("Credentials сохранены: %s", path)


def remove_credentials() -> bool:
    """Удалить локальный token.json (кнопка «Сбросить авторизацию»)."""
    path = config.token_path()
    try:
        if path.is_file():
            path.unlink()
            logger.info("token.json удалён по просьбе пользователя")
            return True
    except OSError as exc:
        logger.error("Не удалось удалить token.json: %s", exc)
    return False


def run_oauth() -> Credentials:
    """Запустить OAuth Desktop flow в системном браузере (ТЗ, раздел 12)."""
    secret = config.client_secret_path()
    if not secret.is_file():
        raise AuthError(NO_CLIENT_SECRET_MSG)
    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            str(secret), scopes=config.SCOPES
        )
        creds = flow.run_local_server(
            host="localhost", port=0, open_browser=True, prompt="consent"
        )
    except AuthError:
        raise
    except Exception as exc:
        logger.exception("Ошибка OAuth flow")
        raise AuthError(AUTH_FAILED_MSG, detail=str(exc)) from exc
    logger.info("OAuth завершён")
    return creds


def ensure_credentials() -> Credentials:
    """Загрузить действующие credentials; при необходимости — refresh или OAuth.

    ТЗ, раздел 12: истёкший access token обновляется автоматически;
    нерабочие credentials удаляются и запускается OAuth заново.
    """
    creds = load_credentials()

    if creds is None:
        logger.info("OAuth-токен отсутствует, запускаю авторизацию")
        creds = run_oauth()
        save_credentials(creds)
        return creds

    if not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                logger.info("Обновляю access token")
                creds.refresh(Request())
                save_credentials(creds)
                return creds
            except (GoogleAuthError, OSError) as exc:
                logger.warning("Refresh не удался: %s", exc)
        logger.warning("Credentials недействительны, запускаю OAuth заново")
        remove_credentials()
        creds = run_oauth()
        save_credentials(creds)
    return creds


def build_youtube(creds: Credentials):
    """Создать клиент YouTube Data API v3 (ТЗ, раздел 15)."""
    return build(
        "youtube",
        "v3",
        credentials=creds,
        cache_discovery=False,
        static_discovery=False,
    )
