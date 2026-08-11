"""Composable unit catalog for the unit-conversion workspace.

The calculator keeps a compact canonical unit registry. The converter can
compose compatible numerator/denominator choices on demand so the UI does not
need a huge flat list (for example g/cm3, kg/dm3, kN/cm2, ...).
"""

from __future__ import annotations

import math
from copy import deepcopy
from fractions import Fraction
from typing import Any

import calc_engine as quantity_engine
import unit_conversion as legacy


DENSITY = quantity_engine._dim_sub(
    quantity_engine.MASS,
    quantity_engine._dim_mul(quantity_engine.LENGTH, Fraction(3)),
)

CATEGORY_DIMENSIONS = dict(legacy.CATEGORY_DIMENSIONS)
CATEGORY_DIMENSIONS["density"] = DENSITY


def _unit(
    symbol: str,
    label: str,
    scale: float,
    dimensions: quantity_engine.Dim,
) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "label": label,
        "unit": quantity_engine.UnitDef(symbol, float(scale), dimensions),
    }


def _registered(symbol: str, label: str | None = None) -> dict[str, Any]:
    resolved = quantity_engine.get_unit(symbol)
    if resolved is None:
        raise RuntimeError(f"Missing base unit: {symbol}")
    return {
        "symbol": symbol,
        "label": label or symbol,
        "unit": resolved,
    }


def _length(symbol: str, label: str, scale: float) -> dict[str, Any]:
    return _unit(symbol, label, scale, quantity_engine.LENGTH)


def _power(
    base: dict[str, Any],
    exponent: int,
    symbol: str,
    label: str,
) -> dict[str, Any]:
    unit = base["unit"]
    return _unit(
        symbol,
        label,
        unit.scale**exponent,
        quantity_engine._dim_mul(unit.dimensions, Fraction(exponent)),
    )


LENGTH_COMPONENTS = (
    _registered("mm", "мм"),
    _registered("cm", "см"),
    _length("dm", "дм", 0.1),
    _registered("m", "м"),
    _registered("km", "км"),
    _registered("in", "in"),
    _registered("ft", "ft"),
)
AREA_COMPONENTS = tuple(
    _power(item, 2, f"{item['symbol']}2", f"{item['label']}²")
    for item in LENGTH_COMPONENTS
    if item["symbol"] not in {"km"}
)
VOLUME_COMPONENTS = tuple(
    _power(item, 3, f"{item['symbol']}3", f"{item['label']}³")
    for item in LENGTH_COMPONENTS
    if item["symbol"] not in {"km", "in"}
) + (_registered("L", "л"),)
MASS_COMPONENTS = (
    _registered("g", "г"),
    _registered("kg", "кг"),
    _registered("t", "т"),
    _registered("oz", "oz"),
    _registered("lb", "lb"),
)
FORCE_COMPONENTS = (
    _registered("N", "Н"),
    _registered("daN", "daN"),
    _registered("kN", "кН"),
    _registered("MN", "МН"),
    _registered("kgf", "кгс"),
    _registered("tf", "тс"),
    _registered("lbf", "lbf"),
    _registered("kip", "kip"),
)
TIME_COMPONENTS = (
    _registered("s", "с"),
    _registered("min", "мин"),
    _registered("h", "ч"),
)
TIME_SQUARED_COMPONENTS = tuple(
    _power(item, 2, f"{item['symbol']}2", f"{item['label']}²")
    for item in TIME_COMPONENTS
)


def _public_component(item: dict[str, Any]) -> dict[str, str]:
    return {"symbol": item["symbol"], "label": item["label"]}


def _compose(
    left: dict[str, Any],
    right: dict[str, Any],
    operator: str,
) -> quantity_engine.UnitDef:
    lhs = left["unit"]
    rhs = right["unit"]
    if operator == "/":
        dimensions = quantity_engine._dim_sub(lhs.dimensions, rhs.dimensions)
        scale = lhs.scale / rhs.scale
        symbol = f"{left['symbol']}/{right['symbol']}"
    elif operator == "*":
        dimensions = quantity_engine._dim_add(lhs.dimensions, rhs.dimensions)
        scale = lhs.scale * rhs.scale
        symbol = f"{left['symbol']}*{right['symbol']}"
    else:
        raise ValueError("Unsupported compound unit operator")
    return quantity_engine.UnitDef(symbol, scale, dimensions)


def _display(left: dict[str, Any], right: dict[str, Any], operator: str) -> str:
    glyph = "·" if operator == "*" else "/"
    return f"{left['label']}{glyph}{right['label']}"


def _preset(symbol: str, label: str | None = None) -> dict[str, Any]:
    unit = quantity_engine.get_unit(symbol)
    if unit is None:
        raise RuntimeError(f"Missing preset unit: {symbol}")
    return {
        "symbol": unit.symbol,
        "label": label or unit.symbol,
        "unit": unit,
    }


