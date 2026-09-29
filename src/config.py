"""Централизованные константы и настройки по умолчанию.

Здесь НЕ существует настройки privacy/приватности: статус видео жёстко
зашит в youtube_uploader.py как литерал "private" и ни откуда не читается.
"""

from __future__ import annotations

import os
import sys
from hashlib import sha256
from pathlib import Path

APP_NAME = "YouTubePrivateUploader"
INSTALLATION_ID_FILENAME = ".installation-id"

# --- Лимиты YouTube Data API v3 (проверены по официальной документации) ---
MAX_TITLE_LENGTH = 100
MAX_DESCRIPTION_UTF8_BYTES = 5000
MAX_TAGS_TOTAL_CHARS = 500
MAX_THUMBNAIL_BYTES = 2 * 1024 * 1024  # 2 МБ

# --- Файлы папки ролика ---
SUPPORTED_VIDEO_EXTENSIONS = (
    ".mp4",
    ".mov",
    ".mkv",
    ".avi",
    ".m4v",
    ".webm",
    ".mpeg",
    ".mpg",
)
COVER_FILENAME = "Cover-G"
COVER_EXTENSIONS = (".jpg", ".jpeg", ".png")
COMMON_COVER_NAMES = ("thumbnail", "thumb", "cover", "poster", "обложка", COVER_FILENAME)
TITLE_FILENAME = "title.txt"
DESCRIPTION_FILENAME = "description.txt"
SETTINGS_FILENAME = "settings.yaml"
DUP_MARKER_FILENAME = ".youtube-upload.json"

# --- Значения по умолчанию для settings.yaml (ТЗ, раздел 8) ---
DEFAULT_CATEGORY_ID = "22"
DEFAULT_TAGS: list[str] = []
DEFAULT_MADE_FOR_KIDS = False
DEFAULT_NOTIFY_SUBSCRIBERS = False

# --- ОAuth ---
# youtube.upload — загрузка видео; youtube.force-ssl — плейлисты
# (список плейлистов канала + добавление видео в плейлист).
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]
APPLICATION_NAME = "YouTube Private Uploader"


def desktop_dir() -> Path:
    """Путь к «Рабочему столу» пользователя (через Windows API, ctypes).

    Пользователь может выбрать его как рабочую папку вручную.
    """
    try:
        import ctypes
        from ctypes import wintypes

        CSIDL_DESKTOPDIRECTORY = 0x0010
        buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
        result = ctypes.windll.shell32.SHGetFolderPathW(
            None, CSIDL_DESKTOPDIRECTORY, None, 0, buf
        )
        if result == 0 and buf.value:
            return Path(buf.value)
    except (AttributeError, OSError):
        return Path.home() / "Desktop"
    return Path.home() / "Desktop"


def project_root() -> Path:
    """Корень проекта (папка, где лежит src/, config/, ...)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def config_dir() -> Path:
    """Каталог config/ относительно приложения (client_secret.json)."""
    return project_root() / "config"


def client_secret_path() -> Path:
    """config/client_secret.json — OAuth Client JSON, пользователь кладёт сам."""
    return config_dir() / "client_secret.json"


def app_data_dir(env_override: str = "YOUTUBE_PRIVATE_UPLOADER_DATA_DIR") -> Path:
    """Per-installation data under %APPDATA%\\YouTubePrivateUploader.

    Переменная окружения YOUTUBE_PRIVATE_UPLOADER_DATA_DIR позволяет
    перенаправить каталог данных (используется в тестах).
    """
    override = os.environ.get(env_override)
    if override:
        return Path(override)
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    root = project_root()
    marker = root / INSTALLATION_ID_FILENAME
    try:
        installation_id = marker.read_text(encoding="ascii").strip().lower()
    except (OSError, UnicodeError):
        installation_id = ""
    if len(installation_id) != 64 or any(c not in "0123456789abcdef" for c in installation_id):
        # Source checkouts and manually copied portable builds have no installer marker.
        # A stable path key still keeps them separate from old unscoped AppData.
        installation_id = sha256(str(root.resolve()).casefold().encode("utf-8")).hexdigest()
    return Path(base) / APP_NAME / "installations" / installation_id


def logs_dir() -> Path:
    """Каталог логов текущей установки."""
    return app_data_dir() / "logs"


def token_path() -> Path:
    """OAuth-токен текущей установки."""
    return app_data_dir() / "token.json"


def settings_path() -> Path:
    """Настройки текущей установки."""
    return app_data_dir() / "settings.json"


# --- Retry / resumable upload (ТЗ, разделы 16-17) ---
MAX_RETRIES = 8
RETRYABLE_STATUS_CODES = frozenset({500, 502, 503, 504})
# Временные исключения соединения, которые имеет смысл повторить.
RETRYABLE_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    ConnectionResetError,
    ConnectionAbortedError,
    ConnectionRefusedError,
)

# --- Ссылки ---
VIDEO_URL_TEMPLATE = "https://www.youtube.com/watch?v={video_id}"
STUDIO_URL_TEMPLATE = (
    "https://studio.youtube.com/video/{video_id}/edit"
)
