"""Pure domain helpers for the separate unit-conversion workspace."""

from __future__ import annotations

import ast
import math
import re
from copy import deepcopy
from fractions import Fraction
from typing import Any

import calc_engine as quantity_engine
from number_formatting import format_number as format_display_number


UNIT_CATEGORIES: tuple[dict[str, Any], ...] = (
    {
        "id": "length",
        "label": "Линейные размеры",
        "units": (
            ("mm", "Миллиметр, мм"),
            ("cm", "Сантиметр, см"),
            ("m", "Метр, м"),
            ("km", "Километр, км"),
            ("in", "Дюйм"),
            ("ft", "Фут"),
            ("mi", "Миля"),
        ),
    },
    {
        "id": "area",
        "label": "Площади",
        "units": (
            ("mm2", "Квадратный миллиметр, мм²"),
            ("cm2", "Квадратный сантиметр, см²"),
            ("m2", "Квадратный метр, м²"),
            ("ha", "Гектар"),
            ("km2", "Квадратный километр, км²"),
            ("in2", "Квадратный дюйм"),
            ("ft2", "Квадратный фут"),
        ),
    },
    {
        "id": "volume",
        "label": "Объёмы",
        "units": (
            ("mL", "Миллилитр"),
            ("cm3", "Кубический сантиметр, см³"),
            ("L", "Литр"),
            ("m3", "Кубический метр, м³"),
            ("gal", "Галлон США"),
            ("ft3", "Кубический фут"),
        ),
    },
    {
        "id": "mass",
        "label": "Масса",
        "units": (
            ("g", "Грамм, г"),
            ("kg", "Килограмм, кг"),
            ("t", "Метрическая тонна, т"),
            ("oz", "Унция"),
            ("lb", "Фунт"),
        ),
    },
    {
        "id": "force",
        "label": "Силы",
        "units": (
            ("N", "Ньютон, Н"),
            ("kgf", "Килограмм-сила, кгс"),
            ("tf", "Тонна-сила, тс"),
            ("kN", "Килоньютон, кН"),
            ("MN", "Меганьютон, МН"),
            ("daN", "Деканьютон, daN"),
            ("lbf", "Фунт-сила"),
            ("kip", "Килофунт-сила, kip"),
        ),
    },
    {
        "id": "distributed_force",
        "label": "Распределённые силы",
        "units": (
            ("N/m", "Н/м"),
            ("kgf/m", "кгс/м"),
            ("tf/m", "тс/м"),
            ("kN/m", "кН/м"),
            ("MN/m", "МН/м"),
        ),
    },
    {
        "id": "moment",
        "label": "Моменты сил",
        "units": (
            ("N*m", "Н·м"),
            ("kgf*m", "кгс·м"),
            ("tf*m", "тс·м"),
            ("kN*m", "кН·м"),
            ("MN*m", "МН·м"),
        ),
    },
    {
        "id": "speed",
        "label": "Скорости",
        "units": (
            ("m/s", "м/с"),
            ("km/h", "км/ч"),
            ("ft/s", "фут/с"),
        ),
    },
    {
        "id": "acceleration",
        "label": "Ускорения",
        "units": (
            ("m/s2", "м/с²"),
            ("g0", "g"),
            ("ft/s2", "фут/с²"),
        ),
    },
    {
        "id": "pressure",
        "label": "Давления",
        "units": (
            ("kgf/m2", "кгс/м²"),
            ("tf/m2", "тс/м²"),
            ("Pa", "Паскаль, Па"),
            ("kPa", "Килопаскаль, кПа"),
            ("MPa", "Мегапаскаль, МПа"),
            ("GPa", "Гигапаскаль, ГПа"),
            ("bar", "Бар"),
            ("atm", "Атмосфера"),
            ("mmHg", "мм рт. ст."),
            ("psi", "psi"),
        ),
    },
    {
        "id": "specific_weight",
        "label": "Удельный вес",
        "units": (
            ("N/m3", "Н/м³"),
            ("kgf/m3", "кгс/м³"),
            ("tf/m3", "тс/м³"),
            ("kN/m3", "кН/м³"),
        ),
    },
    {
        "id": "time",
        "label": "Время",
        "units": (
            ("s", "Секунда"),
            ("min", "Минута"),
            ("h", "Час"),
        ),
    },
    {
        "id": "temperature",
        "label": "Температура",
        "units": (
            ("degC", "Градус Цельсия"),
            ("K", "Кельвин"),
            ("degF", "Градус Фаренгейта"),
        ),
    },
)

