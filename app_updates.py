"""Update checks, download, install and restart (see ``update_core``).

The checker runs in background threads and tells the renderer about every
phase change through ``window.__numcalcUpdates``. Preferences live in the
regular storage under ``updates``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any, Callable

import update_core as core
from product_info import APP_VERSION

STORAGE_KEY = "updates"
FIRST_CHECK_DELAY = 8.0
CHECK_INTERVAL = 60 * 60
DAY = 24 * 60 * 60
# How long NumCalc looks for a file the browser is downloading.
DOWNLOAD_WATCH = 20 * 60
RESTART_ARGUMENT = "--after-update="


def can_self_update() -> bool:
    """Only the one-file Windows EXE replaces itself.

    A source run is never "outdated", and a one-folder build keeps its
    libraries in ``_internal`` beside the EXE, which a new EXE would not match.
    """

    if os.name != "nt" or not getattr(sys, "frozen", False):
        return False
    return is_one_file_bundle(current_exe(), getattr(sys, "_MEIPASS", ""))


def is_one_file_bundle(exe: Path, bundle: str) -> bool:
    """A one-file EXE unpacks to a temporary folder outside its own folder."""

    if not bundle:
        return False
    folder = os.path.normcase(os.path.abspath(exe.parent))
    unpacked = os.path.normcase(os.path.abspath(bundle))
    return os.path.commonpath([folder, unpacked]) != folder


def current_exe() -> Path:
    return Path(sys.executable).resolve()


class Updater:
    def __init__(
        self,
        storage: Any,
        notify: Callable[[dict[str, Any]], None],
        *,
        fetch: core.Fetch = core.https_get,
        exe: Path | None = None,
        downloads: Callable[[], Path | None] = core.downloads_dir,
        version_of: Callable[[Path], str | None] = core.exe_version,
        installable: bool | None = None,
    ) -> None:
        self._storage = storage
        self._notify = notify
        self._fetch = fetch
        self._exe = exe or current_exe()
        self._downloads = downloads
        self._version_of = version_of
        self._installable = can_self_update() if installable is None else installable
        self._lock = threading.RLock()
        saved = storage.get(STORAGE_KEY, {}) if storage is not None else {}
        saved = saved if isinstance(saved, dict) else {}
        self.auto = saved.get("auto", True) is not False
        self.channel = core.channel_key(saved.get("channel"))
        self.folder_setting = str(saved.get("folder", "") or "")
        self.share = saved.get("share") is True
        self.skipped = str(saved.get("skipped", "") or "")
        self.checked_at = float(saved.get("checked_at", 0) or 0)
        self.phase = "idle"
        self.update: core.Update | None = None
        self.offered: core.Update | None = None
        self.message = ""
        self.note = ""
        self.done = 0
        self.total: int | None = None
        self._watching = False
        # Whether the latest check was asked for: the renderer opens the
        # dialog for those and only shows the title-bar badge otherwise.
        self.manual = False
        core.remove_leftovers(self._exe)

    # Preferences -----------------------------------------------------------

    def folder(self) -> Path | None:
        """The shared folder: the setting, else ``numcalc-update.txt`` beside the EXE."""

        if self.folder_setting.strip():
            return Path(self.folder_setting.strip().strip('"'))
        return core.folder_from_side_file(self._exe)

    def _save(self) -> None:
        if self._storage is None:
            return
        self._storage.set(STORAGE_KEY, {
            "auto": self.auto,
            "channel": self.channel,
            "folder": self.folder_setting,
            "share": self.share,
            "skipped": self.skipped,
            "checked_at": self.checked_at,
        })

    def set_preferences(self, values: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            channel = core.channel_key(values.get("channel", self.channel))
            folder = str(values.get("folder", self.folder_setting) or "").strip()
            if (channel, folder) != (self.channel, self.folder_setting) and self.phase in ("available", "failed", "blocked"):
                # Another source may offer a different version.
                self.phase = "idle"
                self.update = None
            self.auto = values.get("auto", self.auto) is not False
            self.channel = channel
            self.folder_setting = folder
            self.share = values.get("share", self.share) is True
            self._save()
        return self._publish()

    # State -----------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            side = core.folder_from_side_file(self._exe)
            return {
                "phase": self.phase,
                "manual": self.manual,
                "current": APP_VERSION,
                "installable": self._installable,
                "update": self.update.as_dict() if self.update else None,
                "message": self.message,
                "note": self.note,
                "done": self.done,
                "total": self.total,
                "previous": self._installable and core.previous_path(self._exe).exists(),
                "settings": {
                    "auto": self.auto,
                    "channel": self.channel,
                    "folder": self.folder_setting,
                    "side_folder": str(side) if side else "",
                    "share": self.share,
                },
                "channels": [
                    {"id": key, "label": label} for key, label in core.CHANNEL_LABELS.items()
                ],
            }

    def _publish(self) -> dict[str, Any]:
        state = self.snapshot()
        try:
            self._notify(state)
        except Exception:
            pass
        return state

    def _set(self, phase: str, **fields: Any) -> None:
        with self._lock:
            self.phase = phase
            for name, value in fields.items():
                setattr(self, name, value)
        self._publish()

    # Checks ----------------------------------------------------------------

    def start_background_checks(self, alive: Callable[[], bool]) -> threading.Thread | None:
        """A quiet check soon after start, then hourly; GitHub at most daily."""

        if not self._installable:
            return None

        def loop() -> None:
            time.sleep(FIRST_CHECK_DELAY)
            while alive():
                if self.auto and self.phase == "idle":
                    due = time.time() - self.checked_at >= DAY
                    self.check(manual=False, online=due, wait=True)
                time.sleep(CHECK_INTERVAL)

        thread = threading.Thread(target=loop, name="NumCalcUpdates", daemon=True)
        thread.start()
        return thread

    def check(self, manual: bool = True, online: bool = True, wait: bool = False) -> dict[str, Any]:
        """Look, in order, in Downloads, the shared folder and — when ``online`` — GitHub."""

        with self._lock:
            if self.phase in ("checking", "downloading"):
                return self.snapshot()
            self.phase = "checking"
            self.manual = manual
            self.note = ""
            self.message = ""
        self._publish()
        thread = threading.Thread(target=self._run_check, args=(manual, online), daemon=True)
        thread.start()
        if wait:
            thread.join()
        return self.snapshot()

    def _find(self, online: bool) -> tuple[str, Any]:
        downloads = self._downloads()
        if downloads is not None:
            found = core.find_downloaded(downloads, APP_VERSION, self._version_of)
            if found:
                try:
                    return "found", core.downloaded_update(*found)
                except OSError:
                    pass
        folder = self.folder()
        folder_error = ""
        if folder is not None:
            try:
                found = core.check_folder(folder, APP_VERSION)
                if found:
                    return "found", found
                if not online:
                    return "latest", None
            except core.UpdateError as error:
                folder_error = str(error)
        if not online:
            return ("failed", folder_error) if folder_error else ("latest", None)
        try:
            found = core.check(APP_VERSION, self.channel, self._fetch)
        except core.UpdateError as error:
            if folder is not None and not folder_error:
                # A shared folder that is up to date answers for the network.
                return "latest", None
            if error.answered:
                return "failed", str(error)
            reason = f"{error}. Папка обновлений: {folder_error}" if folder_error else str(error)
            return "blocked", reason
        return ("found", found) if found else ("latest", None)

    def _run_check(self, manual: bool, online: bool) -> None:
        try:
            outcome, value = self._find(online)
        except Exception as error:  # an unexpected failure must not stick in "checking"
            outcome, value = "failed", str(error)
        with self._lock:
            if online:
                # Remembered even when blocked: GitHub is asked at most daily.
                self.checked_at = time.time()
                self._save()
        if outcome == "found" and (manual or value.version != self.skipped):
            self._set("available", update=value, offered=value)
        elif outcome == "blocked" and manual:
            self._set("blocked", message=value)
        elif outcome == "failed" and manual:
            self._set("idle", note=f"Не удалось проверить: {value}")
        elif manual:
            label = core.CHANNEL_LABELS[self.channel].lower()
            self._set("idle", note=f"Установлена последняя версия ({label})")
        else:
            self._set("idle")

    def skip(self) -> dict[str, Any]:
        with self._lock:
            if self.update is not None:
                self.skipped = self.update.version
                self._save()
            self.phase = "idle"
            self.update = None
        return self._publish()

    def dismiss(self) -> dict[str, Any]:
        """Close a finished or failed state; an offer stays available."""

        with self._lock:
            if self.phase in ("blocked", "failed"):
                self.phase = "idle"
            self.note = ""
        return self._publish()

    # Install ---------------------------------------------------------------

    def download(self, wait: bool = False) -> dict[str, Any]:
        with self._lock:
            found = self.update if self.phase == "available" else self.offered if self.phase == "failed" else None
            if found is None:
                return self.snapshot()
            self.offered = found
            if not self._installable:
                self.phase = "failed"
                self.message = "Обновление устанавливается только в собранной Windows-версии NumCalc.exe"
                return self._publish()
            self.phase = "downloading"
            self.update = found
            self.done, self.total = 0, None
        self._publish()
        thread = threading.Thread(target=self._run_download, args=(found,), daemon=True)
        thread.start()
        if wait:
            thread.join()
        return self.snapshot()

    def _run_download(self, found: core.Update) -> None:
        last = [0.0]

        def progress(done: int, total: int | None) -> None:
            self.done, self.total = done, total
            now = time.monotonic()
            if now - last[0] >= 0.25:
                last[0] = now
                self._publish()

        try:
            data = core.get(found.exe_url, progress, self._fetch)
            core.install(self._exe, data, found.sha256)
        except PermissionError:
            self._set("failed", message="Нет прав на запись в папку программы. Скачайте новую версию со страницы выпуска.")
            return
        except (core.UpdateError, OSError) as error:
            self._set("failed", message=f"Обновление не установлено: {error}")
            return
        note = ""
        folder = self.folder()
        if self.share and folder is not None:
            # Colleagues behind the same firewall take it from the shared folder.
            try:
                if core.publish_to_folder(folder, found, data):
                    note = f"Версия {found.version} выложена в папку обновлений"
            except OSError as error:
                note = f"Не удалось выложить версию в папку обновлений: {error}"
        self._set("ready", note=note)

    def rollback(self) -> dict[str, Any]:
        try:
            core.rollback(self._exe)
        except (core.UpdateError, OSError) as error:
            self._set(self.phase, note=f"Откат не выполнен: {error}")
        else:
            self._set("rolled_back", update=None, note="")
        return self.snapshot()

    def open_in_browser(self) -> dict[str, Any]:
        """Open the release in the browser and watch Downloads for the file."""

        webbrowser.open(core.browser_url())
        self._set("idle", note="Скачайте NumCalc.exe в браузере: NumCalc заметит файл в «Загрузках»")
        with self._lock:
            if self._watching:
                return self.snapshot()
            self._watching = True

        def watch() -> None:
            started = time.monotonic()
            try:
                while time.monotonic() - started < DOWNLOAD_WATCH:
                    time.sleep(3)
                    downloads = self._downloads()
                    found = core.find_downloaded(downloads, APP_VERSION, self._version_of) if downloads else None
                    if not found:
                        continue
                    try:
                        update = core.downloaded_update(*found)
                    except OSError:
                        continue
                    if self.phase in ("idle", "blocked"):
                        self._set("available", update=update, offered=update, note="", manual=True)
                    return
            finally:
                self._watching = False

        threading.Thread(target=watch, name="NumCalcDownloadWatch", daemon=True).start()
        return self.snapshot()

    def restart_command(self) -> list[str]:
        return [str(self._exe), f"{RESTART_ARGUMENT}{os.getpid()}"]


def wait_for_previous_process(argv: list[str], timeout: float = 15.0) -> None:
    """Let the updated EXE start only after the old process released the guard."""

    pid = next((arg[len(RESTART_ARGUMENT):] for arg in argv if arg.startswith(RESTART_ARGUMENT)), "")
    if not pid.isdigit() or os.name != "nt":
        return
    import ctypes

    synchronize = 0x00100000
    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    handle = kernel32.OpenProcess(synchronize, False, int(pid))
    if handle:
        try:
            kernel32.WaitForSingleObject(handle, int(timeout * 1000))
        finally:
            kernel32.CloseHandle(handle)


def install(app: Any) -> None:
    """Expose updates to the renderer and start quiet background checks."""

    if getattr(app, "_updates_installed", False):
        return
    app._updates_installed = True
    app._updater = None

    def notify(state: dict[str, Any]) -> None:
        window = getattr(app, "_window", None)
        if window is None:
            return
        payload = json.dumps(state, ensure_ascii=False)
        window.evaluate_js(f"window.__numcalcUpdates && window.__numcalcUpdates({payload})")

    def updater() -> Updater:
        if app._updater is None:
            api = getattr(app, "_api", None)
            app._updater = Updater(getattr(api, "_storage", None), notify)
        return app._updater

    def restart() -> bool:
        try:
            environment = dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1")
            flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            subprocess.Popen(updater().restart_command(), env=environment, creationflags=flags, close_fds=True)
        except OSError as error:
            updater()._set(updater().phase, note=f"Не удалось перезапустить: {error}. Запустите NumCalc вручную")
            return False
        threading.Thread(target=app.request_quit, daemon=True).start()
        return True

    api_class = app.AppApi
    api_class.update_state = lambda self: updater().snapshot()
    api_class.update_check = lambda self: updater().check(manual=True)
    api_class.update_download = lambda self: updater().download()
    api_class.update_skip = lambda self: updater().skip()
    api_class.update_dismiss = lambda self: updater().dismiss()
    api_class.update_rollback = lambda self: updater().rollback()
    api_class.update_open_browser = lambda self: updater().open_in_browser()
    api_class.update_set_preferences = lambda self, values: updater().set_preferences(
        values if isinstance(values, dict) else {}
    )
    api_class.update_restart = lambda self: restart()

    def check_from_tray() -> None:
        try:
            app.show_window()
        except Exception:
            pass
        updater().check(manual=True)

    app.check_updates_from_tray = check_from_tray

    original_main = app.main

    def main() -> None:
        updater().start_background_checks(lambda: not getattr(app, "_quitting", False))
        original_main()

    app.main = main


def install_restart_wait(app: Any) -> None:
    """Outermost entry wrapper: wait for the replaced process before the guard."""

    if getattr(app, "_update_restart_wait_installed", False):
        return
    app._update_restart_wait_installed = True
    original_main = app.main

    def main() -> None:
        wait_for_previous_process(sys.argv[1:])
        original_main()

    app.main = main
