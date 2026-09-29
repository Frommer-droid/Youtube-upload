"""Локальная валидация до вызова YouTube API (ТЗ, раздел 24).

- validate_folder() — проверка папки ролика целиком (файлы + содержимое);
- validate_package() — проверка состояния полей VideoPackage (используется GUI
  после ручного редактирования названия/описания/тегов пользователем).
"""

from __future__ import annotations

import logging
from pathlib import Path

from . import config, folder_parser
from .models import ValidationCode, ValidationIssue, VideoPackage

logger = logging.getLogger("youtube_uploader.validators")

NO_CLIENT_SECRET_MSG = (
    "Не найден файл OAuth client_secret.json.\n\n"
    "Откройте инструкцию SETUP_GOOGLE.md и выполните первоначальную настройку."
)
THUMBNAIL_TOO_LARGE_MSG = (
    "Размер обложки превышает допустимый размер YouTube API — 2 МБ.\n"
    "Уменьшите размер изображения и повторите загрузку."
)


def _clean_tags(raw_tags) -> tuple[list[str] | None, str | None]:
    if not isinstance(raw_tags, list):
        return None, (
            "Теги должны быть списком строк:\n"
            "tags:\n  - слово\n  - ещё слово"
        )
    cleaned = []
    for item in raw_tags:
        if not isinstance(item, str):
            return None, "Все теги должны быть строками."
        tag = item.strip()
        if tag:
            cleaned.append(tag)
    total = sum(len(tag) + 1 for tag in cleaned)
    if total > config.MAX_TAGS_TOTAL_CHARS:
        return None, (
            f"Совокупный размер тегов превышает лимит YouTube — "
            f"{total} символов из {config.MAX_TAGS_TOTAL_CHARS}.\n"
            "Сократите теги."
        )
    return cleaned, None


def validate_package(
    package: VideoPackage | None,
    check_client_secret: bool = True,
) -> list[ValidationIssue]:
    """Проверка содержимого пакета: лимиты YouTube + обложка + теги.

    Не проверяет структуру папки (видео/файлы) — этим занимается validate_folder.
    """
    issues: list[ValidationIssue] = []
    if package is None:
        issues.append(
            ValidationIssue(
                ValidationCode.NO_VIDEO,
                "Не выбран видеофайл.\nВыберите папку ролика или видео вручную.",
            )
        )
        return issues

    if not package.title:
        issues.append(
            ValidationIssue(
                ValidationCode.EMPTY_TITLE,
                "Название пустое. Введите название песни.",
            )
        )
    elif len(package.title) > config.MAX_TITLE_LENGTH:
        issues.append(
            ValidationIssue(
                ValidationCode.TITLE_TOO_LONG,
                f"Название длиннее лимита YouTube — {len(package.title)} символов "
                f"из {config.MAX_TITLE_LENGTH}.\nСократите название.",
            )
        )

    size = len(package.description.encode("utf-8"))
    if size > config.MAX_DESCRIPTION_UTF8_BYTES:
        issues.append(
            ValidationIssue(
                ValidationCode.DESCRIPTION_TOO_LARGE,
                f"Описание превышает лимит YouTube — {size} байт UTF-8 "
                f"из {config.MAX_DESCRIPTION_UTF8_BYTES}.\nСократите описание.",
            )
        )

    if not package.video_path or not package.video_path.is_file():
        issues.append(
            ValidationIssue(
                ValidationCode.NO_VIDEO,
                "Видеофайл не найден по указанному пути.",
            )
        )
    elif package.video_path.suffix.lower() not in config.SUPPORTED_VIDEO_EXTENSIONS:
        issues.append(
            ValidationIssue(
                ValidationCode.NO_VIDEO,
                "Видеофайл имеет неподдерживаемое расширение. "
                "Допустимо: mp4, mov, mkv, avi, m4v, webm, mpeg, mpg.",
            )
        )

    if not package.thumbnail_path or not package.thumbnail_path.is_file():
        issues.append(
            ValidationIssue(
                ValidationCode.NO_THUMBNAIL,
                "Не выбрана обложка.\nНажмите «Добавить обложку» или положите "
                "изображение JPEG/PNG рядом с видео.",
            )
        )
    else:
        ext = package.thumbnail_path.suffix.lower()
        if ext not in (".jpg", ".jpeg", ".png"):
            issues.append(
                ValidationIssue(
                    ValidationCode.THUMBNAIL_FORMAT,
                    "Обложка должна быть в формате JPEG или PNG.",
                )
            )
        try:
            size = package.thumbnail_path.stat().st_size
        except OSError:
            size = 0
        if size > config.MAX_THUMBNAIL_BYTES:
            issues.append(
                ValidationIssue(
                    ValidationCode.THUMBNAIL_TOO_LARGE, THUMBNAIL_TOO_LARGE_MSG
                )
            )

    raw_cat = package.category_id
    if isinstance(raw_cat, bool) or not isinstance(raw_cat, (str, int)):
        issues.append(
            ValidationIssue(
                ValidationCode.INVALID_SETTING_VALUE,
                "category_id должен быть строкой или числом.",
            )
        )
    elif not str(raw_cat).isdigit():
        issues.append(
            ValidationIssue(
                ValidationCode.INVALID_SETTING_VALUE,
                "category_id должен содержать только цифры.",
            )
        )

    _cleaned_tags, tags_err = _clean_tags(package.tags)
    if tags_err:
        issues.append(ValidationIssue(ValidationCode.INVALID_TAGS, tags_err))

    if check_client_secret and not config.client_secret_path().is_file():
        issues.append(
            ValidationIssue(ValidationCode.NO_CLIENT_SECRET, NO_CLIENT_SECRET_MSG)
        )

    return issues


