"""Тесты загрузчика без реального YouTube API — только mock (ТЗ, раздел 34).

Критичная проверка: privacyStatus навсегда "private".
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from googleapiclient.errors import HttpError

from src import youtube_uploader
from src.models import Outcome, VideoPackage


class Resp:
    def __init__(self, status):
        self.status = status
        self.reason = f"HTTP {status}"


def make_http_error(status: int, reason: str = "", message: str = "") -> HttpError:
    payload = {
        "error": {
            "code": status,
            "message": message or f"error {status}",
            "errors": [{"reason": reason, "message": message or f"error {status}"}],
        }
    }
    return HttpError(Resp(status), json.dumps(payload).encode("utf-8"))


class FakeMedia:
    pass


class FakeRequest:
    """next_chunk(): первые `fail_times` вызовов падают ошибкой, потом успех."""

    def __init__(self, error=None, error_times=1, response=None):
        self.error = error
        self.error_times = error_times
        self.calls = 0
        self.response = response or {"id": "VID123"}

    def next_chunk(self):
        self.calls += 1
        if self.error is not None and self.calls <= self.error_times:
            raise self.error
        return (None, self.response)


class FakePlaylistItems:
    def __init__(self, error=None):
        self.error = error
        self.kwargs = None

    def insert(self, **kwargs):
        self.kwargs = kwargs
        if self.error is not None:
            raise self.error
        return self

    def execute(self):
        return {}


class FakePlaylists:
    def __init__(self, response=None, error=None):
        self.response = response or {"items": []}
        self.error = error
        self.kwargs = None

    def list(self, **kwargs):
        self.kwargs = kwargs
        return self

    def execute(self):
        if self.error is not None:
            raise self.error
        return self.response


class FakeYouTube:
    """Записывает все вызовы API; сеть не трогает."""

    def __init__(
        self,
        insert_error=None,
        insert_error_times=1,
        thumb_error=None,
        playlist_items_error=None,
        playlists_response=None,
        playlists_error=None,
    ):
        self.insert_kwargs = None
        self.thumb_kwargs = None
        self._insert_error = insert_error
        self._insert_error_times = insert_error_times
        self._thumb_error = thumb_error
        self._playlist_items = FakePlaylistItems(playlist_items_error)
        self._playlists = FakePlaylists(playlists_response, playlists_error)

    def videos(self):
        return self

    def insert(self, **kwargs):
        self.insert_kwargs = kwargs
        return FakeRequest(
            error=self._insert_error, error_times=self._insert_error_times
        )

    def thumbnails(self):
        return self

    def set(self, **kwargs):
        self.thumb_kwargs = kwargs
        if self._thumb_error is not None:
            raise self._thumb_error
        return self

    def playlistItems(self):
        return self._playlist_items

    def playlists(self):
        return self._playlists

    def execute(self):
        return {}


def make_package(tmp_path: Path) -> VideoPackage:
    video = tmp_path / "video.mp4"
    thumb = tmp_path / "thumbnail.jpg"
    video.write_bytes(b"\x00" * 1000)
    thumb.write_bytes(b"\xff\xd8" * 8)
    return VideoPackage(
        folder=tmp_path,
        video_path=video,
        thumbnail_path=thumb,
        title="Шарль Бодлер — Сплин",
        description="Описание",
        category_id="22",
        tags=["Бодлер", "поэзия"],
        made_for_kids=False,
        notify_subscribers=False,
    )


def test_build_upload_body_privacy_hardcoded():
    package = make_package(Path("."))
    body = youtube_uploader.build_upload_body(package)
    assert body["status"]["privacyStatus"] == "private"
    assert body["snippet"]["title"] == "Шарль Бодлер — Сплин"
    assert body["snippet"]["categoryId"] == "22"
    assert body["status"]["selfDeclaredMadeForKids"] is False
    assert body["snippet"]["tags"] == ["Бодлер", "поэзия"]


def test_build_upload_body_without_tags():
    package = make_package(Path("."))
    package.tags = []
    body = youtube_uploader.build_upload_body(package)
    assert "tags" not in body["snippet"]


def test_run_upload_success(tmp_path, monkeypatch):
    monkeypatch.setattr(youtube_uploader.time, "sleep", lambda s: None)
    youtube = FakeYouTube()
    progress = []
    stages = []
    result = youtube_uploader.run_upload(
        youtube,
        make_package(tmp_path),
        on_progress=lambda p: progress.append(p),
        on_stage=lambda s: stages.append(s),
    )
    assert result.outcome == Outcome.SUCCESS
    assert result.video_id == "VID123"
    assert result.thumbnail_uploaded is True
    assert result.video_url == "https://www.youtube.com/watch?v=VID123"

    kwargs = youtube.insert_kwargs
    assert kwargs["part"] == "snippet,status"
    assert kwargs["body"]["status"]["privacyStatus"] == "private"
    assert kwargs["notifySubscribers"] is False
    media = kwargs["media_body"]
    assert media.resumable() is True

    assert youtube.thumb_kwargs["videoId"] == "VID123"


def test_thumbnail_mime_type_matches_jpeg_extension(tmp_path):
    thumb = tmp_path / "cover.jpeg"
    thumb.write_bytes(b"jpeg")
    youtube = FakeYouTube()
    youtube_uploader.upload_thumbnail(youtube, "VID123", thumb)
    assert youtube.thumb_kwargs["media_body"].mimetype() == "image/jpeg"


def test_run_upload_retry_on_503(tmp_path, monkeypatch):
    monkeypatch.setattr(youtube_uploader.time, "sleep", lambda s: None)
    youtube = FakeYouTube(
        insert_error=make_http_error(503, message="Service Unavailable")
    )
    result = youtube_uploader.run_upload(youtube, make_package(tmp_path))
    assert result.outcome == Outcome.SUCCESS
    assert result.video_id == "VID123"


def test_run_upload_retries_exhausted(tmp_path, monkeypatch):
    monkeypatch.setattr(youtube_uploader.time, "sleep", lambda s: None)
    youtube = FakeYouTube(
        insert_error=make_http_error(503),
        insert_error_times=youtube_uploader.config.MAX_RETRIES + 1,
    )
    result = youtube_uploader.run_upload(youtube, make_package(tmp_path))
    assert result.outcome == Outcome.FAILED
    assert result.video_id is None
    assert "интернет" in result.message.lower()


def test_run_upload_non_retryable_400(tmp_path, monkeypatch):
    monkeypatch.setattr(youtube_uploader.time, "sleep", lambda s: None)
    youtube = FakeYouTube(
        insert_error=make_http_error(400, reason="invalidArgument", message="bad title"),
        insert_error_times=99,
    )
    result = youtube_uploader.run_upload(youtube, make_package(tmp_path))
    assert result.outcome == Outcome.FAILED
    assert "YouTube отклонил запрос" in result.message


def test_run_upload_quota_exceeded(tmp_path, monkeypatch):
    monkeypatch.setattr(youtube_uploader.time, "sleep", lambda s: None)
    youtube = FakeYouTube(
        insert_error=make_http_error(403, reason="quotaExceeded"),
        insert_error_times=99,
    )
    result = youtube_uploader.run_upload(youtube, make_package(tmp_path))
    assert result.outcome == Outcome.FAILED
    assert "квоты" in result.message.lower()


def test_run_upload_thumbnail_failure_partial(tmp_path, monkeypatch):
    monkeypatch.setattr(youtube_uploader.time, "sleep", lambda s: None)
    youtube = FakeYouTube(
        thumb_error=make_http_error(400, reason="invalidImage", message="bad image")
    )
    result = youtube_uploader.run_upload(youtube, make_package(tmp_path))
    assert result.outcome == Outcome.PARTIAL_SUCCESS
    assert result.video_id == "VID123"
    assert result.thumbnail_uploaded is False
    assert "обложку установить не удалось" in result.message


def test_run_upload_canceled(tmp_path, monkeypatch):
    monkeypatch.setattr(youtube_uploader.time, "sleep", lambda s: None)
    youtube = FakeYouTube()
    result = youtube_uploader.run_upload(
        youtube, make_package(tmp_path), is_canceled=lambda: True
    )
    assert result.outcome == Outcome.FAILED
    assert "отменена" in result.message


def test_upload_video_requires_video_id(tmp_path, monkeypatch):
    monkeypatch.setattr(youtube_uploader.time, "sleep", lambda s: None)

    class NoIdRequest(FakeRequest):
        def next_chunk(self):
            return (None, {})

    class NoIdYouTube(FakeYouTube):
        def insert(self, **kwargs):
            self.insert_kwargs = kwargs
            return NoIdRequest()

    youtube = NoIdYouTube()
    result = youtube_uploader.run_upload(youtube, make_package(tmp_path))
    assert result.outcome == Outcome.FAILED
    assert "Video ID" in result.message


def test_list_playlists_maps_items():
    youtube = FakeYouTube(
        playlists_response={
            "items": [
                {"id": "PL1", "snippet": {"title": "НейроМьюз"}},
                {"id": "PL2", "snippet": {"title": ""}},
                {"id": "", "snippet": {"title": "плохой"}},
                {"id": "PL1", "snippet": {"title": "дубль"}},
            ]
        }
    )
    items = youtube_uploader.list_playlists(youtube)
    assert items == [
        {"id": "PL1", "title": "НейроМьюз"},
        {"id": "PL2", "title": ""},
    ]
    kwargs = youtube._playlists.kwargs
    assert kwargs["part"] == "snippet"
    assert kwargs["mine"] is True
    assert kwargs["maxResults"] == 50


def test_list_playlists_insufficient_permissions_reauth():
    youtube = FakeYouTube(
        playlists_error=make_http_error(
            403, reason="insufficientPermissions", message="access not configured"
        )
    )
    with pytest.raises(youtube_uploader.UploadError) as exc_info:
        youtube_uploader.list_playlists(youtube)
    assert exc_info.value.reauth is True
    assert "прав" in exc_info.value.message


def test_list_playlists_auth_lost():
    youtube = FakeYouTube(
        playlists_error=make_http_error(
            401, reason="invalid_grant", message="Token has been expired"
        )
    )
    with pytest.raises(youtube_uploader.UploadError) as exc_info:
        youtube_uploader.list_playlists(youtube)
    assert exc_info.value.reauth is False
    assert "Авторизация Google потеряна" in exc_info.value.message


def test_add_video_to_playlist_body():
    youtube = FakeYouTube()
    youtube_uploader.add_video_to_playlist(youtube, "PL7", "VID123")
    kwargs = youtube._playlist_items.kwargs
    assert kwargs["part"] == "snippet"
    assert kwargs["body"]["snippet"]["playlistId"] == "PL7"
    assert kwargs["body"]["snippet"]["resourceId"] == {
        "kind": "youtube#video",
        "videoId": "VID123",
    }


def test_run_upload_with_playlist_success(tmp_path, monkeypatch):
    monkeypatch.setattr(youtube_uploader.time, "sleep", lambda s: None)
    package = make_package(tmp_path)
    package.playlist_id = "PL7"
    youtube = FakeYouTube()
    result = youtube_uploader.run_upload(youtube, package)
    assert result.outcome == Outcome.SUCCESS
    assert result.video_id == "VID123"
    assert result.thumbnail_uploaded is True
    assert result.playlist_added is True
    assert result.playlist_requested is True
    assert "Плейлист:" in result.message
    assert "Добавлено" in result.message
    assert youtube._playlist_items.kwargs["body"]["snippet"]["playlistId"] == "PL7"


def test_run_upload_with_playlist_failure_partial(tmp_path, monkeypatch):
    monkeypatch.setattr(youtube_uploader.time, "sleep", lambda s: None)
    package = make_package(tmp_path)
    package.playlist_id = "PL_GONE"
    youtube = FakeYouTube(playlist_items_error=make_http_error(404, message="not found"))
    result = youtube_uploader.run_upload(youtube, package)
    assert result.outcome == Outcome.PARTIAL_SUCCESS
    assert result.video_id == "VID123"
    assert result.thumbnail_uploaded is True
    assert result.playlist_added is False
    assert result.playlist_requested is True
    assert "плейлист" in result.message
    assert "YouTube Studio" in result.message


def test_run_upload_playlist_and_thumbnail_fail(tmp_path, monkeypatch):
    monkeypatch.setattr(youtube_uploader.time, "sleep", lambda s: None)
    package = make_package(tmp_path)
    package.playlist_id = "PL7"
    youtube = FakeYouTube(
        thumb_error=make_http_error(400, reason="invalidImage", message="bad image"),
        playlist_items_error=make_http_error(401, reason="invalid_grant"),
    )
    result = youtube_uploader.run_upload(youtube, package)
    assert result.outcome == Outcome.PARTIAL_SUCCESS
    assert result.thumbnail_uploaded is False
    assert result.playlist_added is False
    assert "обложку" in result.message
    assert "плейлист" in result.message


def test_run_upload_without_playlist_no_call(tmp_path, monkeypatch):
    monkeypatch.setattr(youtube_uploader.time, "sleep", lambda s: None)
    package = make_package(tmp_path)
    package.playlist_id = ""
    youtube = FakeYouTube()
    result = youtube_uploader.run_upload(youtube, package)
    assert result.outcome == Outcome.SUCCESS
    assert result.playlist_added is False
    assert result.playlist_requested is False
    assert youtube._playlist_items.kwargs is None
