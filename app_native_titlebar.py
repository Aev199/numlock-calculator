"""DPI-safe native titlebar dragging for the frameless Windows window."""

from __future__ import annotations

import ctypes
import os
from typing import Any

WM_NCLBUTTONDOWN = 0x00A1
HTCAPTION = 2


class _Point(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def _mouse_lparam(x: int, y: int) -> int:
    """Pack signed screen coordinates into the LPARAM shape Windows expects."""

    return ((int(y) & 0xFFFF) << 16) | (int(x) & 0xFFFF)


def begin_windows_caption_drag(user32: Any, hwnd: int | None) -> bool:
    """Ask Windows to move a frameless window from the current cursor position.

    All coordinates come from Win32. No CSS/client/screen coordinate conversion
    is involved, so Windows owns DPI and text/display scaling behavior.
    """

    if not hwnd:
        return False

    point = _Point()
    try:
        if not user32.GetCursorPos(ctypes.byref(point)):
            return False
        user32.ReleaseCapture()
        return bool(
            user32.PostMessageW(
                int(hwnd),
                WM_NCLBUTTONDOWN,
                HTCAPTION,
                _mouse_lparam(point.x, point.y),
            )
        )
    except Exception:
        return False


def install(app: Any) -> None:
    """Expose native titlebar dragging through the existing pywebview API."""

    if getattr(app, "_native_titlebar_installed", False):
        return
    app._native_titlebar_installed = True

    def api_begin_window_drag(_self: Any) -> bool:
        if os.name != "nt" or getattr(app, "_quitting", False):
            return False
        handle_getter = getattr(app, "window_handle", None)
        if not callable(handle_getter):
            return False
        handle = handle_getter()
        if not handle:
            return False
        return begin_windows_caption_drag(app._user32(), handle)

    app.AppApi.begin_window_drag = api_begin_window_drag
