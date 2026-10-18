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

    def test_single_bar_returns_square_centimetres(self):
        result = self.engine.evaluate("d16")
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.unit, "cm2")
        self.assertEqual(result.result, "2.010619 см²")
        self.assertAlmostEqual(result.raw_value, 2.0106192982974678)

    def test_multiple_bars_return_total_square_centimetres(self):
        result = self.engine.evaluate("2d20")
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.unit, "cm2")
        self.assertEqual(result.result, "6.283185 см²")

    def test_bar_terms_without_spacing_can_be_summed(self):
        result = self.engine.evaluate("2d20+d16")
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.unit, "cm2")
        self.assertEqual(result.result, "8.293805 см²")

    def test_single_spacing_term_returns_square_centimetres_per_metre(self):
        result = self.engine.evaluate("d16s150")
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.unit, "cm2/m")
        self.assertEqual(result.result, "13.404129 см²/м")

    def test_multiple_spacing_terms_are_summed_per_metre(self):
        result = self.engine.evaluate("4d20s200+d16s150")
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.unit, "cm2/m")
        self.assertEqual(result.result, "76.235982 см²/м")
        self.assertAlmostEqual(result.raw_value, 76.23598172711232)

    def test_spaces_and_decimal_values_are_supported(self):
        bars = self.engine.evaluate("2 d12,5 + d10")
        self.assertTrue(bars.ok, bars.error)
        self.assertEqual(bars.unit, "cm2")

        distributed = self.engine.evaluate("2 d12,5 s 175 + d10 s200")
        self.assertTrue(distributed.ok, distributed.error)
        self.assertEqual(distributed.unit, "cm2/m")

    def test_mixed_bar_and_spacing_forms_are_not_rewritten(self):
        expression = "2d20+d16s150"
        self.assertEqual(rewrite_reinforcement_area(expression), expression)
        result = self.engine.evaluate(expression)
        self.assertFalse(result.ok)

    def test_non_reinforcement_expression_is_not_rewritten(self):
        self.assertEqual(rewrite_reinforcement_area("2 + 3"), "2 + 3")
        self.assertEqual(rewrite_reinforcement_area("width + d20s200"), "width + d20s200")

    def test_long_expression_editor_never_soft_wraps(self):
        css = (ROOT / "renderer" / "app-shell-utility.css").read_text(encoding="utf-8")
        html = (ROOT / "renderer" / "app-shell.html").read_text(encoding="utf-8")
        self.assertIn('id="expressionInput"', html)
        self.assertIn('wrap="off"', html)
        self.assertIn(".expression-input {", css)
        self.assertIn("white-space: pre", css)
        self.assertIn("overflow-x: auto", css)
        self.assertIn("overflow-wrap: normal", css)
        self.assertIn("word-break: normal", css)


if __name__ == "__main__":
    unittest.main()
