import unittest
from pathlib import Path

import app_renderer


ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "renderer"


class CompactPaletteFitTests(unittest.TestCase):
    def test_palette_fit_layer_is_loaded_after_compact_controller(self):
        scripts = list(app_renderer.SCRIPT_PARTS)
        compact_index = scripts.index("app-shell-v2.compact.js")
        fit_index = scripts.index("app-shell-v2.compact-palette-fit.js")
        self.assertEqual(fit_index, compact_index + 1)

    def test_compact_palette_fits_native_window_to_rendered_content(self):
        html = app_renderer.render_document(RENDERER)
        self.assertIn("COMPACT_PALETTE_RESULTS_MAX_HEIGHT = 232", html)
        self.assertIn("compactPaletteContentHeight", html)
        self.assertIn("palette.getBoundingClientRect().height", html)
        self.assertIn("scheduleCompactPaletteFit", html)
        self.assertIn("dom.paletteResults.style.maxHeight", html)
        self.assertIn("renderPaletteWithoutContentFit", html)
        self.assertIn("openPaletteWithoutContentFit", html)
        self.assertIn("closePaletteWithoutContentFit", html)


if __name__ == "__main__":
    unittest.main()
