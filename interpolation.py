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
    "z00": "z₀₀",
    "z10": "z₁₀",
    "z01": "z₀₁",
    "z11": "z₁₁",
    "y": "y",
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


def bilinear_interpolate(
    x0: float,
    x1: float,
    y0: float,
    y1: float,
    z00: float,
    z10: float,
    z01: float,
    z11: float,
    x: float,
    y: float,
) -> float:
    """Return bilinear interpolation on the rectangle's four corners."""

    if x0 == x1:
        raise ValueError("Опорные значения x₀ и x₁ должны различаться")
    if y0 == y1:
        raise ValueError("Опорные значения y₀ и y₁ должны различаться")
    tx = (x - x0) / (x1 - x0)
    ty = (y - y0) / (y1 - y0)
    return (
        z00 * (1 - tx) * (1 - ty)
        + z10 * tx * (1 - ty)
        + z01 * (1 - tx) * ty
        + z11 * tx * ty
    )


def calculate(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """Validate a renderer payload and calculate a 1D or 2D result."""

    data = payload if isinstance(payload, Mapping) else {}
    values = data.get("values", data)
    values = values if isinstance(values, Mapping) else {}
    mode = str(data.get("mode", "1d")).strip().lower()
    if mode in {"1d", "one_d", "one-dimensional"}:
        mode = "1d"
    elif mode in {"2d", "two_d", "two-dimensional"}:
        mode = "2d"
    else:
        return {"ok": False, "error": "Выберите режим 1D или 2D"}

    try:
        if mode == "1d":
            x0 = parse_number(values.get("x0"), "x0")
            y0 = parse_number(values.get("y0"), "y0")
            x1 = parse_number(values.get("x1"), "x1")
            y1 = parse_number(values.get("y1"), "y1")
            x = parse_number(values.get("x"), "x")
            result = linear_interpolate(x0, y0, x1, y1, x)
            formula = "y = y₀ + (x − x₀) · (y₁ − y₀) / (x₁ − x₀)"
        else:
            x0 = parse_number(values.get("x0"), "x0")
            x1 = parse_number(values.get("x1"), "x1")
            y0 = parse_number(values.get("y0"), "y0")
            y1 = parse_number(values.get("y1"), "y1")
            z00 = parse_number(values.get("z00"), "z00")
            z10 = parse_number(values.get("z10"), "z10")
            z01 = parse_number(values.get("z01"), "z01")
            z11 = parse_number(values.get("z11"), "z11")
            x = parse_number(values.get("x"), "x")
            y = parse_number(values.get("y"), "y")
            result = bilinear_interpolate(
                x0, x1, y0, y1, z00, z10, z01, z11, x, y
            )
            formula = "z = Σ zᵢⱼ · wᵢⱼ (билинейная интерполяция)"
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
        "mode": "1d",
        "one_d": {"x0": "", "y0": "", "x1": "", "y1": "", "x": ""},
        "two_d": {
            "x0": "",
            "x1": "",
            "y0": "",
            "y1": "",
            "z00": "",
            "z10": "",
            "z01": "",
            "z11": "",
            "x": "",
            "y": "",
        },
    }


def normalize_state(value: Any) -> dict[str, Any]:
    """Keep persisted interpolation state bounded and backward compatible."""

    state = default_state()
    if not isinstance(value, Mapping):
        return state

    mode = str(value.get("mode", "1d")).strip().lower()
    state["mode"] = "2d" if mode == "2d" else "1d"
    for section, keys in (("one_d", state["one_d"]), ("two_d", state["two_d"])):
        raw_section = value.get(section)
        if not isinstance(raw_section, Mapping):
            continue
        for key in keys:
            raw = raw_section.get(key, "")
            text = str(raw if raw is not None else "").strip()
            keys[key] = text[:80]
    return state
