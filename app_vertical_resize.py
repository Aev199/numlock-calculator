"""Windows-only vertical resize policy for the standard NumCalc window.

The standard 384px-wide layout may grow downward to expose more history while
remaining fixed horizontally. Compact mode stays locked to the renderer-owned
size so its fitted layout remains deterministic.

pywebview 6.2.1 uses a borderless WinForms Form for ``frameless=True`` and the
WebView2 control fills its client area. NumCalc places a tiny WinForms panel at
the bottom of the form. The panel owns the SizeNS cursor and starts the standard
Windows HTBOTTOM resize loop on left mouse-down. Its idle/hover colours mirror
the renderer theme and its native border is explicitly disabled, so the hit
target remains convenient without looking like a separate strip.
"""

from __future__ import annotations

import logging
import os
from typing import Any


logger = logging.getLogger("numcalc.vertical_resize")

FULL_WINDOW_WIDTH = 384
FULL_WINDOW_MIN_HEIGHT = 432
# WinForms treats a zero component of a non-zero MaximumSize literally, so use
# a deliberately large practical ceiling instead of ``(width, 0)``.
FULL_WINDOW_MAX_HEIGHT = 100_000
BOTTOM_RESIZE_GRIP_LOGICAL_PX = 7

# Keep these in sync with renderer/app-shell.css: --panel and --soft.
LIGHT_GRIP_IDLE = "#fafafa"
LIGHT_GRIP_HOVER = "#f0f0f0"
DARK_GRIP_IDLE = "#202020"
DARK_GRIP_HOVER = "#2b2b2b"

WM_NCLBUTTONDOWN = 0x00A1
HTBOTTOM = 15


