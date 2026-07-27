import threading
import types
import unittest
from pathlib import Path

import calc_engine
import unit_conversion
from calculation_limits import install_calculator_limits, install_unit_limits
from input_normalization import (
    install_calculator_normalization,
    install_unit_normalization,
)

install_calculator_normalization(calc_engine)
install_unit_normalization(unit_conversion)
install_calculator_limits(calc_engine)
install_unit_limits(unit_conversion)

from calc_engine_runtime import CalculatorSession, make_history_entry

import app_renderer
import app_units_backend


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
                raise AssertionError("app_units_backend must replace the prototype commit")

        storage = Storage()
        api = AppApi(storage)
        renderer = Path(__file__).resolve().parents[1] / "renderer"
        app = types.SimpleNamespace(
            AppApi=AppApi,
            _api=api,
            MAX_HISTORY=500,
            make_history_entry=make_history_entry,
            RENDERER_DIR=renderer,
            build_html=lambda: "legacy",
            webview=types.SimpleNamespace(
                create_window=lambda *args, **kwargs: object(),
            ),
        )
        return app, api, storage

    def test_simple_arithmetic_rejects_functions_and_units(self):
        self.assertEqual(unit_conversion.evaluate_simple("(100 + 25) / 2"), 62.5)
        self.assertEqual(unit_conversion.evaluate_simple("2,5 × 4"), 10.0)
        with self.assertRaises(ValueError):
            unit_conversion.evaluate_simple("sin(30)")
        with self.assertRaises(ValueError):
            unit_conversion.evaluate_simple("10 kN")

    def test_forgiving_decimal_input_matches_calculator(self):
        cases = {
            "3100*.,1": 310.0,
            "3100*,1": 310.0,
            "3100⋅,1": 310.0,
            "3100⋅.1": 310.0,
            ",1": 0.1,
            "2*-0,5": -1.0,
        }
        for expression, expected in cases.items():
            with self.subTest(expression=expression):
                self.assertEqual(unit_conversion.evaluate_simple(expression), expected)

    def test_simple_arithmetic_resource_limits(self):
        with self.assertRaisesRegex(ValueError, "длин"):
            unit_conversion.evaluate_simple("1+" * 140 + "1")
        with self.assertRaisesRegex(ValueError, "глубин"):
            unit_conversion.evaluate_simple("-" * 80 + "1")
        with self.assertRaisesRegex(ValueError, "показатель"):
            unit_conversion.evaluate_simple("2^101")

    def test_conversion_catalog_and_temperature(self):
        app, api, _storage = self.make_app()
        app_units_backend.install(app)

        response = api.convert_units("(100 + 25) / 2", "length", "cm", "m")
        self.assertTrue(response["ok"], response.get("error"))
        self.assertEqual(response["source_value"], "62.5")
        self.assertEqual(response["result"], "0.625")

        temperature = api.convert_units("0", "temperature", "degC", "K")
        self.assertTrue(temperature["ok"], temperature.get("error"))
        self.assertEqual(temperature["result"], "273.15")

        invalid = api.convert_units("sin(30)", "length", "m", "mm")
        self.assertFalse(invalid["ok"])

    def test_engineering_force_and_derived_units(self):
        app, api, _storage = self.make_app()
        app_units_backend.install(app)

        tonne_force = api.convert_units("1", "force", "tf", "kN")
        self.assertTrue(tonne_force["ok"], tonne_force.get("error"))
        self.assertAlmostEqual(float(tonne_force["result"]), 9.80665, places=6)

        distributed = api.convert_units("4", "distributed_force", "tf/m", "kgf/m")
        self.assertTrue(distributed["ok"], distributed.get("error"))
        self.assertEqual(distributed["result"], "4000")

        pressure = api.convert_units("1", "pressure", "tf/m2", "kPa")
        self.assertTrue(pressure["ok"], pressure.get("error"))
        self.assertAlmostEqual(float(pressure["result"]), 9.80665, places=6)

        acceleration = api.convert_units("1", "acceleration", "g0", "m/s2")
        self.assertTrue(acceleration["ok"], acceleration.get("error"))
        self.assertAlmostEqual(float(acceleration["result"]), 9.80665, places=6)

        categories = {item["id"] for item in unit_conversion.unit_payload()}
        self.assertTrue({"distributed_force", "moment", "speed", "acceleration", "specific_weight"} <= categories)

        payload = api.units_bootstrap()["categories"]
        force = next(item for item in payload if item["id"] == "force")
        self.assertIn(
            {"symbol": "tf", "label": "Тонна-сила — тс"},
            force["units"],
        )

    def test_calculator_handoff_revision_and_converter_state(self):
        app, api, storage = self.make_app()
        app_units_backend.install(app)

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

        dimensional = api.commit("2 m")
        self.assertTrue(dimensional["ok"], dimensional.get("error"))
        self.assertEqual(dimensional["calculator_handoff"]["revision"], 1)
        self.assertEqual(dimensional["calculator_handoff"]["value"], "312.5")

    def test_units_are_removed_from_calculator_suggestions(self):
        app, api, _storage = self.make_app()
        app_units_backend.install(app)
        items = api.suggestions("")
        self.assertTrue(items)
        self.assertFalse(any(item.get("kind") == "unit" for item in items))
        self.assertFalse(any(item.get("group") == "Единицы" for item in items))
        self.assertFalse(any(item.get("kind") == "unit" for item in api.bootstrap()["suggestions"]))

    def test_renderer_contains_two_modes_and_unit_pickers(self):
        app, _api, _storage = self.make_app()
        app_units_backend.install(app)
        app_renderer.install(app)
        html = app.build_html()
        self.assertIn('id="calculatorModeTab"', html)
        self.assertIn('id="unitsModeTab"', html)
        self.assertIn('id="unitsPanel"', html)
        self.assertIn('id="sourceUnitSelect"', html)
        self.assertIn('id="targetUnitSelect"', html)
        self.assertIn('id="sourceUnitBadge"', html)
        self.assertIn('id="targetUnitBadge"', html)
        self.assertIn("switchMode('units')", html)
        self.assertNotIn("Функции и единицы (Ctrl+K)", html)

    def test_backend_does_not_mutate_renderer_builder(self):
        app, _api, _storage = self.make_app()
        original = app.build_html
        app_units_backend.install(app)
        self.assertIs(app.build_html, original)


if __name__ == "__main__":
    unittest.main()
