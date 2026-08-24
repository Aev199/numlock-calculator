"""Single source of NumCalc product identity and release version."""

APP_NAME = "NumCalc"
APP_VERSION = "1.3.0"
APP_ID = "Aev199.NumCalc"
COMPANY_NAME = "Aev199"
EXECUTABLE_NAME = "NumCalc"
DESCRIPTION = "Компактный keyboard-first инженерный калькулятор для Windows"
COPYRIGHT = "Copyright © 2026 Aev199"
LICENSE_NAME = "MIT"
REPOSITORY_URL = "https://github.com/Aev199/numlock-calculator"
INSPIRATION_URL = "https://nlcalc.narod.ru/"


def version_tuple() -> tuple[int, int, int, int]:
    """Return a Windows file-version tuple, ignoring prerelease labels."""
    numeric = APP_VERSION.split("-", 1)[0].split(".")
    parts = [int(part) for part in numeric[:4]]
    return tuple((parts + [0, 0, 0, 0])[:4])
