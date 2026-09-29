# -*- coding: utf-8 -*-
"""Чистая GUI-оболочка PyInstaller для portable/onedir PySide6-приложений."""

from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStatusBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


APP_TITLE = "YouTubePrivateUploader — Сборка"
APP_USER_MODEL_ID = "ArtemPirog.YouTubePrivateUploader.Builder"
APP_GUID = "88F81170-5D02-4934-926E-E07DCEB8F514"
SETTINGS_FILE = "settings.json"
SETTINGS_KEY = "YouTubePrivateUploader"
LEGACY_SETTINGS_FILE = "PyCompiler_settings.json"


def resource_path(relative_path: str) -> str:
    try:
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class CompilerThread(QThread):
    new_log_line = Signal(str)
    finished_compilation = Signal(bool, str)

    def __init__(self, command: list[str], workdir: str, env: dict | None = None):
        super().__init__()
        self.command = command
        self.workdir = workdir
        self.env = env or os.environ.copy()

    def _run_process(self) -> int:
        process = subprocess.Popen(
            self.command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="ignore",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            cwd=self.workdir,
            env=self.env,
        )
        assert process.stdout is not None
        while True:
            line = process.stdout.readline()
            if not line:
                break
            self.new_log_line.emit(line.rstrip())
        process.wait()
        return process.returncode

    def run(self) -> None:
        try:
            return_code = self._run_process()
            if return_code == 0:
                self.finished_compilation.emit(True, "Сборка завершена успешно.")
                return
            self.finished_compilation.emit(
                False,
                f"Ошибка сборки (код {return_code}).",
            )
        except FileNotFoundError:
            self.finished_compilation.emit(
                False,
                "PyInstaller не найден. Убедитесь, что он установлен в выбранном Python.",
            )
        except Exception as exc:
            self.finished_compilation.emit(False, f"Неожиданная ошибка: {exc}")


class PyCompilerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        tools_dir = os.path.dirname(__file__)
        self.settings_path = os.path.join(tools_dir, SETTINGS_FILE)
        self.legacy_settings_path = os.path.join(tools_dir, LEGACY_SETTINGS_FILE)
        self.thread: CompilerThread | None = None
        self.colors = {
            "bg_main": "#17212B",
            "bg_panel": "#0E1621",
            "accent": "#3AE2CE",
            "button_primary": "#4B82E5",
            "button_warning": "#BF8255",
            "button_action": "#6AF1E2",
            "text": "#FFFFFF",
        }

        self._setup_window()
        self._create_widgets()
        self._connect_signals()
        self._apply_styles()
        self._load_settings()

    def _setup_window(self) -> None:
        self.setWindowTitle(APP_TITLE)
        icon_path = resource_path("logo.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.resize(780, 520)
        self.setMinimumSize(360, 260)
        status = QStatusBar(self)
        self.setStatusBar(status)
        status.showMessage("Готово к сборке")

    def _create_widgets(self) -> None:
        central = QWidget()
        central.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        root_layout = QVBoxLayout(central)
        root_layout.setSpacing(16)

        spec_label = QLabel("Spec-файл для сборки:")
        self.spec_combo = QComboBox()
        self.spec_combo.setEditable(True)
        self.spec_combo.setPlaceholderText("Выберите .spec файл...")
        browse_btn = QPushButton("Выбрать")
        browse_btn.setFixedWidth(120)
        browse_btn.clicked.connect(self._browse_spec_file)

        spec_row = QHBoxLayout()
        spec_row.addWidget(self.spec_combo, stretch=1)
        spec_row.addWidget(browse_btn)

        python_label = QLabel("Интерпретатор Python:")
        self.python_path_edit = QLineEdit()
        self.python_path_edit.setPlaceholderText("Авто (.venv или текущий Python)")
        self.python_browse_btn = QPushButton("Выбрать")
        self.python_browse_btn.setFixedWidth(120)
        self.python_browse_btn.clicked.connect(self._browse_python_interpreter)

        python_row = QHBoxLayout()
        python_row.addWidget(self.python_path_edit, stretch=1)
        python_row.addWidget(self.python_browse_btn)

        controls_row = QHBoxLayout()
        self.build_btn = QPushButton("Собрать")
        self.build_btn.setObjectName("build_btn")
        self.clear_log_btn = QPushButton("Очистить лог")
        self.clear_log_btn.setObjectName("clear_log_btn")
        controls_row.addWidget(self.build_btn)
        controls_row.addWidget(self.clear_log_btn)
        controls_row.addStretch(1)

        log_label = QLabel("Лог PyInstaller:")
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("Здесь появится вывод PyInstaller...")

        root_layout.addWidget(spec_label)
        root_layout.addLayout(spec_row)
        root_layout.addWidget(python_label)
        root_layout.addLayout(python_row)
        root_layout.addLayout(controls_row)
        root_layout.addWidget(log_label)
        root_layout.addWidget(self.log_output, stretch=1)

        self.setCentralWidget(central)
        self.centralWidget().setObjectName("root_widget")

    def _connect_signals(self) -> None:
        self.build_btn.clicked.connect(self._start_compilation)
        self.clear_log_btn.clicked.connect(self.log_output.clear)

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            f"""
            QWidget#root_widget {{
                background-color: {self.colors['bg_main']};
                font-family: "Aptos", "Segoe UI", sans-serif;
                font-size: 15pt;
                color: {self.colors['text']};
            }}
            QLabel {{
                color: {self.colors['accent']};
                font-weight: 600;
            }}
            QTextEdit, QComboBox, QLineEdit {{
                background-color: {self.colors['bg_panel']};
                color: {self.colors['text']};
                border: 1px solid rgba(58,226,206,0.3);
                border-radius: 8px;
                padding: 6px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {self.colors['bg_panel']};
                color: {self.colors['text']};
                selection-background-color: {self.colors['accent']};
                selection-color: black;
            }}
            QPushButton {{
                border-radius: 8px;
                border: 1px solid transparent;
                padding: 10px 18px;
                font-size: 15pt;
                color: {self.colors['text']};
                background-color: {self.colors['button_primary']};
            }}
            QPushButton#build_btn {{
                background-color: {self.colors['button_action']};
                color: black;
                font-weight: 700;
            }}
            QPushButton#clear_log_btn {{
                background-color: {self.colors['button_warning']};
            }}
            QPushButton:hover {{
                border-color: {self.colors['accent']};
            }}
            QStatusBar {{
                background-color: {self.colors['bg_panel']};
                color: {self.colors['text']};
            }}
        """
        )

    def _append_log(self, message: str) -> None:
        self.log_output.append(message)
        self.log_output.ensureCursorVisible()

    def _browse_spec_file(self) -> None:
        current_text = self.spec_combo.currentText().strip()
        start_dir = os.path.dirname(current_text) if current_text else "."
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выбор spec-файла",
            start_dir,
            "Spec Files (*.spec)",
        )
        if file_path:
            self._add_to_history(file_path)

    def _start_compilation(self) -> None:
        spec_file = self.spec_combo.currentText().strip()
        if not spec_file or not os.path.exists(spec_file):
            QMessageBox.warning(self, "Ошибка", "Укажите путь к .spec файлу.")
            return
        project_root = self._get_project_root(spec_file)
        canonical_spec = os.path.join(
            project_root, "Build_Tools", "YouTubePrivateUploader.spec"
        )
        if os.path.normcase(os.path.abspath(spec_file)) != os.path.normcase(canonical_spec):
            QMessageBox.warning(self, "Ошибка", "Выберите канонический spec проекта.")
            return
        python_exe = os.path.join(project_root, ".venv", "Scripts", "python.exe")
        chosen_python = self.python_path_edit.text().strip()
        if chosen_python and os.path.normcase(os.path.abspath(self._normalize_python_exe(chosen_python))) != os.path.normcase(python_exe):
            QMessageBox.warning(self, "Ошибка", "Сборка требует Python из проектной .venv.")
            return
        if not os.path.isfile(python_exe):
            QMessageBox.warning(self, "Ошибка", "Python в проектной .venv не найден.")
            return
        powershell_exe = os.path.join(
            os.environ["SystemRoot"], "System32", "WindowsPowerShell", "v1.0", "powershell.exe"
        )
        command = [
            powershell_exe,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            os.path.join(project_root, "build.ps1"),
        ]
        self._add_to_history(spec_file)
        self._append_log(">>> Старт проверенной сборки через build.ps1")
        self.statusBar().showMessage("Сборка...")
        self.build_btn.setEnabled(False)

        self.thread = CompilerThread(command, project_root)
        self.thread.new_log_line.connect(self._append_log)
        self.thread.finished_compilation.connect(self._on_compilation_finished)
        self.thread.start()

    def _on_compilation_finished(self, success: bool, message: str) -> None:
        self.build_btn.setEnabled(True)
        self.statusBar().showMessage(message)
        self._append_log(message)


    def _add_to_history(self, path: str) -> None:
        existing = [self.spec_combo.itemText(i) for i in range(self.spec_combo.count())]
        if path not in existing:
            self.spec_combo.insertItem(0, path)
        self.spec_combo.setCurrentText(path)
        self._save_settings()

    def _normalize_python_exe(self, path: str) -> str:
        if path.lower().endswith("pythonw.exe"):
            alt = os.path.join(os.path.dirname(path), "python.exe")
            if os.path.exists(alt):
                return alt
        return path

    def _get_project_root(self, spec_file: str) -> str:
        spec_dir = os.path.abspath(os.path.dirname(spec_file) or ".")
        return os.path.abspath(os.path.join(spec_dir, ".."))

    def _browse_python_interpreter(self) -> None:
        current_text = self.python_path_edit.text().strip()
        start_dir = os.path.dirname(current_text) if current_text else "."
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выбор интерпретатора Python",
            start_dir,
            "Python (*.exe);;Все файлы (*)",
        )
        if file_path:
            self.python_path_edit.setText(file_path)
            self._save_settings()

    def _load_settings(self) -> None:
        data = self._read_settings_file(self.settings_path)
        if SETTINGS_KEY not in data:
            legacy = self._read_settings_file(self.legacy_settings_path)
            if legacy:
                data[SETTINGS_KEY] = legacy
                self._write_settings_file(data)
        app_data = data.get(SETTINGS_KEY, {})
        if not isinstance(app_data, dict):
            app_data = {}
        try:
            history = app_data.get("spec_file_history", [])
            last_index = app_data.get("last_spec_index", 0)
            last_path = (app_data.get("last_spec_path") or "").strip()
            geo = app_data.get("window_geometry") or {}
            was_maximized = bool(app_data.get("window_maximized", False))
            for entry in history:
                self.spec_combo.addItem(entry)
            if last_path:
                if last_path not in history:
                    self.spec_combo.insertItem(0, last_path)
                self.spec_combo.setCurrentText(last_path)
            elif 0 <= last_index < len(history):
                self.spec_combo.setCurrentIndex(last_index)
            self.python_path_edit.setText(app_data.get("python_path", ""))
            self._restore_geometry(geo, was_maximized)
        except Exception as exc:
            self._append_log(f"Не удалось загрузить настройки: {exc}")

    def _save_settings(self) -> None:
        history = [self.spec_combo.itemText(i) for i in range(self.spec_combo.count())]
        g = self.geometry()
        app_data = {
            "spec_file_history": history,
            "last_spec_index": self.spec_combo.currentIndex(),
            "last_spec_path": self.spec_combo.currentText().strip(),
            "python_path": self.python_path_edit.text().strip(),
            "window_geometry": {
                "x": g.x(),
                "y": g.y(),
                "w": g.width(),
                "h": g.height(),
            },
            "window_maximized": self.isMaximized(),
        }
        data = self._read_settings_file(self.settings_path)
        data[SETTINGS_KEY] = app_data
        self._write_settings_file(data)

    def _read_settings_file(self, path: str) -> dict:
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8-sig") as fh:
                data = json.load(fh)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _write_settings_file(self, data: dict) -> None:
        try:
            with open(self.settings_path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
        except Exception as exc:
            self._append_log(f"Не удалось сохранить настройки: {exc}")

    def _restore_geometry(self, geo: dict, was_maximized: bool) -> None:
        try:
            x = int(geo.get("x", 0))
            y = int(geo.get("y", 0))
            w = int(geo.get("w", 0))
            h = int(geo.get("h", 0))
            if w > 100 and h > 100:
                self.setGeometry(x, y, w, h)
            if was_maximized:
                self.showMaximized()
        except Exception:
            pass

    def closeEvent(self, event) -> None:
        self._save_settings()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                APP_USER_MODEL_ID
            )
        except Exception:
            pass
    window = PyCompilerApp()
    window.show()
    sys.exit(app.exec())
