"""Runtime refinements layered over the core AST calculator.

Kept separate during the keyboard-first prototype so behavior fixes can be
reviewed independently from the larger parser implementation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import calc_engine as core

EngineSettings = core.EngineSettings
HistoryEntry = core.HistoryEntry
make_history_entry = core.make_history_entry


@dataclass(slots=True)
class Evaluation:
    expression: str
    normalized: str
    result: str = ""
    raw_value: float | None = None
    unit: str | None = None
    ok: bool = True
    error: str | None = None
    position: int | None = None
    assigned_variable: str | None = None
    incomplete: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "expression": self.expression,
            "normalized": self.normalized,
            "result": self.result,
            "raw_value": self.raw_value,
            "unit": self.unit,
            "ok": self.ok,
            "error": self.error,
            "position": self.position,
            "assigned_variable": self.assigned_variable,
            "incomplete": self.incomplete,
        }


def _looks_incomplete(expression: str) -> bool:
    text = expression.rstrip()
    if not text:
        return True
    if text.endswith(("+", "-", "*", "/", "^", "(", ":=", " to")):
        return True
    return text.count("(") > text.count(")")


def _format_dimensions(dimensions: core.Dim) -> str:
    names = ("m", "kg", "s", "K")
    numerator: list[str] = []
    denominator: list[str] = []
    for name, exponent in zip(names, dimensions, strict=True):
        if exponent == 0:
            continue
        target = numerator if exponent > 0 else denominator
        power = abs(exponent)
        if power == 1:
            target.append(name)
        elif power.denominator == 1:
            target.append(f"{name}{power.numerator}")
        else:
            target.append(f"{name}^({power.numerator}/{power.denominator})")
    top = "*".join(numerator) or "1"
    return top if not denominator else f"{top}/{'*'.join(denominator)}"


class CalculatorSession(core.CalculatorSession):
    """Core session with side-effect-free preview and cleaner diagnostics."""

    def evaluate(self, expression: str, *, commit: bool = False) -> Evaluation:
        original = str(expression or "")
        normalized = core.normalize_expression(original)
        try:
            variable, body = core._split_assignment(normalized)
            source, target = core._split_conversion(body)
            quantity = self._evaluate_source(source)
            unit_symbol = None
            output_quantity = quantity
            if target:
                output_quantity, unit_symbol = self._convert(quantity, target)
            if variable:
                lowered = variable.lower()
                if lowered in {"pi", "e", "tau", "ans"} or lowered in core.UNIT_DEFS:
                    raise core.CalculationError(f"Имя {variable} зарезервировано")
                if commit:
                    self.variables[lowered] = quantity
            if commit:
                self.ans = quantity
            return Evaluation(
                expression=original,
                normalized=normalized,
                result=self.format_quantity(output_quantity, unit_symbol),
                raw_value=output_quantity.value,
                unit=unit_symbol,
                assigned_variable=variable,
            )
        except core.CalculationError as exc:
            return Evaluation(
                expression=original,
                normalized=normalized,
                ok=False,
                error=exc.message,
                position=exc.position,
                incomplete=_looks_incomplete(normalized),
            )
        except (ArithmeticError, ValueError, TypeError) as exc:
            return Evaluation(
                expression=original,
                normalized=normalized,
                ok=False,
                error=str(exc) or "Ошибка вычисления",
                incomplete=_looks_incomplete(normalized),
            )

    def format_quantity(self, quantity: core.Quantity, explicit_unit: str | None = None) -> str:
        value = quantity.value
        if not math.isfinite(value):
            raise core.CalculationError("Результат не является конечным числом")
        if explicit_unit is None and not quantity.dimensionless:
            explicit_unit = core.CANONICAL_UNITS.get(quantity.dimensions) or _format_dimensions(quantity.dimensions)
        return super().format_quantity(quantity, explicit_unit)
