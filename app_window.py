"""Renderer-agnostic window focus and visibility controller.

This module owns only native window activation, visibility and renderer focus
state. It never builds or modifies frontend HTML.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any

SW_RESTORE = 9


def install(app: Any) -> None:
    """Install focus-aware window behavior without touching the renderer."""

    if getattr(app, "_window_controller_installed", False):
        return
    app._window_controller_installed = True
    app._renderer_focused = False

    def set_renderer_focused(focused: bool) -> None:
        with app._state_lock:
            app._renderer_focused = bool(focused)

    def api_window_focus_changed(_self: Any, focused: bool) -> bool:
        set_renderer_focused(bool(focused))
        return True

    def window_handle() -> int | None:
        if os.name != "nt" or app._window is None:
            return None
        try:
            native = getattr(app._window, "native", None)
            handle = getattr(native, "Handle", None)
            if handle is None:
                return None
            if hasattr(handle, "ToInt64"):
                return int(handle.ToInt64())
            return int(handle)
        except Exception:
            return None

    def capture_foreground_window() -> None:
        if os.name != "nt":
            return
        try:
            handle = int(app._user32().GetForegroundWindow())
            own_handle = window_handle()
            if handle and handle != own_handle:
                app._previous_foreground_hwnd = handle
        except Exception:
            pass

    def activate_native_window() -> None:
        if os.name != "nt":
            return
        handle = window_handle()
        if not handle:
            return
        try:
            user32 = app._user32()
            user32.ShowWindow(handle, SW_RESTORE)
            user32.BringWindowToTop(handle)
            user32.SetForegroundWindow(handle)
        except Exception:
            pass

    def request_editor_focus(select_all: bool = True) -> None:
        if app._window is None or app._quitting:
            return

        def apply_focus() -> None:
            activate_native_window()
            time.sleep(0.02)
            try:
                argument = "true" if select_all else "false"
                app._window.evaluate_js(
                    "window.__nlcalcRestoreEditorFocus && "
                    f"window.__nlcalcRestoreEditorFocus({argument});"
                )
            except Exception:
                pass

        threading.Thread(
            target=apply_focus,
            name="NumLockCalcFocus",
            daemon=True,
        ).start()

    def show_window() -> None:
        if app._window is None or app._quitting:
            return
        capture_foreground_window()
        try:
            app._window.show()
            app._window.restore()
            with app._state_lock:
                app._visible = True
            request_editor_focus(True)
        except Exception:
            pass

    def refocus_window() -> None:
        if app._window is None or app._quitting:
            return
        capture_foreground_window()
        try:
            app._window.show()
            app._window.restore()
        except Exception:
            pass
        request_editor_focus(True)

    def hide_window() -> None:
        if app._window is None or app._quitting:
            return
        try:
            app._window.hide()
        finally:
            with app._state_lock:
                app._visible = False
                app._renderer_focused = False

    def toggle_window() -> None:
        if app._window is None or app._quitting:
            return
        with app._state_lock:
            visible = app._visible
            focused = app._renderer_focused
        if visible and focused:
            hide_window()
        elif visible:
            refocus_window()
        else:
            show_window()

    def on_shown() -> None:
        with app._state_lock:
            app._visible = True
        request_editor_focus(True)

    def on_loaded() -> None:
        request_editor_focus(True)

    app.AppApi.window_focus_changed = api_window_focus_changed
    app.set_renderer_focused = set_renderer_focused
    app.window_handle = window_handle
    app.capture_foreground_window = capture_foreground_window
    app.activate_native_window = activate_native_window
    app.request_editor_focus = request_editor_focus
    app.show_window = show_window
    app.refocus_window = refocus_window
    app.hide_window = hide_window
    app.toggle_window = toggle_window
    app.on_shown = on_shown
    app.on_loaded = on_loaded

