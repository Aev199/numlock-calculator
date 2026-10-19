"""Flash-free window height changes.

Two things made compact/full switches and compact overlays flash:

* the WinForms form and WebView2 kept pywebview's default white background,
  so every newly exposed strip showed white for a frame before the page
  repainted it in the dark theme;
* a resize ran as separate native steps (minimum, size, maximum), and a
  minimum above the current height made WinForms resize on its own first.

The window background now follows the theme, and the size bounds are relaxed
before the regular resize, so the window changes size in a single step.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any

import app_window

LOGGER_NAME = "numcalc"
THEME_BACKGROUND = {"dark": "#202020", "light": "#fafafa"}


def background_for(theme: Any) -> str:
    """The page background (``--panel``) of a theme as a hex colour."""

    return THEME_BACKGROUND["light" if theme == "light" else "dark"]


def target_height(compact: Any, content_height: Any) -> int:
    """The logical height ``set_compact_window`` will settle on."""

    if not compact:
        return app_window.DEFAULT_WINDOW_HEIGHT
    try:
        requested = int(round(float(content_height)))
    except (TypeError, ValueError, OverflowError):
        requested = app_window.COMPACT_WINDOW_HEIGHT
    return max(
        app_window.COMPACT_MIN_SIZE[1],
        min(app_window.COMPACT_MAX_CONTENT_HEIGHT, requested),
    )


def install(app: Any) -> None:
    if getattr(app, "_window_background_installed", False):
        return
    app._window_background_installed = True
    logger = logging.getLogger(LOGGER_NAME)
    resize_lock = threading.Lock()

    original_create_window = app.webview.create_window
    original_set_ui_settings = app.AppApi.set_ui_settings
    original_set_compact_window = app.AppApi.set_compact_window

    def current_theme() -> str:
        settings = getattr(getattr(app, "_api", None), "_ui_settings", None)
        return settings.get("theme", "dark") if isinstance(settings, dict) else "dark"

    def on_ui_thread(native: Any, action: Any) -> None:
        from System import Action

        if bool(getattr(native, "InvokeRequired", False)):
            native.Invoke(Action(action))
        else:
            action()

    def apply_native_background(theme: Any) -> bool:
        window = getattr(app, "_window", None)
        native = getattr(window, "native", None)
        if os.name != "nt" or native is None:
            return False
        colour = background_for(theme)
        try:
            from System.Drawing import Color, ColorTranslator

            def apply() -> None:
                native.BackColor = ColorTranslator.FromHtml(colour)
                webview = getattr(native, "webview", None)
                if webview is not None and hasattr(webview, "DefaultBackgroundColor"):
                    webview.DefaultBackgroundColor = Color.FromArgb(
                        255, int(colour[1:3], 16), int(colour[3:5], 16), int(colour[5:7], 16),
                    )

            on_ui_thread(native, apply)
            return True
        except Exception:
            logger.exception("Could not apply the window background")
            return False

    def relax_bounds(height: int) -> bool:
        """Let the next resize reach ``height`` in one step, without clamping."""

        window = getattr(app, "_window", None)
        native = getattr(window, "native", None)
        if os.name != "nt" or native is None or getattr(app, "_quitting", False):
            return False
        try:
            from System.Drawing import Size

            def relax() -> None:
                scale = float(getattr(native, "_scale", 1.0) or 1.0)
                current = int(native.Height)
                wanted = max(1, int(height * scale))
                native.MinimumSize = Size(1, min(current, wanted))
                native.MaximumSize = Size(int(native.Width), max(current, wanted))

            on_ui_thread(native, relax)
            return True
        except Exception:
            logger.exception("Could not relax the window size bounds")
            return False

    def create_window(*args: Any, **kwargs: Any) -> Any:
        kwargs["background_color"] = background_for(current_theme())
        return original_create_window(*args, **kwargs)

    def set_ui_settings(self: Any, settings: dict[str, Any]) -> dict[str, Any]:
        response = original_set_ui_settings(self, settings)
        if isinstance(settings, dict) and "theme" in settings:
            apply_native_background(response.get("theme", settings.get("theme")))
        return response

    def set_compact_window(self: Any, compact: bool, content_height: Any = None) -> dict[str, Any]:
        # Serialised so two fits cannot interleave their bound changes. The
        # regular policy then resizes once and settles the final bounds.
        with resize_lock:
            relax_bounds(target_height(app._coerce_bool(compact, False), content_height))
            return original_set_compact_window(self, compact, content_height)

    app.webview.create_window = create_window
    app.AppApi.set_ui_settings = set_ui_settings
    app.AppApi.set_compact_window = set_compact_window
    app.apply_native_background = apply_native_background
    app.relax_window_bounds = relax_bounds
