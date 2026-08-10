"""Apply centralized product metadata to runtime modules."""

from __future__ import annotations

import time
from typing import Any

import app_native_dialogs
from product_info import (
    APP_NAME,
    APP_VERSION,
    INSPIRATION_URL,
    LICENSE_NAME,
    REPOSITORY_URL,
)


_TRUSTED_PRODUCT_LINKS = (INSPIRATION_URL, REPOSITORY_URL)


def install(app: Any, tray_module: Any) -> None:
    if getattr(app, "_product_identity_installed", False):
        return
    app._product_identity_installed = True
    app.APP_NAME = APP_NAME
    app.APP_VERSION = APP_VERSION
    app.REPOSITORY_URL = REPOSITORY_URL
    tray_module.TRAY_TITLE = APP_NAME
    tray_module.AUTOSTART_VALUE = APP_NAME
    tray_module.HELP_TEXT = """Клавиши
NumLock — показать или скрыть NumCalc
Enter — вычислить
↑ / ↓ — история и подсказки
Tab — функции
Alt+← / Alt+→ — режимы
Alt+↑ — компактный режим
Alt+↓ — полный режим
Ctrl+H — история
Ctrl+C — копировать
Ctrl+Space — автодополнение
Esc — закрыть текущее окно или подсказку

Выражения
+  −  *  /  ^  %  !  ( )
Точка и запятая принимаются как десятичный разделитель.
Переменные: имя = выражение или имя := выражение.
Последний результат: ans.

Режимы
Калькулятор — расчёт, история, память, переменные и формулы.
Единицы — преобразование величин.
Интерполяция — линейная интерполяция по двум точкам.
Компактный режим показывает только калькулятор; история доступна по Ctrl+H.

Настройки и история хранятся локально. Телеметрии нет.
"""
    tray_module.ABOUT_LINKS = (
        ("NumLock Calculator — Владимир Потапов", INSPIRATION_URL),
        ("GitHub", REPOSITORY_URL),
    )
    tray_module.ABOUT_TEXT = (
        f"{APP_NAME} {APP_VERSION}\n"
        "Калькулятор для Windows\n"
        f"Лицензия: {LICENSE_NAME}\n\n"
        "NumLock Calculator — Владимир Потапов\n"
        f"{INSPIRATION_URL}\n\n"
        f"GitHub: {REPOSITORY_URL}"
    )
    tray_module.ABOUT_DIALOG_CONTENT = (
        f"Версия {APP_VERSION}\n"
        "Калькулятор для Windows\n"
        f"Лицензия: {LICENSE_NAME}\n\n"
        "NumLock Calculator — Владимир Потапов"
    )

    def open_product_link(self: Any, url: str) -> bool:
        return app_native_dialogs.open_external_url(url, _TRUSTED_PRODUCT_LINKS)

    api_class = getattr(app, "AppApi", None)
    if api_class is not None:
        api_class.open_product_link = open_product_link

    # Keep the tray implementation unchanged, but replace its unreliable native
    # TaskDialog path with the renderer-owned modal. The function is invoked only
    # after pywebview has started, so the main window and JavaScript bridge exist.
    def show_about_in_renderer(
        _title: str,
        _instruction: str,
        _content: str,
        _links: Any,
    ) -> bool:
        window = getattr(app, "_window", None)
        if window is None:
            return False
        try:
            app.show_window()
        except Exception:
            pass

        for delay in (0.0, 0.08, 0.16):
            if delay:
                time.sleep(delay)
            try:
                window.evaluate_js(
                    "window.__nlcalcShowAbout && window.__nlcalcShowAbout()"
                )
                return True
            except Exception:
                continue
        return False

    dialogs = getattr(tray_module, "app_native_dialogs", None)
    if dialogs is not None:
        dialogs.show_link_dialog = show_about_in_renderer
