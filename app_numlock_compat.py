"""Classic NumLock Calculator key behavior for the keyboard-first shell.

The physical NumLock event is allowed to reach Windows. The calculator reacts
immediately, then the native hook thread verifies the resulting toggle state
and restores NumLock to ON. Reading and restoring on the hook thread avoids
stale GetKeyState values from unrelated worker threads.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import threading
import time
from typing import Any

WH_KEYBOARD_LL = 13
HC_ACTION = 0
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_QUIT = 0x0012
WM_APP_RESTORE_NUMLOCK = 0x8001
LLKHF_LOWER_IL_INJECTED = 0x00000002
LLKHF_INJECTED = 0x00000010
INJECTED_MASK = LLKHF_LOWER_IL_INJECTED | LLKHF_INJECTED
NUMLOCK_RESTORE_DELAY = 0.045
NUMLOCK_RELEASE_RECHECK_DELAY = 0.010

_hook_thread: threading.Thread | None = None
_hook_thread_id: int | None = None
_hook_handle: int | None = None
_hook_callback: Any = None
_hook_ready = threading.Event()
_restore_lock = threading.RLock()


def install(app: Any) -> None:
    """Replace NumLock registration while preserving the stabilized UI."""

    app._restoring_numlock = False
    app._numlock_restore_needed = False
    app._numlock_hook_mode = "none"

    def post_restore_message(delay: float = NUMLOCK_RESTORE_DELAY) -> None:
        """Ask the native hook thread to check and restore NumLock."""

        def post() -> None:
            if delay > 0:
                time.sleep(delay)
            if app._quitting:
                return

            thread_id = _hook_thread_id
            if os.name == "nt" and thread_id:
                try:
                    app._user32().PostThreadMessageW(
                        thread_id,
                        WM_APP_RESTORE_NUMLOCK,
                        0,
                        0,
                    )
                    return
                except Exception:
                    pass

            # This path is used only by the library fallback. Its hook suppresses
            # the physical system toggle, so NumLock should already remain ON.
            try:
                app.ensure_numlock_on()
            except Exception:
                pass

        threading.Thread(
            target=post,
            name="NumLockRestoreRequest",
            daemon=True,
        ).start()

    def restore_numlock_after_toggle(delay: float = NUMLOCK_RESTORE_DELAY) -> None:
        post_restore_message(delay)

    def on_numlock_press(
        _event: Any = None,
        was_on_before: bool | None = None,
    ) -> None:
        if was_on_before is None:
            try:
                was_on_before = bool(app.numlock_is_on())
            except Exception:
                was_on_before = True

        with app._state_lock:
            if app._quitting or app._restoring_numlock or app._numlock_down:
                return
            app._numlock_down = True
            # If NumLock was ON before the genuine press, Windows is about to
            # switch it OFF and the hook thread must switch it back ON.
            app._numlock_restore_needed = bool(was_on_before)

        app.toggle_window()
        if was_on_before:
            app.restore_numlock_after_toggle(NUMLOCK_RESTORE_DELAY)

    def on_numlock_release(_event: Any = None) -> None:
        with app._state_lock:
            app._numlock_down = False
            restore_needed = bool(app._numlock_restore_needed)

        if restore_needed:
            # A second idempotent check covers slow drivers and remote sessions.
            app.restore_numlock_after_toggle(NUMLOCK_RELEASE_RECHECK_DELAY)

    def on_numlock_event(event: Any) -> None:
        event_type = getattr(event, "event_type", None)
        if event_type == "up":
            on_numlock_release(event)
            return

        with app._state_lock:
            if app._restoring_numlock:
                return
        if event_type == "down":
            on_numlock_press(event)

    def call_next_hook(
        user32: Any,
        n_code: int,
        w_param: int,
        l_param: int,
    ) -> int:
        return int(
            user32.CallNextHookEx(
                _hook_handle,
                n_code,
                w_param,
                l_param,
            )
        )

    def restore_on_hook_thread(user32: Any) -> None:
        """Restore toggle state from the hook message-loop thread itself."""

        with _restore_lock:
            if app._quitting:
                return

            try:
                is_on = bool(user32.GetKeyState(app.VK_NUMLOCK) & 0x0001)
            except Exception:
                is_on = True

            if not is_on:
                with app._state_lock:
                    app._restoring_numlock = True
                try:
                    # keybd_event produces LLKHF_INJECTED events. The hook passes
                    # them to Windows but never treats them as a user invocation.
                    user32.keybd_event(
                        app.VK_NUMLOCK,
                        app.NUMLOCK_SCAN_CODE,
                        app.KEYEVENTF_EXTENDEDKEY,
                        0,
                    )
                    user32.keybd_event(
                        app.VK_NUMLOCK,
                        app.NUMLOCK_SCAN_CODE,
                        app.KEYEVENTF_EXTENDEDKEY | app.KEYEVENTF_KEYUP,
                        0,
                    )
                finally:
                    with app._state_lock:
                        app._restoring_numlock = False

            with app._state_lock:
                app._numlock_restore_needed = False

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
        user32.PostThreadMessageW.argtypes = [
            ctypes.c_ulong,
            ctypes.c_uint,
            ctypes.c_size_t,
            ctypes.c_ssize_t,
        ]
        user32.PostThreadMessageW.restype = wintypes.BOOL
        _hook_thread_id = int(kernel32.GetCurrentThreadId())

        @low_level_proc
        def keyboard_proc(n_code: int, w_param: int, l_param: int) -> int:
            if n_code == HC_ACTION:
                event = ctypes.cast(
                    l_param,
                    ctypes.POINTER(KBDLLHOOKSTRUCT),
                ).contents
                if int(event.vkCode) == app.VK_NUMLOCK:
                    flags = int(event.flags)
                    if not (flags & INJECTED_MASK):
                        if int(w_param) in (WM_KEYDOWN, WM_SYSKEYDOWN):
                            # At this point Windows has not applied the physical
                            # toggle yet, so this is the true pre-press state.
                            was_on = bool(
                                user32.GetKeyState(app.VK_NUMLOCK) & 0x0001
                            )
                            on_numlock_press(was_on_before=was_on)
                        elif int(w_param) in (WM_KEYUP, WM_SYSKEYUP):
                            on_numlock_release()

                    # Both genuine and injected events must reach Windows: the
                    # genuine event creates the brief OFF state, and the injected
                    # event restores ON.
                    return call_next_hook(user32, n_code, w_param, l_param)

            return call_next_hook(user32, n_code, w_param, l_param)

        _hook_callback = keyboard_proc
        # Passing NULL is the standard and most compatible choice for a
        # WH_KEYBOARD_LL callback hosted by the current Python process.
        hook = user32.SetWindowsHookExW(
            WH_KEYBOARD_LL,
            keyboard_proc,
            None,
            0,
        )
        _hook_handle = int(hook) if hook else None
        _hook_ready.set()
        if not hook:
            return

        message = wintypes.MSG()
        try:
            while True:
                result = user32.GetMessageW(
                    ctypes.byref(message),
                    None,
                    0,
                    0,
                )
                if result <= 0:
                    break
                if int(message.message) == WM_APP_RESTORE_NUMLOCK:
                    restore_on_hook_thread(user32)
                    continue
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
        # The native hook must not depend on the optional keyboard package used
        # for Ctrl+Shift+Q and clipboard insertion.
        try:
            app.ensure_numlock_on()
        except Exception:
            pass

        native_ok = register_native_hook()
        app._numlock_hook_mode = "native" if native_ok else "none"

        try:
            import keyboard
        except Exception:
            app._keyboard_module = None
            return

        app._keyboard_module = keyboard
        if not native_ok:
            # A reliable classic blink cannot be implemented without the native
            # thread. Suppress the physical toggle so NumLock at least remains ON
            # while the calculator still responds.
            keyboard.hook_key(
                "num lock",
                on_numlock_event,
                suppress=True,
            )
            app._numlock_hook_mode = "fallback-suppressed"

        try:
            keyboard.add_hotkey(
                "ctrl+shift+q",
                app.request_quit,
                suppress=False,
                trigger_on_release=True,
            )
        except Exception:
            pass

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
            app._restoring_numlock = False
            app._numlock_restore_needed = False
            app._numlock_hook_mode = "none"

    def main() -> None:
        app._window = app.webview.create_window(
            title=app.APP_NAME,
            html=app.build_html(),
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
        app._window.events.shown += app.on_shown
        app._window.events.loaded += app.on_loaded
        register_hotkeys()
        try:
            app.webview.start(private_mode=True)
        finally:
            unregister_hotkeys()

    app.restore_numlock_after_toggle = restore_numlock_after_toggle
    app.on_numlock_press = on_numlock_press
    app.on_numlock_release = on_numlock_release
    app.on_numlock_event = on_numlock_event
    app.register_numlock_hook = register_native_hook
    app.stop_numlock_hook = stop_native_hook
    app.register_hotkeys = register_hotkeys
    app.unregister_hotkeys = unregister_hotkeys
    app.main = main
