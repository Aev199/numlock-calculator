"""Which calculations are worth a history entry."""

from __future__ import annotations

import re
from typing import Any

_PLAIN_NUMBER = re.compile(r"[+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)(?:e[+-]?\d+)?", re.IGNORECASE)


def _canonical_expression(expression: str) -> str:
    return re.sub(r"\s+", "", str(expression)).replace("⋅", "*").replace("×", "*")


def history_worthy(expression: str, history: list[dict[str, Any]]) -> bool:
    """Whether a calculation adds something to the history.

    A bare number (Enter pressed again on a result) and a repeat of the
    latest entry are skipped; the calculation itself still happens.
    """

    canonical = _canonical_expression(expression)
    if not canonical or _PLAIN_NUMBER.fullmatch(canonical):
        return False
    latest = history[0].get("expression", "") if history else ""
    return _canonical_expression(latest) != canonical
