"""Тесты метаданных: конфигурация, служебный файл .youtube-upload.json (ТЗ, разделы 8, 21)."""

from __future__ import annotations

from pathlib import Path

from PyInstaller.utils.win32 import versioninfo

from conftest import make_video_folder
from src import config, models


def test_default_config_values():
    assert config.DEFAULT_CATEGORY_ID == "22"
    assert config.DEFAULT_TAGS == []
    assert config.DEFAULT_MADE_FOR_KIDS is False
    assert config.DEFAULT_NOTIFY_SUBSCRIBERS is False
    assert config.MAX_TITLE_LENGTH == 100
    assert config.MAX_DESCRIPTION_UTF8_BYTES == 5000
    assert config.MAX_TAGS_TOTAL_CHARS == 500
    assert config.MAX_THUMBNAIL_BYTES == 2 * 1024 * 1024


def test_supported_extensions_include_spec_list():
    for ext in (".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm", ".mpeg", ".mpg"):
        assert ext in config.SUPPORTED_VIDEO_EXTENSIONS


def test_scopes_minimal():
    # youtube.upload — загрузка; youtube.force-ssl — плейлисты.
    assert config.SCOPES == [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube.force-ssl",
    ]


def test_token_lives_in_appdata_not_in_video_folder(tmp_path):
    import os

    os.environ["YOUTUBE_PRIVATE_UPLOADER_DATA_DIR"] = str(tmp_path / "data")
    try:
        assert config.token_path() == tmp_path / "data" / "token.json"
        folder = make_video_folder(tmp_path)
        assert not (folder / config.DUP_MARKER_FILENAME).exists()
    finally:
        os.environ.pop("YOUTUBE_PRIVATE_UPLOADER_DATA_DIR", None)


def test_appdata_dir_default_uses_apdata_env(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    monkeypatch.delenv("YOUTUBE_PRIVATE_UPLOADER_DATA_DIR", raising=False)
    install_dir = tmp_path / "install"
    install_dir.mkdir()
    install_id = "a" * 64
    (install_dir / config.INSTALLATION_ID_FILENAME).write_text(install_id, encoding="ascii")
    monkeypatch.setattr(config, "project_root", lambda: install_dir)
    assert config.app_data_dir() == (
        tmp_path / "Roaming" / "YouTubePrivateUploader" / "installations" / install_id
    )


def test_marker_roundtrip(tmp_path):
    folder = make_video_folder(tmp_path)
    marker = models.UploadMarker(
        video_id="abc123",
        uploaded_at="2026-08-11T18:30:00+03:00",
        status="private",
        thumbnail_uploaded=True,
    )
    path = models.write_marker(folder, marker)
    assert path.name == ".youtube-upload.json"
    loaded = models.read_marker(folder)
    assert loaded is not None
    assert loaded.video_id == "abc123"
    assert loaded.status == "private"
    assert loaded.thumbnail_uploaded is True


def test_marker_video_name_roundtrip(tmp_path):
    folder = make_video_folder(tmp_path)
    models.write_marker(
        folder,
        models.UploadMarker(
            video_id="abc123",
            uploaded_at=models.now_iso(),
            status="private",
            video_name="clip.mp4",
        ),
    )
    loaded = models.read_marker(folder)
    assert loaded is not None
    assert loaded.video_name == "clip.mp4"


def test_marker_missing(tmp_path):
    folder = make_video_folder(tmp_path)
    assert models.read_marker(folder) is None


def test_marker_corrupt_returns_none(tmp_path):
    folder = make_video_folder(tmp_path)
    (folder / config.DUP_MARKER_FILENAME).write_text("{broken json", encoding="utf-8")
    assert models.read_marker(folder) is None


def test_video_url_template():
    url = config.VIDEO_URL_TEMPLATE.format(video_id="abc123")
    assert url == "https://www.youtube.com/watch?v=abc123"


def test_studio_url_template():
    url = config.STUDIO_URL_TEMPLATE.format(video_id="abc123")
    assert "studio.youtube.com" in url and "abc123" in url


def test_windows_exe_version_matches_release_version():
    root = Path(__file__).resolve().parents[1]
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    resource = versioninfo.load_version_info_from_text_file(
        str(root / "Build_Tools" / "version_info.txt")
    )
    numbers = tuple(int(part) for part in version.split(".")) + (0,)
    assert resource.ffi.fileVersionMS == numbers[0] << 16 | numbers[1]
    assert resource.ffi.fileVersionLS == numbers[2] << 16 | numbers[3]
    assert resource.ffi.productVersionMS == resource.ffi.fileVersionMS
    assert resource.ffi.productVersionLS == resource.ffi.fileVersionLS
    strings = {
        item.name: item.val for item in resource.kids[0].kids[0].kids
    }
    assert strings["FileVersion"] == version
    assert strings["ProductVersion"] == version
