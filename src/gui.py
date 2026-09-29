"""PySide6-интерфейс: главное окно и фоновая загрузка (ТЗ, разделы 22-29, 40-41).

Только UI и взаимодействие с пользователем; OAuth/API вызываются в core-модулях.
"""

from __future__ import annotations

import json
import logging
import threading
import webbrowser
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import (
    config,
    icons,
    models,
    styles,
    templates,
    ui_scale,
    ui_scale_runtime,
    youtube_auth,
    youtube_uploader,
)
from .models import (
    Outcome,
    UploadResult,
    ValidationCode,
    ValidationIssue,
    VideoPackage,
)
from .theme import COLORS, ERROR, MUTED, SUCCESS, WARNING
from .validators import validate_package

logger = logging.getLogger("youtube_uploader.gui")

GREEN = SUCCESS
ORANGE = WARNING
RED = ERROR

FIRST_OAUTH_MSG = (
    "Сейчас откроется браузер Google.\n\n"
    "Выберите именно тот Google-аккаунт, которому принадлежит нужный YouTube-канал."
)
CLOSE_WHILE_UPLOAD_MSG = (
    "Сейчас выполняется загрузка видео.\n\n"
    "Если закрыть приложение, загрузка будет прервана.\n\n"
    "Закрыть программу?"
)
RESET_AUTH_MSG = (
    "Удалить сохранённую авторизацию Google?\n\n"
    "При следующей загрузке приложение запросит авторизацию заново.\n"
    "Файл client_secret.json удалён не будет."
)
PLAYLIST_NONE_LABEL = "— без плейлиста —"
PLAYLIST_REAUTH_MSG = (
    "Для работы с плейлистами нужно обновить права приложения.\n\n"
    "Сейчас откроется окно Google — войдите и подтвердите доступ."
)
NO_CLIENT_SECRET_PLAYLISTS_MSG = (
    "Список плейлистов можно загрузить после авторизации Google.\n\n"
    "Положите файл client_secret.json в папку config/ проекта."
)
CLEAR_FIELDS_MSG = (
    "Очистить название песни, перевод и ссылки на посты в Telegram и MAX?"
)

VIDEO_FILE_FILTER = (
    "Видеофайлы (*.mp4 *.mov *.mkv *.avi *.m4v *.webm *.mpeg *.mpg);;Все файлы (*.*)"
)
IMAGE_FILE_FILTER = "Изображения (*.jpg *.jpeg *.png);;Все файлы (*.*)"

COMMON_CATEGORIES = [
    ("1", "Фильмы и анимация"),
    ("2", "Авто и транспорт"),
    ("10", "Музыка"),
    ("15", "Питомцы и животные"),
    ("17", "Спорт"),
    ("19", "Путешествия и события"),
    ("20", "Игры"),
    ("22", "Люди и блоги"),
    ("23", "Юмор"),
    ("24", "Развлечения"),
    ("25", "Новости и политика"),
    ("26", "Хобби и стиль"),
    ("27", "Образование"),
    ("28", "Наука и техника"),
]


