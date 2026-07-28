"""Shared forgiving normalization for keyboard-entered numeric expressions.

The UI displays multiplication as U+22C5 (``⋅``), while the calculation
backends use ``*``.  This layer also repairs the common Windows numeric-keypad
sequence ``.,1`` / ``,.1`` into a leading decimal fraction instead of exposing
a Python syntax error to the user.
"""

from __future__ import annotations

import re
from functools import wraps
from typing import Any, Callable

_DECIMAL_AFTER_DIGIT = re.compile(r"(?<=\d)[.,]{1,2}(?=\d)")
_DECIMAL_AFTER_BOUNDARY = re.compile(r"(?<!\d)[.,]{1,2}(?=\d)")
_IMPLICIT_MULTIPLY_BEFORE_PAREN = re.compile(r"(?<=[\d)])\s*(?=\()")


def repair_numeric_input(expression: Any) -> str:
    """Return a parser-friendly form without changing valid arithmetic.

    Examples:
        ``3100*.,1`` -> ``3100*0.1``
        ``3100⋅,1``  -> ``3100*0.1``
        ``,1``        -> ``0.1``
        ``2,5``       -> ``2.5``
        ``150(5)``    -> ``150*(5)``
        ``(2)(3)``    -> ``(2)*(3)``
    """

    value = str(expression or "")
    value = value.replace("⋅", "*").replace("×", "*").replace("·", "*")
    value = _DECIMAL_AFTER_DIGIT.sub(".", value)
    value = _DECIMAL_AFTER_BOUNDARY.sub("0.", value)
    value = _IMPLICIT_MULTIPLY_BEFORE_PAREN.sub("*", value)
    return value


def _install_wrapper(
    module: Any,
    function_name: str,
    marker_name: str,
) -> None:
    if getattr(module, marker_name, False):
        return

    original: Callable[[str], str] = getattr(module, function_name)

    @wraps(original)
    def wrapped(expression: str) -> str:
        return original(repair_numeric_input(expression))

    setattr(module, function_name, wrapped)
    setattr(module, marker_name, True)


def install_calculator_normalization(calc_engine: Any) -> None:
    """Extend the core calculator normalizer, preserving all existing rules."""

    _install_wrapper(
        calc_engine,
        "normalize_expression",
        "_numcalc_numeric_normalization_installed",
    )


def install_unit_normalization(unit_conversion: Any) -> None:
    """Extend the unit-workspace normalizer with the same input behavior."""

    _install_wrapper(
        unit_conversion,
        "normalize_simple_expression",
        "_numcalc_numeric_normalization_installed",
    )
