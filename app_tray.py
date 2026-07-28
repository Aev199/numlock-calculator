"""Frameless window and Windows system-tray integration."""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
from typing import Any, Callable

import app_native_dialogs


TRAY_TITLE = "NumCalc"
AUTOSTART_VALUE = "NumCalc"
REPOSITORY_URL = "https://github.com/Aev199/numlock-calculator"
ABOUT_LINKS: tuple[str, ...] = (REPOSITORY_URL,)
HELP_TEXT = """NumCalc — компактный клавиатурный калькулятор для Windows.

Быстрый старт:
• NumLock показывает скрытое окно, возвращает ему фокус или скрывает активное окно.
• Введите выражение. Предварительный результат появляется во время ввода.
• Enter фиксирует вычисление, сохраняет его в историю и подставляет ответ как новое рабочее значение.
• Полный выход выполняется через меню значка NumCalc в области уведомлений.

Выражения:
• Поддерживаются +, −, умножение, деление, скобки, степень ^, проценты и факториал !.
• Клавиша * отображается как знак ⋅. Неявное умножение также показывается явно: 150(5) → 150⋅(5).
• Можно использовать точку или запятую как десятичный разделитель.
• Tab открывает палитру функций. Доступны тригонометрия, корни, степени, логарифмы и другие функции.
• Открывающая скобка автоматически получает пару; уровни вложенности различаются цветом.

Память и переменные:
• Доступно 10 ячеек памяти M0–M9.
• Переменные создаются как имя = выражение или имя := выражение.
• ans содержит последний подтверждённый результат.

Горячие клавиши:
• Ctrl+C — копировать выражение и результат; для отдельного числа копируется только число.
• Alt+← / Alt+→ — переключить «Калькулятор» и «Единицы».
• Tab — открыть палитру функций.
• Ctrl+Space — открыть автодополнение.
• ↑ / ↓ — выбрать подсказку или перемещаться по истории.
• Escape — закрыть подсказку, очистить поле либо скрыть пустое окно.

Режим «Единицы»:
• Преобразует инженерные величины: длину, площадь, объём, массу, силу, давление, момент, скорость, ускорение, температуру и другие категории.
• В поле можно вводить простую арифметику со скобками.

Данные и диагностика:
• История, память, переменные и настройки хранятся локально.
• NumCalc не содержит телеметрии и не отправляет вычисления в сеть.
• Пункт «Копировать диагностику» помещает в буфер локальные сведения, необходимые для разбора ошибок.
"""
ABOUT_TEXT = """NumCalc
Компактный keyboard-first калькулятор для Windows.

Калькулятор — идеологическое продолжение NumLock Calculator от Владимира Потапова (https://nlcalc.narod.ru/).

Репозиторий: https://github.com/Aev199/numlock-calculator
Лицензия: MIT
"""
ABOUT_DIALOG_CONTENT = (
    "Калькулятор — идеологическое продолжение NumLock Calculator.\n\n"
    '<A HREF="https://github.com/Aev199/numlock-calculator">Репозиторий проекта</A>'
)


