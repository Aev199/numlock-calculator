"""Windows single-instance guard with activation of the existing NumCalc window."""

from __future__ import annotations

import ctypes
import os
import threading
import time
from typing import Any

ERROR_ALREADY_EXISTS = 183
WAIT_OBJECT_0 = 0
WAIT_FAILED = 0xFFFFFFFF
INFINITE = 0xFFFFFFFF
MUTEX_NAME = r"Local\Aev199.NumCalc.Instance"
ACTIVATE_EVENT_NAME = r"Local\Aev199.NumCalc.Activate"


def install(
    app: Any,
    *,
    kernel32: Any | None = None,
    platform_name: str | None = None,
) -> None:
    """Wrap the final application entry point with a process-level guard.

    A second process signals a named auto-reset event and exits.  The first
    process watches that event and restores/focuses its existing window.
    """

    if getattr(app, "_single_instance_installed", False):
        return
    app._single_instance_installed = True
    original_main = app.main
    platform = platform_name or os.name
    app._single_instance_mutex = None
    app._single_instance_event = None
    app._single_instance_thread = None
    app._single_instance_stopping = False

    def native_api() -> Any:
        if kernel32 is not None:
            return kernel32
        return ctypes.windll.kernel32

    def close_handle(api: Any, handle: Any) -> None:
        if not handle:
            return
        try:
            api.CloseHandle(handle)
        except Exception:
            pass

    def activate_when_ready() -> None:
        deadline = time.monotonic() + 5.0
        while (
            getattr(app, "_window", None) is None
            and not getattr(app, "_quitting", False)
            and time.monotonic() < deadline
        ):
            time.sleep(0.05)
        if not getattr(app, "_quitting", False):
            try:
                app.show_window()
            except Exception:
                pass

    def watch_activation(api: Any, event_handle: Any) -> None:
        while not app._single_instance_stopping:
            try:
                result = int(api.WaitForSingleObject(event_handle, INFINITE))
            except Exception:
                return
            if result == WAIT_FAILED or app._single_instance_stopping:
                return
            if result == WAIT_OBJECT_0:
                threading.Thread(
                    target=activate_when_ready,
                    name="NumCalcActivateExisting",
                    daemon=True,
                ).start()

    def main() -> None:
        if platform != "nt":
            original_main()
            return

        api = native_api()
        event_handle = api.CreateEventW(None, False, False, ACTIVATE_EVENT_NAME)
        mutex_handle = api.CreateMutexW(None, False, MUTEX_NAME)
        already_running = int(api.GetLastError()) == ERROR_ALREADY_EXISTS

        if already_running:
            try:
                if event_handle:
                    api.SetEvent(event_handle)
            finally:
                close_handle(api, mutex_handle)
                close_handle(api, event_handle)
            return

        if not mutex_handle or not event_handle:
            close_handle(api, mutex_handle)
            close_handle(api, event_handle)
            original_main()
            return

        app._single_instance_mutex = mutex_handle
        app._single_instance_event = event_handle
        app._single_instance_stopping = False
        watcher = threading.Thread(
            target=watch_activation,
            args=(api, event_handle),
            name="NumCalcSingleInstance",
            daemon=True,
        )
        app._single_instance_thread = watcher
        watcher.start()

        try:
            original_main()
        finally:
            app._single_instance_stopping = True
            try:
                api.SetEvent(event_handle)
            except Exception:
                pass
            if watcher.is_alive() and watcher is not threading.current_thread():
                watcher.join(timeout=0.8)
            close_handle(api, event_handle)
            close_handle(api, mutex_handle)
            app._single_instance_event = None
            app._single_instance_mutex = None
            app._single_instance_thread = None

    app.main = main
