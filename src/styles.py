"""One Dark QSS theme with scale-aware typography and metrics."""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from . import ui_resources  # noqa: F401 — registers embedded stylesheet icons
from .theme import COLORS, DERIVED_COLORS, THEME_COLORS
from .ui_scale import scale_point_size, scale_px

_BASE_FONT_PROPERTY = "_upy_base_font_point_size"


def build_global_stylesheet(
    colors: dict | None = None,
    scale_factor: float = 1.0,
    base_font_point_size: float = 10.0,
) -> str:
    """Build the complete One Dark stylesheet at ``scale_factor``."""
    c = colors or COLORS
    d = DERIVED_COLORS
    t = THEME_COLORS

    def px(value: int) -> str:
        return f"{scale_px(value, scale_factor)}px"

    def pt(value: float) -> str:
        return f"{scale_point_size(value, scale_factor):.1f}pt"

    return f"""
QWidget {{
    background-color: {c["bg_window"]};
    color: {c["text"]};
    font-family: "Tahoma", "Segoe UI", "Aptos";
    font-size: {pt(base_font_point_size)};
}}
QWidget:disabled {{ color: {c["text_muted"]}; }}
QMainWindow, QDialog, QMessageBox {{ background-color: {c["bg_window"]}; }}
QScrollArea {{ border: 0; background: transparent; }}
QWidget#tabPage {{ background: transparent; }}
QLabel {{ background: transparent; }}
QLabel#windowTitle {{ color: {c["text_bright"]}; font-size: {pt(17)}; font-weight: 650; }}
QLabel#windowSubtitle {{ color: {c["text_muted"]}; }}
QLabel#sectionHeader {{ color: {c["blue"]}; font-size: {pt(10.5)}; font-weight: 650; }}
QLabel#muted, QLabel#counter, QLabel#status {{ color: {c["text_muted"]}; }}
QLabel#fileValue {{ color: {c["text_bright"]}; }}
QLabel#previewTitle {{ color: {c["turquoise"]}; font-weight: 600; }}
QLabel#accountStatus {{ color: {c["text_muted"]}; font-weight: 600; }}
QLabel#accountStatus[statusKind="ok"] {{ color: {c["green"]}; }}
QLabel#accountStatus[statusKind="warning"] {{ color: {c["yellow"]}; }}
QLabel#accountStatus[statusKind="error"] {{ color: {c["red"]}; }}
QLabel#badge, QLabel#badgeWarn, QLabel#badgeError {{
    color: {c["bg_deep"]}; font-weight: 700; padding: {px(2)} {px(9)}; border-radius: {px(4)};
}}
QLabel#badge {{ background-color: {c["green"]}; }}
QLabel#badgeWarn {{ background-color: {c["orange"]}; }}
QLabel#badgeError {{ background-color: {c["red"]}; }}
QFrame#card {{ background-color: {c["bg_card"]}; border: 1px solid {c["border"]}; border-radius: {px(8)}; }}
QFrame#card:hover {{ border-color: {t["primary_hover"]}; }}

QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background-color: {c["bg_input"]}; color: {c["text_bright"]};
    border: 1px solid {c["border"]}; border-radius: {px(6)};
    padding: {px(5)} {px(8)}; selection-background-color: {c["selection"]};
    selection-color: {c["text_bright"]};
}}
QLineEdit:hover, QPlainTextEdit:hover, QTextEdit:hover, QComboBox:hover {{ border-color: {d["hover_border"]}; }}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus {{ border-color: {c["border_focus"]}; }}
QLineEdit:read-only, QPlainTextEdit:read-only, QTextEdit:read-only {{ background-color: {c["bg_deep"]}; color: {c["text"]}; }}
QLineEdit:disabled, QPlainTextEdit:disabled, QTextEdit:disabled, QComboBox:disabled {{ background-color: {t["disabled_background"]}; color: {t["disabled_text"]}; border-color: {t["disabled_border"]}; }}
QLineEdit, QPlainTextEdit, QTextEdit {{ placeholder-text-color: {c["text_muted"]}; }}
QComboBox {{ padding-right: {px(28)}; }}
QComboBox::drop-down {{ width: {px(25)}; border: 0; border-left: 1px solid {c["border"]}; }}
QComboBox::down-arrow {{ image: url(:/ui/chevron-down.svg); width: {px(16)}; height: {px(16)}; }}
QComboBox::down-arrow:hover, QComboBox::down-arrow:on {{ image: url(:/ui/chevron-down-active.svg); }}
QComboBox::down-arrow:disabled {{ image: url(:/ui/chevron-down-disabled.svg); }}
QPushButton::menu-indicator, QToolButton::menu-indicator, QToolButton::down-arrow {{ image: url(:/ui/chevron-down.svg); width: {px(16)}; height: {px(16)}; }}
QPushButton::menu-indicator:hover, QToolButton::menu-indicator:hover, QToolButton::down-arrow:hover {{ image: url(:/ui/chevron-down-active.svg); }}
QPushButton::menu-indicator:disabled, QToolButton::menu-indicator:disabled, QToolButton::down-arrow:disabled {{ image: url(:/ui/chevron-down-disabled.svg); }}
QComboBox QAbstractItemView {{
    background-color: {c["bg_deep"]}; color: {c["text"]}; border: 1px solid {c["border"]};
    outline: 0; selection-background-color: {c["selection"]}; selection-color: {c["text_bright"]}; padding: {px(4)};
}}

QPushButton {{
    background-color: {c["bg_button"]}; color: {c["text_bright"]};
    border: 1px solid {c["border"]}; border-radius: {px(6)};
    padding: {px(6)} {px(12)}; min-height: {px(18)};
}}
QPushButton:hover {{ background-color: {c["bg_hover"]}; border-color: {d["hover_border"]}; }}
QPushButton:pressed {{ background-color: {c["bg_pressed"]}; border-color: {c["blue"]}; }}
QPushButton:checked {{ background-color: {t["selection"]}; border-color: {t["accent"]}; }}
QPushButton:focus {{ border-color: {c["blue"]}; }}
QPushButton:disabled {{ background-color: {t["disabled_background"]}; color: {t["disabled_text"]}; border-color: {t["disabled_border"]}; }}
QPushButton#primary {{
    background-color: {c["blue"]}; color: {c["bg_deep"]}; border-color: {c["blue"]};
    font-weight: 700; padding: {px(8)} {px(16)}; font-size: {pt(10.5)};
}}
QPushButton#primary:hover {{ background-color: {t["accent_hover"]}; border-color: {t["accent_hover"]}; }}
QPushButton#primary:pressed {{ background-color: {t["accent_pressed"]}; }}
QPushButton#primary:disabled {{ background-color: {t["disabled_background"]}; color: {t["disabled_text"]}; border-color: {t["disabled_border"]}; }}
QPushButton#danger {{ color: {c["red"]}; border-color: {d["danger_border"]}; }}
QPushButton#danger:hover {{ background-color: {d["danger_hover"]}; border-color: {c["red"]}; }}
QPushButton#warning {{ color: {c["yellow"]}; }}

QTabWidget::pane {{ background-color: {c["bg_deep"]}; border: 1px solid {c["border"]}; border-radius: {px(7)}; top: -1px; }}
QTabBar {{ background: transparent; }}
QTabBar::tab {{
    background-color: transparent; color: {c["text_muted"]}; border: 0;
    border-bottom: {px(2)} solid transparent; padding: {px(8)} {px(12)}; margin-right: {px(2)};
}}
QTabBar::tab:hover {{ color: {c["text_bright"]}; background-color: {d["tab_hover"]}; }}
QTabBar::tab:selected {{ color: {c["text_bright"]}; border-bottom-color: {c["blue"]}; }}
QTabBar::tab:disabled {{ color: {t["disabled_text"]}; }}

QCheckBox {{ spacing: {px(7)}; background: transparent; }}
QCheckBox::indicator {{ width: {px(16)}; height: {px(16)}; background-color: {c["bg_input"]}; border: 1px solid {d["hover_border"]}; border-radius: {px(4)}; }}
QCheckBox::indicator:hover {{ border-color: {c["blue"]}; }}
QCheckBox::indicator:checked {{ background-color: {c["blue"]}; border-color: {c["blue"]}; }}
QCheckBox::indicator:disabled {{ background-color: {t["disabled_background"]}; border-color: {t["disabled_border"]}; }}

QProgressBar {{ background-color: {c["bg_deep"]}; color: {c["text_bright"]}; border: 1px solid {c["border"]}; border-radius: {px(5)}; text-align: center; height: {px(18)}; }}
QProgressBar::chunk {{ background-color: {c["blue"]}; border-radius: {px(4)}; }}
QScrollBar:vertical {{ background: {c["bg_deep"]}; width: {px(12)}; margin: 0; }}
QScrollBar::handle:vertical {{ background: {t["scrollbar"]}; min-height: {px(28)}; border-radius: {px(6)}; margin: {px(2)}; }}
QScrollBar::handle:vertical:hover {{ background: {t["muted"]}; }}
QScrollBar::handle:vertical:pressed {{ background: {t["accent_pressed"]}; }}
QScrollBar:horizontal {{ background: {c["bg_deep"]}; height: {px(12)}; margin: 0; }}
QScrollBar::handle:horizontal {{ background: {t["scrollbar"]}; min-width: {px(28)}; border-radius: {px(6)}; margin: {px(2)}; }}
QScrollBar::handle:horizontal:hover {{ background: {t["muted"]}; }}
QScrollBar::handle:horizontal:pressed {{ background: {t["accent_pressed"]}; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ background: none; border: none; }}
QMenu {{ background-color: {c["bg_deep"]}; color: {c["text"]}; border: 1px solid {c["border"]}; padding: {px(4)}; }}
QMenu::item {{ padding: {px(6)} {px(24)} {px(6)} {px(10)}; border-radius: {px(4)}; }}
QMenu::item:selected {{ background-color: {c["selection"]}; color: {c["text_bright"]}; }}
QToolTip {{ background-color: {c["bg_deep"]}; color: {c["text_bright"]}; border: 1px solid {c["blue"]}; padding: {px(5)}; border-radius: {px(4)}; }}
"""


def _one_dark_palette() -> QPalette:
    c = COLORS
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(c["bg_window"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(c["text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(c["bg_input"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(c["bg_card"]))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(c["bg_deep"]))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(c["text_bright"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(c["text"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(c["bg_button"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(c["text_bright"]))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(c["red"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(c["selection"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(c["text_bright"]))
    palette.setColor(QPalette.ColorRole.Link, QColor(c["blue"]))
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(c["text_muted"])
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.ButtonText,
        QColor(c["text_muted"]),
    )
    return palette


def apply_styles(app: QApplication, scale_factor: float = 1.0) -> None:
    """Apply palette, stable base-font scaling, and global One Dark QSS."""
    base_pt = getattr(app, _BASE_FONT_PROPERTY, None)
    if base_pt is None:
        base_pt = app.font().pointSizeF()
        if base_pt <= 0:
            base_pt = 9.0
        setattr(app, _BASE_FONT_PROPERTY, base_pt)
    font = app.font()
    font.setPointSizeF(scale_point_size(float(base_pt), scale_factor))
    app.setFont(font)
    app.setPalette(_one_dark_palette())
    app.setStyleSheet(build_global_stylesheet(scale_factor=scale_factor))
