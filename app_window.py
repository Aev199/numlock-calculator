"""Renderer-agnostic window focus, visibility and compact-mode controller.

The renderer owns markup and CSS. This module owns native window activation,
visibility, compact sizing and the persisted compact-mode UI setting.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any

SW_RESTORE = 9
DEFAULT_WINDOW_WIDTH = 384
DEFAULT_WINDOW_HEIGHT = 432
COMPACT_WINDOW_HEIGHT = 220
COMPACT_MIN_SIZE = (360, 200)


def install(app: Any) -> None:
    """Install focus-aware window behavior without touching renderer markup."""

    if getattr(app, "_window_controller_installed", False):
        return
    app._window_controller_installed = True
    app._renderer_focused = False
    app._full_window_height = DEFAULT_WINDOW_HEIGHT

    original_api_init = app.AppApi.__init__
    original_set_ui_settings = app.AppApi.set_ui_settings

    def normalize_compact_setting(api: Any) -> None:
        api._ui_settings["compact_mode"] = app._coerce_bool(
            api._ui_settings.get("compact_mode", False),
            False,
        )

    def api_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_api_init(self, *args, **kwargs)
        normalize_compact_setting(self)

    def api_set_ui_settings(self: Any, settings: dict[str, Any]) -> dict[str, Any]:
        values = dict(settings or {})
        marker = object()
        compact_value = values.pop("compact_mode", marker)

        if values:
            original_set_ui_settings(self, values)

        normalize_compact_setting(self)
        if compact_value is not marker:
            self._ui_settings["compact_mode"] = app._coerce_bool(
                compact_value,
                False,
            )
            self._storage.set("ui_settings", self._ui_settings)
        return dict(self._ui_settings)

    def compact_mode_enabled() -> bool:
        api = getattr(app, "_api", None)
        settings = getattr(api, "_ui_settings", {})
        return app._coerce_bool(settings.get("compact_mode", False), False)

    def set_renderer_focused(focused: bool) -> None:
        with app._state_lock:
            app._renderer_focused = bool(focused)

    def api_window_focus_changed(_self: Any, focused: bool) -> bool:
        set_renderer_focused(bool(focused))
        return True

    def api_set_compact_window(_self: Any, compact: bool) -> dict[str, Any]:
        enabled = app._coerce_bool(compact, False)
        window = app._window
        if window is None or app._quitting:
            return {
                "ok": True,
                "compact_mode": enabled,
                "width": DEFAULT_WINDOW_WIDTH,
                "height": COMPACT_WINDOW_HEIGHT if enabled else DEFAULT_WINDOW_HEIGHT,
            }

        try:
            width = int(getattr(window, "width", DEFAULT_WINDOW_WIDTH) or DEFAULT_WINDOW_WIDTH)
            current_height = int(
                getattr(window, "height", DEFAULT_WINDOW_HEIGHT) or DEFAULT_WINDOW_HEIGHT
            )
            if enabled:
                if current_height > COMPACT_WINDOW_HEIGHT + 24:
                    app._full_window_height = current_height
                target_height = COMPACT_WINDOW_HEIGHT
            else:
                target_height = max(
                    COMPACT_WINDOW_HEIGHT + 24,
                    int(getattr(app, "_full_window_height", DEFAULT_WINDOW_HEIGHT)),
                )
            window.resize(width, target_height)
            return {
                "ok": True,
                "compact_mode": enabled,
                "width": width,
                "height": target_height,
            }
        except Exception as exc:
            return {
                "ok": False,
                "compact_mode": enabled,
                "error": str(exc) or "Не удалось изменить размер окна",
            }

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

    app.AppApi.__init__ = api_init
    app.AppApi.set_ui_settings = api_set_ui_settings
    app.AppApi.window_focus_changed = api_window_focus_changed
    app.AppApi.set_compact_window = api_set_compact_window
    app.compact_mode_enabled = compact_mode_enabled
    app.COMPACT_WINDOW_HEIGHT = COMPACT_WINDOW_HEIGHT
    app.COMPACT_MIN_SIZE = COMPACT_MIN_SIZE
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

    # app_storage.install() runs before this module in production; normalize its
    # already-created API as well as all future AppApi instances.
    if getattr(app, "_api", None) is not None:
        normalize_compact_setting(app._api)
