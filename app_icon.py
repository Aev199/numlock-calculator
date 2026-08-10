"""Shared NumCalc icon artwork for the tray and Windows executable."""

from __future__ import annotations

from pathlib import Path
from typing import Any


ICON_BACKGROUND = (82, 109, 255, 255)
ICON_FOREGROUND = (248, 250, 255, 255)
WINDOWS_ICON_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def create_icon_image(size: int = 64) -> Any:
    """Draw the rounded blue NumCalc tile with the white N glyph."""

    from PIL import Image, ImageDraw

    size = max(16, int(size))
    scale = size / 64.0
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    def point(value: float) -> int:
        return round(value * scale)

    draw.rounded_rectangle(
        (point(3), point(3), point(61), point(61)),
        radius=point(15),
        fill=ICON_BACKGROUND,
    )
    width = max(2, point(7))
    draw.line((point(18), point(46), point(18), point(18)), fill=ICON_FOREGROUND, width=width)
    draw.line((point(18), point(18), point(46), point(46)), fill=ICON_FOREGROUND, width=width)
    draw.line((point(46), point(46), point(46), point(18)), fill=ICON_FOREGROUND, width=width)
    return image


def write_windows_icon(path: str | Path) -> Path:
    """Create a multi-resolution ICO used by PyInstaller and Windows shell."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    create_icon_image(256).save(
        target,
        format="ICO",
        sizes=[(size, size) for size in WINDOWS_ICON_SIZES],
    )
    return target
