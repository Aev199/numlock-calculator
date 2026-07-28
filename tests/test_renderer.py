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

    def test_single_template_inlines_one_controller(self):
        app, _calls = self.make_app()
        app_renderer.install(app)
        html = app.build_html()

        self.assertEqual(html.count("nlcalc-consolidated-v2"), 1)
        self.assertIn('id="calculatorModeTab"', html)
        self.assertIn('id="unitsModeTab"', html)
        self.assertIn('id="calculatorPanel"', html)
        self.assertIn('id="unitsPanel"', html)
        self.assertIn("function commitCalculator()", html)
        self.assertIn("function commitUnits()", html)
        self.assertIn("function reconcileHistory", html)
        self.assertIn("window.__nlcalcRestoreEditorFocus", html)
        self.assertIn("input-motion-layer", html)
        self.assertIn("bracket-color-overlay", html)
        self.assertIn("Функции (Tab)", html)
        self.assertNotIn("keydown-v2", html)
        self.assertNotIn(app_renderer.CSS_PLACEHOLDER, html)
        self.assertNotIn(app_renderer.JS_PLACEHOLDER, html)
        self.assertNotIn("nlcalc-motion-v5", html)
        self.assertNotIn("nlcalc-polish-v3", html)
        self.assertNotIn("nlcalc-enter-fast", html)

    def test_controller_parts_are_complete_and_ordered(self):
        renderer = ROOT / "renderer"
        self.assertEqual(len(app_renderer.SCRIPT_PARTS), 15)
        source = "\n".join(
            (renderer / name).read_text(encoding="utf-8")
            for name in app_renderer.SCRIPT_PARTS
        )
        self.assertTrue(source.lstrip().startswith("(function ()"))
        self.assertTrue(source.rstrip().endswith("})();"))
        self.assertEqual(source.count("nlcalc-consolidated-v2"), 1)
        self.assertNotIn("app-shell-v2.motion-keydown.js", app_renderer.SCRIPT_PARTS)
        self.assertNotIn("app-shell-v2.typing.js", app_renderer.SCRIPT_PARTS)
        self.assertLess(
            app_renderer.SCRIPT_PARTS.index("app-shell-v2.part07zzz.js"),
            app_renderer.SCRIPT_PARTS.index("app-shell-v2.ux.js"),
        )
        self.assertLess(
            app_renderer.SCRIPT_PARTS.index("app-shell-v2.ux.js"),
            app_renderer.SCRIPT_PARTS.index("app-shell-v2.multiply.js"),
        )
        self.assertLess(
            app_renderer.SCRIPT_PARTS.index("app-shell-v2.multiply.js"),
            app_renderer.SCRIPT_PARTS.index("app-shell-v2.variables.js"),
        )
        self.assertLess(
            app_renderer.SCRIPT_PARTS.index("app-shell-v2.variables.js"),
            app_renderer.SCRIPT_PARTS.index("app-shell-v2.part08.js"),
        )

    def test_character_input_is_native_and_tab_opens_palette(self):
        app, _calls = self.make_app()
        app_renderer.install(app)
        html = app.build_html()

        self.assertIn("typingFeedback = function () {};", html)
        self.assertNotIn("function interceptTextInsertion(event)", html)
        self.assertNotIn("function interceptPhysicalKey(event)", html)
        self.assertNotIn("window.__NLCALC_MOTION_INPUT_RUNTIME__", html)
        self.assertNotIn("dom.input.value = nextValue", html)
        self.assertIn("event.key === 'Tab'", html)
        self.assertIn("isPaletteShortcut = function () { return false; };", html)
        self.assertIn("dom.input.setRangeText(`(${selected})`", html)
        self.assertIn("TRIG_ORDER = ['sin', 'cos', 'tan', 'atan', 'asin', 'acos']", html)
        self.assertIn("POWER_ORDER = ['sqrt', 'exp', 'log', 'ln', 'log10', 'fact', 'cbrt']", html)

    def test_classic_input_has_no_caret_animation_layer(self):
        app, _calls = self.make_app()
        app_renderer.install(app)
        html = app.build_html()

        self.assertNotIn("beginCaretGlyphMotion", html)
        self.assertNotIn("completeCaretGlyphMotion", html)
        self.assertNotIn("nlcalc-caret-glyph", html)
        self.assertNotIn("caret-glyph-mirroring", html)
        self.assertNotIn("nlcalc-typing-mirror", html)
        self.assertNotIn("CARET_GLYPH_DURATION", html)
        self.assertFalse((ROOT / "renderer" / "app-shell-v2.typing.js").exists())
        self.assertFalse((ROOT / "renderer" / "app-shell-typing.css").exists())

    def test_product_keyboard_shortcuts_and_multiply_display(self):
        app, _calls = self.make_app()
        app_renderer.install(app)
        html = app.build_html()

        self.assertIn("const DISPLAY_MULTIPLY = '⋅';", html)
        self.assertIn("displayExpressionWithoutImplicitMultiply", html)
        self.assertIn(r"/([0-9)])\s*(?=\()/g", html)
        self.assertIn("function copyCurrentCalculation()", html)
        self.assertIn("event.code === 'KeyC'", html)
        self.assertIn("event.key === 'ArrowLeft' || event.key === 'ArrowRight'", html)
        self.assertIn("switchMode(event.key === 'ArrowLeft' ? 'calculator' : 'units')", html)
        self.assertIn("Вычисление скопировано", html)

    def test_variable_drawer_has_persistent_delete_action(self):
        app, _calls = self.make_app()
        app_renderer.install(app)
        html = app.build_html()

        self.assertIn("state.api.delete_variable(name)", html)
        self.assertIn("variable-delete", html)
        self.assertIn("Удалить переменную", html)
        self.assertIn("state.variables = response.variables", html)
        self.assertIn("setCatalog(response.suggestions)", html)

    def test_renderer_reports_errors_and_storage_fallbacks(self):
        app, _calls = self.make_app()
        app_renderer.install(app)
        html = app.build_html()

        self.assertIn("function reportRendererDiagnostic", html)
        self.assertIn("report_diagnostic", html)
        self.assertIn("unhandledrejection", html)
        self.assertIn("data.storage_warning", html)

    def test_race_guards_are_present(self):
        app, _calls = self.make_app()
        app_renderer.install(app)
        html = app.build_html()

        self.assertIn("pendingCommits", html)
        self.assertIn("historyEpoch", html)
        self.assertIn("state.calculator.expression === visibleCommittedValue", html)
        self.assertIn("unitContext() === context", html)
        self.assertIn("incomingRevision < currentRevision", html)
        self.assertIn("if (event.repeat) return", html)
        self.assertIn("event.stopPropagation()", html)
        self.assertIn("cancelCommitAnimation()", html)

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

    def test_keyboard_entry_point_uses_renderer_agnostic_layers(self):
        source = (ROOT / "app_keyboard.py").read_text(encoding="utf-8")
        for module in (
            "app_product",
            "app_storage",
            "app_window",
            "app_renderer",
            "app_units_backend",
            "app_variables",
            "app_diagnostics",
            "app_single_instance",
        ):
            self.assertIn(f"import {module}", source)
        self.assertIn("install_calculator_normalization(calc_engine)", source)
        self.assertIn("install_unit_normalization(unit_conversion)", source)
        self.assertIn("app_product.install(app, app_tray)", source)
        self.assertIn("app_storage.install(app)", source)
        self.assertIn("app_window.install(app)", source)
        self.assertIn("app_units_backend.install(app)", source)
        self.assertIn("app_variables.install(app)", source)
        self.assertIn("app_renderer.install(app)", source)
        self.assertIn("app_diagnostics.install(app)", source)
        self.assertIn("app_single_instance.install(app)", source)
        self.assertNotIn("import app_stability", source)
        self.assertNotIn("import app_polish", source)
        self.assertNotIn("import app_compact", source)
        self.assertNotIn("import app_units_mode", source)

    def test_window_and_tray_layers_do_not_modify_html(self):
        window_source = (ROOT / "app_window.py").read_text(encoding="utf-8")
        tray_source = (ROOT / "app_tray.py").read_text(encoding="utf-8")
        for source in (window_source, tray_source):
            self.assertNotIn("build_html", source)
            self.assertNotIn(".replace(", source)

    def test_window_size_is_owned_by_renderer_shell(self):
        app, calls = self.make_app()
        app_renderer.install(app)
        app.webview.create_window("test", width=999, height=999, min_size=(1, 1))

        kwargs = calls[0][1]
        self.assertEqual(app_renderer.DEFAULT_WIDTH, 384)
        self.assertEqual(app_renderer.DEFAULT_HEIGHT, 432)
        self.assertEqual(app_renderer.MIN_SIZE, (360, 380))
        self.assertEqual(kwargs["width"], app_renderer.DEFAULT_WIDTH)
        self.assertEqual(kwargs["height"], app_renderer.DEFAULT_HEIGHT)
        self.assertEqual(kwargs["min_size"], app_renderer.MIN_SIZE)

    def test_compact_window_has_matching_internal_density(self):
        css = (ROOT / "renderer" / "app-shell-product.css").read_text(
            encoding="utf-8"
        )
        self.assertIn("@media (max-width: 410px), (max-height: 460px)", css)
        self.assertIn("min-height: 34px", css)
        self.assertIn("max-height: 58px", css)
        self.assertIn("height: 27px", css)
        self.assertIn("overflow-y: auto", css)

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
