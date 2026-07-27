"""Single source of NumCalc product identity and release version."""

APP_NAME = "NumCalc"
APP_VERSION = "1.0.0-rc.1"
APP_ID = "Aev199.NumCalc"
COMPANY_NAME = "Aev199"
EXECUTABLE_NAME = "NumCalc"
DESCRIPTION = "Компактный keyboard-first калькулятор для Windows"
COPYRIGHT = "Copyright © 2026 Aev199"


def version_tuple() -> tuple[int, int, int, int]:
    """Return a Windows file-version tuple, ignoring prerelease labels."""

    numeric = APP_VERSION.split("-", 1)[0].split(".")
    parts = [int(part) for part in numeric[:4]]
    return tuple((parts + [0, 0, 0, 0])[:4])
