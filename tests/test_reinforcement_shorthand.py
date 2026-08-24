import unittest
from pathlib import Path

import calc_engine
from calculation_limits import install_calculator_limits
from input_normalization import (
    install_calculator_normalization,
    rewrite_reinforcement_area,
)

install_calculator_normalization(calc_engine)
install_calculator_limits(calc_engine)

from calc_engine_runtime import CalculatorSession


ROOT = Path(__file__).resolve().parents[1]


class ReinforcementShorthandTests(unittest.TestCase):
    def setUp(self):
        self.engine = CalculatorSession()

    def test_single_reinforcement_term_returns_square_centimetres(self):
        result = self.engine.evaluate("d20s200")
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.unit, "cm2")
        self.assertEqual(result.result, "15.707963 cm2")

    def test_multiple_layers_and_diameters_are_summed(self):
        result = self.engine.evaluate("4d20s200+d16s150")
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.unit, "cm2")
        self.assertEqual(result.result, "76.235982 cm2")
        self.assertAlmostEqual(result.raw_value, 76.23598172711232)

    def test_spaces_and_decimal_values_are_supported(self):
        result = self.engine.evaluate("2 d12,5 s 175 + d10 s200")
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.unit, "cm2")

    def test_non_reinforcement_expression_is_not_rewritten(self):
        self.assertEqual(rewrite_reinforcement_area("2 + 3"), "2 + 3")
        self.assertEqual(rewrite_reinforcement_area("width + d20s200"), "width + d20s200")

    def test_long_expression_editor_never_soft_wraps(self):
        css = (ROOT / "renderer" / "app-shell-utility.css").read_text(encoding="utf-8")
        self.assertIn(".expression-input {", css)
        self.assertIn("white-space: pre", css)
        self.assertIn("overflow-x: auto", css)
        self.assertIn("overflow-wrap: normal", css)
        self.assertIn("word-break: normal", css)


if __name__ == "__main__":
    unittest.main()
