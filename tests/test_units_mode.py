import threading
import types
import unittest
from pathlib import Path

from calc_engine_runtime import CalculatorSession, make_history_entry

import app_units_mode


class Storage:
    def __init__(self, _path=None):
        self.data = {}

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value

    def update(self, values):
        self.data.update(values)


class UnitsModeTests(unittest.TestCase):
    def make_app(self):
        class AppApi:
            def __init__(self, storage):
                self._storage = storage
                self._session = CalculatorSession()
                self._history = []
                self._sequence = 0
                self._lock = threading.RLock()

            def bootstrap(self):
                return {
                    "history": list(self._history),
                    "suggestions": self._session.suggestions(),
                }

            def suggestions(self, query=""):
                return self._session.suggestions(query)

            def commit(self, expression):
                raise AssertionError("app_units_mode must replace the prototype commit")

        storage = Storage()
        api = AppApi(storage)
        renderer = Path(__file__).resolve().parents[1] / "renderer"
        html = """<html><head><style>base</style></head><body data-theme="dark">
<div class="app-shell"><header class="topbar"></header><main class="workspace">
<section class="editor-card"><div class="editor-toolbar"><span class="editor-label">Выражение</span><div class="editor-tools"></div></div>
<textarea id="expressionInput" class="expression-input" rows="2" placeholder="old"></textarea>
<div class="result-block"><div class="result-actions"></div></div></section>
<section class="history-card"></section></main></div>
<script>
(function () {
  'use strict';
  const expressionInput = document.getElementById('expressionInput');
})();
</script></body></html>"""
        app = types.SimpleNamespace(
            AppApi=AppApi,
            _api=api,
            MAX_HISTORY=500,
            make_history_entry=make_history_entry,
            RENDERER_DIR=renderer,
            build_html=lambda: html,
        )
        return app, api, storage

    def test_simple_arithmetic_rejects_functions_and_units(self):
        self.assertEqual(app_units_mode.evaluate_simple("(100 + 25) / 2"), 62.5)
        self.assertEqual(app_units_mode.evaluate_simple("2,5 × 4"), 10.0)
        with self.assertRaises(ValueError):
            app_units_mode.evaluate_simple("sin(30)")
        with self.assertRaises(ValueError):
            app_units_mode.evaluate_simple("10 kN")

    def test_conversion_catalog_and_temperature(self):
        app, api, _storage = self.make_app()
        app_units_mode.install(app)

        response = api.convert_units("(100 + 25) / 2", "length", "cm", "m")
        self.assertTrue(response["ok"], response.get("error"))
        self.assertEqual(response["source_value"], "62.5")
        self.assertEqual(response["result"], "0.625")

        temperature = api.convert_units("0", "temperature", "degC", "K")
        self.assertTrue(temperature["ok"], temperature.get("error"))
        self.assertEqual(temperature["result"], "273.15")

        invalid = api.convert_units("sin(30)", "length", "m", "mm")
        self.assertFalse(invalid["ok"])

    def test_calculator_handoff_revision_and_converter_state(self):
        app, api, storage = self.make_app()
        app_units_mode.install(app)

        first = api.commit("1250 / 4")
        self.assertTrue(first["ok"], first.get("error"))
        self.assertEqual(first["calculator_handoff"]["value"], "312.5")
        self.assertEqual(first["calculator_handoff"]["revision"], 1)

        converted = api.convert_units(
            "312.5", "length", "mm", "m", True, 1
        )
        self.assertTrue(converted["ok"], converted.get("error"))
        self.assertEqual(converted["result"], "0.3125")
        self.assertEqual(converted["state"]["imported_revision"], 1)
        self.assertEqual(storage.get("unit_converter_state")["expression"], "312.5")

        # A dimensional calculator result does not overwrite the plain numeric handoff.
        dimensional = api.commit("2 m")
        self.assertTrue(dimensional["ok"], dimensional.get("error"))
        self.assertEqual(dimensional["calculator_handoff"]["revision"], 1)
        self.assertEqual(dimensional["calculator_handoff"]["value"], "312.5")

    def test_units_are_removed_from_calculator_suggestions(self):
        app, api, _storage = self.make_app()
        app_units_mode.install(app)
        items = api.suggestions("")
        self.assertTrue(items)
        self.assertFalse(any(item.get("kind") == "unit" for item in items))
        self.assertFalse(any(item.get("group") == "Единицы" for item in items))
        self.assertFalse(any(item.get("kind") == "unit" for item in api.bootstrap()["suggestions"]))

    def test_renderer_contains_two_modes_and_unit_pickers(self):
        app, _api, _storage = self.make_app()
        app_units_mode.install(app)
        html = app.build_html()
        self.assertIn('id="calculatorModeTab"', html)
        self.assertIn('id="unitsModeTab"', html)
        self.assertIn('id="unitConverterCard"', html)
        self.assertIn('id="sourceUnitSelect"', html)
        self.assertIn('id="targetUnitSelect"', html)
        self.assertIn('id="sourceUnitBadge"', html)
        self.assertIn('id="targetUnitBadge"', html)
        self.assertIn("const MODE_UNITS = 'units'", html)
        self.assertNotIn("Функции и единицы (Ctrl+K)", html)


if __name__ == "__main__":
    unittest.main()
