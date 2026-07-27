import types
import unittest
from pathlib import Path

import app_renderer


ROOT = Path(__file__).resolve().parents[1]


class ConsolidatedRendererTests(unittest.TestCase):
    def make_app(self):
        calls = []

        def create_window(*args, **kwargs):
            calls.append((args, kwargs))
            return object()

        app = types.SimpleNamespace(
            RENDERER_DIR=ROOT / "renderer",
            webview=types.SimpleNamespace(create_window=create_window),
            build_html=lambda: "legacy",
        )
        return app, calls

    def test_single_template_inlines_exactly_one_css_and_script(self):
        app, _calls = self.make_app()
        app_renderer.install(app)
        html = app.build_html()

        self.assertIn("nlcalc-consolidated-v1", html)
        self.assertIn('id="calculatorModeTab"', html)
        self.assertIn('id="unitsModeTab"', html)
        self.assertIn('id="calculatorPanel"', html)
        self.assertIn('id="unitsPanel"', html)
        self.assertIn("function commitCalculator()", html)
        self.assertIn("function commitUnits()", html)
        self.assertIn("function reconcileHistory", html)
        self.assertIn("window.__nlcalcRestoreEditorFocus", html)
        self.assertIn("event.code === 'KeyK'", html)
        self.assertNotIn(app_renderer.CSS_PLACEHOLDER, html)
        self.assertNotIn(app_renderer.JS_PLACEHOLDER, html)
        self.assertNotIn("nlcalc-motion-v5", html)
        self.assertNotIn("nlcalc-polish-v3", html)
        self.assertNotIn("nlcalc-enter-fast", html)

    def test_both_mode_panels_are_permanent_dom_siblings(self):
        app, _calls = self.make_app()
        app_renderer.install(app)
        html = app.build_html()

        calculator = html.index('id="calculatorPanel"')
        units = html.index('id="unitsPanel"')
        stage_start = html.index('id="modeStage"')
        stage_end = html.index("</main>")
        self.assertLess(stage_start, calculator)
        self.assertLess(calculator, units)
        self.assertLess(units, stage_end)
        self.assertIn(".mode-panel {", html)
        self.assertIn("position: absolute", html)
        self.assertIn("opacity: 0", html)
        self.assertIn(".mode-panel.active", html)

    def test_keyboard_entry_point_uses_only_final_renderer_layers(self):
        source = (ROOT / "app_keyboard.py").read_text(encoding="utf-8")
        self.assertIn("import app_renderer", source)
        self.assertIn("import app_units_backend", source)
        self.assertIn("app_units_backend.install(app)", source)
        self.assertIn("app_renderer.install(app)", source)
        self.assertNotIn("import app_polish", source)
        self.assertNotIn("import app_compact", source)
        self.assertNotIn("import app_units_mode", source)
        self.assertNotIn("app_polish.install", source)
        self.assertNotIn("app_compact.install", source)
        self.assertNotIn("app_units_mode.install", source)

    def test_window_size_is_owned_by_renderer_shell(self):
        app, calls = self.make_app()
        app_renderer.install(app)
        app.webview.create_window("test", width=999, height=999, min_size=(1, 1))

        kwargs = calls[0][1]
        self.assertEqual(kwargs["width"], app_renderer.DEFAULT_WIDTH)
        self.assertEqual(kwargs["height"], app_renderer.DEFAULT_HEIGHT)
        self.assertEqual(kwargs["min_size"], app_renderer.MIN_SIZE)

    def test_install_is_idempotent(self):
        app, _calls = self.make_app()
        app_renderer.install(app)
        first_builder = app.build_html
        first_create_window = app.webview.create_window
        app_renderer.install(app)
        self.assertIs(first_builder, app.build_html)
        self.assertIs(first_create_window, app.webview.create_window)


if __name__ == "__main__":
    unittest.main()
