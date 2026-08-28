"""Windows-only vertical resize policy for the standard NumCalc window.

The standard 384px-wide layout may grow downward to expose more history while
remaining fixed horizontally. Compact mode stays locked to the renderer-owned
size so its fitted layout and overlay sizing remain deterministic.
"""

from __future__ import annotations

import os
from typing import Any


FULL_WINDOW_WIDTH = 384
FULL_WINDOW_MIN_HEIGHT = 432


def resize_bounds(compact: bool, height: Any = None) -> tuple[tuple[int, int], tuple[int, int]]:
    """Return native minimum/maximum bounds for the current window mode.

    A zero WinForms MaximumSize dimension means "unbounded". Therefore the
    full-mode maximum ``(384, 0)`` fixes width while leaving height unlimited.
    Compact mode is locked to the exact measured height supplied by its
    existing renderer/controller.
    """

    if not compact:
        return (
            (FULL_WINDOW_WIDTH, FULL_WINDOW_MIN_HEIGHT),
            (FULL_WINDOW_WIDTH, 0),
        )

    try:
        target_height = int(round(float(height)))
    except (TypeError, ValueError, OverflowError):
        target_height = FULL_WINDOW_MIN_HEIGHT
    target_height = max(1, target_height)
    return (
        (FULL_WINDOW_WIDTH, target_height),
        (FULL_WINDOW_WIDTH, target_height),
    )


def install(app: Any) -> None:
    """Install vertical-only resizing without changing renderer geometry."""

    if getattr(app, "_vertical_resize_installed", False):
        return
    app._vertical_resize_installed = True

    original_create_window = app.webview.create_window
    original_set_compact_window = app.AppApi.set_compact_window
    original_on_loaded = getattr(app, "on_loaded", lambda: None)
    original_on_shown = getattr(app, "on_shown", lambda: None)

    def compact_mode_enabled() -> bool:
        callback = getattr(app, "compact_mode_enabled", None)
        return bool(callback()) if callable(callback) else False

    def apply_native_resize_policy(compact: bool, height: Any = None) -> bool:
        """Apply fixed-width WinForms bounds on the UI thread when available."""

        window = getattr(app, "_window", None)
        if os.name != "nt" or window is None:
            return False
        native = getattr(window, "native", None)
        if (
            native is None
            or not hasattr(native, "MinimumSize")
            or not hasattr(native, "MaximumSize")
        ):
            return False

        minimum, maximum = resize_bounds(compact, height)
        try:
            from System import Action
            from System.Drawing import Size

            def apply() -> None:
                scale = float(getattr(native, "_scale", 1.0) or 1.0)
                native.MinimumSize = Size(
                    max(1, int(round(minimum[0] * scale))),
                    max(1, int(round(minimum[1] * scale))),
                )
                native.MaximumSize = Size(
                    max(0, int(round(maximum[0] * scale))),
                    max(0, int(round(maximum[1] * scale))),
                )

            if bool(getattr(native, "InvokeRequired", False)):
                native.Invoke(Action(apply))
            else:
                apply()
            return True
        except Exception:
            return False

    def create_window(*args: Any, **kwargs: Any) -> Any:
        compact = compact_mode_enabled()
        kwargs["resizable"] = True
        kwargs["width"] = FULL_WINDOW_WIDTH

        if compact:
            current_min = kwargs.get("min_size", (FULL_WINDOW_WIDTH, 160))
            try:
                min_height = max(1, int(current_min[1]))
            except (TypeError, ValueError, IndexError):
                min_height = 160
            kwargs["min_size"] = (FULL_WINDOW_WIDTH, min_height)
        else:
            kwargs["min_size"] = (FULL_WINDOW_WIDTH, FULL_WINDOW_MIN_HEIGHT)

        return original_create_window(*args, **kwargs)

    def set_compact_window(
        self: Any,
        compact: bool,
        content_height: Any = None,
    ) -> dict[str, Any]:
        response = original_set_compact_window(self, compact, content_height)
        if response.get("ok"):
            apply_native_resize_policy(
                bool(response.get("compact_mode", compact)),
                response.get("height", content_height),
            )
        return response

    def on_loaded() -> None:
        window = getattr(app, "_window", None)
        compact = compact_mode_enabled()
        height = getattr(window, "height", None) if compact else None
        apply_native_resize_policy(compact, height)
        original_on_loaded()

    def on_shown() -> None:
        window = getattr(app, "_window", None)
        compact = compact_mode_enabled()
        height = getattr(window, "height", None) if compact else None
        apply_native_resize_policy(compact, height)
        original_on_shown()

    app.webview.create_window = create_window
    app.AppApi.set_compact_window = set_compact_window
    app.on_loaded = on_loaded
    app.on_shown = on_shown
    app.apply_vertical_resize_policy = apply_native_resize_policy