CATEGORY_BY_ID = {item["id"]: item for item in UNIT_CATEGORIES}
DEFAULT_STATE = {
    "category": "length",
    "from_unit": "m",
    "to_unit": "mm",
    "expression": "",
    "imported_revision": 0,
}
PLAIN_NUMBER = re.compile(
    r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$",
    flags=re.IGNORECASE,
)
ALLOWED_BINARY = {
    ast.Add: lambda left, right: left + right,
    ast.Sub: lambda left, right: left - right,
    ast.Mult: lambda left, right: left * right,
    ast.Div: lambda left, right: left / right,
    ast.Pow: lambda left, right: left**right,
}
ALLOWED_UNARY = {
    ast.UAdd: lambda value: value,
    ast.USub: lambda value: -value,
}

CATEGORY_DIMENSIONS = {
    "length": quantity_engine.LENGTH,
    "area": quantity_engine._dim_mul(quantity_engine.LENGTH, Fraction(2)),
    "volume": quantity_engine._dim_mul(quantity_engine.LENGTH, Fraction(3)),
    "mass": quantity_engine.MASS,
    "force": quantity_engine.FORCE,
    "distributed_force": quantity_engine.DISTRIBUTED_FORCE,
    "moment": quantity_engine.MOMENT,
    "speed": quantity_engine.SPEED,
    "acceleration": quantity_engine.ACCELERATION,
    "pressure": quantity_engine.PRESSURE,
    "specific_weight": quantity_engine.SPECIFIC_WEIGHT,
    "time": quantity_engine.TIME,
    "temperature": quantity_engine.TEMPERATURE,
}


def _catalog_unit(category: str, symbol: str) -> quantity_engine.UnitDef:
    unit = quantity_engine.get_unit(symbol)
    if (
        unit is None
        or unit.dimensions != CATEGORY_DIMENSIONS.get(category)
    ):
        raise ValueError("Неизвестная единица измерения")
    return unit


# Kept as a compatibility view for callers that used the old public mapping.
# Conversion itself goes through calc_engine.UnitDef below.
UNIT_SCALES: dict[str, dict[str, float]] = {
    category_data["id"]: {
        symbol: _catalog_unit(category_data["id"], symbol).scale
        for symbol, _label in category_data["units"]
    }
    for category_data in UNIT_CATEGORIES
}
G0 = quantity_engine.STANDARD_GRAVITY


def unit_payload() -> list[dict[str, Any]]:
    return [
        {
            "id": category["id"],
            "label": category["label"],
            "units": [
                {
                    "symbol": symbol,
                    "label": label,
                    "short": quantity_engine.unit_display_text(symbol),
                }
                for symbol, label in category["units"]
            ],
        }
        for category in UNIT_CATEGORIES
    ]


def category_symbols(category_id: str) -> tuple[str, ...]:
    category = CATEGORY_BY_ID.get(category_id) or CATEGORY_BY_ID[DEFAULT_STATE["category"]]
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


def sanitize_handoff(value: Any) -> dict[str, Any]:
    raw = value if isinstance(value, dict) else {}
    try:
        revision = max(0, int(raw.get("revision", 0)))
    except (TypeError, ValueError):
        revision = 0
    result = str(raw.get("value", "")).strip()
    if result and not PLAIN_NUMBER.fullmatch(result):
        result = ""
    return {
        "revision": revision,
        "value": result,
        "updated_at": str(raw.get("updated_at", "")),
    }


