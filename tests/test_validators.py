"""Тесты локальной валидации папки (ТЗ, разделы 24, 34)."""

from __future__ import annotations

from conftest import make_video_folder
from src import config, models, validators


def codes(issues):
    return {issue.code for issue in issues}


def test_valid_folder_ok(tmp_path):
    folder = make_video_folder(tmp_path)
    package, issues = validators.validate_folder(folder)
    assert issues == []
    assert package is not None
    assert package.video_path.name == "video.mp4"
    assert package.thumbnail_path.name == "thumbnail.jpg"
    assert package.title == "Шарль Бодлер — Сплин"
    assert package.category_id == config.DEFAULT_CATEGORY_ID
    assert package.tags == []
    assert package.made_for_kids is False


def test_empty_folder(tmp_path):
    package, issues = validators.validate_folder(tmp_path)
    assert package is None
    found = codes(issues)
    assert models.ValidationCode.NO_VIDEO in found
    assert models.ValidationCode.NO_TITLE in found
    assert models.ValidationCode.NO_DESCRIPTION in found
    assert models.ValidationCode.NO_THUMBNAIL in found


def test_folder_missing(tmp_path):
    package, issues = validators.validate_folder(tmp_path / "nope")
    assert package is None
    assert codes(issues) == {models.ValidationCode.FOLDER_MISSING}


def test_multiple_videos(tmp_path):
    folder = make_video_folder(tmp_path)
    (folder / "extra.mkv").write_bytes(b"x")
    package, issues = validators.validate_folder(folder)
    assert package is None
    assert models.ValidationCode.MULTIPLE_VIDEOS in codes(issues)


def test_multiple_thumbnails(tmp_path):
    folder = make_video_folder(tmp_path)
    (folder / "cover.png").write_bytes(b"x")
    package, issues = validators.validate_folder(folder)
    assert package is None
    assert models.ValidationCode.MULTIPLE_THUMBNAILS in codes(issues)


def test_video_named_cover_wins_over_generic_thumbnail(tmp_path):
    folder = make_video_folder(tmp_path)
    (folder / "video.png").write_bytes(b"x")
    package, issues = validators.validate_folder(folder)
    assert issues == []
    assert package.thumbnail_path.name == "video.png"


def test_empty_title(tmp_path):
    folder = make_video_folder(tmp_path)
    (folder / "title.txt").write_text("   \n\n", encoding="utf-8")
    package, issues = validators.validate_folder(folder)
    assert package is not None
    assert models.ValidationCode.EMPTY_TITLE in codes(issues)


def test_title_too_long(tmp_path):
    folder = make_video_folder(tmp_path)
    (folder / "title.txt").write_text("а" * (config.MAX_TITLE_LENGTH + 1), encoding="utf-8")
    package, issues = validators.validate_folder(folder)
    assert package is not None
    issue = next(
        i for i in issues if i.code == models.ValidationCode.TITLE_TOO_LONG
    )
    assert "100" in issue.message


def test_description_too_large(tmp_path):
    folder = make_video_folder(tmp_path)
    text = "э" * 4000  # 4000 * 2 байта = 8000 > 5000
    (folder / "description.txt").write_text(text, encoding="utf-8")
    package, issues = validators.validate_folder(folder)
    assert package is not None
    assert models.ValidationCode.DESCRIPTION_TOO_LARGE in codes(issues)


def test_description_within_limit_ok(tmp_path):
    folder = make_video_folder(tmp_path)
    text = "э" * 1200  # 2400 байт
    (folder / "description.txt").write_text(text, encoding="utf-8")
    _package, issues = validators.validate_folder(folder)
    assert issues == []


def test_thumbnail_too_large(tmp_path):
    folder = make_video_folder(tmp_path)
    (folder / "thumbnail.jpg").write_bytes(b"\x00" * (config.MAX_THUMBNAIL_BYTES + 1))
    package, issues = validators.validate_folder(folder)
    assert package is not None
    issue = next(
        i for i in issues if i.code == models.ValidationCode.THUMBNAIL_TOO_LARGE
    )
    assert "2 МБ" in issue.message


def test_invalid_yaml(tmp_path):
    folder = make_video_folder(tmp_path)
    (folder / "settings.yaml").write_text("tags: [unclosed", encoding="utf-8")
    package, issues = validators.validate_folder(folder)
    assert package is not None
    assert models.ValidationCode.INVALID_YAML in codes(issues)


