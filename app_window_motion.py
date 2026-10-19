"""Flash-free, animated window height changes.

Two things made compact/full switches and compact overlays flash:

* the WinForms form and WebView2 kept pywebview's default white background,
  so every newly exposed strip showed white for a frame before the page
  repainted it in the dark theme;
* a resize was applied as separate native steps (minimum, size, maximum),
  each with its own repaint.

The window background now follows the theme, and a height change runs as one
short ease-out animation inside relaxed bounds before the regular resize policy
settles the final size.
"""

from __future__ import annotations

import ctypes
import logging
import os
import threading
import time
from typing import Any

import app_window

LOGGER_NAME = "numcalc"
THEME_BACKGROUND = {"dark": "#202020", "light": "#fafafa"}
RESIZE_DURATION = 0.16
RESIZE_FRAMES = 10
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010


def background_for(theme: Any) -> str:
    """The page background (``--panel``) of a theme as a hex colour."""

    return THEME_BACKGROUND["light" if theme == "light" else "dark"]


def eased_heights(start: int, end: int, frames: int = RESIZE_FRAMES) -> list[int]:
    """Intermediate heights for an ease-out move; the last one is ``end``."""

    if start == end or frames < 1:
        return [end]
    steps = []
    for index in range(1, frames + 1):
        progress = index / frames
        eased = 1 - (1 - progress) ** 3
        steps.append(round(start + (end - start) * eased))
    steps[-1] = end
    return steps


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
    if getattr(app, "_window_motion_installed", False):
        return
    app._window_motion_installed = True
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

    def animate_height(height: int) -> bool:
        """Move the window height to ``height`` in one short eased motion."""

        window = getattr(app, "_window", None)
        native = getattr(window, "native", None)
        if os.name != "nt" or native is None or getattr(app, "_quitting", False):
            return False
        try:
            from System.Drawing import Size
            from ctypes import wintypes

            user32 = ctypes.windll.user32  # type: ignore[attr-defined]
            handle = native.Handle
            hwnd = handle.ToInt64() if hasattr(handle, "ToInt64") else int(handle)
            rect = wintypes.RECT()
            if not user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect)):
                return False
            width = rect.right - rect.left
            start = rect.bottom - rect.top
            scale = float(getattr(native, "_scale", 1.0) or 1.0)
            end = max(1, int(height * scale))
            if start == end:
                return True

            def relax() -> None:
                native.MinimumSize = Size(1, min(start, end))
                native.MaximumSize = Size(width, max(start, end))

            on_ui_thread(native, relax)
            frame = RESIZE_DURATION / RESIZE_FRAMES
            flags = SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE
            for step in eased_heights(start, end):
                user32.SetWindowPos(wintypes.HWND(hwnd), None, 0, 0, width, step, flags)
                time.sleep(frame)
            return True
        except Exception:
            logger.exception("Could not animate the window height")
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
        # Serialised: a fit scheduled by layout changes must not fight a
        # running animation. The regular policy then settles size and bounds.
        with resize_lock:
            animate_height(target_height(app._coerce_bool(compact, False), content_height))
            return original_set_compact_window(self, compact, content_height)

    app.webview.create_window = create_window
    app.AppApi.set_ui_settings = set_ui_settings
    app.AppApi.set_compact_window = set_compact_window
    app.apply_native_background = apply_native_background
    app.animate_window_height = animate_height
