"""Backend-only unit conversion API for the consolidated renderer."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

import calc_engine as core
from app_units_mode import (
    _CATEGORY_BY_ID,
    _category_symbols,
    _ensure_state,
    _filter_suggestions,
    _format_number,
    _plain_result,
    _sanitize_state,
    _unit_payload,
    evaluate_simple,
)


def install(app: Any) -> None:
    """Extend ``AppApi`` without modifying HTML, CSS or JavaScript."""

    if getattr(app, "_units_backend_installed", False):
        return
    app._units_backend_installed = True

    original_bootstrap = app.AppApi.bootstrap
    original_suggestions = app.AppApi.suggestions

    def bootstrap(self: Any) -> dict[str, Any]:
        _ensure_state(self)
        data = original_bootstrap(self)
        data["suggestions"] = _filter_suggestions(data.get("suggestions", []))
        data["unit_converter"] = {
            "categories": _unit_payload(),
            "state": deepcopy(self._unit_converter_state),
            "calculator_handoff": deepcopy(self._calculator_handoff),
        }
        return data

    def suggestions(self: Any, query: str = "") -> list[dict[str, Any]]:
        return _filter_suggestions(original_suggestions(self, query))

    def commit(self: Any, expression: str) -> dict[str, Any]:
        _ensure_state(self)
        with self._lock:
            evaluation = self._session.evaluate(expression, commit=True)
            response = evaluation.as_dict()
            if evaluation.ok and expression.strip():
                self._sequence += 1
                entry = app.make_history_entry(
                    evaluation,
                    self._session.settings,
                    self._sequence,
                ).as_dict()
                self._history.insert(0, entry)
                self._history = self._history[: app.MAX_HISTORY]
                response["history_entry"] = entry

                plain = _plain_result(response)
                if plain:
                    self._calculator_handoff = {
                        "revision": int(self._calculator_handoff.get("revision", 0)) + 1,
                        "value": plain,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }
                response["calculator_handoff"] = deepcopy(self._calculator_handoff)
                self._storage.update(
                    {
                        "engine_state": self._session.export_state(),
                        "history": self._history[: app.MAX_HISTORY],
                        "calculator_handoff": self._calculator_handoff,
                    }
                )
            else:
                response["calculator_handoff"] = deepcopy(self._calculator_handoff)
            return response

    def units_bootstrap(self: Any) -> dict[str, Any]:
        _ensure_state(self)
        with self._lock:
            return {
                "categories": _unit_payload(),
                "state": deepcopy(self._unit_converter_state),
                "calculator_handoff": deepcopy(self._calculator_handoff),
            }

    def save_unit_converter_state(self: Any, state: dict[str, Any]) -> dict[str, Any]:
        _ensure_state(self)
        with self._lock:
            merged = dict(self._unit_converter_state)
            if isinstance(state, dict):
                merged.update(state)
            self._unit_converter_state = _sanitize_state(merged)
            self._storage.set("unit_converter_state", self._unit_converter_state)
            return deepcopy(self._unit_converter_state)

    def convert_units(
        self: Any,
        expression: str,
        category: str,
        from_unit: str,
        to_unit: str,
        commit: bool = False,
        imported_revision: int | None = None,
    ) -> dict[str, Any]:
        _ensure_state(self)
        with self._lock:
            category_id = str(category)
            if category_id not in _CATEGORY_BY_ID:
                return {"ok": False, "error": "Выберите категорию величины"}

            symbols = _category_symbols(category_id)
            source_symbol = str(from_unit)
            target_symbol = str(to_unit)
            if source_symbol not in symbols or target_symbol not in symbols:
                return {
                    "ok": False,
                    "error": "Единица не относится к выбранной категории",
                }

            try:
                source_value = evaluate_simple(expression)
                source = core.UNIT_DEFS[source_symbol.lower()]
                target = core.UNIT_DEFS[target_symbol.lower()]
                base_value = source.to_base(source_value)
                converted = target.from_base(base_value)
                precision = self._session.settings.precision
                source_text = _format_number(source_value, precision)
                result_text = _format_number(converted, precision)
            except (KeyError, TypeError, ValueError, ArithmeticError) as exc:
                return {"ok": False, "error": str(exc) or "Ошибка преобразования"}

            response = {
                "ok": True,
                "expression": str(expression),
                "source_value": source_text,
                "result": result_text,
                "from_unit": source_symbol,
                "to_unit": target_symbol,
                "category": category_id,
            }
            if commit:
                merged = {
                    "category": category_id,
                    "from_unit": source_symbol,
                    "to_unit": target_symbol,
                    "expression": source_text,
                    "imported_revision": (
                        imported_revision
                        if imported_revision is not None
                        else self._unit_converter_state.get("imported_revision", 0)
                    ),
                }
                self._unit_converter_state = _sanitize_state(merged)
                self._storage.set("unit_converter_state", self._unit_converter_state)
                response["state"] = deepcopy(self._unit_converter_state)
            return response

    app.AppApi.bootstrap = bootstrap
    app.AppApi.suggestions = suggestions
    app.AppApi.commit = commit
    app.AppApi.units_bootstrap = units_bootstrap
    app.AppApi.save_unit_converter_state = save_unit_converter_state
    app.AppApi.convert_units = convert_units
    _ensure_state(app._api)
