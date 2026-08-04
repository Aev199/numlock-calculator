import tempfile
import unittest
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # Linux source-only CI does not install runtime packages.
    Image = None

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

    @unittest.skipIf(Image is None, "Pillow is verified by the Windows build job")
    def test_shared_icon_writes_multiresolution_ico(self):
        tray = app_icon.create_icon_image(64)
        self.assertEqual(tray.getpixel((10, 32)), app_icon.ICON_BACKGROUND)
        self.assertEqual(tray.getpixel((32, 32)), app_icon.ICON_FOREGROUND)
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
