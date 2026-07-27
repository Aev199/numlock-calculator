"""Select durable normal or explicit portable storage for NumCalc."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

PORTABLE_MARKER = "portable.mode"
NORMAL_DATA_FILENAME = "data.json"


def local_data_dir() -> Path:
    root = os.environ.get("LOCALAPPDATA")
    if root:
        return Path(root) / "NumCalc"
    return Path.home() / ".numcalc"


def portable_requested(app_dir: Path, argv: list[str] | None = None) -> bool:
    args = list(sys.argv if argv is None else argv)
    env = os.environ.get("NUMCALC_PORTABLE", "").strip().lower()
    return (
        "--portable" in args
        or env in {"1", "true", "yes", "on"}
        or (app_dir / PORTABLE_MARKER).exists()
    )


def directory_is_writable(directory: Path) -> bool:
    try:
        directory.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".numcalc-write-", dir=str(directory))
        os.close(fd)
        Path(name).unlink(missing_ok=True)
        return True
    except OSError:
        return False


def resolve_storage(app: Any, argv: list[str] | None = None) -> tuple[Path, str, str | None]:
    app_dir = Path(app.application_dir())
    portable = portable_requested(app_dir, argv)
    if portable:
        portable_path = app_dir / app.DATA_FILENAME
        if directory_is_writable(app_dir):
            return portable_path, "portable", None
        fallback = local_data_dir() / NORMAL_DATA_FILENAME
        directory_is_writable(fallback.parent)
        return (
            fallback,
            "normal-fallback",
            "Папка portable-версии недоступна для записи; данные сохраняются в профиле пользователя.",
        )

    target = local_data_dir() / NORMAL_DATA_FILENAME
    if directory_is_writable(target.parent):
        return target, "normal", None

    fallback_dir = Path.home() / "NumCalc"
    if directory_is_writable(fallback_dir):
        return (
            fallback_dir / NORMAL_DATA_FILENAME,
            "home-fallback",
            "LOCALAPPDATA недоступна; данные сохраняются в папке NumCalc профиля пользователя.",
        )

    return (
        app_dir / app.DATA_FILENAME,
        "legacy-fallback",
        "Не удалось открыть стандартное хранилище; используется папка приложения.",
    )


def migrate_legacy_data(legacy: Path, target: Path) -> bool:
    if target.exists() or not legacy.exists() or legacy.resolve() == target.resolve():
        return False
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(legacy, target)
        return True
    except OSError:
        return False


def install(app: Any, *, argv: list[str] | None = None) -> None:
    """Replace the import-time adjacent-file API with the selected data store."""

    if getattr(app, "_storage_location_installed", False):
        return
    app._storage_location_installed = True

    legacy = Path(app.application_dir()) / app.DATA_FILENAME
    target, mode, warning = resolve_storage(app, argv)
    migrated = migrate_legacy_data(legacy, target) if mode == "normal" else False

    app.DATA_FILE = target
    app._storage_mode = mode
    app._storage_warning = warning
    app._storage_migrated = migrated
    app._api = app.AppApi(app.Storage(target))

    original_bootstrap = app.AppApi.bootstrap

    def bootstrap(self: Any) -> dict[str, Any]:
        data = original_bootstrap(self)
        data["storage"] = {
            "path": str(target),
            "mode": mode,
            "migrated": migrated,
        }
        if warning:
            data["storage_warning"] = warning
        return data

    app.AppApi.bootstrap = bootstrap
