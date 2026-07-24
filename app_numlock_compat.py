"""Classic NumLock Calculator key behavior for the keyboard-first shell.

A physical NumLock press is allowed to reach Windows, so the keyboard LED and
system toggle state follow the normal hardware path. NumLock Calc reacts to the
same press and then restores NumLock to the ON state. Synthetic events emitted
by that restoration are ignored by the calculator and therefore cannot toggle
the window a second time.
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
LLKHF_LOWER_IL_INJECTED = 0x00000002
LLKHF_INJECTED = 0x00000010
INJECTED_MASK = LLKHF_LOWER_IL_INJECTED | LLKHF_INJECTED
NUMLOCK_RESTORE_DELAY = 0.04
NUMLOCK_RELEASE_RECHECK_DELAY = 0.015
NUMLOCK_INJECTION_GUARD = 0.06

_hook_thread: threading.Thread | None = None
_hook_thread_id: int | None = None
_hook_handle: int | None = None
_hook_callback: Any = None
_hook_ready = threading.Event()
_restore_lock = threading.RLock()


def install(app: Any) -> None:
    """Replace only NumLock registration while preserving the stabilized UI."""

    app._restoring_numlock = False

    def restore_numlock_after_toggle(delay: float = NUMLOCK_RESTORE_DELAY) -> None:
        """Restore NumLock asynchronously after Windows processes the key press."""

        def restore() -> None:
            if delay > 0:
                time.sleep(delay)
            if app._quitting:
                return

            # Two physical callbacks (down and up) may schedule a restore. The
            # lock prevents both workers from observing OFF and injecting two
            # toggles, which would leave NumLock disabled again.
            with _restore_lock:
                if app._quitting:
                    return
                with app._state_lock:
                    app._restoring_numlock = True
                try:
                    app.ensure_numlock_on()
                    # keyboard's fallback hook can deliver injected events just
                    # after keybd_event returns. Keep the guard alive briefly.
                    time.sleep(NUMLOCK_INJECTION_GUARD)
                finally:
                    with app._state_lock:
                        app._restoring_numlock = False

        threading.Thread(
            target=restore,
            name="NumLockRestore",
            daemon=True,
        ).start()

    def on_numlock_press(_event: Any = None) -> None:
        with app._state_lock:
            if app._quitting or app._restoring_numlock or app._numlock_down:
                return
            app._numlock_down = True

        # React immediately, but do not consume the key. Windows will briefly
        # toggle NumLock OFF through its normal path; the worker restores it ON.
        app.toggle_window()
        app.restore_numlock_after_toggle(NUMLOCK_RESTORE_DELAY)

    def on_numlock_release(_event: Any = None) -> None:
        with app._state_lock:
            if app._restoring_numlock:
                return
            app._numlock_down = False

        # A second check after key-up covers slow keyboard drivers and remote
        # desktop sessions where the toggle state changes later than usual.
        app.restore_numlock_after_toggle(NUMLOCK_RELEASE_RECHECK_DELAY)

    def on_numlock_event(event: Any) -> None:
        with app._state_lock:
            if app._restoring_numlock:
                return
        event_type = getattr(event, "event_type", None)
        if event_type == "down":
            on_numlock_press(event)
        elif event_type == "up":
            on_numlock_release(event)

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
                    flags = int(event.flags)
                    if not (flags & INJECTED_MASK):
                        if int(w_param) in (WM_KEYDOWN, WM_SYSKEYDOWN):
                            threading.Thread(
                                target=on_numlock_press,
                                daemon=True,
                            ).start()
                        elif int(w_param) in (WM_KEYUP, WM_SYSKEYUP):
                            on_numlock_release()

                    # Important: pass both physical and injected events onward.
                    # Physical input briefly performs the genuine Windows
                    # toggle; injected restoration then turns NumLock back ON.
                    return call_next_hook(user32, n_code, w_param, l_param)

            return call_next_hook(user32, n_code, w_param, l_param)

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

            # Normalize startup state before installing the hook, so this
            # synthetic event cannot be mistaken for a user invocation.
            app.ensure_numlock_on()
            app._keyboard_module = keyboard
            if not register_native_hook():
                # Fallback must also let the genuine Windows toggle happen.
                # _restoring_numlock prevents the synthetic re-enable event
                # from opening or hiding the application again.
                keyboard.hook_key(
                    "num lock",
                    on_numlock_event,
                    suppress=False,
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
            app._restoring_numlock = False

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
