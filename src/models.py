"""Dataclass-модели и доменные объекты приложения."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from . import config


@dataclass
class VideoPackage:
    """Подготовленная папка ролика: файлы и метаданные."""

    folder: Path
    video_path: Path
    thumbnail_path: Path
    title: str
    description: str
    category_id: str
    tags: list[str] = field(default_factory=list)
    made_for_kids: bool = False
    notify_subscribers: bool = False
    playlist_id: str = ""


class ValidationCode(str, Enum):
    """Коды ошибок локальной валидации (ТЗ, раздел 24)."""

    FOLDER_MISSING = "FOLDER_MISSING"
    NO_VIDEO = "NO_VIDEO"
    MULTIPLE_VIDEOS = "MULTIPLE_VIDEOS"
    NO_TITLE = "NO_TITLE"
    NO_DESCRIPTION = "NO_DESCRIPTION"
    NO_THUMBNAIL = "NO_THUMBNAIL"
    MULTIPLE_THUMBNAILS = "MULTIPLE_THUMBNAILS"
    EMPTY_TITLE = "EMPTY_TITLE"
    TITLE_TOO_LONG = "TITLE_TOO_LONG"
    DESCRIPTION_TOO_LARGE = "DESCRIPTION_TOO_LARGE"
    THUMBNAIL_FORMAT = "THUMBNAIL_FORMAT"
    THUMBNAIL_TOO_LARGE = "THUMBNAIL_TOO_LARGE"
    INVALID_YAML = "INVALID_YAML"
    INVALID_TAGS = "INVALID_TAGS"
    INVALID_SETTING_VALUE = "INVALID_SETTING_VALUE"
    NO_CLIENT_SECRET = "NO_CLIENT_SECRET"
    TEMPLATE_BROKEN = "TEMPLATE_BROKEN"


@dataclass
class ValidationIssue:
    """Одна найденная проблема: код + человекочитаемое сообщение."""

    code: ValidationCode
    message: str


class Outcome(str, Enum):
    """Итог загрузки (ТЗ, раздел 20)."""

    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"


@dataclass
class UploadResult:
    """Результат полного цикла: видео + обложка."""

    outcome: Outcome
    video_id: str | None = None
    video_url: str | None = None
    thumbnail_uploaded: bool = False
    playlist_added: bool = False
    playlist_requested: bool = False
    message: str = ""
    detail: str | None = None


@dataclass
class UploadMarker:
    """Служебный файл .youtube-upload.json (ТЗ, раздел 21)."""

    video_id: str
    uploaded_at: str
    status: str = "private"
    thumbnail_uploaded: bool = False
    video_name: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> UploadMarker:
        return cls(
            video_id=str(data.get("video_id", "")),
            uploaded_at=str(data.get("uploaded_at", "")),
            status=str(data.get("status", "private")),
            thumbnail_uploaded=bool(data.get("thumbnail_uploaded", False)),
            video_name=str(data.get("video_name", "")),
        )


def marker_path(folder: Path) -> Path:
    """Путь к .youtube-upload.json внутри папки ролика."""
    return folder / config.DUP_MARKER_FILENAME


def write_marker(folder: Path, marker: UploadMarker) -> Path:
    """Сохранить служебный файл в папку ролика."""
    path = marker_path(folder)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(marker.to_dict(), fh, ensure_ascii=False, indent=2)
    return path


def read_marker(folder: Path) -> UploadMarker | None:
    """Прочитать служебный файл; при повреждении вернуть None."""
    path = marker_path(folder)
    if not path.is_file():
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return UploadMarker.from_dict(json.load(fh))
    except (OSError, ValueError, TypeError):
        return None


def now_iso() -> str:
    """Текущее время в ISO 8601 с часовым поясом."""
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
