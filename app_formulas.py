"""Compatibility shell for the removed saved-formulas/profile feature.

NumCalc 1.3.0 keeps this import target temporarily because the keyboard entry
point and older installations may still reference it. The former persistent
formula/profile API, storage hooks and evaluator integration have been removed.
Lightweight user functions are implemented separately in app_user_functions.py.
"""

from __future__ import annotations

from typing import Any


def install(app: Any) -> None:
    """Keep the legacy install hook inert and idempotent."""

    if getattr(app, "_legacy_formulas_removed", False):
        return
    app._legacy_formulas_removed = True
