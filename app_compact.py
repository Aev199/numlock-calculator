"""Compact window sizing for the keyboard-first shell."""

from __future__ import annotations

from typing import Any

DEFAULT_WIDTH = 500
DEFAULT_HEIGHT = 560
MIN_SIZE = (400, 420)


def install(app: Any) -> None:
    """Override the prototype window dimensions without touching its behavior."""

    if getattr(app, "_compact_shell_installed", False):
        return
    app._compact_shell_installed = True

    original_create_window = app.webview.create_window

    def create_window(*args: Any, **kwargs: Any) -> Any:
        # The keyboard-first layout no longer needs the two instructional rows,
        # so the previous 540x650 prototype window wastes a noticeable amount of
        # screen space. Keep enough room for long expressions and a useful history.
        kwargs["width"] = DEFAULT_WIDTH
        kwargs["height"] = DEFAULT_HEIGHT
        kwargs["min_size"] = MIN_SIZE
        return original_create_window(*args, **kwargs)

    app.webview.create_window = create_window
