"""Apply centralized product metadata to runtime modules."""

from __future__ import annotations

from typing import Any

from product_info import APP_NAME, APP_VERSION, DESCRIPTION


def install(app: Any, tray_module: Any) -> None:
    if getattr(app, "_product_identity_installed", False):
        return
    app._product_identity_installed = True
    app.APP_NAME = APP_NAME
    app.APP_VERSION = APP_VERSION
    tray_module.TRAY_TITLE = APP_NAME
    tray_module.AUTOSTART_VALUE = APP_NAME
    tray_module.ABOUT_TEXT = (
        f"{APP_NAME} {APP_VERSION}\n"
        f"{DESCRIPTION}.\n\n"
        "Калькулятор, история, память, переменные и инженерный "
        "конвертер единиц — в одном небольшом окне."
    )
