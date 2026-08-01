import types
import unittest
from pathlib import Path
from unittest.mock import patch

import app_native_dialogs
import app_product
import app_renderer


ROOT = Path(__file__).resolve().parents[1]


class AboutModalTests(unittest.TestCase):
    def make_runtime(self):
        evaluated = []
        shown = []

        class Api:
            pass

        window = types.SimpleNamespace(
            evaluate_js=lambda script: evaluated.append(script),
        )
        app = types.SimpleNamespace(
            AppApi=Api,
            _window=window,
            show_window=lambda: shown.append(True),
        )
        dialogs = types.SimpleNamespace(show_link_dialog=lambda *_args: False)
        tray = types.SimpleNamespace(app_native_dialogs=dialogs)
        return app, tray, evaluated, shown

    def test_tray_about_is_routed_to_renderer(self):
        app, tray, evaluated, shown = self.make_runtime()
        app_product.install(app, tray)

        self.assertTrue(
            tray.app_native_dialogs.show_link_dialog(
                "О программе",
                "NumCalc",
                "content",
                (),
            )
        )
        self.assertEqual(shown, [True])
        self.assertEqual(
            evaluated,
            ["window.__nlcalcShowAbout && window.__nlcalcShowAbout()"],
        )

    def test_product_link_api_uses_exact_allowlist(self):
        app, tray, _evaluated, _shown = self.make_runtime()
        app_product.install(app, tray)
        api = app.AppApi()

        with patch.object(app_native_dialogs, "open_external_url", return_value=True) as opener:
            self.assertTrue(api.open_product_link("https://nlcalc.narod.ru/"))

        opener.assert_called_once_with(
            "https://nlcalc.narod.ru/",
            (
                "https://nlcalc.narod.ru/",
                "https://github.com/Aev199/numlock-calculator",
            ),
        )

    def test_renderer_contains_real_about_anchors_and_bridge_calls(self):
        html = app_renderer.render_document(ROOT / "renderer")

        self.assertIn("window.__nlcalcShowAbout = showAbout", html)
        self.assertIn('href="https://nlcalc.narod.ru/"', html)
        self.assertIn(
            'href="https://github.com/Aev199/numlock-calculator"',
            html,
        )
        self.assertIn("state.api.open_product_link(url)", html)
        self.assertIn("about-overlay", html)


if __name__ == "__main__":
    unittest.main()

