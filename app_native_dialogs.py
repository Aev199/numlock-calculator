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


_TDF_ENABLE_HYPERLINKS = 0x0001
_TDF_ALLOW_DIALOG_CANCELLATION = 0x0008
_TDCBF_OK_BUTTON = 0x0001
_TDN_HYPERLINK_CLICKED = 3


def _normalized_allowed_urls(urls: Iterable[str]) -> frozenset[str]:
    return frozenset(str(url).strip() for url in urls if str(url).strip())


def open_external_url(url: str, allowed_urls: Iterable[str] = ()) -> bool:
    """Open a trusted HTTP(S) URL in the default browser.

    When ``allowed_urls`` is supplied, the URL must match one of those exact
    values. This keeps TaskDialog hyperlink callbacks restricted to application
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
    allowed_urls: Iterable[str],
) -> bool:
    """Show a native TaskDialog whose trusted hyperlinks open in the browser.

    ``content`` may contain TaskDialog links in the form
    ``<A HREF=\"https://example.test\">text</A>``. Windows reports clicks to the
    callback; the dialog does not execute links by itself.
    """

    if os.name != "nt":
        return False

    allowed = _normalized_allowed_urls(allowed_urls)
    if not allowed:
        return False

    try:
        callback_type = ctypes.WINFUNCTYPE(
            ctypes.c_long,
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
            ctypes.c_ssize_t,
        )

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
                ("pButtons", ctypes.c_void_p),
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
                ("pfCallback", callback_type),
                ("lpCallbackData", ctypes.c_ssize_t),
                ("cxWidth", wintypes.UINT),
            ]

        @callback_type
        def callback(
            _hwnd: int,
            notification: int,
            _wparam: int,
            lparam: int,
            _callback_data: int,
        ) -> int:
            if notification == _TDN_HYPERLINK_CLICKED and lparam:
                open_external_url(ctypes.wstring_at(lparam), allowed)
            return 0

        config = TaskDialogConfig()
        config.cbSize = ctypes.sizeof(TaskDialogConfig)
        config.dwFlags = _TDF_ENABLE_HYPERLINKS | _TDF_ALLOW_DIALOG_CANCELLATION
        config.dwCommonButtons = _TDCBF_OK_BUTTON
        config.pszWindowTitle = str(title)
        config.pszMainInstruction = str(instruction)
        config.pszContent = str(content)
        config.pfCallback = callback
        config.cxWidth = 260

        task_dialog = ctypes.windll.comctl32.TaskDialogIndirect
        task_dialog.argtypes = [
            ctypes.POINTER(TaskDialogConfig),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(wintypes.BOOL),
        ]
        task_dialog.restype = ctypes.c_long
        return task_dialog(ctypes.byref(config), None, None, None) >= 0
    except Exception:
        return False
