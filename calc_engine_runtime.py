"""Runtime refinements layered over the core AST calculator."""

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
    dimensions: core.Dim = core.DIMENSIONLESS
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
            "dimensions": core.serialize_dimensions(self.dimensions),
            "dimension": core.format_dimension(self.dimensions),
            "quantity": core.quantity_payload(
                self.raw_value,
                self.unit,
                self.dimensions,
            ),
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
            target.append(
                f"{name}^({power.numerator}/{power.denominator})"
            )
    top = "*".join(numerator) or "1"
    return top if not denominator else f"{top}/{'*'.join(denominator)}"


FUNCTION_DESCRIPTIONS = {
    "sin": "Синус",
    "cos": "Косинус",
    "tan": "Тангенс",
    "asin": "Арксинус",
    "acos": "Арккосинус",
    "atan": "Арктангенс",
    "sqrt": "Квадратный корень",
    "cbrt": "Кубический корень",
    "ln": "Натуральный логарифм",
    "log": "Логарифм",
    "log10": "Десятичный логарифм",
    "exp": "Экспонента",
    "fact": "Факториал",
    "factorial": "Факториал",
    "abs": "Модуль",
    "floor": "Округлить вниз",
    "ceil": "Округлить вверх",
    "round": "Округлить",
    "min": "Минимум",
    "max": "Максимум",
    "mean": "Среднее",
    "sum": "Сумма",
}

FUNCTION_GROUPS = {
    "sin": "Тригонометрия",
    "cos": "Тригонометрия",
    "tan": "Тригонометрия",
    "asin": "Тригонометрия",
    "acos": "Тригонометрия",
    "atan": "Тригонометрия",
    "sqrt": "Степени и логарифмы",
    "cbrt": "Степени и логарифмы",
    "ln": "Степени и логарифмы",
    "log": "Степени и логарифмы",
    "log10": "Степени и логарифмы",
    "exp": "Степени и логарифмы",
    "fact": "Степени и логарифмы",
    "factorial": "Степени и логарифмы",
    "abs": "Округление и статистика",
    "floor": "Округление и статистика",
    "ceil": "Округление и статистика",
    "round": "Округление и статистика",
    "min": "Округление и статистика",
    "max": "Округление и статистика",
    "mean": "Округление и статистика",
    "sum": "Округление и статистика",
}


class CalculatorSession(core.CalculatorSession):
    """Core session with side-effect-free preview and cleaner diagnostics."""

    def evaluate(
        self, expression: str, *, commit: bool = False
    ) -> Evaluation:
        original = str(expression or "")
        normalized = core.normalize_expression(original)
        try:
            variable, body = core._split_assignment(normalized)
            source, target = core._split_conversion(body)
            quantity = self._evaluate_source(source)
            unit_symbol = None
            output_quantity = quantity
            output_dimensions = quantity.dimensions
            if target:
                output_quantity, unit_symbol, output_dimensions = self._convert(
                    quantity,
                    target,
                )
            if variable:
                lowered = variable.lower()
                if (
                    lowered in {"pi", "e", "tau", "ans"}
                    or lowered in core.UNIT_DEFS
                ):
                    raise core.CalculationError(
                        f"Имя {variable} зарезервировано"
                    )
                if commit:
                    self.variables[lowered] = quantity
            if commit:
                self.ans = quantity
            result_unit = unit_symbol or core.display_unit_for(quantity)
            if result_unit is None and not quantity.dimensionless:
                result_unit = _format_dimensions(quantity.dimensions)
            raw_value = (
                output_quantity.value
                if unit_symbol
                else core.base_value_in_unit(quantity.value, result_unit)
            )
            return Evaluation(
                expression=original,
                normalized=normalized,
                result=self.format_quantity(
                    output_quantity,
                    unit_symbol or result_unit,
                ),
                raw_value=raw_value,
                unit=result_unit,
                dimensions=output_dimensions,
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

    def format_quantity(
        self,
        quantity: core.Quantity,
        explicit_unit: str | None = None,
    ) -> str:
        value = quantity.value
        if not math.isfinite(value):
            raise core.CalculationError(
                "Результат не является конечным числом"
            )
        if explicit_unit is None and not quantity.dimensionless:
            explicit_unit = (
                core.display_unit_for(quantity)
                or _format_dimensions(quantity.dimensions)
            )
        return super().format_quantity(quantity, explicit_unit)

    def suggestions(self, query: str = "") -> list[dict[str, str]]:
        """Return commands with stable user-facing groups for the palette."""
        needle = query.strip().lower()
        items: list[dict[str, str]] = []

        def matches(*values: str) -> bool:
            if not needle:
                return True
            return any(needle in value.lower() for value in values)

        for name in core.FUNCTION_NAMES:
            description = FUNCTION_DESCRIPTIONS.get(name, "Функция")
            group = FUNCTION_GROUPS.get(
                name, "Округление и статистика"
            )
            if matches(name, description, group):
                items.append(
                    {
                        "kind": "function",
                        "group": group,
                        "label": name,
                        "insert": f"{name}()",
                        "description": description,
                    }
                )

        constants = (
            ("pi", "π", "Число π"),
            ("e", "e", "Число Эйлера"),
            ("tau", "τ", "2π"),
            ("ans", "ans", "Последний результат"),
        )
        for label, insert, description in constants:
            if matches(label, insert, description, "Константы"):
                items.append(
                    {
                        "kind": "constant",
                        "group": "Константы",
                        "label": label,
                        "insert": insert,
                        "description": description,
                    }
                )

        seen_units: set[str] = set()
        for unit in core.UNIT_DEFS.values():
            if unit.symbol in seen_units:
                continue
            seen_units.add(unit.symbol)
            if matches(
                unit.symbol, "Единицы", "Единица измерения"
            ):
                items.append(
                    {
                        "kind": "unit",
                        "group": "Единицы",
                        "label": unit.symbol,
                        "insert": unit.symbol,
                        "description": "Единица измерения",
                    }
                )

        for name in sorted(self.variables):
            value = self.format_quantity(self.variables[name])
            if matches(name, value, "Переменные"):
                items.append(
                    {
                        "kind": "variable",
                        "group": "Переменные",
                        "label": name,
                        "insert": name,
                        "description": value,
                    }
                )

        for index, value in enumerate(self.memories):
            formatted = self.format_quantity(value)
            label = f"M{index}"
            if matches(label, formatted, "Память"):
                items.append(
                    {
                        "kind": "memory",
                        "group": "Память",
                        "label": label,
                        "insert": formatted,
                        "description": formatted,
                    }
                )

        group_order = {
            "Тригонометрия": 0,
            "Степени и логарифмы": 1,
            "Округление и статистика": 2,
            "Константы": 3,
            "Единицы": 4,
            "Переменные": 5,
            "Память": 6,
        }
        items.sort(
            key=lambda item: (
                group_order.get(item["group"], 99),
                item["label"].lower(),
            )
        )
        return items[:120]
