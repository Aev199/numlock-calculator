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
        "label": "Длина",
        "units": (
            ("mm", "Миллиметр"),
            ("cm", "Сантиметр"),
            ("m", "Метр"),
            ("km", "Километр"),
            ("in", "Дюйм"),
            ("ft", "Фут"),
            ("mi", "Миля"),
        ),
    },
    {
        "id": "area",
        "label": "Площадь",
        "units": (
            ("mm2", "Квадратный миллиметр"),
            ("cm2", "Квадратный сантиметр"),
            ("m2", "Квадратный метр"),
            ("ha", "Гектар"),
            ("km2", "Квадратный километр"),
            ("in2", "Квадратный дюйм"),
            ("ft2", "Квадратный фут"),
        ),
    },
    {
        "id": "volume",
        "label": "Объём",
        "units": (
            ("mL", "Миллилитр"),
            ("cm3", "Кубический сантиметр"),
            ("L", "Литр"),
            ("m3", "Кубический метр"),
            ("gal", "Галлон США"),
            ("ft3", "Кубический фут"),
        ),
    },
    {
        "id": "mass",
        "label": "Масса",
        "units": (
            ("g", "Грамм"),
            ("kg", "Килограмм"),
            ("t", "Тонна"),
            ("oz", "Унция"),
            ("lb", "Фунт"),
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
    {
        "id": "force",
        "label": "Сила",
        "units": (
            ("N", "Ньютон"),
            ("kN", "Килоньютон"),
            ("kgf", "Килограмм-сила"),
            ("lbf", "Фунт-сила"),
        ),
    },
    {
        "id": "pressure",
        "label": "Давление",
        "units": (
            ("Pa", "Паскаль"),
            ("kPa", "Килопаскаль"),
            ("MPa", "Мегапаскаль"),
            ("GPa", "Гигапаскаль"),
            ("bar", "Бар"),
            ("atm", "Атмосфера"),
            ("mmHg", "Миллиметр ртутного столба"),
            ("psi", "Фунт на квадратный дюйм"),
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
