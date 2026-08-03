"""Numerical helpers for the linear interpolation mode.

The interpolation tab deliberately accepts numbers, not calculator
expressions.  Keeping the parser small makes invalid input explicit and
prevents a malformed field from being evaluated as executable syntax.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from typing import Any


_NUMBER_RE = re.compile(
    r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$"
)

_LABELS = {
    "x0": "x₀",
    "x1": "x₁",
    "y0": "y₀",
    "y1": "y₁",
    "x": "x",
}


def parse_number(value: Any, name: str) -> float:
    """Parse one finite numeric field, accepting the UI decimal comma."""

    if isinstance(value, bool):
        raise ValueError(f"Поле «{_LABELS.get(name, name)}» должно быть числом")
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = str(value or "").strip().replace("−", "-").replace(",", ".")
        if not text:
            raise ValueError(f"Заполните поле «{_LABELS.get(name, name)}»")
        if len(text) > 80 or not _NUMBER_RE.fullmatch(text):
            raise ValueError(f"Поле «{_LABELS.get(name, name)}» должно быть числом")
        number = float(text)
    if not math.isfinite(number):
        raise ValueError(f"Поле «{_LABELS.get(name, name)}» должно быть конечным числом")
    return number


def linear_interpolate(x0: float, y0: float, x1: float, y1: float, x: float) -> float:
    """Return y at x on the line through (x0, y0) and (x1, y1)."""

    if x0 == x1:
        raise ValueError("Опорные значения x₀ и x₁ должны различаться")
    return y0 + (x - x0) * (y1 - y0) / (x1 - x0)


def calculate(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """Validate a renderer payload and calculate a 1D result."""

    data = payload if isinstance(payload, Mapping) else {}
    values = data.get("values", data)
    values = values if isinstance(values, Mapping) else {}
    mode = str(data.get("mode", "1d")).strip().lower()
    if mode not in {"1d", "one_d", "one-dimensional"}:
        return {"ok": False, "error": "Доступна только линейная интерполяция 1D"}
    mode = "1d"

    try:
        x0 = parse_number(values.get("x0"), "x0")
        y0 = parse_number(values.get("y0"), "y0")
        x1 = parse_number(values.get("x1"), "x1")
        y1 = parse_number(values.get("y1"), "y1")
        x = parse_number(values.get("x"), "x")
        result = linear_interpolate(x0, y0, x1, y1, x)
        formula = "y = y₀ + (x − x₀) · (y₁ − y₀) / (x₁ − x₀)"
    except (ArithmeticError, TypeError, ValueError) as exc:
        return {"ok": False, "mode": mode, "error": str(exc) or "Ошибка интерполяции"}

    if not math.isfinite(result):
        return {"ok": False, "mode": mode, "error": "Результат не является конечным числом"}
    return {
        "ok": True,
        "mode": mode,
        "raw_value": result,
        "formula": formula,
    }


def default_state() -> dict[str, Any]:
    """Return the compact persisted state used by the interpolation tab."""

    return {
        "one_d": {"x0": "", "y0": "", "x1": "", "y1": "", "x": ""},
    }


def normalize_state(value: Any) -> dict[str, Any]:
    """Keep persisted interpolation state bounded and backward compatible."""

    state = default_state()
    if not isinstance(value, Mapping):
        return state

    raw_section = value.get("one_d", value)
    if not isinstance(raw_section, Mapping):
        return state
    for key in state["one_d"]:
        raw = raw_section.get(key, "")
        text = str(raw if raw is not None else "").strip()
        state["one_d"][key] = text[:80]
    return state
