from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def write(relative: str, content: str) -> None:
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def replace(relative: str, old: str, new: str, *, required: bool = True) -> None:
    content = read(relative)
    if old not in content:
        if required:
            raise RuntimeError(f"Expected text not found in {relative}: {old!r}")
        return
    write(relative, content.replace(old, new))


def insert_once(relative: str, marker: str, addition: str) -> None:
    content = read(relative)
    if addition.strip() in content:
        return
    if marker not in content:
        raise RuntimeError(f"Insertion marker not found in {relative}: {marker!r}")
    write(relative, content.replace(marker, addition + marker, 1))


APP_ICON_SOURCE = '''"""Shared NumCalc icon artwork for the tray and Windows executable."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


ICON_BACKGROUND = (82, 109, 255, 255)
ICON_FOREGROUND = (248, 250, 255, 255)
WINDOWS_ICON_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def create_icon_image(size: int = 64) -> Image.Image:
    """Draw the rounded blue NumCalc tile with the white N glyph."""

    size = max(16, int(size))
    scale = size / 64.0
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    def point(value: float) -> int:
        return round(value * scale)

    draw.rounded_rectangle(
        (point(3), point(3), point(61), point(61)),
        radius=point(15),
        fill=ICON_BACKGROUND,
    )
    width = max(2, point(7))
    draw.line((point(18), point(46), point(18), point(18)), fill=ICON_FOREGROUND, width=width)
    draw.line((point(18), point(18), point(46), point(46)), fill=ICON_FOREGROUND, width=width)
    draw.line((point(46), point(46), point(46), point(18)), fill=ICON_FOREGROUND, width=width)
    return image


def write_windows_icon(path: str | Path) -> Path:
    """Create a multi-resolution ICO used by PyInstaller and Windows shell."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    create_icon_image(256).save(
        target,
        format="ICO",
        sizes=[(size, size) for size in WINDOWS_ICON_SIZES],
    )
    return target
'''

NUMBER_FORMATTING_SOURCE = '''"""Shared numeric presentation helpers for calculator outputs."""

from __future__ import annotations

import math


VALID_NUMBER_FORMATS = {"auto", "engineering"}
VALID_DECIMAL_SEPARATORS = {".", ","}
MIN_DECIMAL_PLACES = 0
MAX_DECIMAL_PLACES = 15
DEFAULT_DECIMAL_PLACES = 6


def normalize_number_format(value: object) -> str:
    candidate = str(value or "auto").strip().lower()
    return candidate if candidate in VALID_NUMBER_FORMATS else "auto"


def normalize_decimal_separator(value: object) -> str:
    candidate = str(value or ".").strip().lower()
    if candidate in {",", "comma", "запятая"}:
        return ","
    return "."


def normalize_decimal_places(value: object, default: int = DEFAULT_DECIMAL_PLACES) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = int(default)
    return max(MIN_DECIMAL_PLACES, min(MAX_DECIMAL_PLACES, parsed))


def _trim_fixed(text: str) -> str:
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in {"", "+0", "-0"} else text


def _format_scientific(value: float, decimal_places: int) -> str:
    mantissa, exponent = f"{value:.{decimal_places}e}".split("e", 1)
    return f"{_trim_fixed(mantissa)}e{int(exponent):+d}"


def _format_engineering(value: float, decimal_places: int) -> str:
    exponent = int(math.floor(math.log10(abs(value)) / 3.0) * 3)
    mantissa = value / (10.0**exponent)
    rounded = round(mantissa, decimal_places)
    if abs(rounded) >= 1000:
        mantissa /= 1000
        exponent += 3
    text = _trim_fixed(f"{mantissa:.{decimal_places}f}")
    return f"{text}e{exponent:+d}" if exponent else text


def format_number(
    value: float,
    precision: int = DEFAULT_DECIMAL_PLACES,
    number_format: str = "auto",
    decimal_separator: str = ".",
) -> str:
    """Round to ``precision`` decimal places and omit trailing zeroes.

    The public API keeps the historical ``precision`` key for compatibility
    with saved settings and profiles. Its meaning from NumCalc 1.1 onward is
    the number of digits after the decimal separator, not significant digits.
    """

    if not math.isfinite(value):
        raise ValueError("Результат не является конечным числом")

    decimal_places = normalize_decimal_places(precision)
    mode = normalize_number_format(number_format)
    separator = normalize_decimal_separator(decimal_separator)

    if value == 0:
        text = "0"
    elif mode == "engineering":
        text = _format_engineering(value, decimal_places)
    elif abs(value) >= 1e12 or abs(value) < 1e-6:
        text = _format_scientific(value, decimal_places)
    else:
        text = _trim_fixed(f"{value:.{decimal_places}f}")

    if separator == ",":
        mantissa, marker, exponent = text.partition("e")
        text = mantissa.replace(".", ",") + (marker + exponent if marker else "")
    return text
'''

