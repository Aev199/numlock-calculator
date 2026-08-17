"""Deterministic classic NumLock behavior for the keyboard-first shell.

The physical NumLock key is used as an application trigger and is therefore
suppressed by the native low-level hook.  The visible lock-key blink is
reproduced with our own injected events: one toggle to OFF, a short pause, and
one toggle back to ON.  Because the physical event never changes Windows'
keyboard state, the synthetic ON event cannot race with a still-held key.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import threading
import time
from typing import Any

from hotkey_config import DEFAULT_HOTKEY, validate_hotkey

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
INPUT_KEYBOARD = 1
NUMLOCK_BLINK_SECONDS = 0.055
NUMLOCK_INJECTION_TAG = 0x4E4C4341

# The navigation cluster and the numeric keypad share logical Windows key
# names when NumLock is off.  keyboard.add_hotkey therefore cannot distinguish
# dedicated PageDown from NumPad 3, Home from NumPad 7, and so on.
KEYPAD_NAVIGATION_ALIASES = frozenset(
    {
        "insert",
        "delete",
        "home",
        "end",
        "page up",
        "page down",
        "left",
        "right",
        "up",
        "down",
    }
)
MODIFIER_EVENT_NAMES = {
    "ctrl": "ctrl",
    "control": "ctrl",
    "left ctrl": "ctrl",
    "right ctrl": "ctrl",
    "left control": "ctrl",
    "right control": "ctrl",
    "alt": "alt",
    "left alt": "alt",
    "right alt": "alt",
    "shift": "shift",
    "left shift": "shift",
    "right shift": "shift",
    "windows": "windows",
    "win": "windows",
    "left windows": "windows",
    "right windows": "windows",
    "left win": "windows",
    "right win": "windows",
}

_hook_thread: threading.Thread | None = None
_hook_thread_id: int | None = None
_hook_handle: int | None = None
_hook_callback: Any = None
_hook_ready = threading.Event()
_inject_lock = threading.RLock()


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", INPUT_UNION)]


def install(app: Any) -> None:
    """Replace NumLock registration while preserving the stabilized UI."""

    app._restoring_numlock = False
    app._numlock_cycle_active = False
    app._numlock_hook_mode = "none"
    saved_hotkey = validate_hotkey(
        getattr(getattr(app, "_api", None), "_ui_settings", {}).get(
            "global_hotkey",
            DEFAULT_HOTKEY,
        )
    )
    app._global_hotkey = saved_hotkey.hotkey if saved_hotkey.ok else DEFAULT_HOTKEY
    app._global_hotkey_display = (
        saved_hotkey.display if saved_hotkey.ok else validate_hotkey(DEFAULT_HOTKEY).display
    )
    app._global_hotkey_handle = None
    app._hotkeys_started = False
    app._hotkey_registration_ok = False
    app._hotkey_registration_error = ""

    def send_numlock_toggle() -> bool:
        """Send one complete injected NumLock key cycle."""

        if os.name != "nt":
            return True
        user32 = app._user32()
        try:
            user32.SendInput.argtypes = [
                wintypes.UINT,
                ctypes.POINTER(INPUT),
                ctypes.c_int,
            ]
            user32.SendInput.restype = wintypes.UINT
            events = (INPUT * 2)(
                INPUT(
                    type=INPUT_KEYBOARD,
                    ki=KEYBDINPUT(
                        app.VK_NUMLOCK,
                        app.NUMLOCK_SCAN_CODE,
                        app.KEYEVENTF_EXTENDEDKEY,
                        0,
                        NUMLOCK_INJECTION_TAG,
                    ),
                ),
                INPUT(
                    type=INPUT_KEYBOARD,
                    ki=KEYBDINPUT(
                        app.VK_NUMLOCK,
                        app.NUMLOCK_SCAN_CODE,
                        app.KEYEVENTF_EXTENDEDKEY | app.KEYEVENTF_KEYUP,
                        0,
                        NUMLOCK_INJECTION_TAG,
                    ),
                ),
            )
            if int(user32.SendInput(2, events, ctypes.sizeof(INPUT))) == 2:
                return True
        except Exception:
            pass

        # Compatibility fallback for systems where SendInput is unavailable.
        try:
            user32.keybd_event(
                app.VK_NUMLOCK,
                app.NUMLOCK_SCAN_CODE,
                app.KEYEVENTF_EXTENDEDKEY,
                NUMLOCK_INJECTION_TAG,
            )
            user32.keybd_event(
                app.VK_NUMLOCK,
                app.NUMLOCK_SCAN_CODE,
                app.KEYEVENTF_EXTENDEDKEY | app.KEYEVENTF_KEYUP,
                NUMLOCK_INJECTION_TAG,
            )
            return True
        except Exception:
            return False

    def run_blink_cycle(started_on: bool) -> None:
        """Produce OFF -> ON, or only ON when startup state was already OFF."""

        with _inject_lock:
            if app._quitting:
                return
            with app._state_lock:
                app._restoring_numlock = True
                app._numlock_cycle_active = True
            try:
                if started_on:
                    off_sent = send_numlock_toggle()
                    if off_sent:
                        time.sleep(NUMLOCK_BLINK_SECONDS)
                        send_numlock_toggle()
                else:
                    # Normalize an unexpected OFF state immediately.
                    send_numlock_toggle()
            finally:
                with app._state_lock:
                    app._restoring_numlock = False
                    app._numlock_cycle_active = False

    def start_blink_cycle(started_on: bool) -> None:
        if app._numlock_hook_mode != "native":
            # The library fallback suppresses every NumLock event, including
            # injected ones, so it cannot safely reproduce the LED blink.
            return
        threading.Thread(
            target=run_blink_cycle,
            args=(bool(started_on),),
            name="NumLockBlink",
            daemon=True,
        ).start()

    def on_global_hotkey() -> None:
        """Toggle asynchronously so the keyboard hook is never blocked by UI work."""

        with app._state_lock:
            if app._quitting:
                return
        threading.Thread(
            target=app.toggle_window,
            name="NumCalcGlobalHotkey",
            daemon=True,
        ).start()

    def canonical_hotkey_event_name(event: Any) -> str:
        """Normalize a keyboard event without losing its keypad identity."""

        name = " ".join(
            str(getattr(event, "name", "") or "")
            .strip()
            .lower()
            .replace("_", " ")
            .split()
        )
        aliases = {
            "pageup": "page up",
            "pagedown": "page down",
            "arrow left": "left",
            "arrow right": "right",
            "arrow up": "up",
            "arrow down": "down",
        }
        return aliases.get(name, name)

    def register_physical_navigation_hotkey(
        keyboard_module: Any,
        hotkey: str,
    ) -> Any:
        """Register a navigation hotkey while excluding keypad aliases."""

        parts = tuple(part.strip() for part in hotkey.split("+") if part.strip())
        required_modifiers = frozenset(parts[:-1])
        main_key = parts[-1]
        pressed_modifiers: set[str] = set()
        active = False

        def handle_event(event: Any) -> bool:
            nonlocal active

            event_type = str(getattr(event, "event_type", "") or "").lower()
            name = canonical_hotkey_event_name(event)
            modifier = MODIFIER_EVENT_NAMES.get(name)
            if modifier:
                if event_type == "down":
                    pressed_modifiers.add(modifier)
                elif event_type == "up":
                    pressed_modifiers.discard(modifier)
                return True

            if name != main_key:
                return True

            # This is the essential distinction: NumPad 3 can be reported as
            # PageDown, but keyboard marks it as a keypad event.
            if bool(getattr(event, "is_keypad", False)):
                return True

            if event_type == "down":
                if pressed_modifiers == required_modifiers:
                    active = True
                    return False
                return True

            if event_type == "up" and active:
                active = False
                on_global_hotkey()
                return False
            return True

        return keyboard_module.hook(handle_event, suppress=True)

    def restore_numlock_after_toggle(_delay: float = 0.0) -> None:
        """Compatibility entry point retained for existing tests/callers."""

        start_blink_cycle(True)

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
            if app._quitting or app._numlock_down:
                return
            app._numlock_down = True

        # UI work must not block the Windows low-level hook callback.
        threading.Thread(target=app.toggle_window, daemon=True).start()
        start_blink_cycle(bool(was_on_before))

    def on_numlock_release(_event: Any = None) -> None:
        with app._state_lock:
            app._numlock_down = False

    def on_numlock_event(event: Any) -> None:
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
                    if flags & INJECTED_MASK:
                        # Our synthetic OFF/ON events must reach Windows.
                        return call_next_hook(user32, n_code, w_param, l_param)

                    if int(w_param) in (WM_KEYDOWN, WM_SYSKEYDOWN):
                        with app._state_lock:
                            repeated = bool(app._numlock_down)
                        if not repeated:
                            started_on = bool(
                                user32.GetKeyState(app.VK_NUMLOCK) & 0x0001
                            )
                            on_numlock_press(was_on_before=started_on)
                    elif int(w_param) in (WM_KEYUP, WM_SYSKEYUP):
                        on_numlock_release()

                    # Suppress both parts of the physical key cycle.  This is the
                    # key difference from the racy implementation: Windows' state
                    # is changed only by our ordered injected events.
                    return 1

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
        app._hotkeys_started = True
        app._hotkey_registration_ok = False
        app._hotkey_registration_error = ""
        app._global_hotkey_handle = None
        validation = validate_hotkey(getattr(app, "_global_hotkey", DEFAULT_HOTKEY))
        if not validation.ok:
            validation = validate_hotkey(DEFAULT_HOTKEY)
            app._global_hotkey = validation.hotkey
        app._global_hotkey_display = validation.display

        try:
            import keyboard
        except Exception as error:
            app._keyboard_module = None
            app._hotkey_registration_error = f"Не удалось подключить глобальную клавишу: {error}"
            return

        app._keyboard_module = keyboard
        registered = False
        if validation.hotkey == DEFAULT_HOTKEY:
            try:
                app.ensure_numlock_on()
            except Exception:
                pass

            native_ok = register_native_hook()
            app._numlock_hook_mode = "native" if native_ok else "none"
            if native_ok:
                registered = True
            else:
                # Safe fallback: keep NumLock ON and use the key only as a trigger.
                # The LED blink is omitted because keyboard suppresses injected events
                # too, but the numeric keypad cannot become arrows.
                try:
                    keyboard.hook_key(
                        "num lock",
                        on_numlock_event,
                        suppress=True,
                    )
                    app._numlock_hook_mode = "fallback-suppressed"
                    registered = True
                except Exception as error:
                    app._hotkey_registration_error = (
                        f"Не удалось зарегистрировать NumLock: {error}"
                    )
        else:
            try:
                main_key = validation.hotkey.rsplit("+", 1)[-1]
                if os.name == "nt" and main_key in KEYPAD_NAVIGATION_ALIASES:
                    app._global_hotkey_handle = register_physical_navigation_hotkey(
                        keyboard,
                        validation.hotkey,
                    )
                else:
                    app._global_hotkey_handle = keyboard.add_hotkey(
                        validation.hotkey,
                        on_global_hotkey,
                        suppress=True,
                        trigger_on_release=True,
                    )
                registered = True
            except Exception as error:
                app._hotkey_registration_error = (
                    f"Не удалось зарегистрировать {validation.display}: {error}"
                )

        if not getattr(app, "_suppress_emergency_hotkey", False):
            try:
                keyboard.add_hotkey(
                    "ctrl+shift+q",
                    app.request_quit,
                    suppress=False,
                    trigger_on_release=True,
                )
            except Exception:
                pass
        app._hotkey_registration_ok = registered

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
            app._numlock_cycle_active = False
            app._numlock_hook_mode = "none"
        app._global_hotkey_handle = None
        app._hotkeys_started = False
        app._hotkey_registration_ok = False

    def configure_global_hotkey(requested: str) -> dict[str, Any]:
        validation = validate_hotkey(requested)
        if not validation.ok:
            return validation.as_dict()

        previous = getattr(app, "_global_hotkey", DEFAULT_HOTKEY)
        if previous == validation.hotkey:
            return validation.as_dict()

        was_running = bool(getattr(app, "_hotkeys_started", False))
        if was_running:
            unregister_hotkeys()
        app._global_hotkey = validation.hotkey
        app._global_hotkey_display = validation.display

        if was_running:
            register_hotkeys()
            if os.name == "nt" and not app._hotkey_registration_ok:
                error = app._hotkey_registration_error or "Не удалось зарегистрировать клавишу"
                unregister_hotkeys()
                app._global_hotkey = previous
                previous_info = validate_hotkey(previous)
                app._global_hotkey_display = previous_info.display
                register_hotkeys()
                return {
                    "ok": False,
                    "hotkey": previous,
                    "display": previous_info.display,
                    "error": error,
                    "warning": "Предыдущая комбинация восстановлена",
                }
        return validation.as_dict()

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

    app.send_numlock_toggle = send_numlock_toggle
    app.start_numlock_blink = start_blink_cycle
    app.restore_numlock_after_toggle = restore_numlock_after_toggle
    app.on_numlock_press = on_numlock_press
    app.on_numlock_release = on_numlock_release
    app.on_numlock_event = on_numlock_event
    app.register_numlock_hook = register_native_hook
    app.stop_numlock_hook = stop_native_hook
    app.canonical_hotkey_event_name = canonical_hotkey_event_name
    app.register_physical_navigation_hotkey = register_physical_navigation_hotkey
    app.register_hotkeys = register_hotkeys
    app.unregister_hotkeys = unregister_hotkeys
    app.configure_global_hotkey = configure_global_hotkey
    app.get_global_hotkey = lambda: validate_hotkey(
        getattr(app, "_global_hotkey", DEFAULT_HOTKEY)
    ).as_dict()
    app.main = main