COMPOUND_SCHEMAS: dict[str, dict[str, Any]] = {
    "distributed_force": {
        "label": "Распределённые силы",
        "operator": "/",
        "left_label": "Сила",
        "right_label": "Длина",
        "left": FORCE_COMPONENTS,
        "right": LENGTH_COMPONENTS,
        "presets": (),
        "defaults": ("kN/m", "N/m"),
        "component_defaults": ("kN", "m"),
    },
    "moment": {
        "label": "Моменты сил",
        "operator": "*",
        "left_label": "Сила",
        "right_label": "Длина",
        "left": FORCE_COMPONENTS,
        "right": LENGTH_COMPONENTS,
        "presets": (),
        "defaults": ("kN*m", "N*m"),
        "component_defaults": ("kN", "m"),
    },
    "speed": {
        "label": "Скорости",
        "operator": "/",
        "left_label": "Длина",
        "right_label": "Время",
        "left": LENGTH_COMPONENTS,
        "right": TIME_COMPONENTS,
        "presets": (),
        "defaults": ("m/s", "km/h"),
        "component_defaults": ("m", "s"),
    },
    "acceleration": {
        "label": "Ускорения",
        "operator": "/",
        "left_label": "Длина",
        "right_label": "Время²",
        "left": LENGTH_COMPONENTS,
        "right": TIME_SQUARED_COMPONENTS,
        "presets": (_preset("g0", "g"),),
        "defaults": ("m/s2", "g0"),
        "component_defaults": ("m", "s2"),
    },
    "pressure": {
        "label": "Давления",
        "operator": "/",
        "left_label": "Сила",
        "right_label": "Площадь",
        "left": FORCE_COMPONENTS,
        "right": AREA_COMPONENTS,
        "presets": (
            _preset("Pa", "Па"),
            _preset("kPa", "кПа"),
            _preset("MPa", "МПа"),
            _preset("GPa", "ГПа"),
            _preset("bar", "bar"),
            _preset("atm", "atm"),
            _preset("mmHg", "мм рт. ст."),
            _preset("psi", "psi"),
        ),
        "defaults": ("kPa", "MPa"),
        "component_defaults": ("kN", "m2"),
    },
    "specific_weight": {
        "label": "Удельный вес",
        "operator": "/",
        "left_label": "Сила",
        "right_label": "Объём",
        "left": FORCE_COMPONENTS,
        "right": VOLUME_COMPONENTS,
        "presets": (),
        "defaults": ("kN/m3", "N/m3"),
        "component_defaults": ("kN", "m3"),
    },
    "density": {
        "label": "Плотность",
        "operator": "/",
        "left_label": "Масса",
        "right_label": "Объём",
        "left": MASS_COMPONENTS,
        "right": VOLUME_COMPONENTS,
        "presets": (),
        "defaults": ("kg/m3", "g/cm3"),
        "component_defaults": ("kg", "m3"),
    },
}


_DYNAMIC_UNITS: dict[tuple[str, str], quantity_engine.UnitDef] = {}
_DYNAMIC_LABELS: dict[tuple[str, str], str] = {}


def _schema_units(
    category_id: str,
    schema: dict[str, Any],
) -> tuple[tuple[str, str], ...]:
    expected = CATEGORY_DIMENSIONS[category_id]
    result: list[tuple[str, str]] = []
    seen: set[str] = set()
    for left in schema["left"]:
        for right in schema["right"]:
            unit = _compose(left, right, schema["operator"])
            if unit.dimensions != expected:
                continue
            display = _display(left, right, schema["operator"])
            _DYNAMIC_UNITS[(category_id, unit.symbol)] = unit
            _DYNAMIC_LABELS[(category_id, unit.symbol)] = display
            if unit.symbol not in seen:
                seen.add(unit.symbol)
                result.append((unit.symbol, display))
    for preset in schema.get("presets", ()):
        unit = preset["unit"]
        if unit.dimensions != expected:
            continue
        _DYNAMIC_UNITS[(category_id, unit.symbol)] = unit
        _DYNAMIC_LABELS[(category_id, unit.symbol)] = preset["label"]
        if unit.symbol not in seen:
            seen.add(unit.symbol)
            result.append((unit.symbol, preset["label"]))

    defaults = tuple(schema.get("defaults", ()))
    if defaults:
        by_symbol = dict(result)
        leading = [
            (symbol, by_symbol[symbol])
            for symbol in defaults
            if symbol in by_symbol
        ]
        default_set = {symbol for symbol, _label in leading}
        result = leading + [item for item in result if item[0] not in default_set]
    return tuple(result)


_COMPOUND_UNITS = {
    category_id: _schema_units(category_id, schema)
    for category_id, schema in COMPOUND_SCHEMAS.items()
}


