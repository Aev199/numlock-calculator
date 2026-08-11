"""Single-source renderer for the keyboard-first NumCalc UI.

The desktop shell, calculation engine and persistence stay in Python. This
module owns the complete frontend document and performs only deterministic
placeholder substitution for the bundled CSS and JavaScript sources.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from product_info import APP_NAME, APP_VERSION


TEMPLATE_NAME = "app-shell.html"
STYLE_PARTS = (
    "app-shell.css",
    "app-shell-ux.css",
    "app-shell-product.css",
    "app-shell-about.css",
    "app-shell-hotkey.css",
    "app-shell-formulas.css",
    "app-shell-interpolation.css",
    "app-shell-onboarding.css",
    "app-shell-mode-transitions.css",
    "app-shell-icons.css",
    "app-shell-compact.css",
    "app-shell-utility.css",
)
SCRIPT_PARTS = (
    *(f"app-shell-v2.part{index:02d}.js" for index in range(6)),
    "app-shell-v2.ux.js",
    "app-shell-v2.multiply.js",
    "app-shell-v2.copy.js",
    "app-shell-v2.digit-grouping.js",
    # part06 starts the event binder and part07 continues it before opening
    # initialize(); keep feature layers before that boundary so their drawer
    # functions remain in the consolidated controller scope.
    "app-shell-v2.variables.js",
    "app-shell-v2.formulas.js",
    "app-shell-v2.formula-guidance.js",
    "app-shell-v2.interpolation.js",
    "app-shell-v2.hotkey.js",
    "app-shell-v2.about.js",
    "app-shell-v2.onboarding.js",
    "app-shell-v2.mode-transitions.js",
    "app-shell-v2.icons.js",
    "app-shell-v2.compact.js",
    "app-shell-v2.compact-palette-fit.js",
    "app-shell-v2.part06.js",
    "app-shell-v2.part07.js",
    "app-shell-v2.part08.js",
)
CSS_PLACEHOLDER = "/*__NUMLOCK_CALC_CSS__*/"
JS_PLACEHOLDER = "/*__NUMLOCK_CALC_JS__*/"
PRODUCT_NAME_PLACEHOLDER = "__NUMCALC_PRODUCT_NAME__"
PRODUCT_VERSION_PLACEHOLDER = "__NUMCALC_PRODUCT_VERSION__"
DEFAULT_WIDTH = 384
DEFAULT_HEIGHT = 432
MIN_SIZE = (360, 380)
COMPACT_STARTUP_HEIGHT = 188
COMPACT_MIN_SIZE = (360, 160)


def _inject_product_identity(source: str) -> str:
    return (
        source.replace(PRODUCT_NAME_PLACEHOLDER, APP_NAME)
        .replace(PRODUCT_VERSION_PLACEHOLDER, APP_VERSION)
    )


def render_document(renderer_dir: Path) -> str:
    """Assemble the one supported frontend document from checked-in parts."""

    renderer = Path(renderer_dir)
    template = _inject_product_identity(
        (renderer / TEMPLATE_NAME).read_text(encoding="utf-8")
    )
    if not STYLE_PARTS or STYLE_PARTS[-1] != "app-shell-utility.css":
        raise RuntimeError("Cross-feature utility stylesheet must be last")
    core_css = (renderer / "app-shell.css").read_text(encoding="utf-8")
    if "linear-gradient(145deg" in core_css:
        raise RuntimeError("Legacy decorative brand gradient returned to core CSS")
    if "mode-workspace-old-forward" in core_css or "mode-panel-enter-forward" in core_css:
        raise RuntimeError("Legacy directional mode animation returned to core CSS")
    css = "\n".join(
        (renderer / name).read_text(encoding="utf-8")
        for name in STYLE_PARTS
    )
    javascript = _inject_product_identity(
        "\n".join(
            (renderer / name).read_text(encoding="utf-8")
            for name in SCRIPT_PARTS
        )
    )

    if CSS_PLACEHOLDER not in template or JS_PLACEHOLDER not in template:
        raise RuntimeError(
            "Consolidated renderer template is missing asset placeholders"
        )
    if javascript.count("nlcalc-consolidated-v2") != 1:
        raise RuntimeError("Consolidated renderer controller is incomplete")
    if "TRIG_ORDER" not in javascript or "bracket-color-overlay" not in css:
        raise RuntimeError("Consolidated renderer keyboard UX is incomplete")
    if "pywebview-no-drag" not in css or APP_NAME not in template:
        raise RuntimeError("NumCalc product shell is incomplete")
    if "app-shell-v2.multiply.js" not in SCRIPT_PARTS:
        raise RuntimeError("Consolidated renderer multiplication display is incomplete")
    if "app-shell-v2.copy.js" not in SCRIPT_PARTS:
        raise RuntimeError("Consolidated renderer clipboard behavior is incomplete")
    if (
        "app-shell-v2.digit-grouping.js" not in SCRIPT_PARTS
        or "DIGIT_GROUP_SEPARATOR" not in javascript
        or "applyVisualDigitGroupingToEditor" not in javascript
    ):
        raise RuntimeError("Consolidated renderer digit grouping is incomplete")
    if "app-shell-v2.variables.js" not in SCRIPT_PARTS:
        raise RuntimeError("Consolidated renderer variable layer is incomplete")
    if "app-shell-v2.formulas.js" not in SCRIPT_PARTS or "formulasButton" not in template:
        raise RuntimeError("Consolidated renderer formula layer is incomplete")
    if "app-shell-v2.formula-guidance.js" not in SCRIPT_PARTS:
        raise RuntimeError("Consolidated renderer formula guidance is incomplete")
    if "app-shell-v2.about.js" not in SCRIPT_PARTS or "about-overlay" not in css:
        raise RuntimeError("Consolidated renderer About dialog is incomplete")
    if "app-shell-v2.icons.js" not in SCRIPT_PARTS or "ui-glyph" not in css:
        raise RuntimeError("Unified utility icon layer is incomplete")
    if (
        "app-shell-v2.compact.js" not in SCRIPT_PARTS
        or "app-shell-v2.compact-palette-fit.js" not in SCRIPT_PARTS
        or "app-shell-compact.css" not in STYLE_PARTS
        or "data-compact-mode" not in css
        or "set_compact_window" not in javascript
        or "compactVisibleContentHeight" not in javascript
        or "compactPaletteContentHeight" not in javascript
        or "openCompactHistory" not in javascript
    ):
        raise RuntimeError("Compact calculator mode is incomplete")
    if (
        "app-shell-v2.interpolation.js" not in SCRIPT_PARTS
        or "interpolationTab" not in template
        or "interpolationPanel" not in template
    ):
        raise RuntimeError("Consolidated renderer interpolation layer is incomplete")
    if (
        "app-shell-v2.onboarding.js" not in SCRIPT_PARTS
        or "onboardingOverlay" not in template
        or "helpButton" not in template
    ):
        raise RuntimeError("Consolidated renderer onboarding layer is incomplete")
    if (
        "app-shell-v2.mode-transitions.js" not in SCRIPT_PARTS
        or "MODE_MOTION_ORDER" not in javascript
        or "modeIndicator" not in template
    ):
        raise RuntimeError("Consolidated renderer mode motion is incomplete")
    if PRODUCT_NAME_PLACEHOLDER in javascript or PRODUCT_VERSION_PLACEHOLDER in javascript:
        raise RuntimeError("Renderer product identity placeholders were not resolved")

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

    def compact_mode_enabled() -> bool:
        return bool(getattr(app, "compact_mode_enabled", lambda: False)())

    def build_html() -> str:
        document = render_document(Path(app.RENDERER_DIR))
        if compact_mode_enabled():
            document = document.replace(
                'data-motion="full"',
                'data-motion="full" data-compact-mode="true"',
                1,
            )
        return document

    def create_window(*args: Any, **kwargs: Any) -> Any:
        compact = compact_mode_enabled()
        kwargs["width"] = DEFAULT_WIDTH
        kwargs["height"] = (
            int(getattr(app, "COMPACT_WINDOW_HEIGHT", COMPACT_STARTUP_HEIGHT))
            if compact
            else DEFAULT_HEIGHT
        )
        kwargs["min_size"] = (
            tuple(getattr(app, "COMPACT_MIN_SIZE", COMPACT_MIN_SIZE))
            if compact
            else MIN_SIZE
        )
        return original_create_window(*args, **kwargs)

    app.build_html = build_html
    app.webview.create_window = create_window
