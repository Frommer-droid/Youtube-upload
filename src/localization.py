"""Русская локализация Qt (контекстные меню, диалоги) для PySide6."""

from __future__ import annotations

import sys

from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator
from PySide6.QtWidgets import QApplication

RUSSIAN_LOCALE = QLocale(QLocale.Language.Russian, QLocale.Country.Russia)


def set_russian_qt_locale() -> None:
    QLocale.setDefault(RUSSIAN_LOCALE)


def install_russian_qt_translations(app: QApplication) -> None:
    """Загрузить qtbase_ru.qm: стандартные меню Copy/Paste/Delete — на русском."""
    translator = QTranslator(app)
    path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if translator.load(RUSSIAN_LOCALE, "qtbase", "_", path):
        app.installTranslator(translator)
        app._russian_qt_translators = [translator]
    else:
        print(
            "Не найдены русские переводы Qt (qtbase_ru.qm)",
            file=sys.stderr,
        )