"""Single-source renderer for the keyboard-first NumCalc UI.

The desktop shell, calculation engine and persistence stay in Python. This
module owns the complete frontend document and performs only deterministic
placeholder substitution for the bundled CSS and JavaScript sources.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


TEMPLATE_NAME = "app-shell.html"
STYLE_PARTS = (
    "app-shell.css",
    "app-shell-ux.css",
    "app-shell-product.css",
    "app-shell-about.css",
    "app-shell-hotkey.css",
    "app-shell-formulas.css",
)
SCRIPT_PARTS = (
    *(f"app-shell-v2.part{index:02d}.js" for index in range(6)),
    "app-shell-v2.ux.js",
    "app-shell-v2.multiply.js",
    "app-shell-v2.copy.js",
    # part06 starts the event binder and part07 continues it before opening
    # initialize(); keep feature layers before that boundary so their drawer
    # functions remain in the consolidated controller scope.
    "app-shell-v2.variables.js",
    "app-shell-v2.formulas.js",
    "app-shell-v2.hotkey.js",
    "app-shell-v2.about.js",
    "app-shell-v2.part06.js",
    "app-shell-v2.part07.js",
    "app-shell-v2.part08.js",
)
CSS_PLACEHOLDER = "/*__NUMLOCK_CALC_CSS__*/"
JS_PLACEHOLDER = "/*__NUMLOCK_CALC_JS__*/"
DEFAULT_WIDTH = 384
DEFAULT_HEIGHT = 432
MIN_SIZE = (360, 380)


def render_document(renderer_dir: Path) -> str:
    """Assemble the one supported frontend document from checked-in parts."""

    renderer = Path(renderer_dir)
    template = (renderer / TEMPLATE_NAME).read_text(encoding="utf-8")
    css = "\n".join(
        (renderer / name).read_text(encoding="utf-8")
        for name in STYLE_PARTS
    )
    javascript = "\n".join(
        (renderer / name).read_text(encoding="utf-8")
        for name in SCRIPT_PARTS
    )

    if CSS_PLACEHOLDER not in template or JS_PLACEHOLDER not in template:
        raise RuntimeError(
            "Consolidated renderer template is missing asset placeholders"
        )
    if javascript.count("nlcalc-consolidated-v2") != 1:
        raise RuntimeError("Consolidated renderer controller is incomplete")
    if "TRIG_ORDER" not in javascript or "bracket-color-overlay" not in css:
        raise RuntimeError("Consolidated renderer keyboard UX is incomplete")
    if "pywebview-no-drag" not in css or "NumCalc" not in template:
        raise RuntimeError("NumCalc product shell is incomplete")
    if "app-shell-v2.multiply.js" not in SCRIPT_PARTS:
        raise RuntimeError("Consolidated renderer multiplication display is incomplete")
    if "app-shell-v2.copy.js" not in SCRIPT_PARTS:
        raise RuntimeError("Consolidated renderer clipboard behavior is incomplete")
    if "app-shell-v2.variables.js" not in SCRIPT_PARTS:
        raise RuntimeError("Consolidated renderer variable layer is incomplete")
    if "app-shell-v2.formulas.js" not in SCRIPT_PARTS or "formulasButton" not in template:
        raise RuntimeError("Consolidated renderer formula layer is incomplete")
    if "app-shell-v2.about.js" not in SCRIPT_PARTS or "about-overlay" not in css:
        raise RuntimeError("Consolidated renderer About dialog is incomplete")

    return (
        template.replace(CSS_PLACEHOLDER, css, 1)
        .replace(JS_PLACEHOLDER, javascript, 1)
    )


def install(app: Any) -> None:
    """Install the consolidated renderer as the sole HTML builder."""

    if getattr(app, "_consolidated_renderer_installed", False):
        return
    app._consolidated_renderer_installed = True
    original_create_window = app.webview.create_window

    def build_html() -> str:
        return render_document(Path(app.RENDERER_DIR))

    def create_window(*args: Any, **kwargs: Any) -> Any:
        kwargs["width"] = DEFAULT_WIDTH
        kwargs["height"] = DEFAULT_HEIGHT
        kwargs["min_size"] = MIN_SIZE
        return original_create_window(*args, **kwargs)

    app.build_html = build_html
    app.webview.create_window = create_window
