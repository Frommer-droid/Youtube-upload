"""Offscreen checks for theme icons and persisted window settings."""

from __future__ import annotations

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton

from src import config, templates
from src.gui import MainWindow
from src.models import Outcome, UploadResult
from src.theme import COLORS


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_fresh_install_ignores_legacy_data_and_desktop_video(tmp_path, monkeypatch):
    roaming = tmp_path / "Roaming"
    legacy_dir = roaming / config.APP_NAME
    legacy_dir.mkdir(parents=True)
    legacy_settings = legacy_dir / "settings.json"
    old_contents = json.dumps(
        {
            "form": {"song": "Старая песня", "tg": "https://example.com/old"},
            "playlist": {"id": "old-playlist", "title": "Старый плейлист"},
        },
        ensure_ascii=False,
    )
    legacy_settings.write_text(old_contents, encoding="utf-8")
    (legacy_dir / "templates.json").write_text(
        json.dumps({"title": "Старый шаблон {song}"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (legacy_dir / "token.json").write_text("{}", encoding="utf-8")
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    (desktop / "video.mp4").write_bytes(b"video")
    install_dir = tmp_path / "install"
    install_dir.mkdir()
    marker = install_dir / config.INSTALLATION_ID_FILENAME
    marker.write_text("a" * 64, encoding="ascii")
    monkeypatch.delenv("YOUTUBE_PRIVATE_UPLOADER_DATA_DIR", raising=False)
    monkeypatch.setenv("APPDATA", str(roaming))
    monkeypatch.setattr(config, "project_root", lambda: install_dir)
    monkeypatch.setattr(config, "desktop_dir", lambda: desktop)
    _app()

    first = MainWindow()
    try:
        assert first.folder is None
        assert first.video_path is None
        assert first.song_edit.text() == ""
        assert first.tg_edit.text() == ""
        assert first.max_edit.text() == ""
        assert first.tags_edit.text() == ""
        assert first._selected_playlist_id() == ""
        assert first._templates == templates.default_templates()
        assert not config.token_path().exists()
        first.song_edit.setText("Новая песня")
        monkeypatch.setattr(
            "src.gui.QFileDialog.getOpenFileName",
            lambda *args: (str(desktop / "video.mp4"), ""),
        )
        first._select_video()
        assert first.folder == desktop
        assert first.video_path == desktop / "video.mp4"
        first._save_form_state()
    finally:
        first.close()

    second = MainWindow()
    try:
        assert second.song_edit.text() == "Новая песня"
        assert second.folder == desktop
        assert second.video_path == desktop / "video.mp4"
    finally:
        second.close()

    marker.write_text("b" * 64, encoding="ascii")
    third = MainWindow()
    try:
        assert third.song_edit.text() == ""
        assert third.folder is None
        assert third.video_path is None
    finally:
        third.close()
    assert legacy_settings.read_text(encoding="utf-8") == old_contents


def test_folder_picker_starts_at_user_desktop_and_keeps_selected_folder(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("YOUTUBE_PRIVATE_UPLOADER_DATA_DIR", str(tmp_path / "data"))
    desktop = tmp_path / "Moved Desktop"
    desktop.mkdir()
    folder = tmp_path / "My Videos"
    folder.mkdir()
    (folder / "clip.mp4").write_bytes(b"video")
    monkeypatch.setattr(config, "desktop_dir", lambda: desktop)
    picked_from = []

    def choose_folder(_parent, _caption, initial):
        picked_from.append(initial)
        return str(folder)

    monkeypatch.setattr("src.gui.QFileDialog.getExistingDirectory", choose_folder)
    _app()
    window = MainWindow()
    try:
        assert window.folder is None
        window._select_folder()
        assert picked_from == [str(desktop)]
        assert window.folder == folder
        assert window.video_path == folder / "clip.mp4"
        window._reset_for_new()
        assert window.folder == folder
    finally:
        window.close()


def test_upload_another_video_keeps_form_fields(tmp_path, monkeypatch):
    monkeypatch.setenv("YOUTUBE_PRIVATE_UPLOADER_DATA_DIR", str(tmp_path / "data"))
    _app()
    window = MainWindow()
    try:
        window.song_edit.setText("Песня")
        window.translator_edit.setText("Переводчик")
        window.tg_edit.setText("https://t.me/post")
        window.max_edit.setText("https://max.ru/post")
        window.tags_edit.setText("тег")
        window.poem_edit.setPlainText("Стихотворение")
        window.category_combo.setCurrentIndex(0)
        window.kids_check.setChecked(True)
        window.notify_check.setChecked(True)
        window.playlist_combo.addItem("Плейлист", "playlist-id")
        window.playlist_combo.setCurrentIndex(1)
        window._finish(UploadResult(outcome=Outcome.SUCCESS, video_id="VID123"))

        window.btn_again.click()

        assert window.song_edit.text() == "Песня"
        assert window.translator_edit.text() == "Переводчик"
        assert window.tg_edit.text() == "https://t.me/post"
        assert window.max_edit.text() == "https://max.ru/post"
        assert window.tags_edit.text() == "тег"
        assert window.poem_edit.toPlainText() == "Стихотворение"
        assert window.category_combo.currentIndex() == 0
        assert window.kids_check.isChecked()
        assert window.notify_check.isChecked()
        assert window.playlist_combo.currentIndex() == 1
        assert window.last_result is None
        assert window.result_card.isHidden()
        form = json.loads(config.settings_path().read_text(encoding="utf-8"))["form"]
        assert form["song"] == "Песня"
        assert form["translator"] == "Переводчик"
        assert form["tg"] == "https://t.me/post"
        assert form["max"] == "https://max.ru/post"
    finally:
        window.close()


def test_clear_button_only_clears_song_translator_and_post_links(tmp_path, monkeypatch):
    monkeypatch.setenv("YOUTUBE_PRIVATE_UPLOADER_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(
        "src.gui.QMessageBox.question", lambda *_args: QMessageBox.StandardButton.Yes
    )
    _app()
    window = MainWindow()
    try:
        window.song_edit.setText("Песня")
        window.translator_edit.setText("Переводчик")
        window.tg_edit.setText("https://t.me/post")
        window.max_edit.setText("https://max.ru/post")
        window.tags_edit.setText("тег")
        window.poem_edit.setPlainText("Стихотворение")
        window.category_combo.setCurrentIndex(0)
        window.kids_check.setChecked(True)
        window.notify_check.setChecked(True)
        window.playlist_combo.addItem("Плейлист", "playlist-id")
        window.playlist_combo.setCurrentIndex(1)

        window.btn_clear.click()

        assert window.btn_clear.text() == "Очистить название, перевод и ссылки"
        assert window.song_edit.text() == ""
        assert window.translator_edit.text() == ""
        assert window.tg_edit.text() == ""
        assert window.max_edit.text() == ""
        assert window.tags_edit.text() == "тег"
        assert window.poem_edit.toPlainText() == "Стихотворение"
        assert window.category_combo.currentIndex() == 0
        assert window.kids_check.isChecked()
        assert window.notify_check.isChecked()
        assert window.playlist_combo.currentIndex() == 1
        form = json.loads(config.settings_path().read_text(encoding="utf-8"))["form"]
        assert (form["song"], form["tg"], form["max"]) == ("", "", "")
        assert form["translator"] == ""
        assert form["tags"] == ["тег"]
        assert form["poem"] == "Стихотворение"
    finally:
        window.close()


def test_translator_field_updates_preview_and_restores_on_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("YOUTUBE_PRIVATE_UPLOADER_DATA_DIR", str(tmp_path / "data"))
    app = _app()
    first = MainWindow()
    try:
        first.show()
        app.processEvents()
        assert first.translator_edit.accessibleName() == "Перевод"
        assert first.song_edit.y() < first.translator_edit.y() < first.tg_edit.y()
        first.desc_tpl_edit.setPlainText(
            "ТГ: {telegram_url}\nМАКС: {max_url}\nПеревод: {translator}"
        )
        first.translator_edit.setText("Иван Иванов")
        assert "Перевод: Иван Иванов" in first.desc_preview.toPlainText()
        form = json.loads(config.settings_path().read_text(encoding="utf-8"))["form"]
        assert form["translator"] == "Иван Иванов"
    finally:
        first.close()

    second = MainWindow()
    try:
        assert second.translator_edit.text() == "Иван Иванов"
        assert "Перевод: Иван Иванов" in second.desc_preview.toPlainText()
    finally:
        second.close()


def test_selected_video_uses_matching_cover_and_keeps_manual_choice(tmp_path, monkeypatch):
    monkeypatch.setenv("YOUTUBE_PRIVATE_UPLOADER_DATA_DIR", str(tmp_path / "data"))
    folder = tmp_path / "videos"
    folder.mkdir()
    first_video = folder / "first.mp4"
    second_video = folder / "second.mp4"
    first_video.write_bytes(b"video")
    second_video.write_bytes(b"video")
    (folder / "first.jpg").write_bytes(b"cover")
    (folder / "second.png").write_bytes(b"cover")
    manual_cover = tmp_path / "manual.jpeg"
    manual_cover.write_bytes(b"cover")
    choices = iter((first_video, manual_cover, second_video))
    monkeypatch.setattr(
        "src.gui.QFileDialog.getOpenFileName",
        lambda *args: (str(next(choices)), ""),
    )
    _app()
    window = MainWindow()
    try:
        window._load_folder(folder)
        window._select_video()
        assert window.video_path == first_video
        assert window.thumb_path == folder / "first.jpg"
        window._select_thumbnail()
        assert window.thumb_path == manual_cover
        window._select_video()
        assert window.video_path == second_video
        assert window.thumb_path == manual_cover
    finally:
        window.close()


def test_every_action_button_and_tab_has_an_icon(tmp_path, monkeypatch):
    monkeypatch.setenv("YOUTUBE_PRIVATE_UPLOADER_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(config, "desktop_dir", lambda: tmp_path)
    _app()
    window = MainWindow()
    try:
        assert [window.tabs.tabText(i) for i in range(window.tabs.count())] == [
            "Загрузка",
            "Стихотворение",
            "Шаблоны",
            "Предпросмотр",
            "Настройки",
        ]
        assert all(
            not window.tabs.tabIcon(i).isNull() for i in range(window.tabs.count())
        )
        action_buttons = window.findChildren(QPushButton)
        assert len(action_buttons) == 16
        assert all(not button.icon().isNull() for button in action_buttons)
    finally:
        window.close()


def test_turquoise_accent_and_centered_equal_height_main_actions(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("YOUTUBE_PRIVATE_UPLOADER_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(config, "desktop_dir", lambda: tmp_path)
    app = _app()
    window = MainWindow()
    try:
        assert COLORS["turquoise"] == "#56FFFC"
        window.show()
        app.processEvents()

        buttons = (window.btn_upload, window.btn_cancel, window.btn_clear)
        assert len({button.height() for button in buttons}) == 1
        assert len({button.y() for button in buttons}) == 1

        left = min(button.geometry().left() for button in buttons)
        right = max(button.geometry().right() for button in buttons)
        group_center = (left + right) / 2
        card_center = window.btn_upload.parentWidget().rect().center().x()
        assert abs(group_center - card_center) <= 2
    finally:
        window.close()


def test_success_state_keeps_only_clear_and_result_actions(tmp_path, monkeypatch):
    monkeypatch.setenv("YOUTUBE_PRIVATE_UPLOADER_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(config, "desktop_dir", lambda: tmp_path)
    _app()
    window = MainWindow()
    try:
        window._finish(
            UploadResult(
                outcome=Outcome.SUCCESS,
                video_id="VID123",
                video_url="https://www.youtube.com/watch?v=VID123",
                message="Видео успешно загружено на YouTube.",
            )
        )

        assert not window.btn_clear.isHidden()
        assert window.btn_upload.isHidden()
        assert window.btn_cancel.isHidden()
        assert window.readiness_header.isHidden()
        assert window.issues_text.isHidden()
        assert window.progress.isHidden()
        assert window.stage_label.isHidden()
        assert window.result_header.isHidden()
        assert window.result_message.isHidden()
        assert window.result_detail.isHidden()
        assert window.result_instructions.isHidden()
        assert all(
            not button.isHidden()
            for button in (
                window.btn_open_video,
                window.btn_copy,
                window.btn_studio,
                window.btn_again,
            )
        )
    finally:
        window.close()


def test_authorization_controls_live_in_settings_and_busy_state_is_shared(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("YOUTUBE_PRIVATE_UPLOADER_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(config, "desktop_dir", lambda: tmp_path)
    _app()
    window = MainWindow()
    try:
        upload_page = window.tabs.widget(0)
        templates_page = window.tabs.widget(2)
        settings_page = window.tabs.widget(4)
        preview_page = window.tabs.widget(3)
        assert preview_page.isAncestorOf(window.desc_preview)
        assert not upload_page.isAncestorOf(window.desc_preview)
        assert settings_page.isAncestorOf(window.auth_label)
        assert settings_page.isAncestorOf(window.btn_reset_auth)
        assert settings_page.isAncestorOf(window.btn_settings_playlists)
        assert not upload_page.isAncestorOf(window.btn_reset_auth)
        assert templates_page.isAncestorOf(window.title_tpl_edit)
        assert templates_page.isAncestorOf(window.desc_tpl_edit)
        assert window.song_edit.accessibleName() == "Название песни"
        assert window.playlist_combo.accessibleName() == "Плейлист канала"

        window._set_busy_ui(True)
        assert not window.btn_playlists.isEnabled()
        assert not window.btn_settings_playlists.isEnabled()
        assert not window.btn_reset_auth.isEnabled()
        window._set_busy_ui(False)
        assert window.btn_playlists.isEnabled()
        assert window.btn_settings_playlists.isEnabled()
    finally:
        window.close()


def test_geometry_is_saved_with_explicit_and_legacy_keys(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setenv("YOUTUBE_PRIVATE_UPLOADER_DATA_DIR", str(data_dir))
    monkeypatch.setattr(config, "desktop_dir", lambda: tmp_path)
    _app()
    window = MainWindow()
    try:
        window.setGeometry(41, 53, 820, 700)
        window._normal_geometry = window.geometry()
        window._save_geometry()
        saved = json.loads(config.settings_path().read_text(encoding="utf-8"))
        assert saved["geometry_v"] == 3
        assert saved["window_pos_x"] == saved["x"]
        assert saved["window_pos_y"] == saved["y"]
        assert saved["window_width"] == saved["width"]
        assert saved["window_height"] == saved["height"]
        assert saved["maximized"] is False
    finally:
        window.close()


def test_geometry_v2_settings_remain_compatible(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "settings.json").write_text(
        json.dumps({"geometry_v": 2, "x": 30, "y": 40, "width": 810, "height": 700}),
        encoding="utf-8",
    )
    monkeypatch.setenv("YOUTUBE_PRIVATE_UPLOADER_DATA_DIR", str(data_dir))
    monkeypatch.setattr(config, "desktop_dir", lambda: tmp_path)
    _app()
    window = MainWindow()
    try:
        assert window._geometry_was_restored is True
        available = window.screen().availableGeometry()
        assert window.width() == min(810, available.width())
        assert window.height() == min(700, available.height())
    finally:
        window.close()


def test_maximized_state_keeps_normal_geometry_for_restart(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setenv("YOUTUBE_PRIVATE_UPLOADER_DATA_DIR", str(data_dir))
    monkeypatch.setattr(config, "desktop_dir", lambda: tmp_path)
    app = _app()
    window = MainWindow()
    try:
        normal = QRect(11, 17, 790, 690)
        window.show()
        app.processEvents()
        window.setGeometry(normal)
        app.processEvents()
        window.showMaximized()
        app.processEvents()
        window._save_geometry()
        saved = json.loads(config.settings_path().read_text(encoding="utf-8"))
        assert saved["maximized"] is True
        assert saved["window_width"] == normal.width()
        assert saved["window_height"] == normal.height()
    finally:
        window.close()

    restored = MainWindow()
    try:
        assert restored._startup_maximized is True
        assert restored._normal_geometry.width() == normal.width()
        assert restored._normal_geometry.height() == normal.height()
    finally:
        restored.close()