def resize_bounds(compact: bool, height: Any = None) -> tuple[tuple[int, int], tuple[int, int]]:
    """Return native minimum/maximum bounds for the current window mode."""

    if not compact:
        return (
            (FULL_WINDOW_WIDTH, FULL_WINDOW_MIN_HEIGHT),
            (FULL_WINDOW_WIDTH, FULL_WINDOW_MAX_HEIGHT),
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


def grip_height_for_scale(scale: Any) -> int:
    """Return a DPI-aware physical height for the native bottom grip."""

    try:
        value = float(scale)
    except (TypeError, ValueError, OverflowError):
        value = 1.0
    if value <= 0:
        value = 1.0
    return max(4, int(round(BOTTOM_RESIZE_GRIP_LOGICAL_PX * value)))


def grip_palette(theme: Any) -> tuple[str, str]:
    """Return renderer-matched idle/hover colours for a UI theme."""

    if str(theme or "").strip().lower() == "light":
        return LIGHT_GRIP_IDLE, LIGHT_GRIP_HOVER
    return DARK_GRIP_IDLE, DARK_GRIP_HOVER


def install(app: Any) -> None:
    """Install bottom-only native resizing without changing renderer geometry."""

    if getattr(app, "_vertical_resize_installed", False):
        return
    app._vertical_resize_installed = True
    app._vertical_resize_grip = None

    original_create_window = app.webview.create_window
    original_set_compact_window = app.AppApi.set_compact_window
    original_set_ui_settings = app.AppApi.set_ui_settings
    original_on_loaded = getattr(app, "on_loaded", lambda: None)
    original_on_shown = getattr(app, "on_shown", lambda: None)

    def compact_mode_enabled() -> bool:
        callback = getattr(app, "compact_mode_enabled", None)
        return bool(callback()) if callable(callback) else False

    def current_theme(api: Any = None) -> str:
        owner = api if api is not None else getattr(app, "_api", None)
        settings = getattr(owner, "_ui_settings", {})
        if isinstance(settings, dict):
            return "light" if str(settings.get("theme", "dark")).lower() == "light" else "dark"
        return "dark"

    def native_window_handle(native: Any) -> int | None:
        try:
            handle = getattr(native, "Handle", None)
            if handle is None:
                return None
            if hasattr(handle, "ToInt64"):
                return int(handle.ToInt64())
            return int(handle)
        except Exception:
            return None

    def refresh_native_grip_theme(theme: Any = None) -> bool:
        """Repaint the native grip to match the live renderer theme."""

        state = getattr(app, "_vertical_resize_grip", None)
        if not isinstance(state, dict):
            return False
        native = state.get("native")
        control = state.get("control")
        if native is None or control is None or bool(getattr(control, "IsDisposed", False)):
            return False

        selected_theme = current_theme() if theme is None else theme
        idle, hover = grip_palette(selected_theme)
        colour = hover if bool(state.get("hovered", False)) else idle

        try:
            from System import Action
            from System.Drawing import ColorTranslator
            import System.Windows.Forms as WinForms

            def apply() -> None:
                control.BorderStyle = getattr(WinForms.BorderStyle, "None")
                control.Margin = WinForms.Padding(0)
                control.Padding = WinForms.Padding(0)
                control.BackColor = ColorTranslator.FromHtml(colour)

            if bool(getattr(native, "InvokeRequired", False)):
                native.Invoke(Action(apply))
            else:
                apply()
            return True
        except Exception:
            logger.exception("Could not refresh the NumCalc bottom resize grip theme")
            return False

    def begin_bottom_resize(native: Any) -> bool:
        """Enter the standard Windows resize loop for the bottom edge."""

        if os.name != "nt" or compact_mode_enabled():
            return False
        hwnd = native_window_handle(native)
        if not hwnd:
            return False

        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.WinDLL("user32", use_last_error=True)
            user32.ReleaseCapture.argtypes = []
            user32.ReleaseCapture.restype = wintypes.BOOL
            user32.SendMessageW.argtypes = [
                wintypes.HWND,
                wintypes.UINT,
                wintypes.WPARAM,
                wintypes.LPARAM,
            ]
            user32.SendMessageW.restype = ctypes.c_ssize_t
            user32.ReleaseCapture()
            user32.SendMessageW(hwnd, WM_NCLBUTTONDOWN, HTBOTTOM, 0)
            return True
        except Exception:
            logger.exception("Could not start the NumCalc bottom resize loop")
            return False

    def ensure_native_bottom_resize_grip(compact: bool) -> bool:
        """Create or update the WinForms panel that receives bottom-edge mouse input."""

        if os.name != "nt":
            return False
        window = getattr(app, "_window", None)
        native = getattr(window, "native", None) if window is not None else None
        if native is None or not hasattr(native, "Controls"):
            return False

        try:
            import System.Windows.Forms as WinForms
            from System.Drawing import ColorTranslator

            scale = float(getattr(native, "_scale", 1.0) or 1.0)
            grip_height = grip_height_for_scale(scale)
            borderless = getattr(WinForms.BorderStyle, "None")
            existing = getattr(app, "_vertical_resize_grip", None)
            if isinstance(existing, dict) and existing.get("native") is native:
                control = existing.get("control")
                if control is not None and not bool(getattr(control, "IsDisposed", False)):
                    control.Height = grip_height
                    control.BorderStyle = borderless
                    control.Margin = WinForms.Padding(0)
                    control.Padding = WinForms.Padding(0)
                    control.Visible = not compact
                    if compact:
                        existing["hovered"] = False
                    refresh_native_grip_theme()
                    if control.Visible:
                        control.BringToFront()
                    return True

            idle, _hover = grip_palette(current_theme())
            grip = WinForms.Panel()
            grip.Name = "numcalcBottomResizeGrip"
            grip.TabStop = False
            grip.Cursor = WinForms.Cursors.SizeNS
            grip.Dock = WinForms.DockStyle.Bottom
            grip.Height = grip_height
            grip.BorderStyle = borderless
            grip.Margin = WinForms.Padding(0)
            grip.Padding = WinForms.Padding(0)
            grip.BackColor = ColorTranslator.FromHtml(idle)
            grip.Visible = not compact

            def on_mouse_enter(_sender: Any, _event: Any) -> None:
                state = getattr(app, "_vertical_resize_grip", None)
                if isinstance(state, dict):
                    state["hovered"] = True
                refresh_native_grip_theme()

            def on_mouse_leave(_sender: Any, _event: Any) -> None:
                state = getattr(app, "_vertical_resize_grip", None)
                if isinstance(state, dict):
                    state["hovered"] = False
                refresh_native_grip_theme()

            def on_mouse_down(_sender: Any, event: Any) -> None:
                if event.Button == WinForms.MouseButtons.Left:
                    begin_bottom_resize(native)

            grip.MouseEnter += on_mouse_enter
            grip.MouseLeave += on_mouse_leave
            grip.MouseDown += on_mouse_down
            native.Controls.Add(grip)
            if grip.Visible:
                grip.BringToFront()

            # Keep the control and Python event delegates alive for the form lifetime.
            app._vertical_resize_grip = {
                "native": native,
                "control": grip,
                "hovered": False,
                "mouse_enter": on_mouse_enter,
                "mouse_leave": on_mouse_leave,
                "mouse_down": on_mouse_down,
            }
            return True
        except Exception:
            logger.exception("Could not install the NumCalc bottom resize grip")
            return False

    def apply_native_resize_policy(compact: bool, height: Any = None) -> bool:
        """Apply fixed-width bounds and keep the bottom resize grip in sync."""

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

            result = {"grip": False}

            def apply() -> None:
                scale = float(getattr(native, "_scale", 1.0) or 1.0)
                native.MinimumSize = Size(
                    max(1, int(round(minimum[0] * scale))),
                    max(1, int(round(minimum[1] * scale))),
                )
                native.MaximumSize = Size(
                    max(1, int(round(maximum[0] * scale))),
                    max(1, int(round(maximum[1] * scale))),
                )
                result["grip"] = ensure_native_bottom_resize_grip(compact)

            if bool(getattr(native, "InvokeRequired", False)):
                native.Invoke(Action(apply))
            else:
                apply()
            return bool(result["grip"])
        except Exception:
            logger.exception("Could not apply the NumCalc native resize policy")
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

    def set_ui_settings(self: Any, settings: dict[str, Any]) -> dict[str, Any]:
        response = original_set_ui_settings(self, settings)
        if isinstance(settings, dict) and "theme" in settings:
            refresh_native_grip_theme(response.get("theme", settings.get("theme")))
        return response

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
    app.AppApi.set_ui_settings = set_ui_settings
    app.AppApi.set_compact_window = set_compact_window
    app.on_loaded = on_loaded
    app.on_shown = on_shown
    app.apply_vertical_resize_policy = apply_native_resize_policy
    app.ensure_native_bottom_resize_grip = ensure_native_bottom_resize_grip
    app.refresh_native_grip_theme = refresh_native_grip_theme
    app.begin_bottom_resize = begin_bottom_resize
