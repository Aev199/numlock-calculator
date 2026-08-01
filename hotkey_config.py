"""Validation and presentation helpers for the configurable global hotkey."""

from __future__ import annotations

import re
import string
from dataclasses import dataclass


DEFAULT_HOTKEY = "num lock"

_MODIFIER_ORDER = ("ctrl", "alt", "shift", "windows")
_MODIFIER_ALIASES = {
    "control": "ctrl",
    "ctrl": "ctrl",
    "alt": "alt",
    "option": "alt",
    "shift": "shift",
    "win": "windows",
    "windows": "windows",
    "meta": "windows",
    "super": "windows",
}
_KEY_ALIASES = {
    "numlock": "num lock",
    "num_lock": "num lock",
    "capslock": "caps lock",
    "caps_lock": "caps lock",
    "scrolllock": "scroll lock",
    "scroll_lock": "scroll lock",
    "pageup": "page up",
    "page_up": "page up",
    "pagedown": "page down",
    "page_down": "page down",
    "printscreen": "print screen",
    "print_screen": "print screen",
    "prtsc": "print screen",
    "esc": "escape",
    "return": "enter",
    "del": "delete",
    "ins": "insert",
}
_STANDALONE_KEYS = {
    "num lock",
    "caps lock",
    "scroll lock",
    "pause",
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
    "print screen",
    "space",
    "tab",
    "enter",
    "escape",
    *(f"f{index}" for index in range(1, 25)),
}
_RESERVED = {
    "ctrl+space": "Ctrl+Space уже открывает автодополнение",
    "alt+left": "Alt+← уже переключает вкладки",
    "alt+right": "Alt+→ уже переключает вкладки",
    "tab": "Tab уже открывает палитру функций",
    "ctrl+c": "Ctrl+C уже копирует выражение и ответ",
    "ctrl+shift+q": "эта комбинация зарезервирована для служебного выхода",
    "alt+f4": "Alt+F4 зарезервирована Windows",
    "ctrl+alt+delete": "Ctrl+Alt+Delete зарезервирована Windows",
    "ctrl+escape": "Ctrl+Esc зарезервирована Windows",
    "windows+l": "Win+L зарезервирована Windows",
}
_DISPLAY_NAMES = {
    "ctrl": "Ctrl",
    "alt": "Alt",
    "shift": "Shift",
    "windows": "Win",
    "num lock": "NumLock",
    "caps lock": "CapsLock",
    "scroll lock": "ScrollLock",
    "page up": "PageUp",
    "page down": "PageDown",
    "print screen": "PrintScreen",
    "space": "Space",
    "escape": "Esc",
    "enter": "Enter",
    "tab": "Tab",
    "insert": "Insert",
    "delete": "Delete",
    "home": "Home",
    "end": "End",
    "left": "←",
    "right": "→",
    "up": "↑",
    "down": "↓",
}


@dataclass(frozen=True)
class HotkeyValidation:
    ok: bool
    hotkey: str
    display: str
    error: str = ""
    warning: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "hotkey": self.hotkey,
            "display": self.display,
            "error": self.error,
            "warning": self.warning,
        }


def _clean_token(token: str) -> str:
    normalized = " ".join(token.strip().lower().replace("_", " ").split())
    return _KEY_ALIASES.get(normalized.replace(" ", ""), normalized)


def _display_name(token: str) -> str:
    if token in _DISPLAY_NAMES:
        return _DISPLAY_NAMES[token]
    if len(token) == 1 and token in string.ascii_lowercase + string.digits:
        return token.upper()
    if token.startswith("f") and token[1:].isdigit():
        return token.upper()
    return token.title()


def validate_hotkey(value: object) -> HotkeyValidation:
    """Return a canonical keyboard-library hotkey or a user-facing error."""

    raw = str(value or "").strip().lower()
    if not raw:
        return HotkeyValidation(False, "", "", "Введите комбинацию клавиш")

    tokens = [part.strip() for part in re.split(r"\s*\+\s*", raw)]
    if any(not token for token in tokens):
        return HotkeyValidation(False, "", "", "Комбинация содержит пустую клавишу")

    modifiers: list[str] = []
    keys: list[str] = []
    for token in tokens:
        cleaned = _clean_token(token)
        if cleaned in _MODIFIER_ALIASES:
            modifier = _MODIFIER_ALIASES[cleaned]
            if modifier in modifiers:
                return HotkeyValidation(False, "", "", "Модификатор указан дважды")
            modifiers.append(modifier)
        else:
            if cleaned in _MODIFIER_ORDER:
                return HotkeyValidation(False, "", "", "Некорректная клавиша")
            if cleaned in keys:
                return HotkeyValidation(False, "", "", "Клавиша указана дважды")
            keys.append(cleaned)

    if len(keys) != 1:
        return HotkeyValidation(
            False,
            "",
            "",
            "Укажите одну основную клавишу и, при необходимости, модификаторы",
        )

    key = keys[0]
    if key not in _STANDALONE_KEYS:
        valid_single = len(key) == 1 and key in string.ascii_lowercase + string.digits + string.punctuation
        valid_function = bool(re.fullmatch(r"f(?:[1-9]|1[0-9]|2[0-4])", key))
        if not (valid_single or valid_function):
            return HotkeyValidation(False, "", "", f"Клавиша «{key}» не поддерживается")
        if not modifiers:
            return HotkeyValidation(
                False,
                "",
                "",
                "Для букв, цифр и знаков нужен хотя бы один модификатор",
            )

    ordered_modifiers = [item for item in _MODIFIER_ORDER if item in modifiers]
    canonical = "+".join((*ordered_modifiers, key))
    display = " + ".join(_display_name(item) for item in (*ordered_modifiers, key))
    conflict = _RESERVED.get(canonical, "")
    if conflict:
        return HotkeyValidation(False, canonical, display, conflict)
    return HotkeyValidation(True, canonical, display)


def default_hotkey() -> HotkeyValidation:
    return validate_hotkey(DEFAULT_HOTKEY)
