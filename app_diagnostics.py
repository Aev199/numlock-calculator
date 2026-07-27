"""Local rotating diagnostics for NumCalc without telemetry or network access."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import os
import platform
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOGGER_NAME = "numcalc"
LOG_FILENAME = "numcalc.log"
MAX_LOG_BYTES = 1_000_000
BACKUP_COUNT = 3
DIAGNOSTIC_TAIL_BYTES = 200_000


def default_log_dir() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "NumCalc" / "logs"
    return Path.home() / ".numcalc" / "logs"


def configure_logger(log_dir: Path | None = None) -> tuple[logging.Logger, Path]:
    directory = Path(log_dir) if log_dir is not None else default_log_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / LOG_FILENAME
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    resolved = str(path.resolve())
    for handler in logger.handlers:
        if getattr(handler, "baseFilename", None) == resolved:
            return logger, path

    handler = RotatingFileHandler(
        path,
        maxBytes=MAX_LOG_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s [%(threadName)s] %(message)s",
            "%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(handler)
    return logger, path


def install(app: Any, *, log_dir: Path | None = None) -> None:
    """Add file logging, frontend error reporting and copyable diagnostics."""

    if getattr(app, "_diagnostics_installed", False):
        return
    app._diagnostics_installed = True
    logger, log_path = configure_logger(log_dir)
    app.logger = logger
    app.diagnostic_log_path = log_path
    original_main = app.main

    def report_diagnostic(self: Any, source: str, message: str, details: str = "") -> bool:
        source_text = str(source or "frontend")[:80]
        message_text = str(message or "")[:4000]
        details_text = str(details or "")[:16000]
        logger.error("%s: %s%s", source_text, message_text, f"\n{details_text}" if details_text else "")
        return True

    def diagnostic_text() -> str:
        hook_mode = str(getattr(app, "_numlock_hook_mode", "unknown"))
        header = [
            "NumCalc diagnostics",
            f"Generated: {datetime.now(timezone.utc).isoformat()}",
            f"Python: {platform.python_version()}",
            f"Platform: {platform.platform()}",
            f"Frozen: {bool(getattr(sys, 'frozen', False))}",
            f"NumLock hook: {hook_mode}",
            f"Log: {log_path}",
            "",
            "--- log tail ---",
        ]
        try:
            with log_path.open("rb") as handle:
                handle.seek(0, os.SEEK_END)
                size = handle.tell()
                handle.seek(max(0, size - DIAGNOSTIC_TAIL_BYTES))
                tail = handle.read().decode("utf-8", errors="replace")
        except OSError as exc:
            tail = f"Unable to read log: {exc}"
        return "\n".join(header) + "\n" + tail

    def copy_diagnostics() -> bool:
        try:
            copied = bool(app.copy_text_to_clipboard(diagnostic_text()))
            logger.info("Diagnostics copied: %s", copied)
            return copied
        except Exception:
            logger.exception("Failed to copy diagnostics")
            return False

    def api_copy_diagnostics(_self: Any) -> bool:
        return copy_diagnostics()

    def log_runtime_state() -> None:
        deadline = time.monotonic() + 8.0
        last_mode = "unknown"
        while time.monotonic() < deadline and not getattr(app, "_quitting", False):
            last_mode = str(getattr(app, "_numlock_hook_mode", "unknown"))
            if last_mode not in {"none", "unknown"}:
                break
            time.sleep(0.1)
        logger.info("NumLock hook mode: %s", last_mode)

    def main() -> None:
        previous_sys_hook = sys.excepthook
        previous_thread_hook = getattr(threading, "excepthook", None)

        def sys_hook(exc_type: Any, exc_value: BaseException, exc_traceback: Any) -> None:
            logger.critical(
                "Unhandled exception",
                exc_info=(exc_type, exc_value, exc_traceback),
            )
            previous_sys_hook(exc_type, exc_value, exc_traceback)

        def thread_hook(args: Any) -> None:
            logger.critical(
                "Unhandled thread exception in %s",
                getattr(args.thread, "name", "thread"),
                exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
            )
            if previous_thread_hook is not None:
                previous_thread_hook(args)

        sys.excepthook = sys_hook
        if previous_thread_hook is not None:
            threading.excepthook = thread_hook

        logger.info(
            "Starting NumCalc; Python=%s platform=%s frozen=%s",
            platform.python_version(),
            platform.platform(),
            bool(getattr(sys, "frozen", False)),
        )
        threading.Thread(
            target=log_runtime_state,
            name="NumCalcRuntimeDiagnostics",
            daemon=True,
        ).start()
        try:
            original_main()
        except Exception:
            logger.exception("Fatal application error")
            raise
        finally:
            logger.info("NumCalc stopped")
            sys.excepthook = previous_sys_hook
            if previous_thread_hook is not None:
                threading.excepthook = previous_thread_hook

    app.AppApi.report_diagnostic = report_diagnostic
    app.AppApi.copy_diagnostics = api_copy_diagnostics
    app.copy_diagnostics = copy_diagnostics
    app.diagnostic_text = diagnostic_text
    app.main = main
