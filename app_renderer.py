"""Single-source renderer for the keyboard-first NumLock Calc UI.

The desktop shell, calculation engine and persistence stay in Python. This
module owns the complete frontend document and performs only deterministic
placeholder substitution for the bundled CSS and JavaScript assets.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


TEMPLATE_NAME = "app-shell.html"
STYLE_NAME = "app-shell.css"
SCRIPT_NAME = "app-shell.js"
CSS_PLACEHOLDER = "/*__NUMLOCK_CALC_CSS__*/"
JS_PLACEHOLDER = "/*__NUMLOCK_CALC_JS__*/"
DEFAULT_WIDTH = 480
DEFAULT_HEIGHT = 540
MIN_SIZE = (390, 400)


def install(app: Any) -> None:
    """Install the consolidated renderer as the sole HTML builder."""

    if getattr(app, "_consolidated_renderer_installed", False):
        return
    app._consolidated_renderer_installed = True
    original_create_window = app.webview.create_window

    def build_html() -> str:
        renderer = Path(app.RENDERER_DIR)
        template = (renderer / TEMPLATE_NAME).read_text(encoding="utf-8")
        css = (renderer / STYLE_NAME).read_text(encoding="utf-8")
        javascript = (renderer / SCRIPT_NAME).read_text(encoding="utf-8")

        if CSS_PLACEHOLDER not in template or JS_PLACEHOLDER not in template:
            raise RuntimeError("Consolidated renderer template is missing asset placeholders")

        return (
            template.replace(CSS_PLACEHOLDER, css, 1)
            .replace(JS_PLACEHOLDER, javascript, 1)
        )

    def create_window(*args: Any, **kwargs: Any) -> Any:
        kwargs["width"] = DEFAULT_WIDTH
        kwargs["height"] = DEFAULT_HEIGHT
        kwargs["min_size"] = MIN_SIZE
        return original_create_window(*args, **kwargs)

    app.build_html = build_html
    app.webview.create_window = create_window
