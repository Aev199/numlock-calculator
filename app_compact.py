"""Persistent compact-window mode for NumCalc.

Compact mode keeps the calculator engine and history intact while presenting
only the calculator surface. The renderer owns which UI regions are hidden;
this module owns persistence and native window sizing.
"""

from __future__ import annotations

from typing import Any

DEFAULT_WINDOW_WIDTH = 384
DEFAULT_WINDOW_HEIGHT = 432
COMPACT_WINDOW_HEIGHT = 220
MIN_WINDOW_SIZE = (360, 200)


def install(app: Any) -> None:
    """Add the compact-mode setting and native resize API."""

    if getattr(app, "_compact_mode_installed", False):
        return
    app._compact_mode_installed = True
    app._full_window_height = DEFAULT_WINDOW_HEIGHT

    original_init = app.AppApi.__init__
    original_set_ui_settings = app.AppApi.set_ui_settings

    def normalize_compact_setting(api: Any) -> None:
        api._ui_settings["compact_mode"] = app._coerce_bool(
            api._ui_settings.get("compact_mode", False),
            False,
        )

    def api_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        normalize_compact_setting(self)

    def set_ui_settings(self: Any, settings: dict[str, Any]) -> dict[str, Any]:
        values = dict(settings or {})
        marker = object()
        compact_value = values.pop("compact_mode", marker)

        if values:
            original_set_ui_settings(self, values)

        normalize_compact_setting(self)
        if compact_value is not marker:
            self._ui_settings["compact_mode"] = app._coerce_bool(
                compact_value,
                False,
            )
            self._storage.set("ui_settings", self._ui_settings)
        return dict(self._ui_settings)

    def set_compact_window(_self: Any, compact: bool) -> dict[str, Any]:
        enabled = app._coerce_bool(compact, False)
        window = app._window
        if window is None or app._quitting:
            return {
                "ok": True,
                "compact_mode": enabled,
                "width": DEFAULT_WINDOW_WIDTH,
                "height": COMPACT_WINDOW_HEIGHT if enabled else DEFAULT_WINDOW_HEIGHT,
            }

        try:
            width = int(getattr(window, "width", DEFAULT_WINDOW_WIDTH) or DEFAULT_WINDOW_WIDTH)
            current_height = int(
                getattr(window, "height", DEFAULT_WINDOW_HEIGHT) or DEFAULT_WINDOW_HEIGHT
            )
            if enabled:
                if current_height > COMPACT_WINDOW_HEIGHT + 24:
                    app._full_window_height = current_height
                target_height = COMPACT_WINDOW_HEIGHT
            else:
                target_height = max(
                    COMPACT_WINDOW_HEIGHT + 24,
                    int(getattr(app, "_full_window_height", DEFAULT_WINDOW_HEIGHT)),
                )
            window.resize(width, target_height)
            return {
                "ok": True,
                "compact_mode": enabled,
                "width": width,
                "height": target_height,
            }
        except Exception as exc:
            return {
                "ok": False,
                "compact_mode": enabled,
                "error": str(exc) or "Не удалось изменить размер окна",
            }

    def compact_mode_enabled() -> bool:
        api = getattr(app, "_api", None)
        settings = getattr(api, "_ui_settings", {})
        return app._coerce_bool(settings.get("compact_mode", False), False)

    app.AppApi.__init__ = api_init
    app.AppApi.set_ui_settings = set_ui_settings
    app.AppApi.set_compact_window = set_compact_window
    app.compact_mode_enabled = compact_mode_enabled
    app.COMPACT_WINDOW_HEIGHT = COMPACT_WINDOW_HEIGHT
    app.COMPACT_MIN_SIZE = MIN_WINDOW_SIZE

    # app_storage.install() runs before this module, so normalize the already
    # constructed production API as well as future AppApi instances.
    if getattr(app, "_api", None) is not None:
        normalize_compact_setting(app._api)
