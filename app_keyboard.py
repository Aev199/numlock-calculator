"""Keyboard-first entry point."""

import calc_engine
from calc_engine_runtime import CalculatorSession

calc_engine.CalculatorSession = CalculatorSession

import app
import app_numlock_compat
import app_stability

app_stability.install(app)
app_numlock_compat.install(app)


if __name__ == "__main__":
    app.main()
