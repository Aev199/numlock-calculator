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
FULL_MIN_SIZE = (360, 380)
# Startup fallback only. The renderer measures topbar + editor after layout and
# sends the exact compact height through set_compact_window().
COMPACT_WINDOW_HEIGHT = 188
COMPACT_MIN_SIZE = (360, 160)
COMPACT_MAX_CONTENT_HEIGHT = 360


def install(app: Any) -> None:
    """Install focus-aware window behavior without touching renderer markup."""

    if getattr(app, "_window_controller_installed", False):
        return
    app._window_controller_installed = True
    app._renderer_focused = False

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

    def set_native_minimum_size(width: int, height: int) -> bool:
        """Update WinForms MinimumSize before a live compact/full resize.

        pywebview exposes min_size only at window creation time. On Windows its
        native object is the backing WinForms Form, so changing MinimumSize is
        necessary before resize() can cross the original full-mode minimum.
        """

        window = app._window
        if os.name != "nt" or window is None:
            return False
        native = getattr(window, "native", None)
        if native is None or not hasattr(native, "MinimumSize"):
            return False

        try:
            from System import Func, Type
            from System.Drawing import Size

            def apply() -> None:
                scale = float(getattr(native, "_scale", 1.0) or 1.0)
                native.MinimumSize = Size(
                    max(1, int(width * scale)),
                    max(1, int(height * scale)),
                )

            if bool(getattr(native, "InvokeRequired", False)):
                native.Invoke(Func[Type](apply))
            else:
                apply()
            return True
        except Exception:
            return False

    def compact_target_height(value: Any = None) -> int:
        try:
            requested = int(round(float(value)))
        except (TypeError, ValueError, OverflowError):
            requested = COMPACT_WINDOW_HEIGHT
        return max(
            COMPACT_MIN_SIZE[1],
            min(COMPACT_MAX_CONTENT_HEIGHT, requested),
        )

    def api_set_compact_window(
        _self: Any,
        compact: bool,
        content_height: Any = None,
    ) -> dict[str, Any]:
        """Resize the window for compact/full UI.

        In compact mode ``content_height`` is measured by the renderer from the
        actual visible topbar + editor. This avoids a fixed blank strip at the
        bottom and remains stable across DPI/font/layout changes. A larger value
        may be supplied temporarily for compact overlays such as history.

        Full mode intentionally returns to the product's canonical 384x432
        height. Do not derive it from ``window.height``: on WinForms/pywebview
        that runtime property can temporarily reflect the monitor/work-area
        height during native state transitions, which made Alt+Down expand the
        calculator to almost the full screen.
        """

        enabled = app._coerce_bool(compact, False)
        target_height = (
            compact_target_height(content_height)
            if enabled
            else DEFAULT_WINDOW_HEIGHT
        )
        target_min_size = (
            (COMPACT_MIN_SIZE[0], max(COMPACT_MIN_SIZE[1], target_height))
            if enabled
            else FULL_MIN_SIZE
        )
        window = app._window
        if window is None or app._quitting:
            return {
                "ok": True,
                "compact_mode": enabled,
                "width": DEFAULT_WINDOW_WIDTH,
                "height": target_height,
            }

        try:
            width = int(getattr(window, "width", DEFAULT_WINDOW_WIDTH) or DEFAULT_WINDOW_WIDTH)

            # Keep the pywebview model and its backing WinForms Form aligned.
            # The native minimum must change first or WinForms clamps resize().
            try:
                window.min_size = target_min_size
            except Exception:
                pass
            set_native_minimum_size(*target_min_size)
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
    app.set_native_minimum_size = set_native_minimum_size
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
