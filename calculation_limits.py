"""Resource limits for calculator and unit-expression AST evaluation."""

from __future__ import annotations

import ast
from functools import wraps
from typing import Any, Callable

MAX_EXPRESSION_LENGTH = 2048
MAX_AST_NODES = 512
MAX_AST_DEPTH = 64
MAX_COLLECTION_ITEMS = 128
MAX_ABS_EXPONENT = 1000.0


def validate_ast(tree: ast.AST, error_type: type[Exception] = ValueError) -> None:
    """Reject unusually large/deep trees before recursive evaluation starts."""

    stack: list[tuple[ast.AST, int]] = [(tree, 1)]
    nodes = 0
    while stack:
        node, depth = stack.pop()
        nodes += 1
        if nodes > MAX_AST_NODES:
            raise error_type("Выражение содержит слишком много операций")
        if depth > MAX_AST_DEPTH:
            raise error_type("Слишком большая глубина выражения")
        if isinstance(node, (ast.List, ast.Tuple)) and len(node.elts) > MAX_COLLECTION_ITEMS:
            raise error_type("Слишком много элементов в списке")
        if isinstance(node, ast.Call) and len(node.args) > MAX_COLLECTION_ITEMS:
            raise error_type("Слишком много аргументов функции")
        stack.extend((child, depth + 1) for child in ast.iter_child_nodes(node))


def _nested_syntax_error(exc: SyntaxError) -> bool:
    message = str(getattr(exc, "msg", exc)).lower()
    return "too many nested" in message or "recursion" in message


def install_calculator_limits(calc_engine: Any) -> None:
    if getattr(calc_engine, "_numcalc_limits_installed", False):
        return
    calc_engine._numcalc_limits_installed = True

    original_evaluate: Callable[..., Any] = calc_engine.SafeAstEvaluator.evaluate

    @wraps(original_evaluate)
    def evaluate(self: Any, expression: str) -> Any:
        if len(expression) > MAX_EXPRESSION_LENGTH:
            raise calc_engine.CalculationError("Выражение слишком длинное")
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as exc:
            if _nested_syntax_error(exc):
                raise calc_engine.CalculationError("Слишком большая глубина выражения") from exc
            return original_evaluate(self, expression)
        except RecursionError as exc:
            raise calc_engine.CalculationError("Слишком большая глубина выражения") from exc
        validate_ast(tree, calc_engine.CalculationError)
        try:
            return original_evaluate(self, expression)
        except RecursionError as exc:
            raise calc_engine.CalculationError("Слишком большая глубина выражения") from exc

    original_pow: Callable[..., Any] = calc_engine.Quantity.__pow__

    @wraps(original_pow)
    def limited_pow(self: Any, other: Any) -> Any:
        exponent = self._coerce(other)
        if exponent.dimensionless and abs(exponent.value) > MAX_ABS_EXPONENT:
            raise calc_engine.CalculationError("Слишком большой показатель степени")
        return original_pow(self, other)

    calc_engine.SafeAstEvaluator.evaluate = evaluate
    calc_engine.Quantity.__pow__ = limited_pow


def install_unit_limits(unit_conversion: Any) -> None:
    if getattr(unit_conversion, "_numcalc_limits_installed", False):
        return
    unit_conversion._numcalc_limits_installed = True
    original_evaluate: Callable[[str], float] = unit_conversion.evaluate_simple

    @wraps(original_evaluate)
    def evaluate_simple(expression: str) -> float:
        prepared = unit_conversion.normalize_simple_expression(expression)
        if len(prepared) > MAX_EXPRESSION_LENGTH:
            raise ValueError("Выражение слишком длинное")
        try:
            tree = ast.parse(prepared, mode="eval")
        except SyntaxError as exc:
            if _nested_syntax_error(exc):
                raise ValueError("Слишком большая глубина выражения") from exc
            return original_evaluate(expression)
        except RecursionError as exc:
            raise ValueError("Слишком большая глубина выражения") from exc
        validate_ast(tree)
        try:
            return original_evaluate(expression)
        except RecursionError as exc:
            raise ValueError("Слишком большая глубина выражения") from exc

    unit_conversion.evaluate_simple = evaluate_simple