def test_valid_yaml(tmp_path):
    folder = make_video_folder(tmp_path)
    (folder / "settings.yaml").write_text(
        "category_id: '10'\n"
        "tags:\n"
        "  - Бодлер\n"
        "  - поэзия\n"
        "made_for_kids: false\n"
        "notify_subscribers: false\n",
        encoding="utf-8",
    )
    package, issues = validators.validate_folder(folder)
    assert issues == []
    assert package.category_id == "10"
    assert package.tags == ["Бодлер", "поэзия"]
    assert package.made_for_kids is False
    assert package.notify_subscribers is False


def test_yaml_made_for_kids_true(tmp_path):
    folder = make_video_folder(tmp_path)
    (folder / "settings.yaml").write_text(
        "made_for_kids: true\nnotify_subscribers: true\n", encoding="utf-8"
    )
    package, issues = validators.validate_folder(folder)
    assert issues == []
    assert package.made_for_kids is True
    assert package.notify_subscribers is True


def test_yaml_ignores_privacy(tmp_path):
    folder = make_video_folder(tmp_path)
    (folder / "settings.yaml").write_text("privacy: public\n", encoding="utf-8")
    _package, issues = validators.validate_folder(folder)
    assert issues == []


def test_yaml_wrong_tags_type(tmp_path):
    folder = make_video_folder(tmp_path)
    (folder / "settings.yaml").write_text("tags: not-a-list\n", encoding="utf-8")
    _package, issues = validators.validate_folder(folder)
    assert models.ValidationCode.INVALID_TAGS in codes(issues)


def test_yaml_tags_too_long(tmp_path):
    folder = make_video_folder(tmp_path)
    (folder / "settings.yaml").write_text(
        "tags:\n" + "".join(f"  - {'т' * 40}\n" for _ in range(20)),
        encoding="utf-8",
    )
    _package, issues = validators.validate_folder(folder)
    assert models.ValidationCode.INVALID_TAGS in codes(issues)


def test_yaml_wrong_bool_type(tmp_path):
    folder = make_video_folder(tmp_path)
    (folder / "settings.yaml").write_text(
        "made_for_kids: 'yes'\n", encoding="utf-8"
    )
    package, issues = validators.validate_folder(folder)
    assert models.ValidationCode.INVALID_SETTING_VALUE in codes(issues)
    assert package.made_for_kids is False


def test_yaml_category_non_numeric(tmp_path):
    folder = make_video_folder(tmp_path)
    (folder / "settings.yaml").write_text("category_id: 'abc'\n", encoding="utf-8")
    _package, issues = validators.validate_folder(folder)
    assert models.ValidationCode.INVALID_SETTING_VALUE in codes(issues)


def test_yaml_category_int_accepted(tmp_path):
    folder = make_video_folder(tmp_path)
    (folder / "settings.yaml").write_text("category_id: 10\n", encoding="utf-8")
    package, issues = validators.validate_folder(folder)
    assert issues == []
    assert package.category_id == "10"


def test_missing_settings_uses_defaults(tmp_path):
    folder = make_video_folder(tmp_path)
    package, issues = validators.validate_folder(folder)
    assert issues == []
    assert package.category_id == config.DEFAULT_CATEGORY_ID
    assert package.tags == []
    assert package.made_for_kids == config.DEFAULT_MADE_FOR_KIDS
    assert package.notify_subscribers == config.DEFAULT_NOTIFY_SUBSCRIBERS


def test_existing_upload_marker_does_not_block_upload(tmp_path):
    folder = make_video_folder(tmp_path)
    models.write_marker(
        folder,
        models.UploadMarker(
            video_id="abc123",
            uploaded_at=models.now_iso(),
            status="private",
            thumbnail_uploaded=True,
        ),
    )
    package, issues = validators.validate_folder(folder)
    assert package is not None
    assert issues == []


def test_no_client_secret(tmp_path, missing_client_secret):
    folder = make_video_folder(tmp_path)
    package, issues = validators.validate_folder(folder)
    assert package is not None
    assert models.ValidationCode.NO_CLIENT_SECRET in codes(issues)
    assert "SETUP_GOOGLE.md" in next(
        i.message for i in issues if i.code == models.ValidationCode.NO_CLIENT_SECRET
    )
