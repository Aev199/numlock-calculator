"""Keyboard-first NumLock Calc desktop shell."""

from __future__ import annotations

import ctypes
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

import webview

from calc_engine import (
    CalculatorSession,
    DIMENSIONLESS,
    EngineSettings,
    make_history_entry,
    normalize_expression,
    serialize_dimensions,
)
from hotkey_config import DEFAULT_HOTKEY, validate_hotkey


APP_NAME = "NumLock Calc"
# Kept only as the migration source for installations predating the durable
# %LOCALAPPDATA%\NumCalc\data.json store.
LEGACY_DATA_FILENAME = "numlock-calc-data.json"
DATA_FILENAME = LEGACY_DATA_FILENAME
MAX_HISTORY = 500
VK_NUMLOCK = 0x90
NUMLOCK_SCAN_CODE = 0x45
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002


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
DATA_FILE: Path | None = None


class Storage:
    """Thread-safe JSON store used by the selected production data path."""

    def __init__(self, filepath: Path | None):
        self._filepath = Path(filepath) if filepath is not None else None
        self._data: dict[str, Any] = {}
        self._lock = threading.RLock()
        self._load()

    def _load(self) -> None:
        with self._lock:
            if self._filepath is None:
                return
            if not self._filepath.exists():
                return
            try:
                raw = json.loads(self._filepath.read_text(encoding="utf-8"))
                self._data = raw if isinstance(raw, dict) else {}
            except (OSError, json.JSONDecodeError):
                self._data = {}

    def _save(self) -> None:
        with self._lock:
            if self._filepath is None:
                return
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

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = value
            self._save()

    def update(self, values: dict[str, Any]) -> None:
        with self._lock:
            self._data.update(values)
            self._save()


