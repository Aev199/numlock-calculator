"""Keyboard-first entry point.

The runtime refinement class is installed before importing the desktop shell,
so both source runs and PyInstaller use the side-effect-free preview engine.
"""

import calc_engine
from calc_engine_runtime import CalculatorSession

calc_engine.CalculatorSession = CalculatorSession

import app


if __name__ == "__main__":
    app.main()
