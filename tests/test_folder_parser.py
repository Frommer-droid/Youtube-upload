"""Тесты парсера папки ролика (ТЗ, разделы 4-8)."""

from __future__ import annotations

from src import config, folder_parser


def test_find_video_missing(tmp_path):
    video, err = folder_parser.find_video(tmp_path)
    assert video is None
    assert err is not None
    assert "не найден видеофайл" in err


def test_find_video_multiple(tmp_path):
    (tmp_path / "a.mp4").write_bytes(b"x")
    (tmp_path / "b.mov").write_bytes(b"x")
    video, err = folder_parser.find_video(tmp_path)
    assert video is None
    assert err == folder_parser.MULTIPLE_VIDEOS_MSG


def test_find_video_single_uppercase_ext(tmp_path):
    (tmp_path / "video.MP4").write_bytes(b"x")
    video, err = folder_parser.find_video(tmp_path)
    assert err is None
    assert video is not None and video.name == "video.MP4"


def test_find_video_non_supported_ext_ignored(tmp_path):
    (tmp_path / "video.txt").write_text("x")
    (tmp_path / "video.mp4").write_bytes(b"x")
    video, err = folder_parser.find_video(tmp_path)
    assert err is None
    assert video.name == "video.mp4"


def test_find_thumbnail_missing(tmp_path):
    thumb, err = folder_parser.find_thumbnail(tmp_path)
    assert thumb is None
    assert err is not None
    assert "не найдена обложка" in err.casefold()


def test_find_thumbnail_multiple(tmp_path):
    (tmp_path / "thumbnail.jpg").write_bytes(b"x")
    (tmp_path / "cover.png").write_bytes(b"x")
    thumb, err = folder_parser.find_thumbnail(tmp_path)
    assert thumb is None
    assert err == folder_parser.MULTIPLE_THUMBNAILS_MSG


def test_find_thumbnail_single(tmp_path):
    (tmp_path / "thumbnail.jpeg").write_bytes(b"x")
    thumb, err = folder_parser.find_thumbnail(tmp_path)
    assert err is None
    assert thumb.name == "thumbnail.jpeg"


# --- автовыбор после выбора рабочей папки ---


def test_find_latest_video_picks_newest_by_creation(monkeypatch, tmp_path):
    (tmp_path / "old.mp4").write_bytes(b"x")
    (tmp_path / "new.mov").write_bytes(b"x")
    monkeypatch.setattr(
        folder_parser,
        "_ctime",
        lambda p: 100 if p.name == "old.mp4" else 200,
    )
    video, err = folder_parser.find_latest_video(tmp_path)
    assert err is None
    assert video.name == "new.mov"


def test_find_latest_video_tie_breaks_by_name(monkeypatch, tmp_path):
    (tmp_path / "a.mp4").write_bytes(b"x")
    (tmp_path / "b.mp4").write_bytes(b"x")
    monkeypatch.setattr(folder_parser, "_ctime", lambda p: 100)
    video, _ = folder_parser.find_latest_video(tmp_path)
    assert video is not None
    assert video.name == "b.mp4"


def test_find_latest_video_missing(tmp_path):
    video, err = folder_parser.find_latest_video(tmp_path)
    assert video is None
    assert err is not None
    assert "не найден видеофайл" in err


def test_find_latest_video_ignores_non_video(tmp_path):
    (tmp_path / "note.txt").write_text("x")
    (tmp_path / "clip.mp4").write_bytes(b"x")
    video, _ = folder_parser.find_latest_video(tmp_path)
    assert video is not None
    assert video.name == "clip.mp4"


def test_find_cover_exact_name(tmp_path):
    (tmp_path / "Cover-G.jpg").write_bytes(b"x")
    cover, err = folder_parser.find_cover(tmp_path)
    assert err is None
    assert cover.name == "Cover-G.jpg"


def test_find_cover_case_insensitive(tmp_path):
    (tmp_path / "cover-g.PNG").write_bytes(b"x")
    cover, err = folder_parser.find_cover(tmp_path)
    assert err is None
    assert cover.name == "cover-g.PNG"


def test_find_cover_prefers_jpg(tmp_path):
    (tmp_path / "Cover-G.png").write_bytes(b"x")
    (tmp_path / "Cover-G.jpg").write_bytes(b"x")
    cover, err = folder_parser.find_cover(tmp_path)
    assert err is None
    assert cover.name == "Cover-G.jpg"


