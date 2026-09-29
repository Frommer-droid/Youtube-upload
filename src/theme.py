"""One Dark palette and named shades used by the application stylesheet."""

from __future__ import annotations

THEME_COLORS = {
    "background": "#282C34",
    "surface": "#21252B",
    "surface_alt": "#2C313C",
    "surface_hover": "#353B45",
    "surface_pressed": "#181A1F",
    "alternate": "#262A32",
    "selection": "#3E4451",
    "primary": "#3E4451",
    "primary_hover": "#4B5263",
    "accent": "#61AFEF",
    "accent_hover": "#7BC0F6",
    "accent_pressed": "#4D95C7",
    "success": "#98C379",
    "text": "#ABB2BF",
    "text_strong": "#E6E6E6",
    "muted": "#9DA5B4",
    "on_accent": "#21252B",
    "border": "#3E4451",
    "focus": "#61AFEF",
    "danger": "#E06C75",
    "danger_text": "#E8838B",
    "danger_surface": "#352A31",
    "warning": "#D19A66",
    "disabled_text": "#5C6370",
    "disabled_background": "#21252B",
    "disabled_border": "#2C313C",
    "scrollbar": "#4B5263",
}

DERIVED_COLORS = {
    "input": "#1E2227",
    "hover_border": "#596273",
    "tab_hover": "#2D323C",
    "danger_border": "#68444B",
    "danger_hover": "#49343A",
    "cyan": "#56B6C2",
    "turquoise": "#56FFFC",
    "yellow": "#E5C07B",
    "white": "#FFFFFF",
}

# Existing UI modules use semantic names. The palette above is the single
# source of One Dark base values.
COLORS = {
    "bg_window": THEME_COLORS["background"],
    "bg_deep": THEME_COLORS["surface"],
    "bg_card": THEME_COLORS["surface_alt"],
    "bg_input": DERIVED_COLORS["input"],
    "bg_button": THEME_COLORS["surface_hover"],
    "bg_hover": THEME_COLORS["primary_hover"],
    "bg_pressed": THEME_COLORS["surface_pressed"],
    "border": THEME_COLORS["border"],
    "border_focus": THEME_COLORS["focus"],
    "text": THEME_COLORS["text"],
    "text_bright": THEME_COLORS["text_strong"],
    "text_muted": THEME_COLORS["muted"],
    "selection": THEME_COLORS["selection"],
    "blue": THEME_COLORS["accent"],
    "cyan": DERIVED_COLORS["cyan"],
    "green": THEME_COLORS["success"],
    "orange": THEME_COLORS["warning"],
    "red": THEME_COLORS["danger"],
    "turquoise": DERIVED_COLORS["turquoise"],
    "yellow": DERIVED_COLORS["yellow"],
    "white": DERIVED_COLORS["white"],
}

MUTED = COLORS["text_muted"]
SUCCESS = COLORS["green"]
WARNING = COLORS["orange"]
ERROR = COLORS["red"]