def validate_folder(folder: str | Path) -> tuple[VideoPackage | None, list[ValidationIssue]]:
    """Полная локальная проверка папки (файлы + содержимое).

    Возвращает (package, issues). package создан, только если удалось
    прочитать все необходимые файлы; upload разрешён только при issues == [].
    """
    path = Path(folder)
    issues: list[ValidationIssue] = []

    if not path.is_dir():
        issues.append(
            ValidationIssue(
                ValidationCode.FOLDER_MISSING, f"Папка не существует: {path}"
            )
        )
        return None, issues

    video_path, video_err = folder_parser.find_video(path)
    if video_err:
        issues.append(
            ValidationIssue(
                ValidationCode.MULTIPLE_VIDEOS
                if video_err == folder_parser.MULTIPLE_VIDEOS_MSG
                else ValidationCode.NO_VIDEO,
                video_err,
            )
        )

    thumb_path, thumb_err = folder_parser.find_thumbnail(path, video_path)
    if thumb_err:
        issues.append(
            ValidationIssue(
                ValidationCode.MULTIPLE_THUMBNAILS
                if thumb_err == folder_parser.MULTIPLE_THUMBNAILS_MSG
                else ValidationCode.NO_THUMBNAIL,
                thumb_err,
            )
        )

    title, title_err = folder_parser.read_title(path)
    if title_err:
        issues.append(ValidationIssue(ValidationCode.NO_TITLE, title_err))

    description, desc_err = folder_parser.read_description(path)
    if desc_err:
        issues.append(ValidationIssue(ValidationCode.NO_DESCRIPTION, desc_err))

    raw_yaml, yaml_err = folder_parser.raw_settings(path)
    if yaml_err:
        issues.append(ValidationIssue(ValidationCode.INVALID_YAML, yaml_err))

    settings = folder_parser.effective_settings(raw_yaml) if not yaml_err else {}
    raw_cat = settings.get("category_id", config.DEFAULT_CATEGORY_ID)
    raw_kids = settings.get("made_for_kids", config.DEFAULT_MADE_FOR_KIDS)
    raw_notify = settings.get(
        "notify_subscribers", config.DEFAULT_NOTIFY_SUBSCRIBERS
    )
    raw_tags = settings.get("tags", [])
    category_id = raw_cat if isinstance(raw_cat, (str, int)) and not isinstance(raw_cat, bool) else config.DEFAULT_CATEGORY_ID
    made_for_kids = raw_kids if isinstance(raw_kids, bool) else config.DEFAULT_MADE_FOR_KIDS
    notify_subscribers = (
        raw_notify if isinstance(raw_notify, bool) else config.DEFAULT_NOTIFY_SUBSCRIBERS
    )
    tags = list(raw_tags) if isinstance(raw_tags, list) else []

    if not yaml_err:
        raw_cat = settings["category_id"]
        if isinstance(raw_cat, bool) or not isinstance(raw_cat, (str, int)):
            issues.append(
                ValidationIssue(
                    ValidationCode.INVALID_SETTING_VALUE,
                    "category_id в settings.yaml должен быть строкой или числом.",
                )
            )
        elif not str(raw_cat).isdigit():
            issues.append(
                ValidationIssue(
                    ValidationCode.INVALID_SETTING_VALUE,
                    "category_id в settings.yaml должен содержать только цифры.",
                )
            )
        if not isinstance(raw_tags, list):
            issues.append(
                ValidationIssue(
                    ValidationCode.INVALID_TAGS,
                    "tags в settings.yaml должен быть списком строк.",
                )
            )
        for key in ("made_for_kids", "notify_subscribers"):
            if not isinstance(settings[key], bool):
                issues.append(
                    ValidationIssue(
                        ValidationCode.INVALID_SETTING_VALUE,
                        f"{key} в settings.yaml должен быть true или false.",
                    )
                )

    if video_path is None or thumb_path is None or title is None or description is None:
        # Несмотря на отсутствие части файлов, валидируем то, что есть.
        if video_path is not None and thumb_path is not None and title is not None:
            package = VideoPackage(
                folder=path,
                video_path=video_path,
                thumbnail_path=thumb_path,
                title=title,
                description=description or "",
                category_id=str(category_id),
                tags=list(tags),
                made_for_kids=bool(made_for_kids),
                notify_subscribers=bool(notify_subscribers),
            )
            issues += validate_package(package)
        return None, issues

    package = VideoPackage(
        folder=path,
        video_path=video_path,
        thumbnail_path=thumb_path,
        title=title,
        description=description,
        category_id=str(category_id),
        tags=list(tags),
        made_for_kids=bool(made_for_kids),
        notify_subscribers=bool(notify_subscribers),
    )
    issues += validate_package(package)
    return package, issues
