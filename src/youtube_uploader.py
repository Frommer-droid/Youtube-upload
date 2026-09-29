"""Только вызовы YouTube Data API: videos.insert + thumbnails.set (ТЗ, разделы 16-20).

ВНИМАНИЕ: privacyStatus жёстко задан ниже литералом "private" и НЕ читается
ни из settings.yaml, ни из окружения, ни из GUI. Не выносить его в настройки.
"""

from __future__ import annotations

import json
import logging
import random
import time

from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from . import config
from .models import Outcome, UploadResult, VideoPackage

logger = logging.getLogger("youtube_uploader.uploader")

RETRYABLE_EXCEPTIONS = config.RETRYABLE_EXCEPTIONS + (IOError, OSError)

THUMBNAIL_REJECTED_MSG = (
    "YouTube отклонил изображение обложки.\n"
    "Видео при этом уже загружено как Private."
)
QUOTA_MSG = (
    "YouTube API отклонил запрос из-за ограничения квоты.\n\n"
    "Попробуйте позднее или проверьте квоты проекта Google Cloud."
)
NETWORK_MSG = (
    "Не удалось подключиться к YouTube.\n\n"
    "Проверьте интернет-соединение и повторите попытку."
)
PLAYLIST_FORBIDDEN_MSG = (
    "У приложения недостаточно прав для работы с плейлистами.\n\n"
    "Нужно переавторизоваться: сейчас будет выполнен повторный вход в Google."
)
PLAYLIST_MISSING_MSG = (
    "Выбранный плейлист больше не существует (возможно, удалён).\n"
    "Видео при этом уже загружено как Private."
)


class UploadCancelled(Exception):
    """Загрузка прервана пользователем."""


class UploadError(Exception):
    """Ошибка загрузки с человекочитаемым сообщением для UI."""

    def __init__(self, message: str, detail: str | None = None, reauth: bool = False):
        super().__init__(message)
        self.message = message
        self.detail = detail
        self.reauth = reauth


def build_upload_body(package: VideoPackage) -> dict:
    """Тело запроса videos.insert.

    privacyStatus задаётся исключительно этим кодом:
    """
    body = {
        "snippet": {
            "title": package.title,
            "description": package.description,
            "categoryId": package.category_id,
        },
        "status": {
            "privacyStatus": "private",
            "selfDeclaredMadeForKids": package.made_for_kids,
        },
    }
    if package.tags:
        body["snippet"]["tags"] = package.tags
    # Гарантия: статус приватности никогда не может стать иным.
    assert body["status"]["privacyStatus"] == "private"
    return body


def _extract_error_info(exc: HttpError) -> tuple[str, str, str]:
    """Извлечь (status, reason, message) из тела ответа API."""
    status = int(getattr(exc, "resp", None).status) if getattr(exc, "resp", None) else 0
    reason = ""
    message = ""
    content = getattr(exc, "content", b"") or b""
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    try:
        data = json.loads(content)
        error = data.get("error", {}) or {}
        message = error.get("message", "")
        errors = error.get("errors") or []
        if errors:
            reason = errors[0].get("reason", "")
    except (ValueError, AttributeError):
        pass
    return str(status), reason, message


def _http_error_to_upload_error(exc: HttpError) -> UploadError:
    status, reason, message = _extract_error_info(exc)
    logger.error("HttpError %s reason=%s message=%s", status, reason, message)
    if status == "401" or reason == "invalid_grant" or reason == "authError":
        return UploadError(
            "Авторизация Google потеряна.\n\nПовторите авторизацию "
            "кнопкой «Сбросить авторизацию» и загрузите видео снова.",
            detail=f"HTTP {status} reason={reason} {message}",
        )
    if reason in ("quotaExceeded", "quotaExceededBandwidth", "rateLimitExceeded", "dailyLimitExceeded"):
        return UploadError(QUOTA_MSG, detail=f"HTTP {status} {message}")
    if status == "403" or reason == "forbidden":
        human = message or "нет данных"
        return UploadError(
            f"YouTube отклонил запрос: {human}",
            detail=f"HTTP {status} reason={reason}",
        )
    if status == "404":
        return UploadError(
            "Не удалось продолжить загрузку: сессия загрузки была потеряна.",
            detail=f"HTTP 404 {message}",
        )
    if status in {"400", "422"}:
        human = message or "некорректные данные"
        return UploadError(
            f"YouTube отклонил запрос: {human}",
            detail=f"HTTP {status} reason={reason}",
        )
    return UploadError(
        NETWORK_MSG, detail=f"HTTP {status} reason={reason} {message}"
    )


def _sleep_backoff(attempt: int) -> None:
    delay = min(2 ** attempt, 120) + random.uniform(0, 1)
    logger.info("Повторная попытка через %.1f сек (попытка %d)", delay, attempt)
    time.sleep(delay)


