"""Keyboard-first entry point."""

import calc_engine
from calc_engine_runtime import CalculatorSession

calc_engine.CalculatorSession = CalculatorSession

import app
import app_numlock_compat
import app_renderer
import app_stability
import app_tray
import app_units_backend

# Native behavior is installed first. The tray wraps the application lifecycle,
# the units backend extends only the Python API, and the consolidated renderer is
# installed last so no earlier layer can patch or replace its document.
app_stability.install(app)
app_numlock_compat.install(app)
app_tray.install(app)
app_units_backend.install(app)
app_renderer.install(app)


if __name__ == "__main__":
    app.main()
