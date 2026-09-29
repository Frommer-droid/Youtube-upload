"""Масштабирование UI: чистые формулы и нормализация настроек (без Qt).

Стандарт: авто-масштаб от экрана/DPI + ручная поправка -50..50%
(шаг 10), сохранение в settings.json (ui_scale_delta_percent).
"""

from __future__ import annotations

from dataclasses import dataclass

# --- базовый экран: 2560x1440 @ 96 DPI = 100% ---
BASE_LOGICAL_DPI = 96.0
REFERENCE_WIDTH = 2560
REFERENCE_HEIGHT = 1440

AUTO_MIN, AUTO_MAX, AUTO_STEP = 70, 200, 10
DELTA_MIN, DELTA_MAX, DELTA_STEP = -50, 50, 10
FINAL_MIN, FINAL_MAX, FINAL_STEP = 35, 300, 5
MIN_MANUAL_SCALE_REFERENCE_PERCENT = 100

SETTINGS_MODE_KEY = "ui_scale_mode"
SETTINGS_DELTA_KEY = "ui_scale_delta_percent"
SETTINGS_FINAL_KEY = "ui_scale_percent"


@dataclass(frozen=True)
class UIScaleState:
    """Полное состояние масштаба для одного экрана."""

    auto_percent: int
    delta_percent: int
    final_percent: int
    scale_factor: float


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def round_to_step(value: float, step: int) -> int:
    return int(round(value / step) * step)


def normalize_ui_scale_mode(mode) -> str:
    return "auto"


def normalize_ui_scale_delta_percent(delta) -> int:
    """Ручная поправка: -50..50, шаг 10; по умолчанию 0."""
    if delta is None:
        return 0
    try:
        value = float(delta)
    except (TypeError, ValueError):
        return 0
    value = round_to_step(value, DELTA_STEP)
    return int(clamp(value, DELTA_MIN, DELTA_MAX))


def normalize_ui_scale_percent(percent) -> int:
    """Итоговый процент: 35..300, шаг 5; по умолчанию 100."""
    if percent is None:
        return 100
    try:
        value = float(percent)
    except (TypeError, ValueError):
        return 100
    value = round_to_step(value, FINAL_STEP)
    return int(clamp(value, FINAL_MIN, FINAL_MAX))


def migrate_ui_scale_settings(data: dict) -> dict:
    """Нормализовать настройки масштаба; миграция legacy ui_scale_percent → delta.

    Если старые настройки содержат только ui_scale_percent, то delta
    выводится как legacy_percent - 100 и нормализуется.
    """
    data = dict(data or {})
    mode = normalize_ui_scale_mode(data.get(SETTINGS_MODE_KEY))
    if SETTINGS_DELTA_KEY in data:
        delta = normalize_ui_scale_delta_percent(data.get(SETTINGS_DELTA_KEY))
    else:
        legacy = data.get(SETTINGS_FINAL_KEY)
        if legacy is None:
            delta = 0
        else:
            try:
                delta = normalize_ui_scale_delta_percent(float(legacy) - 100)
            except (TypeError, ValueError):
                delta = 0
    final = normalize_ui_scale_percent(data.get(SETTINGS_FINAL_KEY, 100))
    return {
        SETTINGS_MODE_KEY: mode,
        SETTINGS_DELTA_KEY: delta,
        SETTINGS_FINAL_KEY: final,
    }


def calculate_auto_percent(available_width: int, available_height: int, logical_dpi: float) -> int:
    """Автоматический процент от рабочей области экрана и DPI.

    normalised = size * dpi / 96; ratio = min(w/2560, h/1440);
    результат 70..200, шаг 10.
    """
    normalized_width = available_width * logical_dpi / BASE_LOGICAL_DPI
    normalized_height = available_height * logical_dpi / BASE_LOGICAL_DPI
    ratio = min(
        normalized_width / REFERENCE_WIDTH,
        normalized_height / REFERENCE_HEIGHT,
    )
    raw_auto = ratio * 100
    auto = round_to_step(raw_auto, AUTO_STEP)
    return int(clamp(auto, AUTO_MIN, AUTO_MAX))


def calculate_final_percent(auto_percent: int, delta_percent: int) -> int:
    """Итоговый процент: авто + поправка от максимума(auto, 100), шаг 5, 35..300."""
    delta_reference = max(auto_percent, MIN_MANUAL_SCALE_REFERENCE_PERCENT)
    raw_final = auto_percent + delta_reference * delta_percent / 100
    final = round_to_step(raw_final, FINAL_STEP)
    return int(clamp(final, FINAL_MIN, FINAL_MAX))


def calculate_scale_factor(final_percent: int) -> float:
    return final_percent / 100.0


def resolve_ui_scale_state(
    available_width: int, available_height: int, logical_dpi: float, delta_percent: int
) -> UIScaleState:
    auto = calculate_auto_percent(available_width, available_height, logical_dpi)
    delta = normalize_ui_scale_delta_percent(delta_percent)
    final = calculate_final_percent(auto, delta)
    return UIScaleState(
        auto_percent=auto,
        delta_percent=delta,
        final_percent=final,
        scale_factor=calculate_scale_factor(final),
    )


def scale_px(value: int, scale_factor: float) -> int:
    """Пиксельный размер с учётом масштаба (округляется к ближайшему)."""
    return round(value * scale_factor)


def scale_point_size(value: float, scale_factor: float, min_pt: float = 1.0) -> float:
    """Размер шрифта в pt с учётом масштаба (не меньше min_pt)."""
    return max(round(value * scale_factor, 1), min_pt)


def calculate_target_window_size(
    width: int,
    height: int,
    new_factor: float,
    old_factor: float,
    min_width: int = 0,
    min_height: int = 0,
    avail_width: int | None = None,
    avail_height: int | None = None,
) -> tuple[int, int]:
    """Пропорциональный размер окна при смене масштаба (с ограничениями)."""
    if old_factor <= 0:
        base_w, base_h = width, height
    else:
        base_w = width / old_factor
        base_h = height / old_factor
    new_w = round(base_w * new_factor)
    new_h = round(base_h * new_factor)
    if min_width:
        new_w = max(new_w, min_width)
    if min_height:
        new_h = max(new_h, min_height)
    if avail_width:
        new_w = min(new_w, avail_width)
    if avail_height:
        new_h = min(new_h, avail_height)
    return new_w, new_h