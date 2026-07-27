"""Keyboard-first entry point."""

import calc_engine
import unit_conversion
from input_normalization import (
    install_calculator_normalization,
    install_unit_normalization,
)

# Install the forgiving keypad/display normalization before runtime classes and
# backend functions are imported.  The wrappers preserve all original parser
# rules and only repair decimal-separator typos plus the visual multiplication
# glyph used by the renderer.
install_calculator_normalization(calc_engine)
install_unit_normalization(unit_conversion)

from calc_engine_runtime import CalculatorSession

calc_engine.CalculatorSession = CalculatorSession

import app
import app_numlock_compat
import app_renderer
import app_single_instance
import app_tray
import app_units_backend
import app_window

# Native behavior is installed first. The tray wraps only application lifecycle,
# the units backend extends only AppApi, and the consolidated renderer is installed
# last as the sole owner of HTML, CSS and frontend JavaScript. The process guard
# wraps the final entry point so a second launch activates the existing window.
app_window.install(app)
app_numlock_compat.install(app)
app_tray.install(app)
app_units_backend.install(app)
app_renderer.install(app)
app_single_instance.install(app)


if __name__ == "__main__":
    app.main()
