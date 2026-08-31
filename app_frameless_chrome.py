"""Final frameless-window policy for NumCalc on Windows.

pywebview 6.2.1 implements ``shadow=True`` for frameless WinForms windows by
extending a 1 px DWM frame into the client area. With NumCalc's own bottom
resize grip that frame becomes a visible U-shaped outline. NumCalc does not
need pywebview's shadow to resize, so the final create-window layer disables it
before the native BrowserForm is created.
"""

from __future__ import annotations

from typing import Any


def install(app: Any) -> None:
    """Disable pywebview's frameless DWM frame without touching resize logic."""

    if getattr(app, "_frameless_chrome_installed", False):
        return
    app._frameless_chrome_installed = True

    original_create_window = app.webview.create_window

    def create_window(*args: Any, **kwargs: Any) -> Any:
        # pywebview's WinForms backend calls DwmExtendFrameIntoClientArea(1 px)
        # only when shadow=True. Our native bottom grip owns resizing, so the
        # shadow/frame is unnecessary and is the source of the visible outline.
        kwargs["shadow"] = False
        return original_create_window(*args, **kwargs)

    app.webview.create_window = create_window
