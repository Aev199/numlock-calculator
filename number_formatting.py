"""Shared numeric presentation helpers for calculator outputs."""

from __future__ import annotations

import math


VALID_NUMBER_FORMATS = {"auto", "engineering"}
VALID_DECIMAL_SEPARATORS = {".", ","}
MIN_DECIMAL_PLACES = 0
MAX_DECIMAL_PLACES = 15
DEFAULT_DECIMAL_PLACES = 6


def normalize_number_format(value: object) -> str:
    candidate = str(value or "auto").strip().lower()
    return candidate if candidate in VALID_NUMBER_FORMATS else "auto"


def normalize_decimal_separator(value: object) -> str:
    candidate = str(value or ".").strip().lower()
    if candidate in {",", "comma", "запятая"}:
        return ","
    return "."


def normalize_decimal_places(value: object, default: int = DEFAULT_DECIMAL_PLACES) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = int(default)
    return max(MIN_DECIMAL_PLACES, min(MAX_DECIMAL_PLACES, parsed))


def _trim_fixed(text: str) -> str:
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in {"", "+0", "-0"} else text


def _format_scientific(value: float, decimal_places: int) -> str:
    mantissa, exponent = f"{value:.{decimal_places}e}".split("e", 1)
    return f"{_trim_fixed(mantissa)}e{int(exponent):+d}"


def _format_engineering(value: float, decimal_places: int) -> str:
    exponent = int(math.floor(math.log10(abs(value)) / 3.0) * 3)
    mantissa = value / (10.0**exponent)
    rounded = round(mantissa, decimal_places)
    if abs(rounded) >= 1000:
        mantissa /= 1000
        exponent += 3
    text = _trim_fixed(f"{mantissa:.{decimal_places}f}")
    return f"{text}e{exponent:+d}" if exponent else text


def format_number(
    value: float,
    precision: int = DEFAULT_DECIMAL_PLACES,
    number_format: str = "auto",
    decimal_separator: str = ".",
) -> str:
    """Round to ``precision`` decimal places and omit trailing zeroes.

    The public API keeps the historical ``precision`` key for compatibility
    with saved settings and profiles. Its meaning from NumCalc 1.1 onward is
    the number of digits after the decimal separator, not significant digits.
    """

    if not math.isfinite(value):
        raise ValueError("Результат не является конечным числом")

    decimal_places = normalize_decimal_places(precision)
    mode = normalize_number_format(number_format)
    separator = normalize_decimal_separator(decimal_separator)

    if value == 0:
        text = "0"
    elif mode == "engineering":
        text = _format_engineering(value, decimal_places)
    elif abs(value) >= 1e12 or abs(value) < 1e-6:
        text = _format_scientific(value, decimal_places)
    else:
        text = _trim_fixed(f"{value:.{decimal_places}f}")

    if separator == ",":
        mantissa, marker, exponent = text.partition("e")
        text = mantissa.replace(".", ",") + (marker + exponent if marker else "")
    return text
