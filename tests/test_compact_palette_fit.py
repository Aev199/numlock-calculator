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

    def test_compact_palette_uses_natural_content_height_not_current_viewport(self):
        html = app_renderer.render_document(RENDERER)
        self.assertIn("COMPACT_PALETTE_RESULTS_MAX_HEIGHT = 232", html)
        self.assertIn("compactPaletteContentHeight", html)
        self.assertIn("dom.paletteResults.scrollHeight", html)
        self.assertIn("visibleElementHeight(search)", html)
        self.assertIn("visibleElementHeight(groups)", html)
        self.assertNotIn("palette.getBoundingClientRect().height", html)
        self.assertIn("scheduleCompactPaletteFit", html)
        self.assertIn("dom.paletteResults.style.maxHeight", html)
        self.assertIn("renderPaletteWithoutContentFit", html)
        self.assertIn("openPaletteWithoutContentFit", html)
        self.assertIn("closePaletteWithoutContentFit", html)


if __name__ == "__main__":
    unittest.main()
