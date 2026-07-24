"""Windows focus and NumLock refinements for the keyboard-first shell.

This module is imported by ``app_keyboard.py`` before the desktop window starts.
It keeps the larger prototype shell reviewable while replacing its global
NumLock handling and renderer bootstrap with the stabilized implementation.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import threading
import time
from pathlib import Path
from typing import Any

WH_KEYBOARD_LL = 13
HC_ACTION = 0
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_QUIT = 0x0012
SW_RESTORE = 9

_hook_thread: threading.Thread | None = None
_hook_thread_id: int | None = None
_hook_handle: int | None = None
_hook_callback: Any = None
_hook_ready = threading.Event()


def install(app: Any) -> None:
    """Install stabilized behavior into the imported ``app`` module."""

    app._renderer_focused = False

    def build_html() -> str:
        renderer = Path(app.RENDERER_DIR)
        html = (renderer / "index-v2.html").read_text(encoding="utf-8")
        css = (renderer / "style-v2.css").read_text(encoding="utf-8")
        script = (renderer / "script-v2.js").read_text(encoding="utf-8")
        html = html.replace(
            '<link rel="stylesheet" href="style-v2.css">',
            f"<style>\n{css}\n</style>",
        )
        html = html.replace(
            '<script src="script-v2.js"></script>',
            f"<script>\n{script}\n</script>",
        )
        html = html.replace(
            "<head>",
            "<head>\n<script>window.__NUMLOCK_PYWEBVIEW__ = true;</script>",
            1,
        )
        return html

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

    def request_editor_focus() -> None:
        if app._window is None or app._quitting:
            return

        def apply_focus() -> None:
            activate_native_window()
            time.sleep(0.02)
            try:
                app._window.evaluate_js(
                    "window.__nlcalcRestoreEditorFocus && "
                    "window.__nlcalcRestoreEditorFocus();"
                )
            except Exception:
                pass

        threading.Thread(target=apply_focus, daemon=True).start()

    def show_window() -> None:
        if app._window is None or app._quitting:
            return
        capture_foreground_window()
        try:
            app._window.show()
            app._window.restore()
            with app._state_lock:
                app._visible = True
            request_editor_focus()
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
        request_editor_focus()

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

    def on_numlock_press(_event: Any = None) -> None:
        with app._state_lock:
            if app._quitting or app._numlock_down:
                return
            app._numlock_down = True
        toggle_window()

    def on_numlock_release(_event: Any = None) -> None:
        with app._state_lock:
            app._numlock_down = False

    def on_numlock_event(event: Any) -> None:
        event_type = getattr(event, "event_type", None)
        if event_type == "down":
            on_numlock_press(event)
        elif event_type == "up":
            on_numlock_release(event)

    def native_hook_loop() -> None:
        global _hook_thread_id, _hook_handle, _hook_callback

        if os.name != "nt":
            _hook_ready.set()
            return

        callback_factory = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)

        class KBDLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [
                ("vkCode", ctypes.c_ulong),
                ("scanCode", ctypes.c_ulong),
                ("flags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.c_size_t),
            ]

        low_level_proc = callback_factory(
            ctypes.c_ssize_t,
            ctypes.c_int,
            ctypes.c_size_t,
            ctypes.c_ssize_t,
        )
        user32 = app._user32()
        kernel32 = ctypes.windll.kernel32
        kernel32.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
        kernel32.GetModuleHandleW.restype = ctypes.c_void_p
        user32.SetWindowsHookExW.argtypes = [
            ctypes.c_int,
            low_level_proc,
            ctypes.c_void_p,
            ctypes.c_ulong,
        ]
        user32.SetWindowsHookExW.restype = ctypes.c_void_p
        user32.CallNextHookEx.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_size_t,
            ctypes.c_ssize_t,
        ]
        user32.CallNextHookEx.restype = ctypes.c_ssize_t
        _hook_thread_id = int(kernel32.GetCurrentThreadId())

        @low_level_proc
        def keyboard_proc(n_code: int, w_param: int, l_param: int) -> int:
            if n_code == HC_ACTION:
                event = ctypes.cast(
                    l_param,
                    ctypes.POINTER(KBDLLHOOKSTRUCT),
                ).contents
                if int(event.vkCode) == app.VK_NUMLOCK:
                    if int(w_param) in (WM_KEYDOWN, WM_SYSKEYDOWN):
                        threading.Thread(
                            target=on_numlock_press,
                            daemon=True,
                        ).start()
                    elif int(w_param) in (WM_KEYUP, WM_SYSKEYUP):
                        on_numlock_release()
                    return 1
            return int(
                user32.CallNextHookEx(
                    None,
                    n_code,
                    w_param,
                    l_param,
                )
            )

        _hook_callback = keyboard_proc
        hook = user32.SetWindowsHookExW(
            WH_KEYBOARD_LL,
            keyboard_proc,
            kernel32.GetModuleHandleW(None),
            0,
        )
        _hook_handle = int(hook) if hook else None
        _hook_ready.set()
        if not hook:
            return

        message = wintypes.MSG()
        try:
            while user32.GetMessageW(
                ctypes.byref(message),
                None,
                0,
                0,
            ) > 0:
                user32.TranslateMessage(ctypes.byref(message))
                user32.DispatchMessageW(ctypes.byref(message))
        finally:
            try:
                user32.UnhookWindowsHookEx(hook)
            except Exception:
                pass
            _hook_handle = None

    def register_native_hook() -> bool:
        global _hook_thread
        if os.name != "nt":
            return False
        _hook_ready.clear()
        _hook_thread = threading.Thread(
            target=native_hook_loop,
            name="NumLockHook",
            daemon=True,
        )
        _hook_thread.start()
        _hook_ready.wait(timeout=1.0)
        return bool(_hook_handle)

    def stop_native_hook() -> None:
        global _hook_thread, _hook_thread_id, _hook_callback
        if os.name == "nt" and _hook_thread_id:
            try:
                app._user32().PostThreadMessageW(
                    _hook_thread_id,
                    WM_QUIT,
                    0,
                    0,
                )
            except Exception:
                pass
        thread = _hook_thread
        if thread and thread.is_alive():
            thread.join(timeout=0.5)
        _hook_thread = None
        _hook_thread_id = None
        _hook_callback = None

    def register_hotkeys() -> None:
        try:
            import keyboard

            app.ensure_numlock_on()
            app._keyboard_module = keyboard
            if not register_native_hook():
                keyboard.hook_key(
                    "num lock",
                    on_numlock_event,
                    suppress=True,
                )
            keyboard.add_hotkey(
                "ctrl+shift+q",
                app.request_quit,
                suppress=False,
                trigger_on_release=True,
            )
        except Exception:
            app._keyboard_module = None

    def unregister_hotkeys() -> None:
        stop_native_hook()
        if app._keyboard_module is not None:
            try:
                app._keyboard_module.unhook_all()
            except Exception:
                try:
                    app._keyboard_module.unhook_all_hotkeys()
                except Exception:
                    pass
        with app._state_lock:
            app._numlock_down = False

    def on_shown() -> None:
        with app._state_lock:
            app._visible = True
        request_editor_focus()

    def on_loaded() -> None:
        request_editor_focus()

    def main() -> None:
        app._window = app.webview.create_window(
            title=app.APP_NAME,
            html=build_html(),
            width=540,
            height=650,
            min_size=(420, 430),
            js_api=app._api,
            resizable=True,
            easy_drag=False,
            confirm_close=False,
            on_top=True,
        )
        app._window.events.closing += app.on_closing
        app._window.events.shown += on_shown
        app._window.events.loaded += on_loaded
        register_hotkeys()
        try:
            app.webview.start(private_mode=True)
        finally:
            unregister_hotkeys()

    app.AppApi.window_focus_changed = api_window_focus_changed
    app.build_html = build_html
    app.set_renderer_focused = set_renderer_focused
    app.request_editor_focus = request_editor_focus
    app.show_window = show_window
    app.refocus_window = refocus_window
    app.hide_window = hide_window
    app.toggle_window = toggle_window
    app.on_numlock_press = on_numlock_press
    app.on_numlock_release = on_numlock_release
    app.on_numlock_event = on_numlock_event
    app.register_numlock_hook = register_native_hook
    app.stop_numlock_hook = stop_native_hook
    app.register_hotkeys = register_hotkeys
    app.unregister_hotkeys = unregister_hotkeys
    app.on_shown = on_shown
    app.on_loaded = on_loaded
    app.main = main
