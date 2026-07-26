"""Keyboard-first entry point."""

import calc_engine
from calc_engine_runtime import CalculatorSession

calc_engine.CalculatorSession = CalculatorSession

import app
import app_compact
import app_numlock_compat
import app_polish
import app_stability
import app_tray
import app_units_mode

app_stability.install(app)
app_polish.install(app)
app_numlock_compat.install(app)
app_tray.install(app)
app_compact.install(app)
app_units_mode.install(app)


if __name__ == "__main__":
    app.main()
