"""Shared numeric presentation helpers for the calculator and unit converter."""

from __future__ import annotations

import math


VALID_NUMBER_FORMATS = {"auto", "engineering"}
VALID_DECIMAL_SEPARATORS = {".", ","}


def normalize_number_format(value: object) -> str:
    """Return a supported display format, defaulting to the legacy format."""

    candidate = str(value or "auto").strip().lower()
    return candidate if candidate in VALID_NUMBER_FORMATS else "auto"


def normalize_decimal_separator(value: object) -> str:
    """Accept both symbols and readable aliases used by older settings."""

    candidate = str(value or ".").strip().lower()
    if candidate in {",", "comma", "запятая"}:
        return ","
    return "."


def _trim_exponent(text: str) -> str:
    mantissa, exponent = text.split("e", 1)
    mantissa = mantissa.rstrip("0").rstrip(".")
    return f"{mantissa}e{int(exponent):+d}"


def _format_engineering(value: float, precision: int) -> str:
    """Format a finite value with an exponent divisible by three."""

    # Start with a significant-digit scientific representation.  This avoids
    # underflow when a very small finite value would make 10**exponent zero.
    scientific = f"{value:.{precision - 1}e}"
    mantissa_text, exponent_text = scientific.split("e", 1)
    scientific_exponent = int(exponent_text)
    engineering_exponent = (scientific_exponent // 3) * 3
    mantissa = float(mantissa_text) * (10 ** (scientific_exponent - engineering_exponent))

    # Rounding can move 999.9 to 1000. Keep the engineering mantissa in its
    # conventional [1, 1000) interval by carrying into the next exponent.
    if abs(mantissa) >= 1000:
        mantissa /= 1000
        engineering_exponent += 3

    text = f"{mantissa:.{precision}g}"
    if engineering_exponent:
        text = f"{text}e{engineering_exponent:+d}"
    return text


def format_number(
    value: float,
    precision: int = 12,
    number_format: str = "auto",
    decimal_separator: str = ".",
) -> str:
    """Format a finite number using significant digits and user preferences.

    ``precision`` is the number of significant digits.  ``engineering`` keeps
    exponents at multiples of three, while ``auto`` preserves the historical
    compact calculator output.  The decimal separator affects only the
    mantissa; the exponent marker remains ``e`` so copied values stay portable.
    """

    if not math.isfinite(value):
        raise ValueError("Результат не является конечным числом")

    precision = max(3, min(17, int(precision)))
    mode = normalize_number_format(number_format)
    separator = normalize_decimal_separator(decimal_separator)

    if value == 0:
        text = "0"
    elif mode == "engineering":
        text = _format_engineering(value, precision)
    elif abs(value) >= 10 ** max(precision, 6):
        text = _trim_exponent(f"{value:.{precision - 1}e}")
    elif abs(value) < 10 ** (-max(precision - 2, 6)):
        text = _trim_exponent(f"{value:.{precision - 1}e}")
    else:
        text = f"{value:.{precision}g}"

    if separator == ",":
        mantissa, marker, exponent = text.partition("e")
        mantissa = mantissa.replace(".", ",")
        text = mantissa + (marker + exponent if marker else "")
    return text
