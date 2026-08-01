import sys
import tempfile
import types
import unittest
from pathlib import Path

fake_webview = types.SimpleNamespace(
    Window=object,
    create_window=lambda *args, **kwargs: object(),
    start=lambda *args, **kwargs: None,
)
sys.modules.setdefault("webview", fake_webview)

import calc_engine
from calculation_limits import install_calculator_limits
from input_normalization import install_calculator_normalization

install_calculator_normalization(calc_engine)
install_calculator_limits(calc_engine)

from calc_engine_runtime import CalculatorSession

calc_engine.CalculatorSession = CalculatorSession

import app
import app_formulas
import app_numlock_compat
import app_units_backend
import app_variables
import app_window

app_window.install(app)
app_numlock_compat.install(app)
app_units_backend.install(app)
app_variables.install(app)
app_formulas.install(app)


class SavedFormulaApiTests(unittest.TestCase):
    def make_api(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        return app.AppApi(app.Storage(Path(directory.name) / "state.json"))

    def test_formula_supports_engineering_parameter_names_and_dimensions(self):
        api = self.make_api()
        saved = api.save_formula(
            {
                "name": "Давление",
                "expression": "M / W",
                "parameters": [
                    {"name": "M", "default": "10 kN*m"},
                    {"name": "W", "default": "2 m3"},
                ],
            }
        )
        self.assertTrue(saved["ok"], saved.get("error"))
        formula = saved["formula"]

        preview = api.evaluate_formula(
            formula["id"],
            {"M": "20 kN*m", "W": "4 m3"},
            False,
        )
        self.assertTrue(preview["ok"], preview.get("error"))
        self.assertEqual(preview["result"], "5000 Pa")
        self.assertEqual(preview["dimension"], "L^-1 · M · T^-2")
        self.assertEqual(api.bootstrap()["history"], [])
        self.assertNotIn("m", api.bootstrap()["variables"])

    def test_formula_commit_enters_common_history_and_survives_restart(self):
        api = self.make_api()
        formula = api.save_formula(
            {
                "name": "Площадь",
                "expression": "b * h",
                "parameters": [
                    {"name": "b", "default": "2 m"},
                    {"name": "h", "default": "3 m"},
                ],
            }
        )["formula"]
        response = api.run_formula(formula["id"], {}, True)
        self.assertTrue(response["ok"], response.get("error"))
        self.assertEqual(response["result"], "6 m2")
        self.assertEqual(response["history_entry"]["formula_name"], "Площадь")

        restored = app.AppApi(api._storage).bootstrap()
        self.assertEqual(restored["formulas"][0]["name"], "Площадь")
        self.assertEqual(restored["history"][0]["formula_id"], formula["id"])

    def test_profile_supplies_constants_and_format_settings(self):
        api = self.make_api()
        formula = api.save_formula(
            {
                "name": "Вес объёма",
                "expression": "gamma * V",
                "parameters": [{"name": "V", "default": "2 m3"}],
            }
        )["formula"]
        profile = api.save_profile(
            {
                "name": "Железобетон",
                "formula_ids": [formula["id"]],
                "constants": {"gamma": "25 kN/m3"},
                "preferred_units": ["kN", "MPa", "m3"],
                "settings": {"precision": 5, "number_format": "engineering"},
            }
        )
        self.assertTrue(profile["ok"], profile.get("error"))
        activated = api.set_active_profile(profile["profile"]["id"])
        self.assertTrue(activated["ok"], activated.get("error"))
        self.assertEqual(activated["settings"]["precision"], 5)

        result = api.evaluate_formula(formula["id"], {}, False)
        self.assertTrue(result["ok"], result.get("error"))
        self.assertEqual(result["result"], "50e+3 N")
        self.assertEqual(api.bootstrap()["profile_constants"]["gamma"], "25 kN/m3")

    def test_active_profile_scopes_formulas_and_restores_preferred_units(self):
        api = self.make_api()
        allowed = api.save_formula(
            {
                "name": "Разрешённая",
                "expression": "x",
                "parameters": [{"name": "x", "default": "1"}],
            }
        )["formula"]
        hidden = api.save_formula(
            {
                "name": "Скрытая",
                "expression": "y",
                "parameters": [{"name": "y", "default": "2"}],
            }
        )["formula"]
        api.save_unit_converter_state(
            {
                "category": "force",
                "from_unit": "N",
                "to_unit": "kgf",
            }
        )
        profile = api.save_profile(
            {
                "name": "Сценарий",
                "formula_ids": [allowed["id"]],
                "preferred_units": ["kN", "N"],
            }
        )["profile"]

        activated = api.set_active_profile(profile["id"])
        self.assertEqual(
            activated["unit_converter_state"]["from_unit"],
            "kN",
        )
        self.assertEqual(
            activated["unit_converter_state"]["to_unit"],
            "N",
        )
        self.assertTrue(api.evaluate_formula(allowed["id"])["ok"])
        rejected = api.evaluate_formula(hidden["id"])
        self.assertFalse(rejected["ok"])
        self.assertIn("активный профиль", rejected["error"])
        self.assertFalse(
            any(
                item.get("formula_id") == hidden["id"]
                for item in api.suggestions("")
            )
        )

        disabled = api.set_active_profile(None)
        self.assertEqual(
            disabled["unit_converter_state"]["from_unit"],
            "N",
        )
        self.assertEqual(
            disabled["unit_converter_state"]["to_unit"],
            "kgf",
        )

    def test_profile_settings_are_restored_when_disabled_and_default_parameter_unit_is_used(self):
        api = self.make_api()
        profile = api.save_profile({"name": "Профиль", "settings": {"precision": 5}})["profile"]
        self.assertEqual(api.set_active_profile(profile["id"])["settings"]["precision"], 5)
        self.assertEqual(api.set_active_profile(None)["settings"]["precision"], 12)
        formula = api.save_formula(
            {
                "name": "Длина",
                "expression": "x",
                "parameters": [{"name": "x", "default": "10", "unit": "m"}],
            }
        )["formula"]
        self.assertEqual(api.evaluate_formula(formula["id"], {})["result"], "10 m")

    def test_deleting_formula_removes_profile_reference(self):
        api = self.make_api()
        formula = api.save_formula({"name": "x", "expression": "x", "parameters": [{"name": "x", "default": "1"}]})["formula"]
        profile = api.save_profile({"name": "p", "formula_ids": [formula["id"]]})["profile"]
        deleted = api.delete_formula(formula["id"])
        self.assertTrue(deleted["ok"])
        self.assertEqual(deleted["profiles"][0]["formula_ids"], [])
        self.assertEqual(profile["formula_ids"], [formula["id"]])


if __name__ == "__main__":
    unittest.main()
