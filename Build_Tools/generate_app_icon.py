"""Regenerate root logo.ico from assets/app_icon.svg using project dependencies."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parent.parent
SVG_PATH = ROOT / "assets" / "app_icon.svg"
ICO_PATH = ROOT / "logo.ico"
SIZES = (16, 24, 32, 48, 64, 128, 256)


def render_svg(size: int) -> Image.Image:
    renderer = QSvgRenderer(QByteArray(SVG_PATH.read_bytes()))
    if not renderer.isValid():
        raise RuntimeError(f"Invalid SVG: {SVG_PATH}")
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()

    encoded = QByteArray()
    buffer = QBuffer(encoded)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    buffer.close()
    return Image.open(io.BytesIO(bytes(encoded))).convert("RGBA")


def main() -> None:
    images = [render_svg(size) for size in SIZES]
    images[-1].save(
        ICO_PATH,
        format="ICO",
        append_images=images[:-1],
        sizes=[(size, size) for size in SIZES],
    )
    print(f"Generated {ICO_PATH} ({ICO_PATH.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
