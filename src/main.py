"""Точка входа приложения (PySide6): python -m src.main (ТЗ, раздел 39)."""

from __future__ import annotations

import ctypes
import os
import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from . import config, icons, logging_setup
from .localization import install_russian_qt_translations, set_russian_qt_locale
from .styles import apply_styles


def _set_app_user_model_id() -> None:
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "YouTubePrivateUploader"
        )
    except (AttributeError, OSError):
        pass


def main() -> int:
    logger = logging_setup.setup_logging()
    logger.info("Приложение запущено (PySide6)")

    _set_app_user_model_id()
    set_russian_qt_locale()

    app = QApplication(sys.argv)
    install_russian_qt_translations(app)
    application_icon = QIcon(str(config.project_root() / "logo.ico"))
    if application_icon.isNull():
        application_icon = icons.app_mark_icon()
    app.setWindowIcon(application_icon)
    apply_styles(app)

    from .gui import MainWindow

    window = MainWindow()
    logger.info("Главное окно показано")
    window.show()
    QApplication.processEvents()
    if getattr(window, "_startup_maximized", False):
        window.showMaximized()
        QApplication.processEvents()
    window.install_ui_scale_screen_hooks()

    if os.environ.get("YOUTUBE_PRIVATE_UPLOADER_FROZEN_SMOKE") == "1":
        QTimer.singleShot(0, app.quit)

    try:
        return app.exec()
    finally:
        logger.info("Приложение завершено")


if __name__ == "__main__":
    raise SystemExit(main())