ICON_TEST_SOURCE = '''import tempfile
import unittest
from pathlib import Path

from PIL import Image

import app_icon
from calc_engine import EngineSettings
from number_formatting import format_number


ROOT = Path(__file__).resolve().parents[1]


class ReleaseCandidateFormattingTests(unittest.TestCase):
    def test_decimal_places_rounding_omits_trailing_zeroes(self):
        self.assertEqual(format_number(12.3400, 4), "12.34")
        self.assertEqual(format_number(1 / 3, 2), "0.33")
        self.assertEqual(format_number(123.6, 0), "124")
        self.assertEqual(format_number(1.2, 6), "1.2")
        self.assertEqual(format_number(12345, 2, "engineering"), "12.35e+3")
        self.assertEqual(format_number(1.2, 4, decimal_separator=","), "1,2")

    def test_engine_settings_accept_zero_decimal_places(self):
        self.assertEqual(EngineSettings.from_mapping({}).precision, 6)
        self.assertEqual(EngineSettings.from_mapping({"precision": 0}).precision, 0)
        self.assertEqual(EngineSettings.from_mapping({"precision": 99}).precision, 15)

    def test_shared_icon_writes_multiresolution_ico(self):
        tray = app_icon.create_icon_image(64)
        self.assertEqual(tray.getpixel((32, 32)), app_icon.ICON_BACKGROUND)
        with tempfile.TemporaryDirectory() as directory:
            target = app_icon.write_windows_icon(Path(directory) / "NumCalc.ico")
            self.assertTrue(target.is_file())
            with Image.open(target) as icon:
                self.assertEqual(icon.format, "ICO")
                self.assertIn((64, 64), icon.ico.sizes())
                self.assertIn((256, 256), icon.ico.sizes())

    def test_both_pyinstaller_specs_use_shared_icon(self):
        for name in ("NumCalc.spec", "NumCalc-folder.spec"):
            source = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("write_windows_icon", source)
            self.assertIn("icon=str(APP_ICON)", source)


if __name__ == "__main__":
    unittest.main()
'''

write("app_icon.py", APP_ICON_SOURCE)
write("number_formatting.py", NUMBER_FORMATTING_SOURCE)
write("tests/test_release_candidate_fixes.py", ICON_TEST_SOURCE)

replace(
    "app_tray.py",
    "import app_native_dialogs\n",
    "import app_native_dialogs\nfrom app_icon import create_icon_image\n",
)
replace(
    "app_tray.py",
    '''    def create_tray_image() -> Any:\n        from PIL import Image, ImageDraw\n\n        image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))\n        draw = ImageDraw.Draw(image)\n        draw.rounded_rectangle((3, 3, 61, 61), radius=15, fill=(82, 109, 255, 255))\n        line = (248, 250, 255, 255)\n        draw.line((18, 46, 18, 18), fill=line, width=7)\n        draw.line((18, 18, 46, 46), fill=line, width=7)\n        draw.line((46, 46, 46, 18), fill=line, width=7)\n        return image\n''',
    '''    def create_tray_image() -> Any:\n        return create_icon_image(64)\n''',
)
replace(
    "app_tray.py",
    "• Формат результата, точность и десятичный разделитель настраиваются в «Настройках».",
    "• Формат результата, количество знаков после запятой и десятичный разделитель настраиваются в «Настройках».",
)