def _next_chunk_with_retries(request, is_canceled, on_progress=None) -> dict:
    """next_chunk() с exponential backoff для временных ошибок (ТЗ, раздел 17).

    Не ретраим бесконечно: MAX_RETRIES; не ретраим 400/403/квоту/401.
    """
    response = None
    retry = 0
    while response is None:
        if is_canceled is not None and is_canceled():
            raise UploadCancelled()
        try:
            status, response = request.next_chunk()
            if status is not None:
                percent = int(status.progress() * 100)
                if on_progress:
                    on_progress(percent)
                logger.info("Прогресс загрузки: %d%%", percent)
        except HttpError as exc:
            status_code = int(getattr(exc, "resp", None).status) if getattr(exc, "resp", None) else 0
            if status_code in config.RETRYABLE_STATUS_CODES and retry < config.MAX_RETRIES:
                logger.warning("Временная ошибка %s, повторяю", status_code)
                retry += 1
                _sleep_backoff(retry)
                continue
            raise _http_error_to_upload_error(exc) from exc
        except RETRYABLE_EXCEPTIONS as exc:
            if retry < config.MAX_RETRIES:
                logger.warning("Временная ошибка сети: %s", exc)
                retry += 1
                _sleep_backoff(retry)
                continue
            raise UploadError(NETWORK_MSG, detail=str(exc)) from exc
    if not isinstance(response, dict) or not response.get("id"):
        raise UploadError(
            "YouTube не вернул Video ID в ответе на загрузку.",
            detail=str(response)[:2000],
        )
    return response


def upload_video(youtube, package: VideoPackage, on_progress=None, is_canceled=None) -> str:
    """Загрузить видео resumable upload; вернуть videoId.

    ТЗ, разделы 16, 42: загрузка считается успешной только после получения
    ответа videos.insert с YouTube videoId.
    """
    logger.info(
        "Начало загрузки: %s (%d байт), title=%r",
        package.video_path.name,
        package.video_path.stat().st_size,
        package.title[:60],
    )
    body = build_upload_body(package)
    media = MediaFileUpload(
        str(package.video_path),
        mimetype="application/octet-stream",
        resumable=True,
    )
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
        notifySubscribers=package.notify_subscribers,
    )

    response = _next_chunk_with_retries(request, is_canceled, on_progress)
    video_id = str(response["id"])
    logger.info("Видео загружено, video_id=%s", video_id)
    return video_id


def upload_thumbnail(youtube, video_id: str, thumbnail_path) -> None:
    """Установить обложку через thumbnails.set (ТЗ, раздел 19)."""
    logger.info("Устанавливаю обложку для video_id=%s", video_id)
    media = MediaFileUpload(
        str(thumbnail_path),
        mimetype=(
            "image/jpeg"
            if thumbnail_path.suffix.lower() in (".jpg", ".jpeg")
            else "image/png"
        ),
    )
    try:
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=media,
        ).execute()
        logger.info("Обложка установлена для video_id=%s", video_id)
    except HttpError as exc:
        status, reason, message = _extract_error_info(exc)
        logger.error("thumbnails.set: HTTP %s reason=%s %s", status, reason, message)
        if status in ("401",) or reason == "invalid_grant":
            raise UploadError(
                "Авторизация Google потеряна при установке обложки.\n"
                "Видео уже загружено как Private.",
                detail=f"HTTP {status} {message}",
            ) from exc
        raise UploadError(
            THUMBNAIL_REJECTED_MSG, detail=f"HTTP {status} {message}"
        ) from exc


def list_playlists(youtube) -> list[dict]:
    """Список плейлистов канала: [{"id": "...", "title": "..."}] по порядку.

    Экономит квоту: maxResults=50 (обычно больше плейлистов не бывает).
    Ошибка 403 insufficientPermissions означает, что токен устарел по правам
    (scope force-ssl) — для UI помечается флагом reauth=True.
    """
    try:
        response = (
            youtube.playlists()
            .list(part="snippet", mine=True, maxResults=50)
            .execute()
        )
    except HttpError as exc:
        status, reason, message = _extract_error_info(exc)
        logger.error("playlists.list: HTTP %s reason=%s %s", status, reason, message)
        if status == "401" or reason in ("invalid_grant", "authError"):
            raise UploadError(
                "Авторизация Google потеряна.\n\n"
                "Повторите авторизацию кнопкой «Сбросить авторизацию».",
                detail=f"HTTP {status} reason={reason} {message}",
            ) from exc
        if status == "403" or reason in ("forbidden", "insufficientPermissions"):
            raise UploadError(PLAYLIST_FORBIDDEN_MSG, reauth=True) from exc
        raise UploadError(NETWORK_MSG, detail=f"HTTP {status} reason={reason} {message}") from exc
    items = response.get("items") or []
    result: list[dict] = []
    seen: set[str] = set()
    for item in items:
        pid = str(item.get("id", ""))
        if not pid or pid in seen:
            continue
        seen.add(pid)
        snippet = item.get("snippet") or {}
        result.append({"id": pid, "title": str(snippet.get("title", ""))})
    logger.info("Получено плейлистов: %d", len(result))
    return result


