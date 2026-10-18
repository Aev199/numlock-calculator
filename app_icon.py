"""Shared NumCalc icon artwork for the tray and Windows executable."""

from __future__ import annotations

from pathlib import Path
from typing import Any


ICON_BACKGROUND = (82, 109, 255, 255)
ICON_FOREGROUND = (248, 250, 255, 255)
WINDOWS_ICON_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


# The N is one closed outline on a 64-unit grid. Drawing it as a single polygon
# avoids the notches that appear where separate thick lines meet.
_GLYPH = (
    (17, 47), (17, 17), (25, 17), (39, 35.5), (39, 17),
    (47, 17), (47, 47), (39, 47), (25, 28.5), (25, 47),
)
_SUPERSAMPLE = 4


def create_icon_image(size: int = 64) -> Any:
    """Draw the rounded blue NumCalc tile with the white N glyph."""

    from PIL import Image, ImageDraw

    size = max(16, int(size))
    canvas = size * _SUPERSAMPLE
    scale = canvas / 64.0
    image = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (3 * scale, 3 * scale, 61 * scale - 1, 61 * scale - 1),
        radius=14 * scale,
        fill=ICON_BACKGROUND,
    )
    draw.polygon([(x * scale, y * scale) for x, y in _GLYPH], fill=ICON_FOREGROUND)
    return image.resize((size, size), Image.Resampling.LANCZOS)


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
