"""Scalable in-memory SVG icons matched to the One Dark palette."""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from .theme import COLORS

_PATHS = {
    "upload": '<path d="M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5"/><path d="M5 14v5h14v-5"/>',
    "folder": '<path d="M3 6h6l2 2h10v11H3z"/>',
    "refresh": '<path d="M20 6v5h-5"/><path d="M18.2 8A7 7 0 1 0 19 15"/>',
    "video": '<rect x="3" y="5" width="14" height="14" rx="2"/><path d="M17 10l4-2v8l-4-2z"/>',
    "image": '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="8" cy="9" r="1.5"/><path d="M4 17l5-5 3 3 2-2 6 6"/>',
    "playlist": '<path d="M4 6h10M4 11h10M4 16h7"/><path d="M18 10v8m-4-4h8"/>',
    "close": '<path d="M5 5l14 14M19 5L5 19"/>',
    "duplicate": '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/><path d="M14 11v6m-3-3h6"/>',
    "trash": '<path d="M4 7h16M9 7V4h6v3M7 7l1 13h8l1-13M10 11v5m4-5v5"/>',
    "key": '<circle cx="8" cy="12" r="4"/><path d="M12 12h9m-3 0v3m-3-3v2"/>',
    "external": '<path d="M14 4h6v6M20 4l-9 9"/><path d="M18 13v6H5V6h6"/>',
    "copy": '<rect x="8" y="8" width="11" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h2"/>',
    "studio": '<rect x="3" y="5" width="18" height="14" rx="3"/><path d="M10 9l5 3-5 3z"/>',
    "again": '<path d="M4 4v6h6"/><path d="M5.5 9A8 8 0 1 1 5 16"/>',
    "reset": '<path d="M4 4v6h6"/><path d="M5.5 9A8 8 0 1 1 6 17"/>',
    "title": '<path d="M5 5h14M12 5v14M8 19h8"/>',
    "description": '<path d="M5 5h14M5 9h14M5 13h10M5 17h12"/>',
    "poem": '<path d="M19 3c-7 1-11 5-12 12"/><path d="M7 15c3-1 6-1 9-5M7 15l-2 6"/>',
    "settings": '<path d="M4 6h7m4 0h5M11 3v6M4 12h2m4 0h10M6 9v6M4 18h10m4 0h2M14 15v6"/>',
    "scale": '<path d="M8 3H3v5M16 3h5v5M8 21H3v-5M16 21h5v-5"/><path d="M3 8l6-6m12 6l-6-6M3 16l6 6m12-6l-6 6"/>',
}


def _svg(name: str, color: str) -> bytes:
    if name == "youtube":
        body = (
            f'<rect x="2.5" y="6" width="19" height="12" rx="4" fill="{COLORS["red"]}" stroke="none"/>'
            f'<path d="M10 9l6 3-6 3z" fill="{COLORS["text_bright"]}" stroke="none"/>'
        )
    else:
        body = _PATHS[name]
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        f'fill="none" stroke="{color}" stroke-width="1.8" '
        f'stroke-linecap="round" stroke-linejoin="round">{body}</svg>'
    ).encode()


@lru_cache(maxsize=96)
def themed_icon(name: str, color: str | None = None) -> QIcon:
    """Return a sharp multi-size QIcon rendered from an embedded SVG glyph."""
    tone = color or COLORS["text"]
    renderer = QSvgRenderer(QByteArray(_svg(name, tone)))
    icon = QIcon()
    for size in (16, 20, 24, 32, 48, 64, 128):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        renderer.render(painter)
        painter.end()
        icon.addPixmap(pixmap)
    return icon


def app_mark_icon() -> QIcon:
    """One Dark YouTube mark used inside the window when logo.ico is unavailable."""
    return themed_icon("youtube")
