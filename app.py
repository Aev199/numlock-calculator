"""NumLock Calc: pywebview launcher for the portable Windows build."""

from __future__ import annotations

import ctypes
import json
import os
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any

import webview


APP_NAME = "NumLock Calc"
DATA_FILENAME = "numlock-calc-data.json"
VK_NUMLOCK = 0x90
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
NUMLOCK_SCAN_CODE = 0x45


def resource_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent


def application_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


BASE_DIR = resource_dir()
RENDERER_DIR = BASE_DIR / "renderer"
DATA_FILE = application_dir() / DATA_FILENAME


class Storage:
    """Small thread-safe JSON key/value store located next to the executable."""

    def __init__(self, filepath: Path):
        self._filepath = filepath
        self._data: dict[str, Any] = {}
        self._lock = threading.RLock()
        self._load()

    def _load(self) -> None:
        with self._lock:
            if not self._filepath.exists():
                return
            try:
                raw = json.loads(self._filepath.read_text(encoding="utf-8"))
                self._data = raw if isinstance(raw, dict) else {}
            except (OSError, json.JSONDecodeError):
                self._data = {}

    def _save(self) -> None:
        with self._lock:
            self._filepath.parent.mkdir(parents=True, exist_ok=True)
            payload = json.dumps(self._data, ensure_ascii=False, indent=2)
            fd, temp_name = tempfile.mkstemp(
                prefix=f".{self._filepath.stem}-",
                suffix=".tmp",
                dir=str(self._filepath.parent),
                text=True,
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp_name, self._filepath)
            except Exception:
                try:
                    os.unlink(temp_name)
                except OSError:
                    pass
                raise

    def get(self, key: str) -> Any:
        with self._lock:
            return self._data.get(key)

    def set(self, key: str, value: Any) -> bool:
        with self._lock:
            self._data[key] = value
            self._save()
        return True

    def remove(self, key: str) -> bool:
        with self._lock:
            self._data.pop(key, None)
            self._save()
        return True

    def clear(self) -> bool:
        with self._lock:
            self._data.clear()
            self._save()
        return True


class AppApi:
    """Methods exposed to JavaScript through pywebview's promise-based bridge."""

    def __init__(self, storage: Storage):
        self._storage = storage
        self.window: webview.Window | None = None

    def storage_get(self, key: str) -> Any:
        return self._storage.get(key)

    def storage_set(self, key: str, value: Any) -> bool:
        return self._storage.set(key, value)

    def storage_remove(self, key: str) -> bool:
        return self._storage.remove(key)

    def storage_clear(self) -> bool:
        return self._storage.clear()

    def quit_app(self) -> bool:
        request_quit()
        return True


def build_html() -> str:
    html = (RENDERER_DIR / "index.html").read_text(encoding="utf-8")
    css = (RENDERER_DIR / "style.css").read_text(encoding="utf-8")
    core_js = (RENDERER_DIR / "calc-core.js").read_text(encoding="utf-8")
    app_js = (RENDERER_DIR / "script.js").read_text(encoding="utf-8")

    html = html.replace(
        '<link rel="stylesheet" href="style.css">',
        f"<style>\n{css}\n</style>",
    )
    html = html.replace(
        '<script src="calc-core.js"></script>',
        f"<script>\n{core_js}\n</script>",
    )
    html = html.replace(
        '<script src="script.js"></script>',
        f"<script>\n{app_js}\n</script>",
    )
    html = html.replace(
        "<head>",
        "<head>\n<script>window.__NUMLOCK_PYWEBVIEW__ = true;</script>",
        1,
    )
    return html


_window: webview.Window | None = None
_visible = True
_quitting = False
_numlock_down = False
_keyboard_module: Any = None
_state_lock = threading.RLock()
_api = AppApi(Storage(DATA_FILE))


def numlock_is_on(user32: Any | None = None) -> bool:
    """Return the Windows toggle state. Non-Windows test hosts are treated as on."""

    if os.name != "nt" and user32 is None:
        return True
    api = user32 if user32 is not None else ctypes.windll.user32
    return bool(api.GetKeyState(VK_NUMLOCK) & 0x0001)


def ensure_numlock_on(user32: Any | None = None) -> bool:
    """Turn NumLock on before installing the suppressing global hook."""

    if os.name != "nt" and user32 is None:
        return True
    api = user32 if user32 is not None else ctypes.windll.user32
    if numlock_is_on(api):
        return True

    api.keybd_event(VK_NUMLOCK, NUMLOCK_SCAN_CODE, KEYEVENTF_EXTENDEDKEY, 0)
    api.keybd_event(
        VK_NUMLOCK,
        NUMLOCK_SCAN_CODE,
        KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP,
        0,
    )
    return numlock_is_on(api)


def toggle_window() -> None:
    """Toggle visibility exactly once for one accepted NumLock press."""

    global _visible
    if _window is None or _quitting:
        return

    with _state_lock:
        should_hide = _visible

    try:
        if should_hide:
            _window.hide()
            with _state_lock:
                _visible = False
        else:
            _window.show()
            _window.restore()
            with _state_lock:
                _visible = True
    except Exception:
        return


def on_numlock_press(_event: Any = None) -> None:
    """Accept only the first KEY_DOWN until the matching KEY_UP arrives."""

    global _numlock_down
    with _state_lock:
        if _quitting or _numlock_down:
            return
        _numlock_down = True
    toggle_window()


def on_numlock_release(_event: Any = None) -> None:
    global _numlock_down
    with _state_lock:
        _numlock_down = False


def on_numlock_event(event: Any) -> None:
    """Dispatch one suppressed low-level NumLock event."""

    event_type = getattr(event, "event_type", None)
    if event_type == "down":
        on_numlock_press(event)
    elif event_type == "up":
        on_numlock_release(event)


def on_closing() -> bool:
    global _visible
    if _quitting:
        return True
    try:
        if _window is not None:
            _window.hide()
    finally:
        with _state_lock:
            _visible = False
    return False


def on_shown() -> None:
    global _visible
    with _state_lock:
        _visible = True


def unregister_hotkeys() -> None:
    global _numlock_down
    if _keyboard_module is None:
        return
    try:
        _keyboard_module.unhook_all()
    except Exception:
        try:
            _keyboard_module.unhook_all_hotkeys()
        except Exception:
            pass
    finally:
        with _state_lock:
            _numlock_down = False


def request_quit() -> None:
    global _quitting
    if _quitting:
        return
    _quitting = True
    unregister_hotkeys()
    if _window is not None:
        try:
            _window.destroy()
        except Exception:
            pass


def register_hotkeys() -> None:
    global _keyboard_module
    try:
        import keyboard

        ensure_numlock_on()
        _keyboard_module = keyboard
        keyboard.hook_key("num lock", on_numlock_event, suppress=True)
        keyboard.add_hotkey(
            "ctrl+shift+q",
            request_quit,
            suppress=False,
            trigger_on_release=True,
        )
    except Exception:
        _keyboard_module = None


def main() -> None:
    global _window

    _window = webview.create_window(
        title=APP_NAME,
        html=build_html(),
        width=480,
        height=680,
        min_size=(380, 550),
        js_api=_api,
        resizable=True,
        easy_drag=False,
        confirm_close=False,
        on_top=True,
    )
    _api.window = _window
    _window.events.closing += on_closing
    _window.events.shown += on_shown

    register_hotkeys()
    try:
        webview.start(private_mode=True)
    finally:
        unregister_hotkeys()


if __name__ == "__main__":
    main()
