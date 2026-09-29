"""Runtime-применение масштаба к дереву виджетов (margins, sizes, spacing).

Базовые (немасштабированные) значения запоминаются один раз через setattr —
повторное применение не умножает уже масштабированные размеры.
"""

from __future__ import annotations

from PySide6.QtWidgets import QLayout, QWidget

from .ui_scale import scale_px

_BASE_MIN_W = "_upy_base_min_w"
_BASE_MIN_H = "_upy_base_min_h"
_BASE_MAX_W = "_upy_base_max_w"
_BASE_MAX_H = "_upy_base_max_h"
_BASE_FIXED_W = "_upy_base_fixed_w"
_BASE_FIXED_H = "_upy_base_fixed_h"
_BASE_MARGINS = "_upy_base_margins"
_BASE_SPACING = "_upy_base_spacing"
_BASE_ICON = "_upy_base_icon_size"

_DEFAULT_MAX = 16777215  # QWIDGETSIZE_MAX


def apply_widget_overrides(root: QWidget, scale_factor: float) -> None:
    """Масштабировать margins/spacing/min/max/fixed sizes всего дерева."""
    _walk(root, scale_factor)


def _walk(widget: QWidget, scale_factor: float) -> None:
    layout = widget.layout()
    if layout is not None:
        _process_layout(layout, scale_factor)
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item is None:
                continue
            sub_layout = item.layout()
            if sub_layout is not None:
                _process_layout(sub_layout, scale_factor)
            child = item.widget()
            if child is not None and child.parent() is widget:
                _walk(child, scale_factor)
    # Виджеты, не входящие в layout() (например, страницы QTabWidget).
    for child in widget.findChildren(QWidget):
        if child.parent() is widget and child is not widget:
            _walk(child, scale_factor)
    _scale_size_hints(widget, scale_factor)
    _scale_icon_size(widget, scale_factor)


def _process_layout(layout: QLayout, scale_factor: float) -> None:
    margins = getattr(layout, _BASE_MARGINS, None)
    if margins is None:
        m = layout.contentsMargins()
        margins = (m.left(), m.top(), m.right(), m.bottom())
        setattr(layout, _BASE_MARGINS, margins)
    layout.setContentsMargins(
        scale_px(margins[0], scale_factor),
        scale_px(margins[1], scale_factor),
        scale_px(margins[2], scale_factor),
        scale_px(margins[3], scale_factor),
    )
    spacing = getattr(layout, _BASE_SPACING, None)
    if spacing is None:
        spacing = layout.spacing()
        setattr(layout, _BASE_SPACING, spacing)
    if spacing is not None and spacing >= 0:
        layout.setSpacing(scale_px(spacing, scale_factor))


def _scale_size_hints(widget: QWidget, scale_factor: float) -> None:
    base = getattr(widget, _BASE_MIN_W, None)
    if base is None:
        base = widget.minimumWidth()
        setattr(widget, _BASE_MIN_W, base)
    if base > 0:
        widget.setMinimumWidth(scale_px(base, scale_factor))

    base = getattr(widget, _BASE_MIN_H, None)
    if base is None:
        base = widget.minimumHeight()
        setattr(widget, _BASE_MIN_H, base)
    if base > 0:
        widget.setMinimumHeight(scale_px(base, scale_factor))

    base = getattr(widget, _BASE_MAX_W, None)
    if base is None:
        base = widget.maximumWidth()
        setattr(widget, _BASE_MAX_W, base)
    if 0 < base < _DEFAULT_MAX:
        widget.setMaximumWidth(scale_px(base, scale_factor))

    base = getattr(widget, _BASE_MAX_H, None)
    if base is None:
        base = widget.maximumHeight()
        setattr(widget, _BASE_MAX_H, base)
    if 0 < base < _DEFAULT_MAX:
        widget.setMaximumHeight(scale_px(base, scale_factor))

    base = getattr(widget, _BASE_FIXED_W, None)
    if base is None:
        mn = widget.minimumWidth()
        mx = widget.maximumWidth()
        base = mn if mn > 0 and mn == mx else 0
        setattr(widget, _BASE_FIXED_W, base)
    if base > 0:
        widget.setMinimumWidth(scale_px(base, scale_factor))
        widget.setMaximumWidth(scale_px(base, scale_factor))

    base = getattr(widget, _BASE_FIXED_H, None)
    if base is None:
        mn = widget.minimumHeight()
        mx = widget.maximumHeight()
        base = mn if mn > 0 and mn == mx else 0
        setattr(widget, _BASE_FIXED_H, base)
    if base > 0:
        widget.setMinimumHeight(scale_px(base, scale_factor))
        widget.setMaximumHeight(scale_px(base, scale_factor))


def _scale_icon_size(widget: QWidget, scale_factor: float) -> None:
    if not getattr(widget, "setIconSize", None) or not getattr(widget, "iconSize", None):
        return
    try:
        size = widget.iconSize()
    except RuntimeError:
        return
    if size is None or size.width() <= 0 or size.height() <= 0:
        return
    base = getattr(widget, _BASE_ICON, None)
    if base is None:
        base = (size.width(), size.height())
        setattr(widget, _BASE_ICON, base)
    widget.setIconSize(
        size.__class__(scale_px(base[0], scale_factor), scale_px(base[1], scale_factor))
    )
