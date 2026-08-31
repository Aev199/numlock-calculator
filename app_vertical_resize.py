"""Windows-only vertical resize policy for the standard NumCalc window.

The standard 384px-wide layout may grow downward to expose more history while
remaining fixed horizontally. Compact mode stays locked to the renderer-owned
size so its fitted layout and overlay sizing remain deterministic.

pywebview deliberately makes ``frameless=True`` windows non-resizable on
Windows. NumCalc therefore adds one native hit-test zone at the bottom edge of
the backing WinForms form. Returning ``HTBOTTOM`` lets Windows perform the
actual resize loop while the existing min/max bounds keep width fixed.
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
BOTTOM_RESIZE_GRAB_LOGICAL_PX = 7

WM_NCHITTEST = 0x0084
HTBOTTOM = 15
GWL_WNDPROC = -4


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


def bottom_resize_hit_test(
    cursor_x: int,
    cursor_y: int,
    rect: tuple[int, int, int, int],
    border_px: int,
    *,
    compact: bool = False,
) -> bool:
    """Return whether a screen point belongs to NumCalc's bottom resize zone."""

    if compact:
        return False
    left, top, right, bottom = rect
    border = max(1, int(border_px))
    return (
        left <= int(cursor_x) < right
        and top <= int(cursor_y) < bottom
        and int(cursor_y) >= bottom - border
    )


def install(app: Any) -> None:
    """Install vertical-only resizing without changing renderer geometry."""

    if getattr(app, "_vertical_resize_installed", False):
        return
    app._vertical_resize_installed = True
    app._vertical_resize_wndproc_hook = None

    original_create_window = app.webview.create_window
    original_set_compact_window = app.AppApi.set_compact_window
    original_on_loaded = getattr(app, "on_loaded", lambda: None)
    original_on_shown = getattr(app, "on_shown", lambda: None)

    def compact_mode_enabled() -> bool:
        callback = getattr(app, "compact_mode_enabled", None)
        return bool(callback()) if callable(callback) else False

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

    def ensure_native_bottom_resize_hook() -> bool:
        """Subclass the WinForms WndProc and expose only the bottom resize edge."""

        if os.name != "nt":
            return False
        window = getattr(app, "_window", None)
        native = getattr(window, "native", None) if window is not None else None
        if native is None:
            return False

        hwnd = native_window_handle(native)
        if not hwnd:
            return False

        existing = getattr(app, "_vertical_resize_wndproc_hook", None)
        if isinstance(existing, dict) and existing.get("hwnd") == hwnd:
            return True

        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.WinDLL("user32", use_last_error=True)
            long_ptr = ctypes.c_ssize_t

            if ctypes.sizeof(ctypes.c_void_p) == 8:
                get_window_long_ptr = user32.GetWindowLongPtrW
                set_window_long_ptr = user32.SetWindowLongPtrW
            else:
                get_window_long_ptr = user32.GetWindowLongW
                set_window_long_ptr = user32.SetWindowLongW

            get_window_long_ptr.argtypes = [wintypes.HWND, ctypes.c_int]
            get_window_long_ptr.restype = long_ptr
            set_window_long_ptr.argtypes = [
                wintypes.HWND,
                ctypes.c_int,
                ctypes.c_void_p,
            ]
            set_window_long_ptr.restype = long_ptr

            call_window_proc = user32.CallWindowProcW
            call_window_proc.argtypes = [
                ctypes.c_void_p,
                wintypes.HWND,
                wintypes.UINT,
                wintypes.WPARAM,
                wintypes.LPARAM,
            ]
            call_window_proc.restype = long_ptr

            user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
            user32.GetCursorPos.restype = wintypes.BOOL
            user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
            user32.GetWindowRect.restype = wintypes.BOOL

            get_dpi_for_window = getattr(user32, "GetDpiForWindow", None)
            if get_dpi_for_window is not None:
                get_dpi_for_window.argtypes = [wintypes.HWND]
                get_dpi_for_window.restype = wintypes.UINT

            original_proc = int(get_window_long_ptr(hwnd, GWL_WNDPROC) or 0)
            if not original_proc:
                raise OSError("WinForms WndProc is unavailable")

            wndproc_type = ctypes.WINFUNCTYPE(
                long_ptr,
                wintypes.HWND,
                wintypes.UINT,
                wintypes.WPARAM,
                wintypes.LPARAM,
            )

            def call_original(
                callback_hwnd: int,
                message: int,
                wparam: int,
                lparam: int,
            ) -> int:
                return int(
                    call_window_proc(
                        ctypes.c_void_p(original_proc),
                        callback_hwnd,
                        message,
                        wparam,
                        lparam,
                    )
                )

            def wndproc(
                callback_hwnd: int,
                message: int,
                wparam: int,
                lparam: int,
            ) -> int:
                if message == WM_NCHITTEST:
                    try:
                        point = wintypes.POINT()
                        rect = wintypes.RECT()
                        if user32.GetCursorPos(ctypes.byref(point)) and user32.GetWindowRect(
                            callback_hwnd,
                            ctypes.byref(rect),
                        ):
                            dpi = 96
                            if get_dpi_for_window is not None:
                                dpi = max(96, int(get_dpi_for_window(callback_hwnd) or 96))
                            border_px = max(
                                4,
                                int(round(BOTTOM_RESIZE_GRAB_LOGICAL_PX * dpi / 96.0)),
                            )
                            if bottom_resize_hit_test(
                                point.x,
                                point.y,
                                (rect.left, rect.top, rect.right, rect.bottom),
                                border_px,
                                compact=compact_mode_enabled(),
                            ):
                                return HTBOTTOM
                    except Exception:
                        # A hit-test failure must never break normal WinForms dispatch.
                        pass

                return call_original(callback_hwnd, message, wparam, lparam)

            callback = wndproc_type(wndproc)
            ctypes.set_last_error(0)
            previous = int(
                set_window_long_ptr(
                    hwnd,
                    GWL_WNDPROC,
                    ctypes.cast(callback, ctypes.c_void_p),
                )
                or 0
            )
            error = ctypes.get_last_error()
            if previous == 0 and error:
                raise ctypes.WinError(error)

            # Keep the callback alive for the entire native window lifetime.
            app._vertical_resize_wndproc_hook = {
                "hwnd": hwnd,
                "callback": callback,
                "original_proc": original_proc,
                "user32": user32,
            }
            return True
        except Exception:
            logger.exception("Could not install the NumCalc bottom resize hit-test")
            return False

    def apply_native_resize_policy(compact: bool, height: Any = None) -> bool:
        """Apply fixed-width WinForms bounds and the bottom-edge native hit-test."""

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

            result = {"hook": False}

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
                result["hook"] = ensure_native_bottom_resize_hook()

            if bool(getattr(native, "InvokeRequired", False)):
                native.Invoke(Action(apply))
            else:
                apply()
            return bool(result["hook"])
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
    app.ensure_native_bottom_resize_hook = ensure_native_bottom_resize_hook