class AppApi:
    """Promise-based methods exposed to the renderer by pywebview."""

    def __init__(self, storage: Storage):
        self._storage = storage
        state = storage.get("engine_state", {})
        settings = EngineSettings.from_mapping(state.get("settings") if isinstance(state, dict) else None)
        variables = state.get("variables", {}) if isinstance(state, dict) else {}
        memories = state.get("memories", []) if isinstance(state, dict) else []
        self._session = CalculatorSession(settings, variables, memories)
        if isinstance(state, dict):
            self._session.restore_ans(state.get("ans"))
        saved_history = storage.get("history", [])
        self._history: list[dict[str, Any]] = saved_history if isinstance(saved_history, list) else []
        if not self._history:
            legacy_history = storage.get("nlcalc_history")
            if isinstance(legacy_history, str):
                try:
                    legacy_history = json.loads(legacy_history)
                except json.JSONDecodeError:
                    legacy_history = []
            if isinstance(legacy_history, list):
                self._history = [
                    {
                        "id": f"legacy-{index}",
                        "expression": str(item.get("expr", "")),
                        "normalized_expression": normalize_expression(
                            str(item.get("expr", ""))
                        ),
                        "result": str(item.get("res", "")),
                        "raw_value": None,
                        "unit": None,
                        "dimensions": serialize_dimensions(DIMENSIONLESS),
                        "angle_mode": "DEG",
                        "number_base": "DEC",
                        "created_at": "",
                    }
                    for index, item in enumerate(legacy_history)
                    if isinstance(item, dict) and item.get("expr") is not None
                ]
        self._history = [
            self._normalize_history_item(item, index)
            for index, item in enumerate(self._history)
            if isinstance(item, dict)
        ][:MAX_HISTORY]
        saved_ui = storage.get("ui_settings", {})
        self._ui_settings = saved_ui if isinstance(saved_ui, dict) else {}
        if "theme" not in self._ui_settings:
            self._ui_settings["theme"] = "light" if storage.get("nlcalc_theme") == "light" else "dark"
        saved_hotkey = validate_hotkey(self._ui_settings.get("global_hotkey", DEFAULT_HOTKEY))
        self._ui_settings["global_hotkey"] = (
            saved_hotkey.hotkey if saved_hotkey.ok else DEFAULT_HOTKEY
        )
        self._sequence = len(self._history)
        self._lock = threading.RLock()

    @staticmethod
    def _normalize_history_item(
        item: dict[str, Any],
        index: int,
    ) -> dict[str, Any]:
        """Fill the stage-2 history fields while keeping old data readable."""

        normalized_item = dict(item)
        expression = str(
            normalized_item.get(
                "expression",
                normalized_item.get("source_expression", ""),
            )
            or ""
        ).strip()
        normalized = str(
            normalized_item.get(
                "normalized_expression",
                normalized_item.get("normalized", ""),
            )
            or ""
        ).strip()
        if not normalized:
            normalized = normalize_expression(expression).strip()

        normalized_item["id"] = str(normalized_item.get("id") or f"history-{index}")
        normalized_item["expression"] = expression
        normalized_item["source_expression"] = expression
        normalized_item["normalized_expression"] = normalized
        normalized_item["normalized"] = normalized
        normalized_item["result"] = str(normalized_item.get("result", "") or "")
        normalized_item.setdefault("raw_value", None)
        normalized_item.setdefault("unit", None)
        dimensions = normalized_item.get("dimensions")
        if not isinstance(dimensions, list) or len(dimensions) != 4:
            normalized_item["dimensions"] = serialize_dimensions(DIMENSIONLESS)
        normalized_item.setdefault("angle_mode", "DEG")
        normalized_item.setdefault("number_base", "DEC")
        normalized_item.setdefault("precision", 12)
        normalized_item.setdefault("number_format", "auto")
        normalized_item.setdefault("decimal_separator", ".")
        normalized_item.setdefault("created_at", "")
        return normalized_item

    def _persist(self) -> None:
        self._storage.update({
            "engine_state": self._session.export_state(),
            "history": self._history[:MAX_HISTORY],
        })

    def bootstrap(self) -> dict[str, Any]:
        with self._lock:
            return {
                "settings": self._session.settings.as_dict(),
                "history": self._history[:MAX_HISTORY],
                "variables": {
                    key: self._session.format_quantity(value)
                    for key, value in sorted(self._session.variables.items())
                },
                "memories": [self._session.format_quantity(value) for value in self._session.memories],
                "suggestions": self._session.suggestions(),
                "ui_settings": dict(self._ui_settings),
            }

    def preview(self, expression: str) -> dict[str, Any]:
        with self._lock:
            return self._session.evaluate(expression, commit=False).as_dict()

    def commit(self, expression: str) -> dict[str, Any]:
        with self._lock:
            evaluation = self._session.evaluate(expression, commit=True)
            response = evaluation.as_dict()
            if evaluation.ok and expression.strip():
                self._sequence += 1
                entry = make_history_entry(evaluation, self._session.settings, self._sequence).as_dict()
                self._history.insert(0, entry)
                self._history = self._history[:MAX_HISTORY]
                response["history_entry"] = entry
                self._persist()
            return response

    def commit_and_insert(self, expression: str) -> dict[str, Any]:
        response = self.commit(expression)
        if response.get("ok") and response.get("result"):
            threading.Thread(
                target=insert_text_into_previous_window,
                args=(str(response["result"]),),
                daemon=True,
            ).start()
        return response

    def set_settings(self, settings: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            updated = self._session.set_settings(settings)
            self._persist()
            return updated.as_dict()

    def suggestions(self, query: str = "") -> list[dict[str, str]]:
        with self._lock:
            return self._session.suggestions(query)

    def set_ui_settings(self, settings: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            allowed = {"theme", "compact_history"}
            for key, value in settings.items():
                if key in allowed:
                    self._ui_settings[key] = value
            self._storage.set("ui_settings", self._ui_settings)
            return dict(self._ui_settings)

    def get_global_hotkey(self) -> dict[str, Any]:
        with self._lock:
            validation = validate_hotkey(
                self._ui_settings.get("global_hotkey", DEFAULT_HOTKEY)
            )
            if not validation.ok:
                validation = validate_hotkey(DEFAULT_HOTKEY)
            return validation.as_dict()

    def set_global_hotkey(self, hotkey: str) -> dict[str, Any]:
        validation = validate_hotkey(hotkey)
        if not validation.ok:
            return validation.as_dict()

        configure = globals().get("configure_global_hotkey")
        if callable(configure):
            result = configure(validation.hotkey)
            if not result.get("ok"):
                return result

        with self._lock:
            self._ui_settings["global_hotkey"] = validation.hotkey
            self._storage.set("ui_settings", self._ui_settings)
        return validation.as_dict() | {"ok": True}

    def delete_history(self, entry_id: str) -> list[dict[str, Any]]:
        with self._lock:
            self._history = [item for item in self._history if item.get("id") != entry_id]
            self._persist()
            return self._history

    def clear_history(self) -> bool:
        with self._lock:
            self._history = []
            self._persist()
            return True

    def set_memory(self, slot: int, expression: str) -> dict[str, Any]:
        with self._lock:
            result = self._session.set_memory(int(slot), expression)
            if result.ok:
                self._persist()
            response = result.as_dict()
            response["memory"] = self._session.memory_expression(int(slot)) if result.ok else None
            return response

    def get_memory(self, slot: int) -> str:
        with self._lock:
            return self._session.memory_expression(int(slot))

    def copy_text(self, text: str) -> bool:
        return copy_text_to_clipboard(str(text))

    def hide_app(self) -> bool:
        hide_window()
        return True

    def quit_app(self) -> bool:
        request_quit()
        return True


_window: webview.Window | None = None
_visible = True
_quitting = False
_numlock_down = False
_keyboard_module: Any = None
_state_lock = threading.RLock()
_previous_foreground_hwnd: int | None = None
# The entry point replaces this in app_storage.install() after selecting the
# normal or explicit portable location.  The import-time API is memory-only so
# production never reads or writes the obsolete adjacent-file location.
_api = AppApi(Storage(None))


def _user32() -> Any:
    return ctypes.windll.user32


def numlock_is_on(user32: Any | None = None) -> bool:
    if os.name != "nt" and user32 is None:
        return True
    api = user32 if user32 is not None else _user32()
    return bool(api.GetKeyState(VK_NUMLOCK) & 0x0001)


def ensure_numlock_on(user32: Any | None = None) -> bool:
    if os.name != "nt" and user32 is None:
        return True
    api = user32 if user32 is not None else _user32()
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


def _capture_foreground_window() -> None:
    global _previous_foreground_hwnd
    if os.name != "nt":
        return
    try:
        handle = int(_user32().GetForegroundWindow())
        if handle:
            _previous_foreground_hwnd = handle
    except Exception:
        pass


def show_window() -> None:
    global _visible
    if _window is None or _quitting:
        return
    _capture_foreground_window()
    try:
        _window.show()
        _window.restore()
        with _state_lock:
            _visible = True
    except Exception:
        pass


def hide_window() -> None:
    global _visible
    if _window is None or _quitting:
        return
    try:
        _window.hide()
    finally:
        with _state_lock:
            _visible = False


def toggle_window() -> None:
    if _window is None or _quitting:
        return
    with _state_lock:
        should_hide = _visible
    if should_hide:
        hide_window()
    else:
        show_window()


def on_numlock_press(_event: Any = None) -> None:
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
    event_type = getattr(event, "event_type", None)
    if event_type == "down":
        on_numlock_press(event)
    elif event_type == "up":
        on_numlock_release(event)


def on_closing() -> bool:
    if _quitting:
        return True
    hide_window()
    return False


def on_shown() -> None:
    global _visible
    with _state_lock:
        _visible = True


def copy_text_to_clipboard(text: str) -> bool:
    if os.name != "nt":
        return False
    kernel32 = ctypes.windll.kernel32
    user32 = _user32()
    kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
    user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    user32.SetClipboardData.restype = ctypes.c_void_p
    encoded = (text + "\0").encode("utf-16-le")
    handle = None
    opened = False
    try:
        if not user32.OpenClipboard(None):
            return False
        opened = True
        user32.EmptyClipboard()
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
        if not handle:
            return False
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            return False
        ctypes.memmove(pointer, encoded, len(encoded))
        kernel32.GlobalUnlock(handle)
        if not user32.SetClipboardData(CF_UNICODETEXT, handle):
            return False
        handle = None  # Clipboard owns the handle after SetClipboardData.
        return True
    except Exception:
        return False
    finally:
        if handle:
            try:
                kernel32.GlobalFree(handle)
            except Exception:
                pass
        if opened:
            try:
                user32.CloseClipboard()
            except Exception:
                pass


def insert_text_into_previous_window(text: str) -> None:
    if not copy_text_to_clipboard(text):
        return
    target = _previous_foreground_hwnd
    hide_window()
    if os.name != "nt" or not target:
        return
    time.sleep(0.12)
    try:
        _user32().SetForegroundWindow(target)
        time.sleep(0.08)
        if _keyboard_module is not None:
            _keyboard_module.send("ctrl+v")
    except Exception:
        pass


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

