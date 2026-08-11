"""Persist clipboard-only presentation preferences without changing engine state."""

from __future__ import annotations

from typing import Any


SETTING_KEY = "group_copied_digits"


def install(app: Any) -> None:
    """Extend AppApi with the clipboard grouping UI preference."""

    if getattr(app, "_clipboard_settings_installed", False):
        return
    app._clipboard_settings_installed = True

    original_init = app.AppApi.__init__
    original_set_ui_settings = app.AppApi.set_ui_settings

    def init_with_clipboard_setting(self: Any, storage: Any) -> None:
        original_init(self, storage)
        self._ui_settings[SETTING_KEY] = app._coerce_bool(
            self._ui_settings.get(SETTING_KEY, True),
            True,
        )

    def set_ui_settings_with_clipboard_setting(
        self: Any,
        settings: dict[str, Any],
    ) -> dict[str, Any]:
        payload = dict(settings or {})
        has_clipboard_setting = SETTING_KEY in payload
        clipboard_value = payload.pop(SETTING_KEY, True)

        response = original_set_ui_settings(self, payload)
        if not has_clipboard_setting:
            return response

        with self._lock:
            self._ui_settings[SETTING_KEY] = app._coerce_bool(
                clipboard_value,
                True,
            )
            self._storage.set("ui_settings", self._ui_settings)
            return dict(self._ui_settings)

    app.AppApi.__init__ = init_with_clipboard_setting
    app.AppApi.set_ui_settings = set_ui_settings_with_clipboard_setting