def test_find_cover_missing(tmp_path):
    cover, err = folder_parser.find_cover(tmp_path)
    assert cover is None
    assert err is not None
    assert "JPEG" in err


def test_find_cover_accepts_common_name(tmp_path):
    (tmp_path / "thumbnail.jpg").write_bytes(b"x")
    cover, err = folder_parser.find_cover(tmp_path)
    assert err is None
    assert cover.name == "thumbnail.jpg"


def test_find_cover_uses_video_name_before_other_images(tmp_path):
    video = tmp_path / "my-clip.mp4"
    video.write_bytes(b"x")
    (tmp_path / "my-clip.PNG").write_bytes(b"x")
    (tmp_path / "Cover-G.jpg").write_bytes(b"x")
    cover, err = folder_parser.find_cover(tmp_path, video)
    assert err is None
    assert cover.name == "my-clip.PNG"


def test_find_cover_accepts_one_arbitrarily_named_image(tmp_path):
    (tmp_path / "my-artwork.jpeg").write_bytes(b"x")
    cover, err = folder_parser.find_cover(tmp_path)
    assert err is None
    assert cover.name == "my-artwork.jpeg"


def test_find_cover_does_not_guess_among_unrelated_images(tmp_path):
    (tmp_path / "photo-1.jpg").write_bytes(b"x")
    (tmp_path / "photo-2.png").write_bytes(b"x")
    cover, err = folder_parser.find_cover(tmp_path)
    assert cover is None
    assert err == folder_parser.MULTIPLE_THUMBNAILS_MSG


def test_read_text_strips_bom(tmp_path):
    f = tmp_path / "t.txt"
    f.write_bytes(b"\xef\xbb\xbf" + "Шарль Бодлер — Сплин\n\n".encode())
    text, err = folder_parser.read_text_file(f)
    assert err is None
    assert text == "Шарль Бодлер — Сплин"


def test_read_text_missing(tmp_path):
    text, err = folder_parser.read_text_file(tmp_path / "nope.txt")
    assert text is None
    assert err is not None


def test_read_text_not_utf8(tmp_path):
    f = tmp_path / "t.txt"
    f.write_bytes(b"\xff\xfe\x00\x01")
    text, err = folder_parser.read_text_file(f)
    assert text is None
    assert "UTF-8" in err


def test_read_description_preserves_internal_newlines(tmp_path):
    f = tmp_path / "d.txt"
    f.write_bytes("\n\nПервый абзац.\n\nВторой абзац.\n".encode())
    text, err = folder_parser.read_text_file(f)
    assert err is None
    assert text == "Первый абзац.\n\nВторой абзац."


def test_raw_settings_missing(tmp_path):
    raw, err = folder_parser.raw_settings(tmp_path)
    assert raw == {}
    assert err is None


def test_raw_settings_valid(tmp_path):
    (tmp_path / config.SETTINGS_FILENAME).write_text(
        "category_id: '10'\ntags:\n  - Бодлер\nmade_for_kids: false\n",
        encoding="utf-8",
    )
    raw, err = folder_parser.raw_settings(tmp_path)
    assert err is None
    assert raw["category_id"] == "10"
    assert raw["tags"] == ["Бодлер"]
    assert raw["made_for_kids"] is False


def test_raw_settings_invalid_yaml(tmp_path):
    (tmp_path / config.SETTINGS_FILENAME).write_text(
        "tags: [unclosed", encoding="utf-8"
    )
    raw, err = folder_parser.raw_settings(tmp_path)
    assert raw == {}
    assert err is not None
    assert "settings.yaml" in err


def test_raw_settings_not_dict(tmp_path):
    (tmp_path / config.SETTINGS_FILENAME).write_text("- a\n- b\n", encoding="utf-8")
    _raw, err = folder_parser.raw_settings(tmp_path)
    assert "словарь" in err


def test_effective_settings_defaults():
    settings = folder_parser.effective_settings({})
    assert settings["category_id"] == config.DEFAULT_CATEGORY_ID
    assert settings["tags"] == []
    assert settings["made_for_kids"] is False
    assert settings["notify_subscribers"] is False


def test_effective_settings_ignores_privacy():
    settings = folder_parser.effective_settings(
        {"privacy": "public", "category_id": "10"}
    )
    assert "privacy" not in settings
    assert settings["category_id"] == "10"
