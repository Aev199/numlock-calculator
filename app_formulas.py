"""Persistent saved formulas and engineering profiles for NumCalc.

The calculator remains the source of truth for parsing and dimensional
arithmetic.  This module only owns the small persistence/API layer around
formula templates and profiles; formula evaluation is delegated to a cloned
``CalculatorSession`` so previews never mutate the user's variables,
memories, or answer.
"""

from __future__ import annotations

import ast
import re
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

import calc_engine as core
from unit_conversion import (
    category_symbols,
    ensure_state as ensure_unit_state,
    plain_result,
    sanitize_state,
)


MAX_FORMULAS = 200
MAX_PROFILES = 40
MAX_FORMULA_NAME = 80
MAX_FORMULA_EXPRESSION = 1600
MAX_DESCRIPTION = 240
MAX_PARAMETERS = 32
MAX_PARAMETER_NAME = 48
MAX_PARAMETER_VALUE = 240
MAX_CONSTANTS = 32
MAX_PREFERRED_UNITS = 24

_NAME_RE = re.compile(r"^[A-Za-zА-Яа-я_][\wА-Яа-я]*$")
_FORMULA_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
_PROFILE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
_PROFILE_SETTINGS = {
    "angle_mode",
    "number_base",
    "precision",
    "number_format",
    "decimal_separator",
}
_UNIT_STATE_KEYS = {"category", "from_unit", "to_unit", "expression"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _text(value: Any, *, limit: int, default: str = "") -> str:
    text = str(value if value is not None else default).strip()
    return text[:limit]


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _error(message: str, **extra: Any) -> dict[str, Any]:
    return {"ok": False, "error": message, **extra}


def _valid_name(name: str) -> bool:
    return bool(_NAME_RE.fullmatch(name))


def _reserved_names() -> set[str]:
    return {
        *(name.lower() for name in core.FUNCTION_NAMES),
        "pi",
        "e",
        "tau",
        "ans",
    }


def _normalize_settings(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    filtered = {key: item for key, item in value.items() if key in _PROFILE_SETTINGS}
    if not filtered:
        return {}
    return core.EngineSettings.from_mapping(filtered).as_dict()


def _normalize_parameter(raw: Any) -> tuple[dict[str, Any] | None, str | None]:
    if isinstance(raw, str):
        raw = {"name": raw}
    if not isinstance(raw, dict):
        return None, "Параметр должен быть объектом"

    name = _text(raw.get("name", raw.get("label", "")), limit=MAX_PARAMETER_NAME)
    if not _valid_name(name):
        return None, f"Некорректное имя параметра: {name or 'пусто'}"
    if name.lower() in _reserved_names():
        return None, f"Имя параметра зарезервировано: {name}"

    default = raw.get("default", "")
    if default is None:
        default = ""
    if isinstance(default, (int, float)) and not isinstance(default, bool):
        default = str(default)
    default = _text(default, limit=MAX_PARAMETER_VALUE)
    unit = _text(raw.get("unit", ""), limit=32)
    label = _text(raw.get("label", name), limit=80) or name
    description = _text(raw.get("description", ""), limit=MAX_DESCRIPTION)
    return {
        "name": name,
        "label": label,
        "default": default,
        "unit": unit,
        "description": description,
    }, None


def _validate_expression(expression: str) -> str | None:
    if not expression:
        return "Введите выражение формулы"
    try:
        ast.parse(core.prepare_for_ast(expression), mode="eval")
    except (SyntaxError, core.CalculationError, ValueError) as exc:
        return f"Некорректное выражение формулы: {exc}"
    return None


def _normalize_formula(raw: Any, existing: dict[str, Any] | None = None) -> tuple[dict[str, Any] | None, str | None]:
    data = _mapping(raw)
    formula_id = _text(data.get("id", existing.get("id", "") if existing else ""), limit=80)
    if formula_id and not _FORMULA_ID_RE.fullmatch(formula_id):
        return None, "Некорректный идентификатор формулы"
    name = _text(data.get("name", existing.get("name", "") if existing else ""), limit=MAX_FORMULA_NAME)
    if not name:
        return None, "Введите название формулы"
    expression = _text(
        data.get("expression", existing.get("expression", "") if existing else ""),
        limit=MAX_FORMULA_EXPRESSION,
    )
    expression_error = _validate_expression(expression)
    if expression_error:
        return None, expression_error

    raw_parameters = data.get(
        "parameters",
        existing.get("parameters", []) if existing else [],
    )
    if not isinstance(raw_parameters, list):
        return None, "Параметры формулы должны быть списком"
    if len(raw_parameters) > MAX_PARAMETERS:
        return None, f"Допустимо не более {MAX_PARAMETERS} параметров"
    parameters: list[dict[str, Any]] = []
    names: set[str] = set()
    for raw_parameter in raw_parameters:
        parameter, error = _normalize_parameter(raw_parameter)
        if error:
            return None, error
        assert parameter is not None
        lowered = parameter["name"].lower()
        if lowered in names:
            return None, f"Параметр повторяется: {parameter['name']}"
        names.add(lowered)
        parameters.append(parameter)

    timestamp = _now()
    return {
        "id": formula_id or _new_id("formula"),
        "name": name,
        "expression": expression,
        "description": _text(data.get("description", existing.get("description", "") if existing else ""), limit=MAX_DESCRIPTION),
        "parameters": parameters,
        "settings": _normalize_settings(data.get("settings", existing.get("settings", {}) if existing else {})),
        "created_at": str(data.get("created_at", existing.get("created_at", timestamp) if existing else timestamp) or timestamp),
        "updated_at": timestamp,
    }, None


def _normalize_constants(value: Any) -> tuple[dict[str, str] | None, str | None]:
    if value in (None, ""):
        return {}, None
    if not isinstance(value, dict):
        return None, "Константы профиля должны быть объектом"
    if len(value) > MAX_CONSTANTS:
        return None, f"Допустимо не более {MAX_CONSTANTS} констант"
    constants: dict[str, str] = {}
    reserved = _reserved_names()
    for raw_name, raw_value in value.items():
        name = _text(raw_name, limit=MAX_PARAMETER_NAME)
        if not _valid_name(name):
            return None, f"Некорректное имя константы: {name or 'пусто'}"
        if name.lower() in reserved:
            return None, f"Имя константы зарезервировано: {name}"
        value_text = _text(raw_value, limit=MAX_PARAMETER_VALUE)
        if not value_text:
            return None, f"Пустое значение константы: {name}"
        constants[name] = value_text
        reserved.add(name.lower())
    return constants, None


def _normalize_preferred_units(value: Any) -> tuple[list[str] | None, str | None]:
    if value in (None, ""):
        return [], None
    if not isinstance(value, list):
        return None, "Предпочтительные единицы должны быть списком"
    preferred_units: list[str] = []
    for raw_value in value[:MAX_PREFERRED_UNITS]:
        unit_text = _text(raw_value, limit=32)
        if not unit_text:
            continue
        unit = core.get_unit(unit_text)
        if unit is None:
            return None, f"Неизвестная единица профиля: {unit_text}"
        if unit.symbol not in preferred_units:
            preferred_units.append(unit.symbol)
    return preferred_units, None


def _normalize_profile(
    raw: Any,
    existing: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    data = _mapping(raw)
    profile_id = _text(data.get("id", existing.get("id", "") if existing else ""), limit=80)
    if profile_id and not _PROFILE_ID_RE.fullmatch(profile_id):
        return None, "Некорректный идентификатор профиля"
    name = _text(data.get("name", existing.get("name", "") if existing else ""), limit=MAX_FORMULA_NAME)
    if not name:
        return None, "Введите название профиля"

    raw_formula_ids = data.get(
        "formula_ids",
        existing.get("formula_ids", []) if existing else [],
    )
    if not isinstance(raw_formula_ids, list):
        return None, "Формулы профиля должны быть списком"
    formula_ids: list[str] = []
    for value in raw_formula_ids[:MAX_FORMULAS]:
        formula_id = _text(value, limit=80)
        if formula_id and formula_id not in formula_ids:
            formula_ids.append(formula_id)

    constants, error = _normalize_constants(
        data.get("constants", existing.get("constants", {}) if existing else {})
    )
    if error:
        return None, error
    assert constants is not None

    raw_units = data.get(
        "preferred_units",
        existing.get("preferred_units", []) if existing else [],
    )
    preferred_units, error = _normalize_preferred_units(raw_units)
    if error:
        return None, error
    assert preferred_units is not None

    timestamp = _now()
    return {
        "id": profile_id or _new_id("profile"),
        "name": name,
        "description": _text(data.get("description", existing.get("description", "") if existing else ""), limit=MAX_DESCRIPTION),
        "formula_ids": formula_ids,
        "constants": constants,
        "preferred_units": preferred_units,
        "settings": _normalize_settings(
            data.get("settings", existing.get("settings", {}) if existing else {})
        ),
        "created_at": str(data.get("created_at", existing.get("created_at", timestamp) if existing else timestamp) or timestamp),
        "updated_at": timestamp,
    }, None


def _public_profile(profile: dict[str, Any] | None) -> dict[str, Any] | None:
    return deepcopy(profile) if profile else None


def _profile_constants(self: Any) -> dict[str, str]:
    profile = next(
        (item for item in self._profiles if item.get("id") == self._active_profile_id),
        None,
    )
    return dict(profile.get("constants", {})) if profile else {}


def _formula_by_id(self: Any, formula_id: Any) -> dict[str, Any] | None:
    wanted = str(formula_id or "")
    return next((item for item in self._formulas if item.get("id") == wanted), None)


def _profile_by_id(self: Any, profile_id: Any) -> dict[str, Any] | None:
    wanted = str(profile_id or "")
    return next((item for item in self._profiles if item.get("id") == wanted), None)


def _profile_allows_formula(self: Any, formula_id: Any) -> bool:
    profile = _profile_by_id(self, self._active_profile_id)
    if not profile:
        return True
    allowed = profile.get("formula_ids", [])
    return not allowed or str(formula_id) in allowed


def _apply_preferred_units(
    profile: dict[str, Any] | None,
    state: dict[str, Any],
) -> dict[str, Any]:
    normalized = sanitize_state(state)
    if not profile:
        return normalized
    preferred = [
        str(item)
        for item in profile.get("preferred_units", [])
        if item
    ]
    if not preferred:
        return normalized
    symbols = set(category_symbols(normalized["category"]))
    matches = [item for item in preferred if item in symbols]
    if not matches:
        return normalized
    source = matches[0]
    target = next(
        (item for item in matches[1:] if item != source),
        normalized["to_unit"],
    )
    return sanitize_state(normalized | {"from_unit": source, "to_unit": target})


def _ensure_state(self: Any) -> None:
    if getattr(self, "_formula_state_loaded", False):
        return
    self._formula_state_loaded = True
    raw_formulas = self._storage.get("formulas", self._storage.get("saved_formulas", []))
    raw_profiles = self._storage.get("profiles", self._storage.get("engineering_profiles", []))
    self._formulas = []
    self._profiles = []
    if isinstance(raw_formulas, list):
        for raw in raw_formulas[:MAX_FORMULAS]:
            formula, _error_message = _normalize_formula(raw)
            if formula and not any(item["id"] == formula["id"] for item in self._formulas):
                self._formulas.append(formula)
    if isinstance(raw_profiles, list):
        for raw in raw_profiles[:MAX_PROFILES]:
            profile, _error_message = _normalize_profile(raw)
            if profile and not any(item["id"] == profile["id"] for item in self._profiles):
                self._profiles.append(profile)
    active = self._storage.get("active_profile_id")
    self._active_profile_id = str(active) if active and _profile_by_id(self, active) else None
    saved_base_settings = self._storage.get("profile_base_settings")
    self._profile_base_settings = (
        core.EngineSettings.from_mapping(saved_base_settings).as_dict()
        if isinstance(saved_base_settings, dict)
        else None
    )
    saved_base_units = self._storage.get("profile_base_unit_state")
    self._profile_base_unit_state = (
        sanitize_state(saved_base_units)
        if isinstance(saved_base_units, dict)
        else None
    )
    ensure_unit_state(self)
    active_profile = _profile_by_id(self, self._active_profile_id)
    if active_profile and active_profile.get("settings"):
        self._session.set_settings(active_profile["settings"])
    if active_profile:
        self._unit_converter_state = _apply_preferred_units(
            active_profile,
            self._unit_converter_state,
        )


def _persist_state(self: Any) -> None:
    self._storage.update(
        {
            "formulas": deepcopy(self._formulas),
            "profiles": deepcopy(self._profiles),
            "active_profile_id": self._active_profile_id,
            "profile_base_settings": deepcopy(getattr(self, "_profile_base_settings", None)),
            "profile_base_unit_state": deepcopy(
                getattr(self, "_profile_base_unit_state", None)
            ),
        }
    )


def _clone_session(self: Any, settings: dict[str, Any]) -> Any:
    state = self._session.export_state()
    session = type(self._session)(
        core.EngineSettings.from_mapping(settings),
        state.get("variables", {}),
        state.get("memories", []),
    )
    session.restore_ans(state.get("ans"))
    return session


def _assign_value(session: Any, name: str, value: Any) -> tuple[Any | None, str | None]:
    if isinstance(value, bool) or value is None:
        return None, "Значение параметра должно быть числом или выражением"
    value_text = _text(value, limit=MAX_PARAMETER_VALUE)
    if not value_text:
        return None, "Пустое значение параметра"
    # The core calculator deliberately reserves unit names for ordinary
    # assignments (``m := 1`` would otherwise make ``m`` ambiguous).  A
    # formula parameter such as the conventional engineering ``M`` should
    # still be usable.  Evaluate its value under a private name, then expose
    # the resulting Quantity under the parameter's normalized identifier.
    assignment_name = name
    shadowed_unit = name.lower() in core.UNIT_DEFS
    if shadowed_unit:
        assignment_name = "__numcalc_formula_value"
    result = session.evaluate(f"{assignment_name} := {value_text}", commit=True)
    if not result.ok:
        return None, result.error or f"Не удалось вычислить параметр {name}"
    if shadowed_unit:
        quantity = session.variables.get(assignment_name.lower())
        if quantity is None:
            return None, f"Не удалось сохранить параметр {name}"
        session.variables[name.lower()] = quantity
        session.variables.pop(assignment_name.lower(), None)
    return result, None


def _with_parameter_unit(parameter: dict[str, Any], value: Any) -> str:
    value_text = _text(value, limit=MAX_PARAMETER_VALUE)
    unit = _text(parameter.get("unit", ""), limit=32)
    if not unit:
        return value_text
    # A unit field is a default presentation/input unit.  An explicitly
    # supplied unit or conversion target wins over it.
    if re.search(r"\d\s+[A-Za-zА-Яа-я°]", value_text) or re.search(r"\bto\b", value_text, re.IGNORECASE):
        return value_text
    return f"({value_text}) {unit}"


def _formula_response(
    formula: dict[str, Any],
    result: Any,
    values: dict[str, str],
) -> dict[str, Any]:
    response = result.as_dict()
    response.update(
        {
            "formula_id": formula["id"],
            "formula_name": formula["name"],
            "formula": deepcopy(formula),
            "parameters": values,
            "formula_expression": formula["expression"],
        }
    )
    return response


def install(app: Any) -> None:
    """Install formula/profile APIs without changing the calculator core."""

    if getattr(app, "_formulas_backend_installed", False):
        return
    app._formulas_backend_installed = True

    original_bootstrap = app.AppApi.bootstrap
    original_suggestions = app.AppApi.suggestions

    def bootstrap(self: Any) -> dict[str, Any]:
        _ensure_state(self)
        data = original_bootstrap(self)
        active = _profile_by_id(self, self._active_profile_id)
        data["formulas"] = deepcopy(self._formulas)
        data["profiles"] = deepcopy(self._profiles)
        data["active_profile_id"] = self._active_profile_id
        data["active_profile"] = _public_profile(active)
        data["profile_constants"] = _profile_constants(self)
        data["available_formula_ids"] = [
            formula["id"]
            for formula in self._formulas
            if _profile_allows_formula(self, formula["id"])
        ]
        return data

    def suggestions(self: Any, query: str = "") -> list[dict[str, Any]]:
        _ensure_state(self)
        items = list(original_suggestions(self, query))
        needle = str(query or "").strip().lower()
        for formula in self._formulas:
            if not _profile_allows_formula(self, formula["id"]):
                continue
            if needle and not any(
                needle in str(value).lower()
                for value in (formula.get("name"), formula.get("expression"), formula.get("description"))
            ):
                continue
            items.append(
                {
                    "kind": "formula",
                    "group": "Сохранённые формулы",
                    "label": formula["name"],
                    "insert": formula["expression"],
                    "description": formula.get("description") or "Сохранённая формула",
                    "formula_id": formula["id"],
                }
            )
        return items[:160]

    def save_formula(self: Any, payload: dict[str, Any]) -> dict[str, Any]:
        _ensure_state(self)
        with self._lock:
            formula_id = str(_mapping(payload).get("id", "") or "")
            existing = _formula_by_id(self, formula_id) if formula_id else None
            if formula_id and existing is None:
                return _error("Формула не найдена")
            formula, error = _normalize_formula(payload, existing)
            if error:
                return _error(error)
            assert formula is not None
            duplicate = next(
                (
                    item
                    for item in self._formulas
                    if item["id"] != formula["id"]
                    and item["name"].casefold() == formula["name"].casefold()
                ),
                None,
            )
            if duplicate:
                return _error("Формула с таким названием уже существует")
            if existing:
                index = self._formulas.index(existing)
                self._formulas[index] = formula
            else:
                if len(self._formulas) >= MAX_FORMULAS:
                    return _error(f"Достигнут лимит формул: {MAX_FORMULAS}")
                self._formulas.insert(0, formula)
            _persist_state(self)
            return {"ok": True, "formula": deepcopy(formula), "formulas": deepcopy(self._formulas)}

    def delete_formula(self: Any, formula_id: str) -> dict[str, Any]:
        _ensure_state(self)
        with self._lock:
            formula = _formula_by_id(self, formula_id)
            if formula is None:
                return _error("Формула не найдена")
            self._formulas = [item for item in self._formulas if item["id"] != formula["id"]]
            for profile in self._profiles:
                profile["formula_ids"] = [
                    item for item in profile.get("formula_ids", []) if item != formula["id"]
                ]
            _persist_state(self)
            return {"ok": True, "deleted": formula["id"], "formulas": deepcopy(self._formulas), "profiles": deepcopy(self._profiles)}

    def save_profile(self: Any, payload: dict[str, Any]) -> dict[str, Any]:
        _ensure_state(self)
        with self._lock:
            profile_id = str(_mapping(payload).get("id", "") or "")
            existing = _profile_by_id(self, profile_id) if profile_id else None
            if profile_id and existing is None:
                return _error("Профиль не найден")
            profile, error = _normalize_profile(payload, existing)
            if error:
                return _error(error)
            assert profile is not None
            formula_ids = set(item["id"] for item in self._formulas)
            missing = [item for item in profile["formula_ids"] if item not in formula_ids]
            if missing:
                return _error(f"Формула профиля не найдена: {missing[0]}")
            duplicate = next(
                (
                    item
                    for item in self._profiles
                    if item["id"] != profile["id"]
                    and item["name"].casefold() == profile["name"].casefold()
                ),
                None,
            )
            if duplicate:
                return _error("Профиль с таким названием уже существует")
            if existing:
                index = self._profiles.index(existing)
                self._profiles[index] = profile
            else:
                if len(self._profiles) >= MAX_PROFILES:
                    return _error(f"Достигнут лимит профилей: {MAX_PROFILES}")
                self._profiles.insert(0, profile)
            if self._active_profile_id == profile["id"] and profile.get("settings"):
                self._session.set_settings(profile["settings"])
                self._storage.update({"engine_state": self._session.export_state()})
            if self._active_profile_id == profile["id"]:
                ensure_unit_state(self)
                self._unit_converter_state = _apply_preferred_units(
                    profile,
                    self._unit_converter_state,
                )
                self._storage.set("unit_converter_state", self._unit_converter_state)
            _persist_state(self)
            return {"ok": True, "profile": deepcopy(profile), "profiles": deepcopy(self._profiles)}

    def delete_profile(self: Any, profile_id: str) -> dict[str, Any]:
        _ensure_state(self)
        with self._lock:
            profile = _profile_by_id(self, profile_id)
            if profile is None:
                return _error("Профиль не найден")
            self._profiles = [item for item in self._profiles if item["id"] != profile["id"]]
            if self._active_profile_id == profile["id"]:
                self._active_profile_id = None
                if getattr(self, "_profile_base_settings", None):
                    self._session.set_settings(self._profile_base_settings)
                self._profile_base_settings = None
                ensure_unit_state(self)
                if getattr(self, "_profile_base_unit_state", None):
                    self._unit_converter_state = sanitize_state(
                        self._profile_base_unit_state
                    )
                    self._storage.set(
                        "unit_converter_state",
                        self._unit_converter_state,
                    )
                self._profile_base_unit_state = None
                self._storage.update({"engine_state": self._session.export_state()})
            _persist_state(self)
            return {"ok": True, "deleted": profile["id"], "profiles": deepcopy(self._profiles), "active_profile_id": self._active_profile_id}

    def set_active_profile(self: Any, profile_id: str | None) -> dict[str, Any]:
        _ensure_state(self)
        with self._lock:
            requested = str(profile_id or "")
            profile = _profile_by_id(self, requested) if requested else None
            if requested and profile is None:
                return _error("Профиль не найден")
            previous_profile_id = self._active_profile_id
            ensure_unit_state(self)
            if profile and profile["id"] != previous_profile_id:
                if getattr(self, "_profile_base_unit_state", None):
                    self._unit_converter_state = sanitize_state(
                        self._profile_base_unit_state
                    )
                else:
                    self._profile_base_unit_state = deepcopy(
                        self._unit_converter_state
                    )
            if not profile and previous_profile_id:
                if getattr(self, "_profile_base_settings", None):
                    self._session.set_settings(self._profile_base_settings)
                self._profile_base_settings = None
                if getattr(self, "_profile_base_unit_state", None):
                    self._unit_converter_state = sanitize_state(
                        self._profile_base_unit_state
                    )
                self._profile_base_unit_state = None
            elif profile and profile["id"] != previous_profile_id:
                if not getattr(self, "_profile_base_settings", None):
                    self._profile_base_settings = self._session.settings.as_dict()
            self._active_profile_id = profile["id"] if profile else None
            if profile and profile.get("settings"):
                self._session.set_settings(profile["settings"])
            if profile:
                self._unit_converter_state = _apply_preferred_units(
                    profile,
                    self._unit_converter_state,
                )
            self._storage.set("unit_converter_state", self._unit_converter_state)
            _persist_state(self)
            self._storage.update({"engine_state": self._session.export_state()})
            return {
                "ok": True,
                "active_profile_id": self._active_profile_id,
                "active_profile": _public_profile(profile),
                "settings": self._session.settings.as_dict(),
                "profile_constants": _profile_constants(self),
                "unit_converter_state": deepcopy(self._unit_converter_state),
            }

    def evaluate_formula(
        self: Any,
        formula_id: str,
        parameters: dict[str, Any] | None = None,
        commit: bool = False,
    ) -> dict[str, Any]:
        _ensure_state(self)
        with self._lock:
            formula = _formula_by_id(self, formula_id)
            if formula is None:
                return _error("Формула не найдена")
            if not _profile_allows_formula(self, formula["id"]):
                return _error("Формула не входит в активный профиль", formula_id=formula["id"])
            values_input = _mapping(parameters)
            settings = self._session.settings.as_dict() | formula.get("settings", {})
            session = _clone_session(self, settings)
            used_values: dict[str, str] = {}

            for name, value in _profile_constants(self).items():
                _result, error = _assign_value(session, name, value)
                if error:
                    return _error(f"Константа профиля {name}: {error}", formula_id=formula["id"])

            for parameter in formula.get("parameters", []):
                name = parameter["name"]
                candidate = next(
                    (value for key, value in values_input.items() if str(key).lower() == name.lower()),
                    parameter.get("default", ""),
                )
                if candidate in (None, ""):
                    return _error(f"Введите параметр: {parameter.get('label') or name}", formula_id=formula["id"])
                value_text = _with_parameter_unit(parameter, candidate)
                _result, error = _assign_value(session, name, value_text)
                if error:
                    return _error(f"Параметр {parameter.get('label') or name}: {error}", formula_id=formula["id"])
                used_values[name] = value_text

            result = session.evaluate(formula["expression"], commit=True)
            response = _formula_response(formula, result, used_values)
            if not result.ok:
                if hasattr(self, "_calculator_handoff"):
                    response["calculator_handoff"] = deepcopy(self._calculator_handoff)
                return response

            if commit:
                self._session.ans = session.ans
                if hasattr(self, "_calculator_handoff"):
                    plain = plain_result(response)
                    if plain:
                        self._calculator_handoff = {
                            "revision": int(self._calculator_handoff.get("revision", 0)) + 1,
                            "value": plain,
                            "updated_at": _now(),
                        }
                    response["calculator_handoff"] = deepcopy(self._calculator_handoff)
                self._sequence += 1
                entry = app.make_history_entry(
                    result,
                    core.EngineSettings.from_mapping(settings),
                    self._sequence,
                ).as_dict()
                entry["formula_id"] = formula["id"]
                entry["formula_name"] = formula["name"]
                entry["formula_parameters"] = used_values
                self._history.insert(0, entry)
                self._history = self._history[: app.MAX_HISTORY]
                response["history_entry"] = entry
                self._storage.update(
                    {
                        "engine_state": self._session.export_state(),
                        "history": self._history[: app.MAX_HISTORY],
                        **(
                            {"calculator_handoff": self._calculator_handoff}
                            if hasattr(self, "_calculator_handoff")
                            else {}
                        ),
                    }
                )
            elif hasattr(self, "_calculator_handoff"):
                response["calculator_handoff"] = deepcopy(self._calculator_handoff)
            return response

    def formula_bootstrap(self: Any) -> dict[str, Any]:
        _ensure_state(self)
        with self._lock:
            active = _profile_by_id(self, self._active_profile_id)
            return {
                "formulas": deepcopy(self._formulas),
                "profiles": deepcopy(self._profiles),
                "active_profile_id": self._active_profile_id,
                "active_profile": _public_profile(active),
                "profile_constants": _profile_constants(self),
                "settings": self._session.settings.as_dict(),
                "suggestions": self.suggestions(""),
                "unit_converter_state": deepcopy(self._unit_converter_state),
            }

    app.AppApi.bootstrap = bootstrap
    app.AppApi.suggestions = suggestions
    app.AppApi.save_formula = save_formula
    app.AppApi.delete_formula = delete_formula
    app.AppApi.save_profile = save_profile
    app.AppApi.delete_profile = delete_profile
    app.AppApi.set_active_profile = set_active_profile
    app.AppApi.evaluate_formula = evaluate_formula
    app.AppApi.run_formula = evaluate_formula
    app.AppApi.formula_bootstrap = formula_bootstrap
    _ensure_state(app._api)