def install(app: Any) -> None:
    """Install frameless defaults and the complete Windows tray menu."""

    if getattr(app, "_tray_shell_installed", False):
        return
    app._tray_shell_installed = True
    app.APP_NAME = TRAY_TITLE
    app._tray_icon = None
    app._tray_thread = None

    original_create_window = app.webview.create_window
    original_webview_start = app.webview.start
    original_main = app.main
    original_register_hotkeys = getattr(app, "register_hotkeys", lambda: None)

    def run_async(callback: Callable[[], None]) -> None:
        threading.Thread(target=callback, daemon=True).start()

    def toggle_from_tray(_icon: Any = None, _item: Any = None) -> None:
        run_async(app.toggle_window)

    def show_hide_label(_item: Any = None) -> str:
        return "Скрыть" if getattr(app, "_visible", False) else "Показать"

    def show_from_tray(_icon: Any = None, _item: Any = None) -> None:
        run_async(app.show_window)

    def hide_from_tray(_icon: Any = None, _item: Any = None) -> None:
        run_async(app.hide_window)

    def autostart_command() -> str:
        if getattr(sys, "frozen", False):
            return f'"{Path(sys.executable).resolve()}"'
        module_path = Path(getattr(app, "__file__", Path.cwd() / "app.py")).resolve()
        entry = module_path.with_name("app_keyboard.py")
        return f'"{Path(sys.executable).resolve()}" "{entry}"'

    def autostart_enabled() -> bool:
        if os.name != "nt":
            return False
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_READ,
            ) as key:
                value, _kind = winreg.QueryValueEx(key, AUTOSTART_VALUE)
            return str(value).strip() == autostart_command()
        except (FileNotFoundError, OSError):
            return False

    def set_autostart(enabled: bool) -> bool:
        if os.name != "nt":
            return False
        try:
            import winreg

            with winreg.CreateKeyEx(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE,
            ) as key:
                if enabled:
                    winreg.SetValueEx(
                        key,
                        AUTOSTART_VALUE,
                        0,
                        winreg.REG_SZ,
                        autostart_command(),
                    )
                else:
                    try:
                        winreg.DeleteValue(key, AUTOSTART_VALUE)
                    except FileNotFoundError:
                        pass
            return True
        except OSError:
            return False

    def toggle_autostart(icon: Any = None, _item: Any = None) -> None:
        set_autostart(not autostart_enabled())
        if icon is not None:
            try:
                icon.update_menu()
            except Exception:
                pass

    def message_box(title: str, text: str) -> None:
        app_native_dialogs.show_message(title, text)

    def show_help(_icon: Any = None, _item: Any = None) -> None:
        run_async(lambda: message_box("Справка NumCalc", HELP_TEXT))

    def show_about(_icon: Any = None, _item: Any = None) -> None:
        def show() -> None:
            instruction = ABOUT_TEXT.splitlines()[0] if ABOUT_TEXT else TRAY_TITLE
            if not app_native_dialogs.show_link_dialog(
                "О программе",
                instruction,
                ABOUT_DIALOG_CONTENT,
                ABOUT_LINKS,
            ):
                message_box("О программе", ABOUT_TEXT)

        run_async(show)

    def open_repository(_icon: Any = None, _item: Any = None) -> None:
        def open_link() -> None:
            if not app_native_dialogs.open_external_url(
                REPOSITORY_URL,
                (REPOSITORY_URL,),
            ):
                message_box(
                    "NumCalc",
                    f"Не удалось открыть репозиторий.\n\n{REPOSITORY_URL}",
                )

        run_async(open_link)

    def copy_diagnostics_from_tray(_icon: Any = None, _item: Any = None) -> None:
        def copy() -> None:
            callback = getattr(app, "copy_diagnostics", None)
            if callback is None or not callback():
                message_box(
                    "Диагностика NumCalc",
                    "Не удалось скопировать диагностику в буфер обмена.",
                )

        run_async(copy)

    def quit_from_tray(icon: Any = None, _item: Any = None) -> None:
        if icon is not None:
            try:
                icon.stop()
            except Exception:
                pass
        run_async(app.request_quit)

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
                pystray.MenuItem(show_hide_label, toggle_from_tray, default=True),
                pystray.MenuItem(
                    "Автозагрузка Windows",
                    toggle_autostart,
                    checked=lambda _item: autostart_enabled(),
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Справка", show_help),
                pystray.MenuItem("О программе", show_about),
                pystray.MenuItem("Репозиторий", open_repository),
                pystray.MenuItem("Копировать диагностику", copy_diagnostics_from_tray),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Выйти", quit_from_tray),
            )
            icon = pystray.Icon("numcalc", create_tray_image(), TRAY_TITLE, menu)
            thread = threading.Thread(target=icon.run, name="NumCalcTray", daemon=True)
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

    def register_hotkeys_without_quit() -> None:
        """Keep NumLock integration but retire the hidden Ctrl+Shift+Q exit."""
        try:
            import keyboard
        except Exception:
            original_register_hotkeys()
            return
        original_add_hotkey = keyboard.add_hotkey

        def filtered_add_hotkey(hotkey: str, *args: Any, **kwargs: Any) -> Any:
            normalized = "".join(str(hotkey).split()).lower()
            if normalized == "ctrl+shift+q":
                return None
            return original_add_hotkey(hotkey, *args, **kwargs)

        keyboard.add_hotkey = filtered_add_hotkey
        try:
            original_register_hotkeys()
        finally:
            keyboard.add_hotkey = original_add_hotkey

    def create_window(*args: Any, **kwargs: Any) -> Any:
        kwargs.setdefault("frameless", True)
        kwargs.setdefault("easy_drag", False)
        kwargs.setdefault("shadow", True)
        if "title" in kwargs:
            kwargs["title"] = TRAY_TITLE
        return original_create_window(*args, **kwargs)

    def start_webview(*args: Any, **kwargs: Any) -> Any:
        app.start_tray()
        return original_webview_start(*args, **kwargs)

    def main() -> None:
        try:
            original_main()
        finally:
            stop_tray()

    app.register_hotkeys = register_hotkeys_without_quit
    app.webview.create_window = create_window
    app.webview.start = start_webview
    app.start_tray = start_tray
    app.stop_tray = stop_tray
    app.show_from_tray = show_from_tray
    app.hide_from_tray = hide_from_tray
    app.toggle_from_tray = toggle_from_tray
    app.quit_from_tray = quit_from_tray
    app.autostart_enabled = autostart_enabled
    app.set_autostart = set_autostart
    app.show_help = show_help
    app.show_about = show_about
    app.open_repository = open_repository
    app.copy_diagnostics_from_tray = copy_diagnostics_from_tray
    app.main = main
