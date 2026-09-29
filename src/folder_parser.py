"""Разбор подготовленной папки ролика: файлы, title, description, settings (ТЗ, раздел 4-8)."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from . import config

logger = logging.getLogger("youtube_uploader.parser")

MULTIPLE_VIDEOS_MSG = (
    "В папке найдено несколько видеофайлов.\n"
    "Оставьте один видеофайл или выберите другой каталог."
)
MULTIPLE_THUMBNAILS_MSG = (
    "В папке найдено несколько возможных обложек.\n"
    "Выберите нужную вручную или назовите её как видео."
)


def find_video(folder: Path) -> tuple[Path | None, str | None]:
    """Ровно один видеофайл среди поддерживаемых расширений."""
    if not folder.is_dir():
        return None, "Папка не существует."
    files = [
        p
        for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in config.SUPPORTED_VIDEO_EXTENSIONS
    ]
    if not files:
        return None, (
            "В папке не найден видеофайл.\n"
            "Поддерживаются: mp4, mov, mkv, avi, m4v, webm, mpeg, mpg."
        )
    if len(files) > 1:
        return None, MULTIPLE_VIDEOS_MSG
    return files[0], None


def _ctime(path: Path) -> float:
    """Дата создания файла (на Windows это st_ctime)."""
    return path.stat().st_ctime


def find_latest_video(folder: Path) -> tuple[Path | None, str | None]:
    """Последний видеофайл по дате создания (режим рабочего стола).

    При равенстве дат берётся файл, имя которого позже по алфавиту.
    """
    if not folder.is_dir():
        return None, "Папка не существует."
    files = [
        p
        for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in config.SUPPORTED_VIDEO_EXTENSIONS
    ]
    if not files:
        return None, (
            "В папке не найден видеофайл.\n"
            "Поддерживаются: mp4, mov, mkv, avi, m4v, webm, mpeg, mpg."
        )
    return max(files, key=lambda p: (_ctime(p), p.name)), None


def find_cover(
    folder: Path, video: Path | None = None
) -> tuple[Path | None, str | None]:
    """Найти очевидную JPEG/PNG-обложку без привязки к имени владельца.

    Обложка с именем видео имеет приоритет. Затем подходят стандартные
    имена, включая прежнее Cover-G. При неоднозначности выбор остаётся
    за пользователем.
    """
    if not folder.is_dir():
        return None, "Папка не существует."
    images = [
        p
        for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in config.COVER_EXTENSIONS
    ]
    if not images:
        return None, (
            "Не найдена обложка JPEG или PNG.\n"
            "Добавьте изображение в папку или выберите обложку вручную."
        )

    def preferred_file(files: list[Path]) -> Path:
        return min(
            files,
            key=lambda p: (config.COVER_EXTENSIONS.index(p.suffix.lower()), p.name.casefold()),
        )

    if video is not None:
        same_name = [p for p in images if p.stem.casefold() == video.stem.casefold()]
        if same_name:
            return preferred_file(same_name), None

    known_names = {name.casefold() for name in config.COMMON_COVER_NAMES}
    named = [p for p in images if p.stem.casefold() in known_names]
    distinct_names = {p.stem.casefold() for p in named}
    if len(distinct_names) == 1:
        return preferred_file(named), None
    if not named and len(images) == 1:
        return images[0], None
    return None, MULTIPLE_THUMBNAILS_MSG


def find_thumbnail(
    folder: Path, video: Path | None = None
) -> tuple[Path | None, str | None]:
    """Тот же универсальный поиск для проверки подготовленной папки."""
    return find_cover(folder, video)


def read_text_file(path: Path) -> tuple[str | None, str | None]:
    """UTF-8, BOM удаляется, пробелы/переводы строк с краёв убираются (ТЗ, раздел 5)."""
    if not path.is_file():
        return None, f"Файл не найден: {path.name}."
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return None, f"Не удалось прочитать файл {path.name}: {exc}"
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None, f"Файл {path.name} не является текстом в кодировке UTF-8."
    return text.strip(), None


def read_title(folder: Path) -> tuple[str | None, str | None]:
    return read_text_file(folder / config.TITLE_FILENAME)


def read_description(folder: Path) -> tuple[str | None, str | None]:
    return read_text_file(folder / config.DESCRIPTION_FILENAME)


def raw_settings(folder: Path) -> tuple[dict, str | None]:
    """Сырой словарь из settings.yaml (без умолчаний). Пусто, если файла нет."""
    path = folder / config.SETTINGS_FILENAME
    if not path.is_file():
        return {}, None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        logger.warning("Некорректный settings.yaml: %s", exc)
        return {}, f"Некорректный файл settings.yaml: {exc}"
    except OSError as exc:
        return {}, f"Не удалось прочитать settings.yaml: {exc}"
    if data is None:
        return {}, None
    if not isinstance(data, dict):
        return {}, "settings.yaml должен содержать словарь (ключ: значение)."
    return data, None


def effective_settings(raw: dict) -> dict:
    """Применить значения по умолчанию (ТЗ, раздел 8).

    Параметр `privacy` не поддерживается и намеренно игнорируется.
    """
    raw = dict(raw or {})
    return {
        "category_id": raw.get("category_id", config.DEFAULT_CATEGORY_ID),
        "tags": raw.get("tags", list(config.DEFAULT_TAGS)) or [],
        "made_for_kids": raw.get("made_for_kids", config.DEFAULT_MADE_FOR_KIDS),
        "notify_subscribers": raw.get(
            "notify_subscribers", config.DEFAULT_NOTIFY_SUBSCRIBERS
        ),
    }