def _compound_category(category_id: str) -> dict[str, Any]:
    schema = COMPOUND_SCHEMAS[category_id]
    default_left, default_right = schema.get("component_defaults", ("", ""))
    return {
        "id": category_id,
        "label": schema["label"],
        "units": _COMPOUND_UNITS[category_id],
        "picker": {
            "kind": "compound",
            "operator": schema["operator"],
            "left_label": schema["left_label"],
            "right_label": schema["right_label"],
            "left": [_public_component(item) for item in schema["left"]],
            "right": [_public_component(item) for item in schema["right"]],
            "default_left": default_left,
            "default_right": default_right,
            "presets": [
                {"symbol": item["unit"].symbol, "label": item["label"]}
                for item in schema.get("presets", ())
            ],
        },
    }


def _build_categories() -> tuple[dict[str, Any], ...]:
    result: list[dict[str, Any]] = []
    for category in legacy.UNIT_CATEGORIES:
        category_id = category["id"]
        if category_id in COMPOUND_SCHEMAS:
            result.append(_compound_category(category_id))
        else:
            result.append(deepcopy(category))
        if category_id == "specific_weight":
            result.append(_compound_category("density"))
    return tuple(result)


UNIT_CATEGORIES = _build_categories()
CATEGORY_BY_ID = {item["id"]: item for item in UNIT_CATEGORIES}
DEFAULT_STATE = dict(legacy.DEFAULT_STATE)


def resolve_unit(category: str, symbol: str) -> quantity_engine.UnitDef:
    expected = CATEGORY_DIMENSIONS.get(category)
    dynamic = _DYNAMIC_UNITS.get((category, symbol))
    unit = dynamic or quantity_engine.get_unit(symbol)
    if unit is None or unit.dimensions != expected:
        raise ValueError("Неизвестная единица измерения")
    return unit


def unit_display(category: str, symbol: str) -> str:
    return _DYNAMIC_LABELS.get((category, symbol), symbol)


def unit_payload() -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for category in UNIT_CATEGORIES:
        item = {
            "id": category["id"],
            "label": category["label"],
            # Preserve the established public shape for all unit entries.
            "units": [
                {"symbol": symbol, "label": label}
                for symbol, label in category["units"]
            ],
        }
        if "picker" in category:
            item["picker"] = deepcopy(category["picker"])
        payload.append(item)
    return payload


def category_symbols(category_id: str) -> tuple[str, ...]:
    category = (
        CATEGORY_BY_ID.get(category_id)
        or CATEGORY_BY_ID[DEFAULT_STATE["category"]]
    )
    return tuple(symbol for symbol, _label in category["units"])


def sanitize_state(value: Any) -> dict[str, Any]:
    raw = value if isinstance(value, dict) else {}
    category = str(raw.get("category", DEFAULT_STATE["category"]))
    if category not in CATEGORY_BY_ID:
        category = DEFAULT_STATE["category"]
    symbols = category_symbols(category)
    source = str(raw.get("from_unit", symbols[0]))
    target = str(raw.get("to_unit", symbols[1] if len(symbols) > 1 else symbols[0]))
    if source not in symbols:
        source = symbols[0]
    if target not in symbols:
        target = symbols[1] if len(symbols) > 1 else symbols[0]
    if target == source and len(symbols) > 1:
        target = next(symbol for symbol in symbols if symbol != source)
    try:
        imported_revision = max(0, int(raw.get("imported_revision", 0)))
    except (TypeError, ValueError):
        imported_revision = 0
    return {
        "category": category,
        "from_unit": source,
        "to_unit": target,
        "expression": str(raw.get("expression", "")),
        "imported_revision": imported_revision,
    }


def ensure_state(api: Any) -> None:
    if not hasattr(api, "_unit_converter_state"):
        api._unit_converter_state = sanitize_state(
            api._storage.get("unit_converter_state", {})
        )
    if not hasattr(api, "_calculator_handoff"):
        api._calculator_handoff = legacy.sanitize_handoff(
            api._storage.get("calculator_handoff", {})
        )


def convert_value(
    value: float,
    category: str,
    from_unit: str,
    to_unit: str,
) -> float:
    source = resolve_unit(category, from_unit)
    target = resolve_unit(category, to_unit)
    base_value = source.to_base(float(value))
    converted = target.from_base(base_value)
    if not math.isfinite(converted):
        raise ValueError("Результат не является конечным числом")
    return converted


def conversion_quantity(
    value: float,
    category: str,
    from_unit: str,
    to_unit: str,
) -> dict[str, Any]:
    source = resolve_unit(category, from_unit)
    target = resolve_unit(category, to_unit)
    base_value = source.to_base(float(value))
    converted = target.from_base(base_value)
    return quantity_engine.quantity_payload(
        converted,
        target.symbol,
        target.dimensions,
    )