def add_video_to_playlist(youtube, playlist_id: str, video_id: str) -> None:
    """Добавить уже загруженное видео в плейлист (playlistItems.insert)."""
    body = {
        "snippet": {
            "playlistId": playlist_id,
            "resourceId": {"kind": "youtube#video", "videoId": video_id},
        }
    }
    try:
        youtube.playlistItems().insert(part="snippet", body=body).execute()
        logger.info("Видео %s добавлено в плейлист %s", video_id, playlist_id)
    except HttpError as exc:
        status, reason, message = _extract_error_info(exc)
        logger.error("playlistItems.insert: HTTP %s reason=%s %s", status, reason, message)
        if status == "401" or reason in ("invalid_grant", "authError"):
            raise UploadError(
                "Авторизация Google потеряна при добавлении в плейлист.\n"
                "Видео при этом уже загружено как Private.",
                detail=f"HTTP {status} {message}",
            ) from exc
        if status == "404":
            raise UploadError(PLAYLIST_MISSING_MSG, detail=f"HTTP 404 {message}") from exc
        raise UploadError(
            "Не удалось добавить видео в плейлист.\n"
            "Видео при этом уже загружено как Private.",
            detail=f"HTTP {status} reason={reason} {message}",
        ) from exc


def run_upload(
    youtube,
    package: VideoPackage,
    on_progress=None,
    on_stage=None,
    is_canceled=None,
) -> UploadResult:
    """Полный цикл: видео → thumbnail → итог (ТЗ, разделы 16-20)."""
    if on_stage:
        on_stage("Загрузка видео...")

    try:
        video_id = upload_video(youtube, package, on_progress, is_canceled)
    except UploadCancelled:
        return UploadResult(
            outcome=Outcome.FAILED, message="Загрузка отменена."
        )
    except UploadError as exc:
        return UploadResult(
            outcome=Outcome.FAILED, message=exc.message, detail=exc.detail
        )

    url = config.VIDEO_URL_TEMPLATE.format(video_id=video_id)

    if on_stage:
        on_stage("Видео загружено. Устанавливаю обложку...")

    thumb_ok = True
    thumb_error: UploadError | None = None
    try:
        upload_thumbnail(youtube, video_id, package.thumbnail_path)
    except UploadCancelled:
        return UploadResult(
            outcome=Outcome.PARTIAL_SUCCESS,
            video_id=video_id,
            video_url=url,
            thumbnail_uploaded=False,
            playlist_requested=bool(package.playlist_id),
            message="Видео загружено как Private, установка обложки была прервана.",
        )
    except UploadError as exc:
        logger.error("Не удалось установить обложку: %s", exc.detail)
        thumb_ok = False
        thumb_error = exc

    playlist_ok: bool | None = None
    playlist_error: UploadError | None = None
    if package.playlist_id:
        playlist_ok = False
        if on_stage:
            on_stage("Добавляю видео в плейлист...")
        try:
            add_video_to_playlist(youtube, package.playlist_id, video_id)
            playlist_ok = True
        except UploadError as exc:
            logger.error("Не удалось добавить в плейлист: %s", exc.detail)
            playlist_error = exc

    problems = [
        (name, exc)
        for name, exc in (
            ("обложку установить не удалось", thumb_error),
            ("видео в плейлист добавить не удалось", playlist_error),
        )
        if exc is not None
    ]

    if problems:
        lines = [
            "Видео успешно загружено на YouTube как Private.",
            "",
            "Однако:",
        ]
        for name, exc in problems:
            lines.append(f"- {name}:\n  {exc.message}")
        lines.extend(
            [
                "",
                "Видео удалять не нужно.",
                "Проблемы можно поправить вручную в YouTube Studio.",
            ]
        )
        return UploadResult(
            outcome=Outcome.PARTIAL_SUCCESS,
            video_id=video_id,
            video_url=url,
            thumbnail_uploaded=thumb_ok,
            playlist_added=bool(playlist_ok),
            playlist_requested=bool(package.playlist_id),
            message="\n".join(lines),
            detail="; ".join(exc.detail or "" for _, exc in problems) or None,
        )

    playlist_line = (
        "Плейлист:\nДобавлено\n\n"
        if playlist_ok
        else ""
    )
    return UploadResult(
        outcome=Outcome.SUCCESS,
        video_id=video_id,
        video_url=url,
        thumbnail_uploaded=True,
        playlist_added=bool(playlist_ok),
        playlist_requested=bool(package.playlist_id),
        message=(
            "Видео успешно загружено на YouTube.\n\n"
            f"Название:\n{package.title}\n\n"
            "Статус:\nPRIVATE\n\n"
            "Обложка:\nУстановлена\n\n"
            f"{playlist_line}"
            f"Video ID:\n{video_id}"
        ),
    )
