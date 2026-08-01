"""Small native dialogs used by the Windows tray shell.

The module has no import-time Windows side effects, so it remains safe to import
from tests and on non-Windows development machines.
"""

from __future__ import annotations

import ctypes
import os
import webbrowser
from ctypes import wintypes
from typing import Iterable
from urllib.parse import urlparse


_TDF_ALLOW_DIALOG_CANCELLATION = 0x0008
_TDF_USE_COMMAND_LINKS = 0x0010
_TDCBF_OK_BUTTON = 0x0001
_LINK_BUTTON_BASE = 1000


def _normalized_allowed_urls(urls: Iterable[str]) -> frozenset[str]:
    return frozenset(str(url).strip() for url in urls if str(url).strip())


def _normalized_links(links: Iterable[tuple[str, str]]) -> tuple[tuple[str, str], ...]:
    result: list[tuple[str, str]] = []
    seen: set[str] = set()
    for label, url in links:
        target = str(url).strip()
        parsed = urlparse(target)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or target in seen:
            continue
        caption = str(label).strip() or target
        result.append((caption, target))
        seen.add(target)
    return tuple(result)


def open_external_url(url: str, allowed_urls: Iterable[str] = ()) -> bool:
    """Open a trusted HTTP(S) URL in the default browser.

    When ``allowed_urls`` is supplied, the URL must match one of those exact
    values. This keeps native-dialog callbacks restricted to application
    constants rather than arbitrary executable strings.
    """

    target = str(url).strip()
    parsed = urlparse(target)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False

    allowed = _normalized_allowed_urls(allowed_urls)
    if allowed and target not in allowed:
        return False

    try:
        return bool(webbrowser.open(target, new=2))
    except Exception:
        return False


def show_message(title: str, text: str) -> bool:
    """Show an informational message box on Windows."""

    if os.name != "nt":
        return False
    try:
        ctypes.windll.user32.MessageBoxW(None, str(text), str(title), 0x40)
        return True
    except Exception:
        return False


def show_link_dialog(
    title: str,
    instruction: str,
    content: str,
    links: Iterable[tuple[str, str]],
) -> bool:
    """Show a TaskDialog with explicit clickable link actions.

    Command-link buttons are used instead of relying on automatic URL rendering
    in a message box. The selected trusted URL is opened only after exact
    allow-list validation.
    """

    if os.name != "nt":
        return False

    normalized_links = _normalized_links(links)
    if not normalized_links:
        return False

    try:
        class TaskDialogButton(ctypes.Structure):
            _fields_ = [
                ("nButtonID", ctypes.c_int),
                ("pszButtonText", wintypes.LPCWSTR),
            ]

        class TaskDialogConfig(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.UINT),
                ("hwndParent", wintypes.HWND),
                ("hInstance", wintypes.HINSTANCE),
                ("dwFlags", wintypes.UINT),
                ("dwCommonButtons", wintypes.UINT),
                ("pszWindowTitle", wintypes.LPCWSTR),
                ("mainIcon", ctypes.c_void_p),
                ("pszMainInstruction", wintypes.LPCWSTR),
                ("pszContent", wintypes.LPCWSTR),
                ("cButtons", wintypes.UINT),
                ("pButtons", ctypes.POINTER(TaskDialogButton)),
                ("nDefaultButton", ctypes.c_int),
                ("cRadioButtons", wintypes.UINT),
                ("pRadioButtons", ctypes.c_void_p),
                ("nDefaultRadioButton", ctypes.c_int),
                ("pszVerificationText", wintypes.LPCWSTR),
                ("pszExpandedInformation", wintypes.LPCWSTR),
                ("pszExpandedControlText", wintypes.LPCWSTR),
                ("pszCollapsedControlText", wintypes.LPCWSTR),
                ("footerIcon", ctypes.c_void_p),
                ("pszFooter", wintypes.LPCWSTR),
                ("pfCallback", ctypes.c_void_p),
                ("lpCallbackData", ctypes.c_ssize_t),
                ("cxWidth", wintypes.UINT),
            ]

        button_array_type = TaskDialogButton * len(normalized_links)
        buttons = button_array_type(
            *(
                TaskDialogButton(_LINK_BUTTON_BASE + index, label)
                for index, (label, _url) in enumerate(normalized_links)
            )
        )
        button_urls = {
            _LINK_BUTTON_BASE + index: url
            for index, (_label, url) in enumerate(normalized_links)
        }
        allowed_urls = tuple(url for _label, url in normalized_links)

        config = TaskDialogConfig()
        config.cbSize = ctypes.sizeof(TaskDialogConfig)
        config.dwFlags = _TDF_ALLOW_DIALOG_CANCELLATION | _TDF_USE_COMMAND_LINKS
        config.dwCommonButtons = _TDCBF_OK_BUTTON
        config.pszWindowTitle = str(title)
        config.pszMainInstruction = str(instruction)
        config.pszContent = str(content)
        config.cButtons = len(normalized_links)
        config.pButtons = buttons
        config.cxWidth = 280

        selected_button = ctypes.c_int()
        task_dialog = ctypes.windll.comctl32.TaskDialogIndirect
        task_dialog.argtypes = [
            ctypes.POINTER(TaskDialogConfig),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(wintypes.BOOL),
        ]
        task_dialog.restype = ctypes.c_long
        result = task_dialog(
            ctypes.byref(config),
            ctypes.byref(selected_button),
            None,
            None,
        )
        if result < 0:
            return False

        selected_url = button_urls.get(selected_button.value)
        if selected_url and not open_external_url(selected_url, allowed_urls):
            show_message("NumCalc", f"Не удалось открыть ссылку.\n\n{selected_url}")
        return True
    except Exception:
        return False