def ensure_state(api: Any) -> None:
    if not hasattr(api, "_unit_converter_state"):
        api._unit_converter_state = sanitize_state(
            api._storage.get("unit_converter_state", {})
        )
    if not hasattr(api, "_calculator_handoff"):
        api._calculator_handoff = sanitize_handoff(
            api._storage.get("calculator_handoff", {})
        )


def normalize_simple_expression(expression: str) -> str:
    value = str(expression or "").replace("\u00a0", " ")
    value = (
        value.replace("×", "*")
        .replace("·", "*")
        .replace("⋅", "*")
        .replace("÷", "/")
    )
    value = value.replace("−", "-").replace("–", "-").replace("—", "-")
    value = re.sub(r"(?<=\d),(?=\d)", ".", value)
    value = value.replace("^", "**").strip()
    if len(value) > 256:
        raise ValueError("Выражение слишком длинное")
    return value


def evaluate_node(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return evaluate_node(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ValueError("Разрешены только числа и арифметические операции")
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and type(node.op) in ALLOWED_UNARY:
        return float(ALLOWED_UNARY[type(node.op)](evaluate_node(node.operand)))
    if isinstance(node, ast.BinOp) and type(node.op) in ALLOWED_BINARY:
        left = evaluate_node(node.left)
        right = evaluate_node(node.right)
        if isinstance(node.op, ast.Div) and right == 0:
            raise ValueError("Деление на ноль")
        if isinstance(node.op, ast.Pow) and abs(right) > 100:
            raise ValueError("Слишком большой показатель степени")
        try:
            result = ALLOWED_BINARY[type(node.op)](left, right)
        except (ArithmeticError, OverflowError) as exc:
            raise ValueError("Некорректная арифметическая операция") from exc
        if isinstance(result, complex) or not math.isfinite(float(result)):
            raise ValueError("Результат не является конечным числом")
        return float(result)
    raise ValueError("Разрешены только числа, скобки и операции + − × ÷ ^")


def evaluate_simple(expression: str) -> float:
    prepared = normalize_simple_expression(expression)
    if not prepared:
        raise ValueError("Введите значение")
    try:
        tree = ast.parse(prepared, mode="eval")
    except SyntaxError as exc:
        raise ValueError("Проверьте арифметическое выражение") from exc
    return evaluate_node(tree)


def convert_value(value: float, category: str, from_unit: str, to_unit: str) -> float:
    source = _catalog_unit(category, from_unit)
    target = _catalog_unit(category, to_unit)
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
    """Return the shared quantity shape for a converter result."""

    source = _catalog_unit(category, from_unit)
    target = _catalog_unit(category, to_unit)
    base_value = source.to_base(float(value))
    converted = target.from_base(base_value)
    return quantity_engine.quantity_payload(
        converted,
        target.symbol,
        target.dimensions,
    )


def format_number(
    value: float,
    precision: int = 12,
    number_format: str = "auto",
    decimal_separator: str = ".",
) -> str:
    """Keep the converter on the same numeric presentation as the calculator."""

    return format_display_number(
        value,
        precision,
        number_format,
        decimal_separator,
    )


def plain_result(response: dict[str, Any]) -> str:
    result = str(response.get("result", "")).strip()
    portable = result.replace(",", ".")
    return portable if PLAIN_NUMBER.fullmatch(portable) else ""


def filter_suggestions(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    return [
        item
        for item in items
        if isinstance(item, dict)
        and item.get("kind") != "unit"
        and item.get("group") != "Единицы"
    ]


def copy_state(value: dict[str, Any]) -> dict[str, Any]:
    """Return a defensive copy for API payloads."""
    return deepcopy(value)