for spec in ("NumCalc.spec", "NumCalc-folder.spec"):
    replace(
        spec,
        "# -*- mode: python ; coding: utf-8 -*-\n\n\n",
        "# -*- mode: python ; coding: utf-8 -*-\n\nfrom pathlib import Path\n\nfrom app_icon import write_windows_icon\n\n\nAPP_ICON = write_windows_icon(Path('build') / 'NumCalc.ico')\n\n\n",
    )
    replace(
        spec,
        "    version='version_info.txt',\n",
        "    icon=str(APP_ICON),\n    version='version_info.txt',\n",
    )

replace("calc_engine.py", "    precision: int = 12\n", "    precision: int = 6\n")
replace("calc_engine.py", 'precision = int(data.get("precision", 12))', 'precision = int(data.get("precision", 6))')
replace("calc_engine.py", "            precision = 12\n", "            precision = 6\n")
replace("calc_engine.py", "            precision=max(3, min(17, precision)),\n", "            precision=max(0, min(15, precision)),\n")
replace("app.py", 'normalized_item.setdefault("precision", 12)', 'normalized_item.setdefault("precision", 6)')

replace(
    "renderer/app-shell-v2.part00.js",
    "      precision: 12,\n",
    "      precision: 6,\n",
)
replace(
    "renderer/app-shell-v2.part00.js",
    "  const isPlainNumber = value => PLAIN_NUMBER.test(normalize(value));\n",
    '''  const isPlainNumber = value => PLAIN_NUMBER.test(normalize(value));\n  const normalizeDecimalPlacesInput = (value, fallback = 6) => {\n    const parsed = Number.parseInt(value, 10);\n    const selected = Number.isFinite(parsed) ? parsed : fallback;\n    return Math.max(0, Math.min(15, selected));\n  };\n''',
)

replace("renderer/app-shell-v2.hotkey.js", "<span>Значащих знаков</span>", "<span>Знаков после запятой</span>")
replace(
    "renderer/app-shell-v2.hotkey.js",
    'type="number" min="3" max="17" step="1"',
    'type="number" min="0" max="15" step="1"',
)
replace(
    "renderer/app-shell-v2.hotkey.js",
    "    precisionInput.value = String(state.settings.precision || 12);\n",
    "    precisionInput.value = String(state.settings.precision ?? 6);\n",
)
replace(
    "renderer/app-shell-v2.hotkey.js",
    '''      const precision = Math.max(\n        3,\n        Math.min(17, Number.parseInt(precisionInput.value, 10) || 12),\n      );\n''',
    '''      const precision = normalizeDecimalPlacesInput(\n        precisionInput.value,\n        state.settings.precision ?? 6,\n      );\n''',
)
replace(
    "renderer/app-shell-v2.hotkey.js",
    "        if (!response?.precision) {\n",
    "        if (!response || !Number.isInteger(response.precision)) {\n",
)

replace(
    "renderer/app-shell-v2.formulas.js",
    "    if (options.type) input.type = options.type;\n",
    '''    if (options.type) input.type = options.type;\n    if (options.min !== undefined) input.min = String(options.min);\n    if (options.max !== undefined) input.max = String(options.max);\n    if (options.step !== undefined) input.step = String(options.step);\n''',
)
replace(
    "renderer/app-shell-v2.formulas.js",
    "drawerField('Знаков', formulaSettings.precision || state.settings.precision, { id: 'formulaPrecision', type: 'number' })",
    "drawerField('Знаков после запятой', formulaSettings.precision ?? state.settings.precision, { id: 'formulaPrecision', type: 'number', min: 0, max: 15, step: 1 })",
)
replace(
    "renderer/app-shell-v2.formulas.js",
    "precision: Number.parseInt(form.querySelector('#formulaPrecision input').value, 10) || state.settings.precision,",
    "precision: normalizeDecimalPlacesInput(form.querySelector('#formulaPrecision input').value, state.settings.precision ?? 6),",
)
replace(
    "renderer/app-shell-v2.formulas.js",
    "const precision = drawerField('Знаков', profileSettings.precision || state.settings.precision, { id: 'profilePrecision', type: 'number' });",
    "const precision = drawerField('Знаков после запятой', profileSettings.precision ?? state.settings.precision, { id: 'profilePrecision', type: 'number', min: 0, max: 15, step: 1 });",
)
replace(
    "renderer/app-shell-v2.formulas.js",
    "precision: Number.parseInt(form.querySelector('#profilePrecision input').value, 10) || state.settings.precision,",
    "precision: normalizeDecimalPlacesInput(form.querySelector('#profilePrecision input').value, state.settings.precision ?? 6),",
)

