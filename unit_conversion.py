"""Pure domain helpers for the separate unit-conversion workspace."""

from __future__ import annotations

import ast
import math
import re
from copy import deepcopy
from typing import Any


UNIT_CATEGORIES: tuple[dict[str, Any], ...] = (
    {
        "id": "length",
        "label": "Линейные размеры",
        "units": (
            ("mm", "Миллиметр — мм"),
            ("cm", "Сантиметр — см"),
            ("m", "Метр — м"),
            ("km", "Километр — км"),
            ("in", "Дюйм"),
            ("ft", "Фут"),
            ("mi", "Миля"),
        ),
    },
    {
        "id": "area",
        "label": "Площади",
        "units": (
            ("mm2", "Квадратный миллиметр — мм²"),
            ("cm2", "Квадратный сантиметр — см²"),
            ("m2", "Квадратный метр — м²"),
            ("ha", "Гектар"),
            ("km2", "Квадратный километр — км²"),
            ("in2", "Квадратный дюйм"),
            ("ft2", "Квадратный фут"),
        ),
    },
    {
        "id": "volume",
        "label": "Объёмы",
        "units": (
            ("mL", "Миллилитр"),
            ("cm3", "Кубический сантиметр — см³"),
            ("L", "Литр"),
            ("m3", "Кубический метр — м³"),
            ("gal", "Галлон США"),
            ("ft3", "Кубический фут"),
        ),
    },
    {
        "id": "mass",
        "label": "Масса",
        "units": (
            ("g", "Грамм — г"),
            ("kg", "Килограмм — кг"),
            ("t", "Метрическая тонна — т"),
            ("oz", "Унция"),
            ("lb", "Фунт"),
        ),
    },
    {
        "id": "force",
        "label": "Силы",
        "units": (
            ("N", "Ньютон — Н"),
            ("kgf", "Килограмм-сила — кгс"),
            ("tf", "Тонна-сила — тс"),
            ("kN", "Килоньютон — кН"),
            ("MN", "Меганьютон — МН"),
            ("daN", "Деканьютон — daN"),
            ("lbf", "Фунт-сила"),
            ("kip", "Килофунт-сила — kip"),
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
            ("Pa", "Паскаль — Па"),
            ("kPa", "Килопаскаль — кПа"),
            ("MPa", "Мегапаскаль — МПа"),
            ("GPa", "Гигапаскаль — ГПа"),
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

G0 = 9.80665
UNIT_SCALES: dict[str, dict[str, float]] = {
    "length": {"mm": 1e-3, "cm": 1e-2, "m": 1.0, "km": 1e3, "in": 0.0254, "ft": 0.3048, "mi": 1609.344},
    "area": {"mm2": 1e-6, "cm2": 1e-4, "m2": 1.0, "ha": 1e4, "km2": 1e6, "in2": 0.00064516, "ft2": 0.09290304},
    "volume": {"mL": 1e-6, "cm3": 1e-6, "L": 1e-3, "m3": 1.0, "gal": 0.003785411784, "ft3": 0.028316846592},
    "mass": {"g": 1e-3, "kg": 1.0, "t": 1e3, "oz": 0.028349523125, "lb": 0.45359237},
    "force": {"N": 1.0, "kgf": G0, "tf": 1000 * G0, "kN": 1e3, "MN": 1e6, "daN": 10.0, "lbf": 4.4482216152605, "kip": 4448.2216152605},
    "distributed_force": {"N/m": 1.0, "kgf/m": G0, "tf/m": 1000 * G0, "kN/m": 1e3, "MN/m": 1e6},
    "moment": {"N*m": 1.0, "kgf*m": G0, "tf*m": 1000 * G0, "kN*m": 1e3, "MN*m": 1e6},
    "speed": {"m/s": 1.0, "km/h": 1 / 3.6, "ft/s": 0.3048},
    "acceleration": {"m/s2": 1.0, "g0": G0, "ft/s2": 0.3048},
    "pressure": {"kgf/m2": G0, "tf/m2": 1000 * G0, "Pa": 1.0, "kPa": 1e3, "MPa": 1e6, "GPa": 1e9, "bar": 1e5, "atm": 101325.0, "mmHg": 133.3223684211, "psi": 6894.757293168},
    "specific_weight": {"N/m3": 1.0, "kgf/m3": G0, "tf/m3": 1000 * G0, "kN/m3": 1e3},
    "time": {"s": 1.0, "min": 60.0, "h": 3600.0},
}


def unit_payload() -> list[dict[str, Any]]:
    return [
        {
            "id": category["id"],
            "label": category["label"],
            "units": [
                {"symbol": symbol, "label": label}
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
    value = value.replace("×", "*").replace("·", "*").replace("÷", "/")
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
    if category == "temperature":
        if from_unit == "degC":
            kelvin = value + 273.15
        elif from_unit == "degF":
            kelvin = (value + 459.67) * 5 / 9
        elif from_unit == "K":
            kelvin = value
        else:
            raise ValueError("Неизвестная единица температуры")
        if to_unit == "degC":
            return kelvin - 273.15
        if to_unit == "degF":
            return kelvin * 9 / 5 - 459.67
        if to_unit == "K":
            return kelvin
        raise ValueError("Неизвестная единица температуры")

    scales = UNIT_SCALES.get(category)
    if not scales or from_unit not in scales or to_unit not in scales:
        raise ValueError("Неизвестная единица измерения")
    return value * scales[from_unit] / scales[to_unit]


def format_number(value: float, precision: int = 12) -> str:
    if not math.isfinite(value):
        raise ValueError("Результат не является конечным числом")
    precision = max(3, min(17, int(precision)))
    if value == 0:
        return "0"
    if abs(value) >= 10 ** max(precision, 6) or abs(value) < 10 ** (-max(precision - 2, 6)):
        text = f"{value:.{precision - 1}e}"
        mantissa, exponent = text.split("e")
        return f"{mantissa.rstrip('0').rstrip('.')}e{int(exponent):+d}"
    return f"{value:.{precision}g}"


def plain_result(response: dict[str, Any]) -> str:
    result = str(response.get("result", "")).strip()
    return result if PLAIN_NUMBER.fullmatch(result) else ""


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
