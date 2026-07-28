"""Saved-variable management exposed through the existing pywebview API."""

from __future__ import annotations

from typing import Any


def install(app: Any) -> None:
    """Add persistent variable deletion without changing the calculation engine."""

    if getattr(app, "_variable_management_installed", False):
        return
    app._variable_management_installed = True

    def delete_variable(self: Any, name: str) -> dict[str, Any]:
        key = str(name or "").strip().lower()
        with self._lock:
            if not key or key not in self._session.variables:
                return {
                    "ok": False,
                    "error": "Переменная не найдена",
                }

            del self._session.variables[key]
            self._persist()
            return {
                "ok": True,
                "deleted": key,
                "variables": {
                    variable: self._session.format_quantity(value)
                    for variable, value in sorted(self._session.variables.items())
                },
                "suggestions": self._session.suggestions(),
            }

    app.AppApi.delete_variable = delete_variable
