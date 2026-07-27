"""Keyboard-first entry point."""

import calc_engine
from calc_engine_runtime import CalculatorSession

calc_engine.CalculatorSession = CalculatorSession

import app
import app_numlock_compat
import app_renderer
import app_tray
import app_units_backend
import app_window

# Native behavior is installed first. The tray wraps only application lifecycle,
# the units backend extends only AppApi, and the consolidated renderer is installed
# last as the sole owner of HTML, CSS and frontend JavaScript.
app_window.install(app)
app_numlock_compat.install(app)
app_tray.install(app)
app_units_backend.install(app)
app_renderer.install(app)


if __name__ == "__main__":
    app.main()
