import math
import unittest
from pathlib import Path

import app_renderer
import flexible_units


ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "renderer"


class FlexibleUnitTests(unittest.TestCase):
    def test_density_is_exposed_as_composable_mass_per_volume(self):
        payload = flexible_units.unit_payload()
        density = next(item for item in payload if item["id"] == "density")
        self.assertEqual(density["picker"]["kind"], "compound")
        self.assertEqual(density["picker"]["operator"], "/")
        self.assertEqual(density["picker"]["left_label"], "Масса")
        self.assertEqual(density["picker"]["right_label"], "Объём")
        self.assertEqual(density["picker"]["default_left"], "kg")
        self.assertEqual(density["picker"]["default_right"], "m3")
        symbols = [item["symbol"] for item in density["units"]]
        self.assertEqual(symbols[:2], ["kg/m3", "g/cm3"])
        self.assertIn("t/m3", symbols)
        self.assertIn("kg/dm3", symbols)

    def test_density_follows_specific_weight_in_category_order(self):
        ids = [item["id"] for item in flexible_units.unit_payload()]
        index = ids.index("specific_weight")
        self.assertEqual(ids[index + 1], "density")
        self.assertLess(ids.index("density"), ids.index("time"))

    def test_gram_per_cubic_centimeter_converts_to_kg_per_cubic_meter(self):
        value = flexible_units.convert_value(
            1.0,
            "density",
            "g/cm3",
            "kg/m3",
        )
        self.assertTrue(math.isclose(value, 1000.0, rel_tol=1e-12))

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
        self.assertIn("km/h", flexible_units.category_symbols("speed"))
        self.assertIn("g0", flexible_units.category_symbols("acceleration"))

    def test_saved_dynamic_selection_survives_sanitization(self):
        state = flexible_units.sanitize_state(
            {
                "category": "density",
                "from_unit": "g/cm3",
                "to_unit": "kg/m3",
                "expression": "2.4",
            }
        )
        self.assertEqual(state["category"], "density")
        self.assertEqual(state["from_unit"], "g/cm3")
        self.assertEqual(state["to_unit"], "kg/m3")
        self.assertEqual(state["expression"], "2.4")

    def test_renderer_contains_component_pickers_without_removing_flat_selects(self):
        html = app_renderer.render_document(RENDERER)
        self.assertIn('id="sourceUnitSelect"', html)
        self.assertIn('id="targetUnitSelect"', html)
        self.assertIn("renderFlexibleUnitPickers", html)
        self.assertIn("compound-unit-picker", html)
        self.assertIn("Готовые единицы", html)
        self.assertIn("composePickerSymbol", html)
        self.assertIn("picker.default_right", html)
        self.assertIn("compound-unit-hidden", html)


if __name__ == "__main__":
    unittest.main()
