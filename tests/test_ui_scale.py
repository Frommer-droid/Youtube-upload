"""Тесты масштабирования UI: формулы, нормализация, миграция и QSS."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from src import ui_scale
from src.styles import apply_styles, build_global_stylesheet
from src.theme import COLORS


def test_normalize_delta():
    assert ui_scale.normalize_ui_scale_delta_percent(0) == 0
    assert ui_scale.normalize_ui_scale_delta_percent(50) == 50
    assert ui_scale.normalize_ui_scale_delta_percent(-50) == -50
    assert ui_scale.normalize_ui_scale_delta_percent(54) == 50
    assert ui_scale.normalize_ui_scale_delta_percent(1000) == 50
    assert ui_scale.normalize_ui_scale_delta_percent(-1000) == -50
    assert ui_scale.normalize_ui_scale_delta_percent(None) == 0
    assert ui_scale.normalize_ui_scale_delta_percent("abc") == 0


def test_normalize_percent():
    assert ui_scale.normalize_ui_scale_percent(100) == 100
    assert ui_scale.normalize_ui_scale_percent(98) == 100
    assert ui_scale.normalize_ui_scale_percent(47) == 45
    assert ui_scale.normalize_ui_scale_percent(1000) == 300
    assert ui_scale.normalize_ui_scale_percent(10) == 35
    assert ui_scale.normalize_ui_scale_percent(None) == 100


def test_migrate_legacy_percent():
    migrated = ui_scale.migrate_ui_scale_settings({"ui_scale_percent": 120})
    assert migrated["ui_scale_delta_percent"] == 20
    assert migrated["ui_scale_mode"] == "auto"


def test_migrate_keeps_delta():
    migrated = ui_scale.migrate_ui_scale_settings(
        {"ui_scale_delta_percent": 30, "ui_scale_percent": 130}
    )
    assert migrated["ui_scale_delta_percent"] == 30
    assert migrated["ui_scale_percent"] == 130


def test_migrate_empty():
    migrated = ui_scale.migrate_ui_scale_settings({})
    assert migrated == {
        "ui_scale_mode": "auto",
        "ui_scale_delta_percent": 0,
        "ui_scale_percent": 100,
    }


def test_auto_percent_reference_screen():
    assert ui_scale.calculate_auto_percent(2560, 1440, 96.0) == 100


def test_auto_percent_hd():
    # 75.0 попадает ровно на половину шага 10 → банковское округление даёт 80
    assert ui_scale.calculate_auto_percent(1920, 1080, 96.0) == 80


def test_auto_percent_high_dpi_small_screen():
    # 1280x720 @ 120 DPI → нормализовано 1600x900 → ~62.5% → округлено и поднято до 70
    assert ui_scale.calculate_auto_percent(1280, 720, 120.0) == 70


def test_auto_percent_clamps():
    assert ui_scale.calculate_auto_percent(800, 600, 96.0) == 70
    assert ui_scale.calculate_auto_percent(10000, 10000, 96.0) == 200


def test_final_percent_plain():
    assert ui_scale.calculate_final_percent(100, 0) == 100
    assert ui_scale.calculate_final_percent(100, 50) == 150
    assert ui_scale.calculate_final_percent(75, -30) == 45


def test_final_percent_delta_reference():
    # поправка считается от максимума(auto, 100): при auto=70 и delta=50 → 70+50=120
    assert ui_scale.calculate_final_percent(70, 50) == 120


def test_final_percent_clamps():
    assert ui_scale.calculate_final_percent(200, 50) == 300
    assert ui_scale.calculate_final_percent(70, -50) == 35


def test_scale_factor():
    assert ui_scale.calculate_scale_factor(150) == 1.5
    assert ui_scale.calculate_scale_factor(100) == 1.0


def test_scale_px():
    assert ui_scale.scale_px(160, 1.5) == 240
    assert ui_scale.scale_px(140, 0.7) == 98
    assert ui_scale.scale_px(10, 1.0) == 10


def test_scale_point_size():
    assert ui_scale.scale_point_size(10.0, 1.5) == 15.0
    assert ui_scale.scale_point_size(10.0, 0.5, min_pt=4.0) == 5.0
    assert ui_scale.scale_point_size(10.0, 0.1, min_pt=2.0) == 2.0


def test_resolve_state():
    state = ui_scale.resolve_ui_scale_state(2560, 1440, 96.0, 50)
    assert state.auto_percent == 100
    assert state.delta_percent == 50
    assert state.final_percent == 150
    assert state.scale_factor == 1.5


def test_target_window_size():
    w, h = ui_scale.calculate_target_window_size(
        860,
        760,
        1.5,
        1.0,
        min_width=780,
        min_height=680,
        avail_width=2560,
        avail_height=1440,
    )
    assert (w, h) == (1290, 1140)


def test_target_window_size_inverse():
    w, h = ui_scale.calculate_target_window_size(
        1290,
        1140,
        1.0,
        1.5,
        min_width=780,
        min_height=680,
        avail_width=2560,
        avail_height=1440,
    )
    assert (w, h) == (860, 760)


def test_target_window_size_clamps_to_available():
    w, h = ui_scale.calculate_target_window_size(
        860,
        760,
        2.0,
        1.0,
        min_width=780,
        min_height=680,
        avail_width=1200,
        avail_height=900,
    )
    assert w <= 1200 and h <= 900
    assert w >= 780 and h >= 680


def test_stylesheet_scales_fonts_and_padding():
    css_100 = build_global_stylesheet(scale_factor=1.0)
    css_150 = build_global_stylesheet(scale_factor=1.5)
    assert "font-size: 10.0pt" in css_100
    assert "font-size: 15.0pt" in css_150
    assert "padding: 6px 12px" in css_100
    assert "padding: 9px 18px" in css_150
    assert "padding: 5px 8px" in css_100
    assert "padding: 8px 12px" in css_150
    assert "height: 18px" in css_100
    assert "height: 27px" in css_150
    assert "font-size: 10.5pt" in css_100
    assert "font-size: 15.8pt" in css_150
    assert css_150 != css_100


def test_stylesheet_title_scales():
    css_150 = build_global_stylesheet(scale_factor=1.5)
    assert "font-size: 25.5pt" in css_150  # 17pt заголовка при 150%


def test_stylesheet_uses_one_dark_pro_palette():
    css = build_global_stylesheet()
    for token in ("bg_window", "bg_deep", "text", "blue", "green", "red"):
        assert COLORS[token] in css


def test_application_font_scale_returns_to_original_size():
    app = QApplication.instance() or QApplication([])
    apply_styles(app, 1.0)
    base = app.font().pointSizeF()
    apply_styles(app, 1.5)
    assert app.font().pointSizeF() == round(base * 1.5, 1)
    apply_styles(app, 1.0)
    assert app.font().pointSizeF() == base
