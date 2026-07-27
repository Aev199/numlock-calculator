"""Select durable normal or explicit portable storage for NumCalc."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from product_info import APP_NAME

PORTABLE_MARKER = "portable.mode"
NORMAL_DATA_FILENAME = "data.json"


def local_data_dir() -> Path:
    root = os.environ.get("LOCALAPPDATA")
    if root:
        return Path(root) / APP_NAME
    return Path.home() / f".{APP_NAME.lower()}"


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


def _fallback_candidates(app_dir: Path) -> tuple[tuple[Path, str, str], ...]:
    return (
        (
            local_data_dir(),
            "normal-fallback",
            "Папка portable-версии недоступна для записи; данные сохраняются в профиле пользователя.",
        ),
        (
            Path.home() / APP_NAME,
            "home-fallback",
            "Стандартная папка данных недоступна; используется папка NumCalc профиля пользователя.",
        ),
        (
            Path(tempfile.gettempdir()) / APP_NAME,
            "temporary-fallback",
            "Постоянное хранилище недоступно; данные временно сохраняются в системной папке TEMP.",
        ),
        (
            app_dir,
            "legacy-fallback",
            "Стандартное хранилище недоступно; используется папка приложения.",
        ),
    )


def resolve_storage(app: Any, argv: list[str] | None = None) -> tuple[Path, str, str | None]:
    app_dir = Path(app.application_dir())
    portable = portable_requested(app_dir, argv)
    if portable and directory_is_writable(app_dir):
        return app_dir / app.DATA_FILENAME, "portable", None

    target_dir = local_data_dir()
    if not portable and directory_is_writable(target_dir):
        return target_dir / NORMAL_DATA_FILENAME, "normal", None

    seen: set[Path] = set()
    for directory, mode, warning in _fallback_candidates(app_dir):
        normalized = directory.resolve()
        if normalized in seen:
            continue
        seen.add(normalized)
        if directory_is_writable(directory):
            return directory / NORMAL_DATA_FILENAME, mode, warning

    # This path should be practically unreachable, but preserving a concrete
    # target lets the existing Storage layer return a visible write error.
    return (
        app_dir / app.DATA_FILENAME,
        "unavailable",
        "Не найдено доступное для записи хранилище. Изменения могут не сохраниться.",
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
