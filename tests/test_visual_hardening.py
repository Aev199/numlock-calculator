import types
import unittest
from pathlib import Path

import app_product


ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "renderer"


class VisualHardeningTests(unittest.TestCase):
    def test_core_css_is_canonical_not_decorative_legacy(self):
        core = (RENDERER / "app-shell.css").read_text(encoding="utf-8")
        product = (RENDERER / "app-shell-product.css").read_text(encoding="utf-8")
        utility = (RENDERER / "app-shell-utility.css").read_text(encoding="utf-8")

        self.assertNotIn("linear-gradient(145deg", core)
        self.assertNotIn("mode-workspace-old-forward", core)
        self.assertNotIn("mode-panel-enter-forward", core)
        self.assertNotIn("view-transition-name: mode-workspace", core)
        self.assertIn("background: var(--accent);", core)
        self.assertIn("border-radius: 5px;", core)
        self.assertIn("border-bottom: 1px solid var(--border);", core)
        self.assertNotIn("border-radius: 11px", product)
        self.assertLess(len(utility.splitlines()), 80)
        self.assertIn("cross-feature rules", utility.lower())

    def test_brand_title_keeps_intrinsic_trailing_glyph_buffer(self):
        utility = (RENDERER / "app-shell-utility.css").read_text(encoding="utf-8")

        self.assertIn(".brand-title::after", utility)
        self.assertIn('content: "";', utility)
        self.assertIn("width: 4px;", utility)
        self.assertIn("display: inline-block;", utility)
        self.assertIn("overflow: visible;", utility)

    def test_saved_formula_and_profile_ui_is_removed(self):
        source = (RENDERER / "app-shell-v2.formulas.js").read_text(encoding="utf-8")
        css = (RENDERER / "app-shell-formulas.css").read_text(encoding="utf-8")

        self.assertIn("Saved formulas and engineering profiles were removed", source)
        self.assertIn("function renderFormulasDrawer()", source)
        self.assertNotIn("state.api.save_formula(", source)
        self.assertNotIn("state.api.evaluate_formula(", source)
        self.assertNotIn("state.api.set_active_profile(", source)
        self.assertIn("#formulasButton", css)
        self.assertIn("display: none !important", css)

    def test_help_matches_current_compact_shortcuts(self):
        class Api:
            pass

        app = types.SimpleNamespace(AppApi=Api)
        tray = types.SimpleNamespace(app_native_dialogs=None)
        app_product.install(app, tray)
        help_text = tray.HELP_TEXT

        self.assertIn("Alt+↑ — компактный режим", help_text)
        self.assertIn("Alt+↓ — полный режим", help_text)
        self.assertIn("Ctrl+H — история", help_text)
        self.assertIn("Alt+← / Alt+→ — режимы", help_text)
        self.assertIn("Телеметрии нет", help_text)
        self.assertIn("Старые отдельные «Формулы» и «Профили» удалены", help_text)

    def test_about_has_no_duplicate_logo_or_marketing_sentence(self):
        source = (RENDERER / "app-shell-v2.about.js").read_text(encoding="utf-8")

        self.assertNotIn('class="about-mark"', source)
        self.assertNotIn('class="about-details"', source)
        self.assertNotIn("Продолжает идеи", source)
        self.assertIn("Калькулятор для Windows", source)
        self.assertIn('class="about-license">MIT</p>', source)


if __name__ == "__main__":
    unittest.main()
