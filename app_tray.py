"""Frameless window and Windows system-tray integration.

This layer intentionally stays independent from the calculator engine and the
NumLock hook.  It only adjusts window chrome and application lifecycle.
"""

from __future__ import annotations

import os
import threading
from typing import Any, Callable


TRAY_TITLE = "NumLock Calc"


def install(app: Any) -> None:
    """Install frameless window defaults and a Windows tray icon."""

    if getattr(app, "_tray_shell_installed", False):
        return
    app._tray_shell_installed = True
    app._tray_icon = None
    app._tray_thread = None

    original_build_html: Callable[[], str] = app.build_html
    original_create_window = app.webview.create_window
    original_main = app.main

    def build_html() -> str:
        html = original_build_html()
        html = html.replace(
            'class="brand-block"',
            'class="brand-block pywebview-drag-region" title="Перетащить окно"',
            1,
        )
        html = html.replace(
            "</style>",
            "\n.brand-block.pywebview-drag-region{cursor:move;user-select:none}\n"
            ".topbar-actions,.topbar-actions *{cursor:default}\n</style>",
            1,
        )
        return html

    def create_window(*args: Any, **kwargs: Any) -> Any:
        kwargs.setdefault("frameless", True)
        kwargs.setdefault("easy_drag", False)
        kwargs.setdefault("shadow", True)
        return original_create_window(*args, **kwargs)

    def run_async(callback: Callable[[], None]) -> None:
        threading.Thread(target=callback, daemon=True).start()

    def show_from_tray(_icon: Any = None, _item: Any = None) -> None:
        def action() -> None:
            if getattr(app, "_window", None) is None or getattr(app, "_quitting", False):
                return
            try:
                if getattr(app, "_visible", False):
                    app.refocus_window()
                else:
                    app.show_window()
            except Exception:
                try:
                    app.toggle_window()
                except Exception:
                    pass

        run_async(action)

    def hide_from_tray(_icon: Any = None, _item: Any = None) -> None:
        run_async(lambda: app.hide_window())

    def quit_from_tray(icon: Any = None, _item: Any = None) -> None:
        if icon is not None:
            try:
                icon.stop()
            except Exception:
                pass
        run_async(lambda: app.request_quit())

    def create_tray_image() -> Any:
        from PIL import Image, ImageDraw

        image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((3, 3, 61, 61), radius=15, fill=(82, 109, 255, 255))
        line = (248, 250, 255, 255)
        draw.line((18, 46, 18, 18), fill=line, width=7)
        draw.line((18, 18, 46, 46), fill=line, width=7)
        draw.line((46, 46, 46, 18), fill=line, width=7)
        return image

    def start_tray() -> bool:
        if os.name != "nt" or app._tray_icon is not None:
            return False
        try:
            import pystray

            menu = pystray.Menu(
                pystray.MenuItem(
                    "Показать калькулятор",
                    show_from_tray,
                    default=True,
                ),
                pystray.MenuItem("Скрыть", hide_from_tray),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Выйти", quit_from_tray),
            )
            icon = pystray.Icon(
                "numlock-calc",
                create_tray_image(),
                TRAY_TITLE,
                menu,
            )
            thread = threading.Thread(
                target=icon.run,
                name="NumLockCalcTray",
                daemon=True,
            )
            app._tray_icon = icon
            app._tray_thread = thread
            thread.start()
            return True
        except Exception:
            app._tray_icon = None
            app._tray_thread = None
            return False

    def stop_tray() -> None:
        icon = app._tray_icon
        app._tray_icon = None
        if icon is not None:
            try:
                icon.stop()
            except Exception:
                pass
        thread = app._tray_thread
        app._tray_thread = None
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=0.8)

    def main() -> None:
        # create_window is patched before the original shell creates the window.
        # Start the tray immediately before entering pywebview's blocking loop.
        try:
            start_tray()
            original_main()
        finally:
            stop_tray()

    app.build_html = build_html
    app.webview.create_window = create_window
    app.start_tray = start_tray
    app.stop_tray = stop_tray
    app.show_from_tray = show_from_tray
    app.hide_from_tray = hide_from_tray
    app.quit_from_tray = quit_from_tray
    app.main = main
