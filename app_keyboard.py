"""Keyboard-first entry point."""

import calc_engine
import unit_conversion
from calculation_limits import install_calculator_limits, install_unit_limits
from input_normalization import (
    install_calculator_normalization,
    install_unit_normalization,
)

# Install shared input rules and resource limits before runtime classes and
# backend functions are imported. The wrappers preserve the existing AST engine
# while repairing keypad input and bounding unusually large expressions.
install_calculator_normalization(calc_engine)
install_unit_normalization(unit_conversion)
install_calculator_limits(calc_engine)
install_unit_limits(unit_conversion)

from calc_engine_runtime import CalculatorSession

calc_engine.CalculatorSession = CalculatorSession

import app
import app_clipboard_settings
import app_diagnostics
import app_formulas
import app_native_titlebar
import app_numlock_compat
import app_product
import app_renderer
import app_single_instance
import app_storage
import app_tray
import app_units_backend
import app_variables
import app_window

# Product identity and API preference extensions are installed before storage
# creates the production AppApi instance. Native behavior (including compact
# sizing and DPI-safe titlebar dragging) is installed next; the renderer remains
# the sole owner of HTML/CSS/JavaScript. Diagnostics wrap the final runtime,
# while the outer process guard prevents duplicate hooks, trays and writes.
app_product.install(app, app_tray)
app_clipboard_settings.install(app)
app_storage.install(app)
app_window.install(app)
app_native_titlebar.install(app)
app_numlock_compat.install(app)
app_tray.install(app)
app_units_backend.install(app)
app_variables.install(app)
app_formulas.install(app)
app_renderer.install(app)
app_diagnostics.install(app)
app_single_instance.install(app)


if __name__ == "__main__":
    app.main()
