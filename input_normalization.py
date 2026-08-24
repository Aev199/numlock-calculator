"""Shared forgiving normalization for keyboard-entered numeric expressions.

The UI displays multiplication as U+22C5 (``⋅``), while the calculation
backends use ``*``. This layer also repairs the common Windows numeric-keypad
sequence ``.,1`` / ``,.1``, removes visual thousands separators inserted by
the renderer, and expands the compact reinforcement-area notation used by
structural engineers.
"""

from __future__ import annotations

import re
from functools import wraps
from typing import Any, Callable

_DECIMAL_AFTER_DIGIT = re.compile(r"(?<=\d)[.,]{1,2}(?=\d)")
_DECIMAL_AFTER_BOUNDARY = re.compile(r"(?<!\d)[.,]{1,2}(?=\d)")
_IMPLICIT_MULTIPLY_BEFORE_PAREN = re.compile(r"(?<=[\d)])\s*(?=\()")
_DIGIT_GROUPING = re.compile(r"(?<=\d)[ \u00a0\u202f]+(?=\d)")
_REINFORCEMENT_TERM = re.compile(
    r"\s*(?:(?P<count>\d+)\s*)?[dD]\s*"
    r"(?P<diameter>\d+(?:\.\d+)?)\s*"
    r"(?:[sS]\s*(?P<spacing>\d+(?:\.\d+)?)\s*)?"
)


def repair_numeric_input(expression: Any) -> str:
    """Return a parser-friendly form without changing valid arithmetic.

    Examples:
        ``3100*.,1``     -> ``3100*0.1``
        ``3100⋅,1``      -> ``3100*0.1``
        ``,1``           -> ``0.1``
        ``2,5``          -> ``2.5``
        ``150(5)``       -> ``150*(5)``
        ``(2)(3)``       -> ``(2)*(3)``
        ``1 000 000``    -> ``1000000``
    """

    value = str(expression or "")
    value = value.replace("⋅", "*").replace("×", "*").replace("·", "*")
    value = _DIGIT_GROUPING.sub("", value)
    value = _DECIMAL_AFTER_DIGIT.sub(".", value)
    value = _DECIMAL_AFTER_BOUNDARY.sub("0.", value)
    value = _IMPLICIT_MULTIPLY_BEFORE_PAREN.sub("*", value)
    return value


def rewrite_reinforcement_area(expression: Any) -> str:
    """Expand compact reinforcement notation into dimensional expressions.

    Two intentionally separate forms are supported:

    ``d16`` / ``2d20``
        Bar area without spacing. The optional leading integer is the number
        of bars. The result is displayed in ``cm2``.

    ``d16s150`` / ``4d20s200+d16s150``
        Reinforcement area per metre. Diameters and spacings are millimetres;
        the result is displayed in ``cm2/m``.

    Terms joined by ``+`` must use the same form. Mixing terms with and without
    spacing is deliberately not rewritten because those values have different
    physical meanings.

    The shorthand is activated only when the complete expression consists of
    valid reinforcement terms joined by ``+``. Ordinary variables and
    calculator expressions therefore keep their existing meaning.
    """

    value = str(expression or "")
    parts = value.split("+")
    if not parts or any(not part.strip() for part in parts):
        return value

    matches = []
    for part in parts:
        match = _REINFORCEMENT_TERM.fullmatch(part)
        if match is None:
            return value
        matches.append(match)

    spacing_flags = [match.group("spacing") is not None for match in matches]
    if any(spacing_flags) and not all(spacing_flags):
        return value

    expanded: list[str] = []
    if all(spacing_flags):
        for match in matches:
            count = match.group("count") or "1"
            diameter = match.group("diameter")
            spacing = match.group("spacing")
            expanded.append(
                f"({count}*pi*({diameter} mm)^2/4/({spacing} mm))"
            )
        return f"({' + '.join(expanded)}) to cm2/m"

    for match in matches:
        count = match.group("count") or "1"
        diameter = match.group("diameter")
        expanded.append(f"({count}*pi*({diameter} mm)^2/4)")
    return f"({' + '.join(expanded)}) to cm2"


def _calculator_input(expression: Any) -> str:
    return rewrite_reinforcement_area(repair_numeric_input(expression))


def _install_wrapper(
    module: Any,
    function_name: str,
    marker_name: str,
    preprocessor: Callable[[Any], str] = repair_numeric_input,
) -> None:
    if getattr(module, marker_name, False):
        return

    original: Callable[[str], str] = getattr(module, function_name)

    @wraps(original)
    def wrapped(expression: str) -> str:
        return original(preprocessor(expression))

    setattr(module, function_name, wrapped)
    setattr(module, marker_name, True)


def install_calculator_normalization(calc_engine: Any) -> None:
    """Extend the core calculator normalizer, preserving all existing rules."""

    _install_wrapper(
        calc_engine,
        "normalize_expression",
        "_numcalc_numeric_normalization_installed",
        _calculator_input,
    )


def install_unit_normalization(unit_conversion: Any) -> None:
    """Extend the unit-workspace normalizer with the same numeric input behavior."""

    _install_wrapper(
        unit_conversion,
        "normalize_simple_expression",
        "_numcalc_numeric_normalization_installed",
    )