class WorkerSignals(QObject):
    """Сигналы из фонового потока в главный (Qt сигналы потокобезопасны)."""

    progress = Signal(int)
    stage = Signal(str)
    log = Signal(str)
    done = Signal(object)
    auth_error = Signal(str, str)
    fatal = Signal(str)
    playlists = Signal(object)
    playlist_error = Signal(str, str)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube Private Uploader")
        self._normal_geometry = None
        self._clamping_geometry = False
        self._geometry_save_timer = QTimer(self)
        self._geometry_save_timer.setSingleShot(True)
        self._geometry_save_timer.setInterval(400)
        self._geometry_save_timer.timeout.connect(self._save_geometry)
        self.setMinimumSize(780, 680)
        self.resize(860, 760)

        self.folder: Path | None = None
        self.video_path: Path | None = None
        self.thumb_path: Path | None = None
        self.busy = False
        self.cancel_event = threading.Event()
        self.last_result: UploadResult | None = None
        self.signals = WorkerSignals()
        self.current_issues: list[ValidationIssue] = []
        self._templates: dict[str, str] = templates.default_templates()
        self._template_error: str | None = None
        self._loading_templates = False
        self._saved_playlist: dict | None = None
        self._ui_scale_delta_percent = 0
        self._ui_scale_state: ui_scale.UIScaleState | None = None
        self._ui_scale_factor = 1.0
        self._ui_scale_screen = None
        self._ui_scale_app_hooks_installed = False
        self._ui_scale_window_hook_installed = False
        self._startup_maximized = False
        self._geometry_was_restored = False
        self._restoring_state = True
        self._thumb_chosen_manually = False

        self._build_widgets()
        self._apply_icons()
        self._fix_label_size_policies()
        self._connect_signals()
        self._restore_geometry()
        self._restore_playlist_selection()
        self._restore_ui_scale_settings()
        self._load_templates()
        saved_folder = self._saved_folder()
        if saved_folder is not None:
            self._load_folder(saved_folder)
        self._restore_form_state()
        self._restoring_state = False
        ui_scale_runtime.apply_widget_overrides(self, 1.0)
        self._refresh_validation()
        self.apply_ui_scale(allow_window_resize=True, reason="startup")
        if youtube_auth.client_secret_exists() and self._token_has_playlist_scope():
            self._refresh_playlists()
        logger.info("Окно создано")

    # ---------- построение UI ----------

    def _build_widgets(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(10)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(11)
        root.addLayout(brand_row)
        self.brand_icon_label = QLabel()
        self.brand_icon_label.setFixedSize(40, 40)
        self._brand_icon = self.windowIcon()
        if self._brand_icon.isNull():
            self._brand_icon = icons.app_mark_icon()
        self.brand_icon_label.setPixmap(self._brand_icon.pixmap(QSize(36, 36)))
        self.brand_icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_row.addWidget(self.brand_icon_label)

        brand_text = QVBoxLayout()
        brand_text.setSpacing(1)
        brand_row.addLayout(brand_text, stretch=1)
        title = QLabel("YouTube Private Uploader")
        title.setObjectName("windowTitle")
        brand_text.addWidget(title)
        subtitle = QLabel(
            "Видео и обложка из выбранной папки · приватная публикация"
        )
        subtitle.setObjectName("windowSubtitle")
        brand_text.addWidget(subtitle)

        self.tabs = QTabWidget()
        self.tabs.tabBar().setExpanding(True)
        self.tabs.tabBar().setUsesScrollButtons(False)
        self.tabs.tabBar().setElideMode(Qt.TextElideMode.ElideRight)
        root.addWidget(self.tabs, stretch=1)

        upload_content = QWidget()
        upload_content.setObjectName("tabPage")
        ut = QVBoxLayout(upload_content)
        ut.setContentsMargins(12, 12, 12, 12)
        ut.setSpacing(10)
        upload_tab = QScrollArea()
        upload_tab.setFrameShape(QFrame.Shape.NoFrame)
        upload_tab.setWidgetResizable(True)
        upload_tab.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        upload_tab.setWidget(upload_content)
        self.tabs.addTab(upload_tab, "Загрузка")
        self._fill_upload_tab(ut)
        ut.addStretch(1)

        self._build_poem_tab()
        self._build_templates_tab()
        self._build_preview_tab()
        self._build_settings_tab()

    def _build_settings_tab(self):
        tab = QWidget()
        v = QVBoxLayout(tab)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(10)

        account_card = self._make_card()
        v.addWidget(account_card)
        hl = QLabel("Аккаунт YouTube")
        hl.setObjectName("sectionHeader")
        account_card.layout().addWidget(hl)

        status_row = QHBoxLayout()
        account_card.layout().addLayout(status_row)
        status_row.addWidget(QLabel("Состояние:"))
        self.auth_label = QLabel("")
        self.auth_label.setObjectName("accountStatus")
        self.auth_label.setWordWrap(True)
        status_row.addWidget(self.auth_label, stretch=1)

        account_actions = QHBoxLayout()
        account_card.layout().addLayout(account_actions)
        self.btn_settings_playlists = QPushButton("Обновить плейлисты")
        self.btn_settings_playlists.setToolTip(
            "Проверить авторизацию и заново загрузить список плейлистов канала."
        )
        account_actions.addWidget(self.btn_settings_playlists)
        self.btn_reset_auth = QPushButton("Сбросить авторизацию")
        self.btn_reset_auth.setObjectName("warning")
        account_actions.addWidget(self.btn_reset_auth)
        account_actions.addStretch(1)

        card = self._make_card()
        v.addWidget(card)

        hl = QLabel("Масштаб интерфейса")
        hl.setObjectName("sectionHeader")
        card.layout().addWidget(hl)

        h = QHBoxLayout()
        card.layout().addLayout(h)
        h.addWidget(QLabel("Масштаб:"))
        self.ui_scale_combo = QComboBox()
        self.ui_scale_combo.setAccessibleName("Масштаб интерфейса")
        for delta in range(
            ui_scale.DELTA_MIN, ui_scale.DELTA_MAX + 1, ui_scale.DELTA_STEP
        ):
            self.ui_scale_combo.addItem(f"{100 + delta}%", delta)
        self.ui_scale_combo.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        h.addWidget(self.ui_scale_combo)
        h.addStretch(1)

        v.addStretch(1)

        self.tabs.addTab(tab, "Настройки")

    def _apply_icons(self) -> None:
        """Assign one semantic icon language to tabs and every action button."""
        self.tabs.setIconSize(QSize(18, 18))
        tab_icons = (
            ("upload", COLORS["blue"]),
            ("poem", COLORS["yellow"]),
            ("description", COLORS["turquoise"]),
            ("description", COLORS["cyan"]),
            ("settings", COLORS["text"]),
        )
        for index, (name, color) in enumerate(tab_icons):
            self.tabs.setTabIcon(index, icons.themed_icon(name, color))

        button_icons = {
            self.btn_folder: ("folder", COLORS["yellow"]),
            self.btn_rescan: ("refresh", COLORS["cyan"]),
            self.btn_video: ("video", COLORS["turquoise"]),
            self.btn_thumb: ("image", COLORS["green"]),
            self.btn_playlists: ("playlist", COLORS["cyan"]),
            self.btn_settings_playlists: ("refresh", COLORS["cyan"]),
            self.btn_upload: ("upload", COLORS["bg_deep"]),
            self.btn_cancel: ("close", COLORS["red"]),
            self.btn_clear: ("trash", COLORS["red"]),
            self.btn_reset_auth: ("key", COLORS["yellow"]),
            self.btn_open_video: ("external", COLORS["blue"]),
            self.btn_copy: ("copy", COLORS["cyan"]),
            self.btn_studio: ("studio", COLORS["red"]),
            self.btn_again: ("again", COLORS["green"]),
            self.btn_title_reset: ("reset", COLORS["turquoise"]),
            self.btn_desc_reset: ("reset", COLORS["cyan"]),
        }
        for button, (name, color) in button_icons.items():
            button.setIcon(icons.themed_icon(name, color))
            button.setIconSize(QSize(17, 17))

    def _fill_upload_tab(self, ut: QVBoxLayout):
        # --- Карточка: файлы ---
        files_card = self._make_card()
        ut.addWidget(files_card, stretch=0)
        hl = QLabel("Исходные файлы")
        hl.setObjectName("sectionHeader")
        files_card.layout().addWidget(hl)

        files_grid = QGridLayout()
        files_grid.setHorizontalSpacing(10)
        files_grid.setVerticalSpacing(6)
        files_grid.setColumnStretch(1, 1)
        files_card.layout().addLayout(files_grid)
        files_grid.addWidget(QLabel("Рабочая папка:"), 0, 0)
        self.folder_label = QLabel("не выбрана")
        self.folder_label.setObjectName("muted")
        self.folder_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed
        )
        files_grid.addWidget(self.folder_label, 0, 1)
        self.btn_folder = QPushButton("Выбрать папку")
        self.btn_rescan = QPushButton("Обновить файлы")
        folder_actions = QHBoxLayout()
        folder_actions.setSpacing(6)
        folder_actions.addWidget(self.btn_folder)
        folder_actions.addWidget(self.btn_rescan)
        files_grid.addLayout(folder_actions, 0, 2)

        files_grid.addWidget(QLabel("Видео:"), 1, 0)
        self.video_label = QLabel("—")
        self.video_label.setObjectName("fileValue")
        self.video_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed
        )
        files_grid.addWidget(self.video_label, 1, 1)
        self.btn_video = QPushButton("Выбрать видео")
        files_grid.addWidget(self.btn_video, 1, 2)

        files_grid.addWidget(QLabel("Обложка:"), 2, 0)
        self.thumb_label = QLabel("—")
        self.thumb_label.setObjectName("fileValue")
        self.thumb_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed
        )
        files_grid.addWidget(self.thumb_label, 2, 1)
        self.btn_thumb = QPushButton("Добавить обложку")
        files_grid.addWidget(self.btn_thumb, 2, 2)

        # --- Карточка: параметры публикации ---
        meta_card = self._make_card()
        ut.addWidget(meta_card)
        hl = QLabel("Параметры публикации")
        hl.setObjectName("sectionHeader")
        meta_card.layout().addWidget(hl)

        meta_grid = QGridLayout()
        meta_grid.setHorizontalSpacing(10)
        meta_grid.setVerticalSpacing(7)
        meta_grid.setColumnStretch(1, 1)
        meta_card.layout().addLayout(meta_grid)
        meta_grid.addWidget(QLabel("Название песни:"), 0, 0)
        self.song_edit = QLineEdit()
        self.song_edit.setPlaceholderText("Например: Сплин")
        self.song_edit.setAccessibleName("Название песни")
        meta_grid.addWidget(self.song_edit, 0, 1)

        meta_grid.addWidget(QLabel("Перевод:"), 1, 0)
        self.translator_edit = QLineEdit()
        self.translator_edit.setPlaceholderText("Имя переводчика")
        self.translator_edit.setAccessibleName("Перевод")
        meta_grid.addWidget(self.translator_edit, 1, 1)

        meta_grid.addWidget(QLabel("Ссылка Telegram:"), 2, 0)
        self.tg_edit = QLineEdit()
        self.tg_edit.setPlaceholderText("https://t.me/your_channel")
        self.tg_edit.setAccessibleName("Ссылка Telegram")
        meta_grid.addWidget(self.tg_edit, 2, 1)
        meta_grid.addWidget(QLabel("Ссылка MAX:"), 3, 0)
        self.max_edit = QLineEdit()
        self.max_edit.setPlaceholderText("https://max.ru/c/...")
        self.max_edit.setAccessibleName("Ссылка MAX")
        meta_grid.addWidget(self.max_edit, 3, 1)

        meta_grid.addWidget(QLabel("Категория:"), 4, 0)
        self.category_combo = QComboBox()
        self.category_combo.addItems(
            [f"{name} ({cid})" for cid, name in COMMON_CATEGORIES]
        )
        self.category_combo.setCurrentIndex(7)  # "22. Люди и блоги"
        self.category_combo.setAccessibleName("Категория YouTube")
        meta_grid.addWidget(self.category_combo, 4, 1)
        meta_grid.addWidget(QLabel("Теги:"), 5, 0)
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("поэзия, Бодлер, музыка")
        self.tags_edit.setAccessibleName("Теги через запятую")
        meta_grid.addWidget(self.tags_edit, 5, 1)

        meta_grid.addWidget(QLabel("Плейлист:"), 6, 0)
        self.playlist_combo = QComboBox()
        self.playlist_combo.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed
        )
        self.playlist_combo.setAccessibleName("Плейлист канала")
        self.btn_playlists = QPushButton("Обновить")
        self.btn_playlists.setToolTip(
            "Загрузить список плейлистов канала. Нужна авторизация Google."
        )
        playlist_row = QHBoxLayout()
        playlist_row.setSpacing(6)
        playlist_row.addWidget(self.playlist_combo, stretch=1)
        playlist_row.addWidget(self.btn_playlists)
        meta_grid.addLayout(playlist_row, 6, 1)

        options_row = QGridLayout()
        self.kids_check = QCheckBox("Made for Kids (создано для детей)")
        self.notify_check = QCheckBox("Уведомить подписчиков")
        options_row.addWidget(self.kids_check, 0, 0, 1, 3)
        options_row.addWidget(self.notify_check, 1, 0)
        options_row.setColumnStretch(1, 1)
        self.badge = QLabel("PRIVATE")
        self.badge.setObjectName("badge")
        options_row.addWidget(self.badge, 1, 3)
        meta_grid.addLayout(options_row, 7, 0, 1, 2)

        self.desc_counter = QLabel("0/5000 байт")
        self.desc_counter.setObjectName("counter")
        self.desc_preview = QPlainTextEdit()
        self.desc_preview.setReadOnly(True)
        self.desc_preview.setMinimumHeight(140)

        # --- Карточка: проверки ---
        check_card = self._make_card()
        ut.addWidget(check_card)
        self.readiness_header = QLabel("Готовность к публикации")
        self.readiness_header.setObjectName("sectionHeader")
        check_card.layout().addWidget(self.readiness_header)
        self.issues_text = QLabel("")
        self.issues_text.setWordWrap(True)
        self.issues_text.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        self.issues_text.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.issues_text.setStyleSheet(f"color: {MUTED};")
        check_card.layout().addWidget(self.issues_text)

        # --- Прогресс ---
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        check_card.layout().addWidget(self.progress)
        self.stage_label = QLabel("")
        self.stage_label.setStyleSheet(f"color: {MUTED};")
        check_card.layout().addWidget(self.stage_label)

        # --- Кнопки действий ---
        actions = QVBoxLayout()
        actions.setSpacing(6)
        check_card.layout().addLayout(actions)
        btns = QHBoxLayout()
        btns.setSpacing(8)
        actions.addLayout(btns)
        btns.addStretch(1)
        self.btn_upload = QPushButton("Загрузить на YouTube")
        self.btn_upload.setObjectName("primary")
        self.btn_upload.setFixedHeight(38)
        btns.addWidget(self.btn_upload)
        self.btn_cancel = QPushButton("Отменить")
        self.btn_cancel.setObjectName("danger")
        self.btn_cancel.setFixedHeight(38)
        btns.addWidget(self.btn_cancel)
        self.btn_clear = QPushButton("Очистить название, перевод и ссылки")
        self.btn_clear.setFixedHeight(38)
        btns.addWidget(self.btn_clear)
        btns.addStretch(1)

        # --- Карточка результата ---
        self.result_card = self._make_card()
        ut.addWidget(self.result_card)
        self.result_header = QLabel("")
        self.result_header.setObjectName("sectionHeader")
        self.result_card.layout().addWidget(self.result_header)
        self.result_message = QLabel("")
        self.result_message.setWordWrap(True)
        self.result_message.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.result_card.layout().addWidget(self.result_message)
        self.result_detail = QLabel("")
        self.result_detail.setWordWrap(True)
        self.result_detail.setStyleSheet(f"color: {MUTED};")
        self.result_card.layout().addWidget(self.result_detail)
        self.result_instructions = QLabel(
            "Остался один ручной шаг:\n"
            "откройте YouTube Studio, измените доступ с Private на Public\n"
            "и нажмите «Сохранить»."
        )
        self.result_instructions.setWordWrap(True)
        self.result_card.layout().addWidget(self.result_instructions)

        rh = QHBoxLayout()
        self.result_card.layout().addLayout(rh)
        self.btn_open_video = QPushButton("Открыть видео")
        rh.addWidget(self.btn_open_video)
        self.btn_copy = QPushButton("Копировать ссылку")
        rh.addWidget(self.btn_copy)
        self.btn_studio = QPushButton("Открыть YouTube Studio")
        rh.addWidget(self.btn_studio)
        self.btn_again = QPushButton("Загрузить другое видео")
        rh.addWidget(self.btn_again)

        self.result_card.hide()

    def _build_preview_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        preview_card = self._make_card()
        preview_card.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding
        )
        layout.addWidget(preview_card, stretch=1)
        description_row = QHBoxLayout()
        preview_card.layout().addLayout(description_row)
        heading = QLabel("Итоговое описание")
        heading.setObjectName("sectionHeader")
        description_row.addWidget(heading)
        description_row.addStretch(1)
        description_row.addWidget(self.desc_counter)
        self.desc_preview.setAccessibleName("Предпросмотр итогового описания")
        preview_card.layout().addWidget(self.desc_preview, stretch=1)
        self.tabs.addTab(tab, "Предпросмотр")

    def _build_templates_tab(self):
        content = QWidget()
        content.setObjectName("tabPage")
        v = QVBoxLayout(content)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(10)
        card = self._make_card()
        v.addWidget(card)

        hl = QLabel("Шаблон названия")
        hl.setObjectName("sectionHeader")
        card.layout().addWidget(hl)
        self.title_tpl_edit = QPlainTextEdit()
        self.title_tpl_edit.setFixedHeight(64)
        self.title_tpl_edit.setAccessibleName("Шаблон названия")
        card.layout().addWidget(self.title_tpl_edit)

        h = QHBoxLayout()
        card.layout().addLayout(h)
        self.btn_title_reset = QPushButton("Стандартный шаблон")
        h.addWidget(self.btn_title_reset)
        self.title_tpl_status = QLabel("")
        self.title_tpl_status.setStyleSheet(f"color: {RED};")
        self.title_tpl_status.hide()
        h.addWidget(self.title_tpl_status)
        h.addStretch(1)
        self._add_description_template_card(v)
        tab = QScrollArea()
        tab.setFrameShape(QFrame.Shape.NoFrame)
        tab.setWidgetResizable(True)
        tab.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        tab.setWidget(content)
        self.tabs.addTab(tab, "Шаблоны")

    def _add_description_template_card(self, v: QVBoxLayout):
        card = self._make_card()
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        v.addWidget(card)

        hl = QLabel("Шаблон описания")
        hl.setObjectName("sectionHeader")
        card.layout().addWidget(hl)
        self.desc_tpl_edit = QPlainTextEdit()
        self.desc_tpl_edit.setMinimumHeight(170)
        self.desc_tpl_edit.setAccessibleName("Шаблон описания")
        card.layout().addWidget(self.desc_tpl_edit, stretch=1)

        h = QHBoxLayout()
        card.layout().addLayout(h)
        self.btn_desc_reset = QPushButton("Стандартный шаблон")
        h.addWidget(self.btn_desc_reset)
        self.desc_tpl_status = QLabel("")
        self.desc_tpl_status.setStyleSheet(f"color: {RED};")
        self.desc_tpl_status.hide()
        h.addWidget(self.desc_tpl_status)
        h.addStretch(1)

    def _build_poem_tab(self):
        tab = QWidget()
        v = QVBoxLayout(tab)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(10)
        card = self._make_card()
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        v.addWidget(card)

        hl = QLabel("Текст стихотворения")
        hl.setObjectName("sectionHeader")
        card.layout().addWidget(hl)
        self.poem_edit = QPlainTextEdit()
        self.poem_edit.setPlaceholderText(
            "Вставьте текст стихотворения…\n\n"
            "Он автоматически попадёт в конец описания."
        )
        self.poem_edit.setMinimumHeight(230)
        card.layout().addWidget(self.poem_edit, stretch=1)
        self.poem_counter = QLabel("0 символов")
        self.poem_counter.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.poem_counter.setStyleSheet(f"color: {MUTED};")
        card.layout().addWidget(self.poem_counter)
        self.tabs.addTab(tab, "Стихотворение")

    @staticmethod
    def _make_card() -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        card.setLayout(QVBoxLayout())
        card.layout().setContentsMargins(14, 10, 14, 12)
        card.layout().setSpacing(8)
        return card

    def _fix_label_size_policies(self):
        """Keep compact labels fixed, while wrapped labels may grow vertically."""
        for label in self.findChildren(QLabel):
            policy = label.sizePolicy()
            policy.setVerticalPolicy(
                QSizePolicy.Policy.Preferred
                if label.wordWrap()
                else QSizePolicy.Policy.Fixed
            )
            label.setSizePolicy(policy)

    # ---------- сигналы ----------

    def _connect_signals(self):
        self.btn_folder.clicked.connect(self._select_folder)
        self.btn_rescan.clicked.connect(self._rescan_files)
        self.btn_video.clicked.connect(self._select_video)
        self.btn_thumb.clicked.connect(self._select_thumbnail)
        self.btn_upload.clicked.connect(self._start_upload)
        self.btn_cancel.clicked.connect(self._cancel_upload)
        self.btn_clear.clicked.connect(self._clear_song_translator_and_links)
        self.btn_reset_auth.clicked.connect(self._reset_auth)
        self.btn_settings_playlists.clicked.connect(self._refresh_playlists)
        self.btn_open_video.clicked.connect(self._open_video)
        self.btn_copy.clicked.connect(self._copy_link)
        self.btn_studio.clicked.connect(self._open_studio)
        self.btn_again.clicked.connect(self._reset_for_new)

        self.song_edit.textChanged.connect(self._on_meta_changed)
        self.translator_edit.textChanged.connect(self._on_meta_changed)
        self.tg_edit.textChanged.connect(self._on_meta_changed)
        self.max_edit.textChanged.connect(self._on_meta_changed)
        self.poem_edit.textChanged.connect(self._on_meta_changed)
        self.title_tpl_edit.textChanged.connect(self._on_title_template_changed)
        self.desc_tpl_edit.textChanged.connect(self._on_desc_template_changed)
        self.btn_title_reset.clicked.connect(self._reset_title_template)
        self.btn_desc_reset.clicked.connect(self._reset_desc_template)
        self.tags_edit.textChanged.connect(self._on_meta_changed)
        self.category_combo.currentIndexChanged.connect(self._on_meta_changed)
        self.kids_check.stateChanged.connect(self._on_meta_changed)
        self.notify_check.stateChanged.connect(self._on_meta_changed)
        self.btn_playlists.clicked.connect(self._refresh_playlists)
        self.playlist_combo.currentIndexChanged.connect(self._on_playlist_changed)
        self.ui_scale_combo.currentIndexChanged.connect(self._on_ui_scale_delta_changed)

        self.signals.progress.connect(self._on_progress)
        self.signals.stage.connect(self.stage_label.setText)
        self.signals.log.connect(lambda msg: logger.info("UI: %s", msg))
        self.signals.done.connect(self._finish)
        self.signals.auth_error.connect(self._on_auth_error)
        self.signals.fatal.connect(self._on_fatal)
        self.signals.playlists.connect(self._on_playlists_loaded)
        self.signals.playlist_error.connect(self._on_playlist_error)

    # ---------- выбор файлов ----------

    def _select_folder(self):
        if self.busy:
            return
        folder = QFileDialog.getExistingDirectory(
            self, "Выберите рабочую папку", str(self.folder or config.desktop_dir())
        )
        if not folder:
            return
        self._load_folder(Path(folder))

    def _load_folder(self, path: Path):
        if self.busy:
            return
        self.folder = path
        self.folder_label.setText(str(path))
        self._set_compact_success(False)
        self.result_card.hide()
        self.last_result = None
        self._auto_pick_files()
        self._apply_folder_settings()
        self._update_file_labels()
        self._refresh_validation()

    def _rescan_files(self):
        if self.busy or self.folder is None:
            return
        self._auto_pick_files()
        self._update_file_labels()
        self._refresh_validation()

    def _auto_pick_files(self):
        """Автовыбор последнего видео и однозначной обложки из выбранной папки."""
        video, video_err = _find_latest_video_or_note(self.folder)
        thumb, thumb_err = _find_cover_or_note(self.folder, video)
        self.video_path = video
        self.thumb_path = thumb
        self._thumb_chosen_manually = False
        notes = [note for note in (video_err, thumb_err) if note]
        self.stage_label.setText("\n".join(notes) if notes else "")

    def _select_video(self):
        if self.busy:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите видеофайл",
            str(self.folder or config.desktop_dir()),
            VIDEO_FILE_FILTER,
        )
        if path:
            video = Path(path)
            if self.folder is None or video.parent != self.folder:
                self._load_folder(video.parent)
            self.video_path = video
            if not self._thumb_chosen_manually:
                self.thumb_path, thumb_err = _find_cover_or_note(self.folder, video)
                self.stage_label.setText(thumb_err or "")
            self._update_file_labels()
            self._refresh_validation()

    def _select_thumbnail(self):
        if self.busy:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите обложку",
            str(self.folder or config.desktop_dir()),
            IMAGE_FILE_FILTER,
        )
        if path:
            if self.folder is None:
                self._load_folder(Path(path).parent)
            self.thumb_path = Path(path)
            self._thumb_chosen_manually = True
            self.stage_label.setText("")
            self._update_file_labels()
            self._refresh_validation()

    def _apply_folder_settings(self):
        """Заполнить категорию/теги/чекбоксы из settings.yaml папки."""
        if self.folder is None:
            return
        raw, _yaml_err = _read_yaml_safe(self.folder)
        settings = _effective_settings(raw)
        category_id = str(settings.get("category_id", config.DEFAULT_CATEGORY_ID))
        self._select_category(category_id)
        tags = settings.get("tags", [])
        self.tags_edit.setText(", ".join(str(t) for t in tags) if tags else "")
        self.kids_check.setChecked(bool(settings.get("made_for_kids", False)))
        self.notify_check.setChecked(bool(settings.get("notify_subscribers", False)))

    def _select_category(self, category_id: str):
        for i, (cid, name) in enumerate(COMMON_CATEGORIES):
            if cid == category_id:
                self.category_combo.setCurrentIndex(i)
                return
        self.category_combo.addItem(f"{category_id} (своя)")
        self.category_combo.setCurrentIndex(self.category_combo.count() - 1)

    def _update_file_labels(self):
        self.video_label.setText(str(self.video_path) if self.video_path else "—")
        self.thumb_label.setText(str(self.thumb_path) if self.thumb_path else "—")

    # ---------- валидация ----------

    def _current_category_id(self) -> str:
        idx = self.category_combo.currentIndex()
        if 0 <= idx < len(COMMON_CATEGORIES):
            return COMMON_CATEGORIES[idx][0]
        return str(self.category_combo.currentText().split(" ")[0])

    def _current_package(self) -> VideoPackage | None:
        if self.video_path is None:
            return None
        title, description = self._build_meta()
        tags = [t.strip() for t in self.tags_edit.text().split(",") if t.strip()]
        return VideoPackage(
            folder=self.folder,
            video_path=self.video_path,
            thumbnail_path=self.thumb_path,
            title=title,
            description=description,
            category_id=self._current_category_id(),
            tags=tags,
            made_for_kids=self.kids_check.isChecked(),
            notify_subscribers=self.notify_check.isChecked(),
            playlist_id=self._selected_playlist_id(),
        )

    def _build_meta(self) -> tuple[str, str]:
        """Итоговые название и описание по текущим шаблонам и полям."""
        try:
            title = templates.build_title(
                self.song_edit.text(), self._templates.get("title")
            )
        except ValueError:
            title = ""
        try:
            description = templates.build_description(
                self.tg_edit.text(),
                self.max_edit.text(),
                self.poem_edit.toPlainText(),
                self._templates.get("description"),
                translator=self.translator_edit.text(),
            )
        except ValueError:
            description = ""
        return title, description

    def _on_meta_changed(self, *_):
        self._rebuild_preview()
        self._refresh_validation()
        self._save_form_state()

    def _rebuild_preview(self):
        """Обновить итоговое описание и счётчики описания/стихотворения."""
        _, description = self._build_meta()

        self.desc_preview.setPlainText(description)
        size = len(description.encode("utf-8"))
        self.desc_counter.setText(f"{size}/{config.MAX_DESCRIPTION_UTF8_BYTES} байт")
        color = RED if size > config.MAX_DESCRIPTION_UTF8_BYTES else MUTED
        self.desc_counter.setStyleSheet(f"color: {color};")

        n_poem = len(self.poem_edit.toPlainText())
        self.poem_counter.setText(f"{n_poem} символов")

    # ---------- шаблоны ----------

    def _load_templates(self):
        self._templates = templates.load_templates()
        self._loading_templates = True
        self.title_tpl_edit.setPlainText(self._templates.get("title", ""))
        self.desc_tpl_edit.setPlainText(self._templates.get("description", ""))
        self._loading_templates = False
        self._validate_templates()

    def _on_title_template_changed(self, *_):
        if self._loading_templates:
            return
        self._templates["title"] = self.title_tpl_edit.toPlainText()
        self._save_and_refresh_templates()

    def _on_desc_template_changed(self, *_):
        if self._loading_templates:
            return
        self._templates["description"] = self.desc_tpl_edit.toPlainText()
        self._save_and_refresh_templates()

    def _save_and_refresh_templates(self):
        try:
            templates.save_templates(self._templates)
            status = ""
        except OSError as exc:
            logger.warning("Не удалось сохранить templates.json: %s", exc)
            status = "Ошибка сохранения!"
        self.title_tpl_status.setText(status)
        self.desc_tpl_status.setText(status)
        self.title_tpl_status.setVisible(bool(status))
        self.desc_tpl_status.setVisible(bool(status))
        self._validate_templates()
        self._rebuild_preview()
        self._refresh_validation()

    def _validate_templates(self):
        title_ok = templates.TITLE_PLACEHOLDER in self._templates.get("title", "")
        desc_ok = all(
            p in self._templates.get("description", "")
            for p in templates.DESCRIPTION_PLACEHOLDERS
        )
        missing = []
        if not title_ok:
            missing.append(templates.TITLE_VAR_MSG)
        if not desc_ok:
            missing.append(templates.DESCRIPTION_VAR_MSG)
        self._template_error = "\n\n".join(missing) if missing else None

    def _reset_title_template(self):
        self._templates["title"] = templates.TITLE_TEMPLATE
        self._loading_templates = True
        self.title_tpl_edit.setPlainText(self._templates["title"])
        self._loading_templates = False
        self._save_and_refresh_templates()

    def _reset_desc_template(self):
        self._templates["description"] = templates.DESCRIPTION_BODY
        self._loading_templates = True
        self.desc_tpl_edit.setPlainText(self._templates["description"])
        self._loading_templates = False
        self._save_and_refresh_templates()

    def _refresh_validation(self):
        if self.busy:
            self._set_busy_ui(True)
            return
        if self._template_error:
            issues = [
                ValidationIssue(ValidationCode.TEMPLATE_BROKEN, self._template_error)
            ]
            package = None
        else:
            package = self._current_package()
            issues = validate_package(package, check_client_secret=True)
        self.current_issues = issues

        html = []
        for issue in issues:
            html.append(f'<span style="color:{RED};">{issue.message}</span>')
        if not issues and package is not None:
            html.append(f'<span style="color:{GREEN};">✓ Всё готово к загрузке</span>')
        self.issues_text.setText(" · ".join(html))
        self.issues_text.setToolTip(
            "\n".join(i.message for i in issues) or "Всё готово к загрузке"
        )

        ok = package is not None and not issues
        self.btn_upload.setEnabled(ok)
        self._update_auth_status()
        logger.info("Валидация: issues=%d, upload=%s", len(issues), ok)

    def _update_auth_status(self):
        status_kind = "muted"
        if youtube_auth.client_secret_exists():
            if config.token_path().is_file():
                if self._token_has_playlist_scope():
                    self.auth_label.setText("Авторизация сохранена, права подтверждены")
                    status_kind = "ok"
                else:
                    self.auth_label.setText(
                        "Авторизация сохранена, но права на плейлисты нужно обновить"
                    )
                    status_kind = "warning"
            else:
                self.auth_label.setText("Авторизация ещё не выполнена")
        else:
            self.auth_label.setText("Не найден config/client_secret.json")
            status_kind = "error"
        self.auth_label.setProperty("statusKind", status_kind)
        self.auth_label.style().unpolish(self.auth_label)
        self.auth_label.style().polish(self.auth_label)

    # ---------- плейлисты ----------

    def _token_has_playlist_scope(self) -> bool:
        creds = youtube_auth.load_credentials()
        if creds is None:
            return False
        scopes = set(getattr(creds, "scopes", []) or [])
        return any(s.endswith("youtube.force-ssl") for s in scopes)

    def _selected_playlist_id(self) -> str:
        data = self.playlist_combo.currentData()
        return str(data) if data else ""

    def _restore_playlist_selection(self):
        try:
            data = json.loads(config.settings_path().read_text(encoding="utf-8"))
            entry = data.get("playlist")
            if isinstance(entry, dict) and entry.get("id"):
                self._saved_playlist = {
                    "id": str(entry["id"]),
                    "title": str(entry.get("title", "")),
                }
        except (OSError, ValueError, TypeError):
            pass
        self.playlist_combo.addItem(PLAYLIST_NONE_LABEL, "")
        if self._saved_playlist:
            label = self._saved_playlist["title"] or self._saved_playlist["id"]
            self.playlist_combo.addItem(label, self._saved_playlist["id"])
            self.playlist_combo.setCurrentIndex(self.playlist_combo.count() - 1)

    def _save_playlist_selection(self):
        if self._restoring_state:
            return
        try:
            path = config.settings_path()
            data = {}
            if path.is_file():
                data = json.loads(path.read_text(encoding="utf-8"))
            data["playlist"] = {
                "id": self._selected_playlist_id(),
                "title": self.playlist_combo.currentText(),
            }
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except (OSError, ValueError, TypeError) as exc:
            logger.warning("Не удалось сохранить выбор плейлиста: %s", exc)

    def _on_playlist_changed(self, *_):
        if self.busy:
            return
        self._save_playlist_selection()

    def _refresh_playlists(self):
        if self.busy:
            return
        if not youtube_auth.client_secret_exists():
            QMessageBox.information(self, "Плейлисты", NO_CLIENT_SECRET_PLAYLISTS_MSG)
            return
        if not self._token_has_playlist_scope() and config.token_path().is_file():
            QMessageBox.information(self, "Авторизация Google", PLAYLIST_REAUTH_MSG)
        self.btn_playlists.setEnabled(False)
        self.btn_settings_playlists.setEnabled(False)
        self.stage_label.setText("Загрузка списка плейлистов...")
        threading.Thread(target=self._playlists_worker, daemon=True).start()

    def _playlists_worker(self):
        try:
            creds = youtube_auth.ensure_credentials()
            youtube = youtube_auth.build_youtube(creds)
            try:
                items = youtube_uploader.list_playlists(youtube)
            except youtube_uploader.UploadError as exc:
                if not exc.reauth:
                    raise
                youtube_auth.remove_credentials()
                creds = youtube_auth.ensure_credentials()
                youtube = youtube_auth.build_youtube(creds)
                items = youtube_uploader.list_playlists(youtube)
            self.signals.playlists.emit(items)
        except youtube_auth.AuthError as exc:
            logger.warning("Авторизация при плейлистах: %s", exc.message)
            self.signals.playlist_error.emit(exc.message, exc.detail or "")
            self.signals.stage.emit("")
        except youtube_uploader.UploadError as exc:
            logger.error("Плейлисты: %s", exc.detail)
            self.signals.playlist_error.emit(exc.message, exc.detail or "")
            self.signals.stage.emit("")
        except Exception as exc:
            logger.exception("Неожиданная ошибка при загрузке плейлистов")
            self.signals.playlist_error.emit(str(exc), "")
            self.signals.stage.emit("")

    def _on_playlists_loaded(self, items: list):
        self.btn_playlists.setEnabled(True)
        self.btn_settings_playlists.setEnabled(True)
        self.stage_label.setText(f"Плейлистов загружено: {len(items)}")
        current = self._selected_playlist_id()
        self.playlist_combo.blockSignals(True)
        self.playlist_combo.clear()
        self.playlist_combo.addItem(PLAYLIST_NONE_LABEL, "")
        found = False
        for item in items:
            self.playlist_combo.addItem(item["title"] or item["id"], item["id"])
            if item["id"] == current:
                found = True
                self.playlist_combo.setCurrentIndex(self.playlist_combo.count() - 1)
        if current and not found:
            label = (self._saved_playlist or {}).get("title", "") or current
            self.playlist_combo.addItem(f"{label} (в списке не найден)", current)
            self.playlist_combo.setCurrentIndex(self.playlist_combo.count() - 1)
        self.playlist_combo.blockSignals(False)
        self._save_playlist_selection()
        self._on_playlist_changed()

    def _on_playlist_error(self, message: str, detail: str):
        self.btn_playlists.setEnabled(True)
        self.btn_settings_playlists.setEnabled(True)
        self.stage_label.setText("")
        QMessageBox.warning(
            self, "Список плейлистов", message + ("\n\n" + detail if detail else "")
        )
        self._update_auth_status()

    # ---------- сохранение полей между запусками ----------

    def _saved_folder(self) -> Path | None:
        try:
            data = json.loads(config.settings_path().read_text(encoding="utf-8"))
            form = data.get("form")
            if isinstance(form, dict) and form.get("folder"):
                folder = Path(str(form["folder"]))
                if folder.is_dir():
                    return folder
        except (OSError, ValueError, TypeError):
            pass
        return None

    def _save_form_state(self):
        if self._restoring_state:
            return
        try:
            path = config.settings_path()
            data = {}
            if path.is_file():
                data = json.loads(path.read_text(encoding="utf-8"))
            data["form"] = {
                "song": self.song_edit.text(),
                "translator": self.translator_edit.text(),
                "tg": self.tg_edit.text(),
                "max": self.max_edit.text(),
                "tags": [
                    t.strip() for t in self.tags_edit.text().split(",") if t.strip()
                ],
                "category_id": self._current_category_id(),
                "made_for_kids": self.kids_check.isChecked(),
                "notify_subscribers": self.notify_check.isChecked(),
                "poem": self.poem_edit.toPlainText(),
                "folder": str(self.folder) if self.folder else "",
            }
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except (OSError, ValueError, TypeError) as exc:
            logger.warning("Не удалось сохранить поля: %s", exc)

    def _restore_form_state(self):
        try:
            data = json.loads(config.settings_path().read_text(encoding="utf-8"))
            form = data.get("form") or {}
        except (OSError, ValueError, TypeError):
            form = {}
        if not isinstance(form, dict):
            return
        self.song_edit.setText(str(form.get("song", "")))
        self.translator_edit.setText(str(form.get("translator", "")))
        self.tg_edit.setText(str(form.get("tg", "")))
        self.max_edit.setText(str(form.get("max", "")))
        saved_tags = form.get("tags") or []
        self.tags_edit.setText(
            ", ".join(str(t) for t in saved_tags) if saved_tags else ""
        )
        category_id = str(form.get("category_id", ""))
        if category_id:
            self._select_category(category_id)
        self.kids_check.setChecked(bool(form.get("made_for_kids", False)))
        self.notify_check.setChecked(bool(form.get("notify_subscribers", False)))
        self.poem_edit.setPlainText(str(form.get("poem", "")))

    def _clear_song_translator_and_links(self):
        if self.busy:
            return
        if QMessageBox.question(self, "Очистить название, перевод и ссылки", CLEAR_FIELDS_MSG) != (
            QMessageBox.StandardButton.Yes
        ):
            return
        self.song_edit.clear()
        self.translator_edit.clear()
        self.tg_edit.clear()
        self.max_edit.clear()
        self._save_form_state()
        self.stage_label.setText("Название, перевод и ссылки очищены")

    # ---------- загрузка ----------

    def _start_upload(self):
        if self.busy or self.current_issues:
            return
        package = self._current_package()
        if package is None:
            return
        if (
            youtube_auth.load_credentials() is None
            and youtube_auth.client_secret_exists()
        ):
            QMessageBox.information(self, "Авторизация Google", FIRST_OAUTH_MSG)
        self._set_busy(True)
        self.cancel_event.clear()
        self._set_compact_success(False)
        self.result_card.hide()
        self.last_result = None
        self.progress.setValue(0)
        self.stage_label.setText("Подготовка...")
        logger.info("Начало загрузки: %s", package.video_path)
        threading.Thread(target=self._worker, args=(package,), daemon=True).start()

    def _worker(self, package: VideoPackage):
        try:
            creds = youtube_auth.ensure_credentials()
            youtube = youtube_auth.build_youtube(creds)
            self.signals.log.emit("Авторизация выполнена")

            result = youtube_uploader.run_upload(
                youtube,
                package,
                on_progress=self.signals.progress.emit,
                on_stage=self.signals.stage.emit,
                is_canceled=lambda: self.cancel_event.is_set(),
            )
            if result.video_id and package.folder is not None:
                try:
                    models.write_marker(
                        package.folder,
                        models.UploadMarker(
                            video_id=result.video_id,
                            uploaded_at=models.now_iso(),
                            status="private",
                            thumbnail_uploaded=result.thumbnail_uploaded,
                            video_name=package.video_path.name,
                        ),
                    )
                    self.signals.log.emit(".youtube-upload.json записан")
                except OSError as exc:
                    self.signals.log.emit(f".youtube-upload.json: {exc}")
            self.signals.done.emit(result)
        except youtube_auth.AuthError as exc:
            self.signals.auth_error.emit(exc.message, exc.detail or "")
        except Exception as exc:
            logger.exception("Неожиданная ошибка в worker")
            self.signals.fatal.emit(str(exc))

    def _set_busy(self, busy: bool):
        self.busy = busy
        self._set_busy_ui(busy)
        if busy:
            self.progress.setValue(0)

    def _set_busy_ui(self, busy: bool):
        for w in (
            self.btn_folder,
            self.btn_rescan,
            self.btn_video,
            self.btn_thumb,
            self.btn_upload,
            self.btn_reset_auth,
            self.btn_again,
            self.btn_open_video,
            self.btn_copy,
            self.btn_studio,
            self.song_edit,
            self.translator_edit,
            self.tg_edit,
            self.max_edit,
            self.poem_edit,
            self.title_tpl_edit,
            self.desc_tpl_edit,
            self.btn_title_reset,
            self.btn_desc_reset,
            self.tags_edit,
            self.category_combo,
            self.kids_check,
            self.notify_check,
            self.playlist_combo,
            self.btn_playlists,
            self.btn_settings_playlists,
            self.btn_clear,
            self.ui_scale_combo,
        ):
            w.setEnabled(not busy)
        self.btn_cancel.setEnabled(busy)

    def _cancel_upload(self):
        self.cancel_event.set()
        self.stage_label.setText("Отмена...")

    def _on_progress(self, percent: int):
        self.progress.setValue(percent)

    def _on_auth_error(self, message: str, detail: str):
        self._set_busy(False)
        text = message + ("\n\nПодробности в логе." if detail else "")
        QMessageBox.critical(self, "Ошибка авторизации", text)
        self._refresh_validation()

    def _on_fatal(self, detail: str):
        self._set_busy(False)
        QMessageBox.critical(
            self,
            "Внутренняя ошибка",
            "Произошла непредвиденная ошибка.\n\nПодробности в логе.\n\n" + detail,
        )
        self._refresh_validation()

    def _finish(self, result: UploadResult):
        self._set_busy(False)
        self.progress.setValue(100)
        self.stage_label.setText("")
        self.last_result = result
        self.result_card.show()

        if result.outcome == Outcome.SUCCESS:
            self.result_header.setText("✓ ГОТОВО — видео загружено как PRIVATE")
            self.result_header.setStyleSheet(f"color: {GREEN}; font-weight: bold;")
            self.result_instructions.hide()
        elif result.outcome == Outcome.PARTIAL_SUCCESS:
            self.result_header.setText(
                "! ЧАСТИЧНЫЙ УСПЕХ — видео загружено, но есть проблема"
            )
            self.result_header.setStyleSheet(f"color: {ORANGE}; font-weight: bold;")
            self.result_instructions.show()
        else:
            self.result_header.setText("✕ ОШИБКА — видео не загружено")
            self.result_header.setStyleSheet(f"color: {RED}; font-weight: bold;")
            self.result_instructions.hide()

        self.result_message.setText(result.message)
        self.result_detail.setText(
            ("Технические детали: " + result.detail) if result.detail else ""
        )
        has_video = result.video_id is not None
        for btn in (self.btn_open_video, self.btn_copy, self.btn_studio):
            btn.setEnabled(has_video)
        self._refresh_validation()
        self._set_compact_success(result.outcome == Outcome.SUCCESS)

    def _set_compact_success(self, compact: bool):
        """После успеха оставить только очистку и кнопки результата."""
        for widget in (
            self.readiness_header,
            self.issues_text,
            self.progress,
            self.stage_label,
            self.btn_upload,
            self.btn_cancel,
            self.result_header,
            self.result_message,
            self.result_detail,
        ):
            widget.setVisible(not compact)

    # ---------- действия результата ----------

    def _open_video(self):
        if self.last_result and self.last_result.video_url:
            webbrowser.open(self.last_result.video_url)

    def _open_studio(self):
        if self.last_result and self.last_result.video_id:
            webbrowser.open(
                config.STUDIO_URL_TEMPLATE.format(video_id=self.last_result.video_id)
            )

    def _copy_link(self):
        if not (self.last_result and self.last_result.video_url):
            return
        QGuiApplication.clipboard().setText(self.last_result.video_url)
        self.stage_label.setText("Ссылка скопирована в буфер обмена")

    def _reset_for_new(self):
        self._set_busy(False)
        self.last_result = None
        self.progress.setValue(0)
        self.stage_label.setText("")
        self._set_compact_success(False)
        self.result_card.hide()
        if self.folder is not None:
            self._rescan_files()
        self._save_form_state()

    # ---------- прочее ----------

    def _reset_auth(self):
        if self.busy:
            return
        if not config.token_path().is_file():
            QMessageBox.information(
                self, "Сброс авторизации", "Сохранённой авторизации нет."
            )
            return
        if QMessageBox.question(self, "Сбросить авторизацию", RESET_AUTH_MSG) == (
            QMessageBox.StandardButton.Yes
        ):
            if youtube_auth.remove_credentials():
                QMessageBox.information(
                    self,
                    "Сброс авторизации",
                    "Авторизация сброшена. При следующей загрузке откроется браузер Google.",
                )
            self._update_auth_status()

    def closeEvent(self, event: QCloseEvent):
        if self.busy:
            answer = QMessageBox.question(
                self, "Загрузка выполняется", CLOSE_WHILE_UPLOAD_MSG
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        self._geometry_save_timer.stop()
        self._save_geometry()
        logger.info("Окно закрыто")
        event.accept()

    def moveEvent(self, event):
        super().moveEvent(event)
        if not (self.isMaximized() or self.isFullScreen() or self.isMinimized()):
            self._normal_geometry = self.geometry()
            self._schedule_geometry_save()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._enforce_window_within_screens()
        if not (self.isMaximized() or self.isFullScreen() or self.isMinimized()):
            self._normal_geometry = self.geometry()
            self._schedule_geometry_save()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            if not (self.isMaximized() or self.isFullScreen() or self.isMinimized()):
                self._normal_geometry = self.geometry()
            self._schedule_geometry_save()

    def _schedule_geometry_save(self):
        self._geometry_save_timer.start()

    def _restore_geometry(self):
        try:
            data = json.loads(config.settings_path().read_text(encoding="utf-8"))
            if data.get("geometry_v") not in (2, 3):
                return
            width = int(data.get("window_width", data.get("width", 860)))
            height = int(data.get("window_height", data.get("height", 760)))
            x = int(data.get("window_pos_x", data.get("x", -1)))
            y = int(data.get("window_pos_y", data.get("y", -1)))
            x, y, width, height = self._clamp_restored_geometry(x, y, width, height)
            self._geometry_was_restored = True
            self._normal_geometry = QRect(x, y, width, height)
            self.setGeometry(x, y, width, height)
            if data.get("maximized"):
                self._startup_maximized = True
        except (OSError, ValueError, TypeError):
            pass

    def _clamp_restored_geometry(self, x: int, y: int, width: int, height: int):
        """Не дать восстановленной геометрии выйти за рабочую область экрана."""
        screen = self._screen_at(x, y)
        if screen is None:
            return x, y, width, height
        avail = screen.availableGeometry()
        min_w = min(self.minimumWidth(), avail.width())
        min_h = min(self.minimumHeight(), avail.height())
        width = max(min(width, avail.width()), min_w)
        height = max(min(height, avail.height()), min_h)
        x = min(max(x, avail.left()), avail.right() + 1 - width)
        y = min(max(y, avail.top()), avail.bottom() + 1 - height)
        return x, y, width, height

    def _screen_at(self, x: int, y: int):
        app = QApplication.instance()
        screens = app.screens() if app else []
        for screen in screens:
            if screen.geometry().intersects(QRect(x, y, 1, 1)):
                return screen
        return app.primaryScreen() if app else (screens[0] if screens else None)

    def _enforce_window_within_screens(self):
        """Аварийная страховка: окно никогда не бывает больше объединения экранов.

        Обычное перемещение/растягивание окна по мониторам не затрагивается;
        срабатывает только когда размер окна выходит за все экраны (например,
        после восстановления из максимизированного состояния).
        """
        if (
            self._clamping_geometry
            or self.isMaximized()
            or self.isFullScreen()
            or self.isMinimized()
        ):
            return
        app = QApplication.instance()
        screens = app.screens() if app else []
        if not screens:
            return
        left = min(s.geometry().left() for s in screens)
        top = min(s.geometry().top() for s in screens)
        right = max(s.geometry().right() for s in screens)
        bottom = max(s.geometry().bottom() for s in screens)
        g = self.geometry()
        if (
            g.left() >= left
            and g.top() >= top
            and g.right() <= right
            and g.bottom() <= bottom
        ):
            return
        self._clamping_geometry = True
        try:
            width = min(g.width(), right - left + 1)
            height = min(g.height(), bottom - top + 1)
            x = min(max(g.x(), left), right - width + 1)
            y = min(max(g.y(), top), bottom - height + 1)
            if (x, y, width, height) != (g.x(), g.y(), g.width(), g.height()):
                self.setGeometry(x, y, width, height)
        finally:
            self._clamping_geometry = False

    def _save_geometry(self):
        try:
            path = config.settings_path()
            data = {}
            if path.is_file():
                data = json.loads(path.read_text(encoding="utf-8"))
            rect = self._normal_geometry or self.geometry()
            data.update(
                {
                    "geometry_v": 3,
                    "window_width": rect.width(),
                    "window_height": rect.height(),
                    "window_pos_x": rect.x(),
                    "window_pos_y": rect.y(),
                    "width": rect.width(),
                    "height": rect.height(),
                    "x": rect.x(),
                    "y": rect.y(),
                    "maximized": self.isMaximized(),
                }
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except (OSError, ValueError, TypeError) as exc:
            logger.warning("Не удалось сохранить геометрию: %s", exc)

    # ---------- масштаб интерфейса ----------

    def _restore_ui_scale_settings(self):
        try:
            data = json.loads(config.settings_path().read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            data = {}
        normalized = ui_scale.migrate_ui_scale_settings(data)
        self._ui_scale_delta_percent = normalized[ui_scale.SETTINGS_DELTA_KEY]
        self.ui_scale_combo.blockSignals(True)
        idx = (self._ui_scale_delta_percent - ui_scale.DELTA_MIN) // ui_scale.DELTA_STEP
        self.ui_scale_combo.setCurrentIndex(
            max(0, min(idx, self.ui_scale_combo.count() - 1))
        )
        self.ui_scale_combo.blockSignals(False)

    def _save_ui_scale_settings(self):
        try:
            path = config.settings_path()
            data = {}
            if path.is_file():
                data = json.loads(path.read_text(encoding="utf-8"))
            data[ui_scale.SETTINGS_MODE_KEY] = "auto"
            data[ui_scale.SETTINGS_DELTA_KEY] = self._ui_scale_delta_percent
            data[ui_scale.SETTINGS_FINAL_KEY] = (
                self._ui_scale_state.final_percent if self._ui_scale_state else 100
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except (OSError, ValueError, TypeError) as exc:
            logger.warning("Не удалось сохранить масштаб: %s", exc)

    def _on_ui_scale_delta_changed(self, *_):
        if self.busy:
            return
        delta = ui_scale.normalize_ui_scale_delta_percent(
            self.ui_scale_combo.currentData()
        )
        self._ui_scale_delta_percent = delta
        self.apply_ui_scale(allow_window_resize=True, reason="manual-delta")

    def apply_ui_scale(
        self, allow_window_resize: bool = False, reason: str = "startup"
    ):
        """Пересчитать масштаб от текущего экрана и применить его.

        Resize окна разрешён только для startup и ручной поправки;
        смена экрана/DPI/топологии масштаб обновляет без изменения размера.
        """
        app = QApplication.instance()
        screen = self.screen() or (app.primaryScreen() if app else None)
        if screen is None:
            return
        avail = screen.availableGeometry()
        state = ui_scale.resolve_ui_scale_state(
            avail.width(),
            avail.height(),
            screen.logicalDotsPerInch(),
            self._ui_scale_delta_percent,
        )
        self._ui_scale_state = state
        old_factor = self._ui_scale_factor
        new_factor = state.scale_factor

        if app is not None:
            styles.apply_styles(app, new_factor)
        ui_scale_runtime.apply_widget_overrides(self, new_factor)
        brand_size = max(12, ui_scale.scale_px(36, new_factor))
        self.brand_icon_label.setPixmap(
            self._brand_icon.pixmap(QSize(brand_size, brand_size))
        )
        self._ui_scale_factor = new_factor

        if allow_window_resize and not self.isMaximized():
            self._ui_scale_resize_window(new_factor, old_factor)

        self._save_ui_scale_settings()
        logger.info(
            "UI-масштаб (%s): авто=%d%% поправка=%d%% итог=%d%%",
            reason,
            state.auto_percent,
            state.delta_percent,
            state.final_percent,
        )

    def _ui_scale_resize_window(self, new_factor: float, old_factor: float) -> None:
        if self._geometry_was_restored and old_factor == 1.0:
            # Сохранённая геометрия уже соответствует прошлому масштабу —
            # не трогаем её при старте, иначе размер умножится на масштаб.
            return
        if old_factor == 1.0:
            base_w, base_h = 860, 760
        else:
            base_w = self.width() / old_factor
            base_h = self.height() / old_factor
        screen = self.screen() or (
            QApplication.instance().primaryScreen() if QApplication.instance() else None
        )
        avail = screen.availableGeometry() if screen else None
        new_w, new_h = ui_scale.calculate_target_window_size(
            round(base_w),
            round(base_h),
            new_factor,
            1.0,
            min_width=self.minimumWidth(),
            min_height=self.minimumHeight(),
            avail_width=avail.width() if avail else None,
            avail_height=avail.height() if avail else None,
        )
        if (new_w, new_h) != (self.width(), self.height()):
            self.resize(new_w, new_h)
            self._save_geometry()

    def install_ui_scale_screen_hooks(self) -> None:
        """Подключать после show() + processEvents(): окно должно иметь windowHandle."""
        app = QApplication.instance()
        if app is None:
            return
        if not self._ui_scale_app_hooks_installed:
            app.primaryScreenChanged.connect(self._on_ui_scale_screen_changed)
            app.screenAdded.connect(self._on_ui_scale_topology_changed)
            app.screenRemoved.connect(self._on_ui_scale_topology_changed)
            self._ui_scale_app_hooks_installed = True
        self._install_ui_scale_window_hook()

    def _install_ui_scale_window_hook(self) -> None:
        if self._ui_scale_window_hook_installed:
            return
        handle = self.windowHandle()
        if handle is None:
            return
        handle.screenChanged.connect(self._on_ui_scale_window_screen_changed)
        self._ui_scale_window_hook_installed = True
        self._ui_scale_watch_screen()

    def _ui_scale_watch_screen(self) -> None:
        app = QApplication.instance()
        screen = self.screen() or (app.primaryScreen() if app else None)
        if screen is self._ui_scale_screen:
            return
        if self._ui_scale_screen is not None:
            for sig in (
                self._ui_scale_screen.logicalDotsPerInchChanged,
                self._ui_scale_screen.geometryChanged,
                self._ui_scale_screen.availableGeometryChanged,
            ):
                try:
                    sig.disconnect(self._on_ui_scale_screen_metrics_changed)
                except (RuntimeError, TypeError):
                    pass
        self._ui_scale_screen = screen
        if screen is not None:
            for sig in (
                screen.logicalDotsPerInchChanged,
                screen.geometryChanged,
                screen.availableGeometryChanged,
            ):
                sig.connect(self._on_ui_scale_screen_metrics_changed)

    def _on_ui_scale_window_screen_changed(self, *_):
        self._ui_scale_watch_screen()
        self.apply_ui_scale(allow_window_resize=False, reason="screen-changed")

    def _on_ui_scale_screen_changed(self, *_):
        """Смена первичного экрана приложения (primaryScreenChanged)."""
        self._ui_scale_watch_screen()
        self.apply_ui_scale(allow_window_resize=False, reason="screen-changed")

    def _on_ui_scale_screen_metrics_changed(self, *_):
        self.apply_ui_scale(allow_window_resize=False, reason="screen-metrics")

    def _on_ui_scale_topology_changed(self, *_):
        self._install_ui_scale_window_hook()
        self._ui_scale_watch_screen()
        self.apply_ui_scale(allow_window_resize=False, reason="screen-topology")

    def get_ui_scale_factor(self) -> float:
        return self._ui_scale_factor


# ---------- helpers ----------


def _find_latest_video_or_note(folder: Path):
    from .folder_parser import find_latest_video

    return find_latest_video(folder)


def _find_cover_or_note(folder: Path, video: Path | None = None):
    from .folder_parser import find_cover

    return find_cover(folder, video)


def _read_yaml_safe(folder: Path):
    from .folder_parser import raw_settings

    return raw_settings(folder)


def _effective_settings(raw: dict) -> dict:
    from .folder_parser import effective_settings

    return effective_settings(raw or {})