replace(
    ".github/workflows/tests.yml",
    "          app_storage.py calculation_limits.py collect_third_party_licenses.py\n",
    "          app_storage.py app_icon.py calculation_limits.py collect_third_party_licenses.py\n",
)

replace(
    "README.md",
    "от 3 до 17 значащих знаков",
    "от 0 до 15 знаков после запятой; хвостовые нули не показываются",
    required=False,
)
replace(
    "README.md",
    "значащих знаков",
    "знаков после запятой",
    required=False,
)
insert_once(
    "README.md",
    "## Установка\n",
    "В версии **1.1.0** иконка EXE, окна и системного трея унифицирована. Точность задаётся количеством знаков после запятой (`0–15`), при этом незначащие хвостовые нули не выводятся.\n\n",
)

insert_once(
    "RELEASE_NOTES.md",
    "## Установка\n",
    "## Финальные исправления release candidate\n\n- иконка Windows-приложения приведена к синей иконке `N`, используемой в системном трее;\n- настройка точности теперь задаёт `0–15` знаков после запятой;\n- хвостовые нули результата не отображаются;\n- форматирование калькулятора, конвертера, интерполяции, формул, профилей, истории и копирования использует единые правила.\n\n",
)
insert_once(
    "CHANGELOG.md",
    "## 1.0.0",
    "### Финальная подготовка 1.1.0\n\n- иконка EXE и окна унифицирована с синей иконкой `N` в системном трее;\n- пользовательская точность переведена со значащих цифр на `0–15` знаков после запятой;\n- хвостовые нули после округления больше не показываются;\n- формулы и инженерные профили используют ту же настройку десятичных знаков.\n\n",
)

replace(
    "docs/WINDOWS_ACCEPTANCE.md",
    "значащих знаков",
    "знаков после запятой",
    required=False,
)
insert_once(
    "docs/WINDOWS_ACCEPTANCE.md",
    "## 2. «О программе»",
    "- [ ] Иконка `NumCalc.exe`, окна, панели задач и Alt+Tab совпадает с синей иконкой `N` в трее.\n- [ ] При 0 знаков после запятой `123,6` округляется до `124`.\n- [ ] При 4 знаках после запятой `12,3400` отображается как `12,34`, без хвостовых нулей.\n\n",
)
insert_once(
    "docs/RELEASE_CHECKLIST.md",
    "## 2. Автоматические проверки",
    "- [x] Иконка приложения и tray строятся из общего источника.\n- [x] Точность переведена на количество знаков после запятой без хвостовых нулей.\n\n",
)

# Keep historical API key names for backward-compatible data.json and profiles,
# but remove obsolete user-facing wording from current release materials.
for relative in (
    "app_tray.py",
    "README.md",
    "RELEASE_NOTES.md",
    "docs/WINDOWS_ACCEPTANCE.md",
    "docs/RELEASE_CHECKLIST.md",
    "renderer/app-shell-v2.hotkey.js",
    "renderer/app-shell-v2.formulas.js",
):
    if "значащих знаков" in read(relative).lower():
        raise RuntimeError(f"Obsolete significant-digits wording remains in {relative}")

print("Release candidate icon and decimal-place fixes applied.")
