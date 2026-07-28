"""Apply centralized product metadata to runtime modules."""

from __future__ import annotations

from typing import Any

from product_info import (
    APP_NAME,
    APP_VERSION,
    DESCRIPTION,
    INSPIRATION_URL,
    LICENSE_NAME,
    REPOSITORY_URL,
)


def install(app: Any, tray_module: Any) -> None:
    if getattr(app, "_product_identity_installed", False):
        return
    app._product_identity_installed = True
    app.APP_NAME = APP_NAME
    app.APP_VERSION = APP_VERSION
    app.REPOSITORY_URL = REPOSITORY_URL
    tray_module.TRAY_TITLE = APP_NAME
    tray_module.AUTOSTART_VALUE = APP_NAME
    tray_module.ABOUT_LINKS = (
        ("NumLock Calculator — сайт Владимира Потапова", INSPIRATION_URL),
        ("Репозиторий NumCalc", REPOSITORY_URL),
    )
    tray_module.ABOUT_TEXT = (
        f"{APP_NAME} {APP_VERSION}\n"
        f"{DESCRIPTION}.\n\n"
        "Калькулятор - идеологическое продолжение NumLock Calculator "
        f"от Владимира Потапова ({INSPIRATION_URL}).\n\n"
        f"Репозиторий: {REPOSITORY_URL}\n"
        f"Лицензия: {LICENSE_NAME}"
    )
    tray_module.ABOUT_DIALOG_CONTENT = (
        "Калькулятор - идеологическое продолжение NumLock Calculator "
        "от Владимира Потапова.\n\n"
        f"Лицензия исходного кода NumCalc: {LICENSE_NAME}"
    )
