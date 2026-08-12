import math
import unittest
from pathlib import Path

import app_renderer
import flexible_units


ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "renderer"


class FlexibleUnitTests(unittest.TestCase):
    def test_specific_weight_contains_force_and_mass_representations(self):
        payload = flexible_units.unit_payload()
        self.assertNotIn("density", {item["id"] for item in payload})
        specific_weight = next(
            item for item in payload
            if item["id"] == "specific_weight"
        )
        self.assertEqual(specific_weight["picker"]["kind"], "compound")
        self.assertEqual(specific_weight["picker"]["operator"], "/")
        self.assertEqual(specific_weight["picker"]["left_label"], "Сила / масса")
        self.assertEqual(specific_weight["picker"]["right_label"], "Объём")
        self.assertEqual(specific_weight["picker"]["default_left"], "kN")
        self.assertEqual(specific_weight["picker"]["default_right"], "m3")
        self.assertAlmostEqual(
            specific_weight["picker"]["gravity_bridge"],
            9.80665,
            places=8,
        )

        symbols = [item["symbol"] for item in specific_weight["units"]]
        self.assertEqual(symbols[:2], ["kN/m3", "t/m3"])
        self.assertIn("N/m3", symbols)
        self.assertIn("tf/m3", symbols)
        self.assertIn("kg/m3", symbols)
        self.assertIn("g/cm3", symbols)
        self.assertIn("kg/dm3", symbols)

        groups = {
            item.get("group")
            for item in specific_weight["picker"]["left"]
        }
        self.assertIn("Сила", groups)
        self.assertIn("Масса (через g₀)", groups)

    def test_mass_density_notation_converts_to_specific_weight(self):
        value = flexible_units.convert_value(
            1.0,
            "specific_weight",
            "g/cm3",
            "kN/m3",
        )
        self.assertTrue(math.isclose(value, 9.80665, rel_tol=1e-12))

        reverse = flexible_units.convert_value(
            value,
            "specific_weight",
            "kN/m3",
            "g/cm3",
        )
        self.assertTrue(math.isclose(reverse, 1.0, rel_tol=1e-12))

        tonne_per_cubic_meter = flexible_units.convert_value(
            1.0,
            "specific_weight",
            "t/m3",
            "kN/m3",
        )
        self.assertTrue(
            math.isclose(tonne_per_cubic_meter, 9.80665, rel_tol=1e-12)
        )

    def test_dynamic_pressure_combination_converts_to_preset(self):
        value = flexible_units.convert_value(
            1.0,
            "pressure",
            "kN/cm2",
            "MPa",
        )
        self.assertTrue(math.isclose(value, 10.0, rel_tol=1e-12))
        pressure = next(
            item for item in flexible_units.unit_payload()
            if item["id"] == "pressure"
        )
        self.assertEqual(
            [item["symbol"] for item in pressure["units"][:2]],
            ["kPa", "MPa"],
        )
        self.assertEqual(pressure["picker"]["default_left"], "kN")
        self.assertEqual(pressure["picker"]["default_right"], "m2")
        presets = {item["symbol"] for item in pressure["picker"]["presets"]}
        self.assertTrue({"Pa", "kPa", "MPa", "bar", "atm", "psi"} <= presets)

    def test_existing_engineering_symbols_remain_valid(self):
        self.assertIn("tf/m", flexible_units.category_symbols("distributed_force"))
        self.assertIn("tf/m2", flexible_units.category_symbols("pressure"))
        self.assertIn("kN/m3", flexible_units.category_symbols("specific_weight"))
        self.assertIn("g/cm3", flexible_units.category_symbols("specific_weight"))
        self.assertIn("km/h", flexible_units.category_symbols("speed"))
        self.assertIn("g0", flexible_units.category_symbols("acceleration"))

    def test_saved_density_selection_migrates_to_specific_weight(self):
        state = flexible_units.sanitize_state(
            {
                "category": "density",
                "from_unit": "g/cm3",
                "to_unit": "kg/m3",
                "expression": "2.4",
            }
        )
        self.assertEqual(state["category"], "specific_weight")
        self.assertEqual(state["from_unit"], "g/cm3")
        self.assertEqual(state["to_unit"], "kg/m3")
        self.assertEqual(state["expression"], "2.4")

    def test_legacy_density_helper_calls_use_specific_weight_bridge(self):
        value = flexible_units.convert_value(
            1.0,
            "density",
            "g/cm3",
            "kN/m3",
        )
        self.assertTrue(math.isclose(value, 9.80665, rel_tol=1e-12))

    def test_renderer_contains_component_pickers_without_removing_flat_selects(self):
        html = app_renderer.render_document(RENDERER)
        self.assertIn('id="sourceUnitSelect"', html)
        self.assertIn('id="targetUnitSelect"', html)
        self.assertIn("renderFlexibleUnitPickers", html)
        self.assertIn("compound-unit-picker", html)
        self.assertIn("Готовые единицы", html)
        self.assertIn("appendGroupedComponentOptions", html)
        self.assertIn("Масса (через g₀)", html)
        self.assertIn("composePickerSymbol", html)
        self.assertIn("picker.default_right", html)
        self.assertIn("compound-unit-hidden", html)


if __name__ == "__main__":
    unittest.main()