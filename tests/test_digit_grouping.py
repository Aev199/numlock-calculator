import unittest
from pathlib import Path

import calc_engine
import unit_conversion
from calc_engine_runtime import CalculatorSession
from input_normalization import (
    install_calculator_normalization,
    install_unit_normalization,
    repair_numeric_input,
)
import app_renderer


ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "renderer"

install_calculator_normalization(calc_engine)
install_unit_normalization(unit_conversion)


class DigitGroupingTests(unittest.TestCase):
    def test_grouped_digits_are_parser_safe(self):
        self.assertEqual(repair_numeric_input("1 000 000 + 2 000"), "1000000 + 2000")
        self.assertEqual(repair_numeric_input("1\u00a0000\u202f000"), "1000000")

        result = CalculatorSession().evaluate("1 000 000 + 2 000")
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.result, "1002000")

        self.assertEqual(unit_conversion.evaluate_simple("1 000 000 + 2 000"), 1002000.0)

    def test_renderer_groups_decimal_literals_without_changing_backend_format(self):
        html = app_renderer.render_document(RENDERER)
        self.assertIn("DIGIT_GROUP_SEPARATOR = ' '", html)
        self.assertIn("groupIntegerDigits", html)
        self.assertIn("applyVisualDigitGroupingToEditor", html)
        self.assertIn("renderResultWithDigitGrouping", html)
        self.assertIn("setInputValueWithDigitGrouping", html)
        self.assertIn("updateHistoryNodeWithDigitGrouping", html)

    def test_grouped_standalone_number_keeps_concise_copy_path(self):
        copy_source = (RENDERER / "app-shell-v2.copy.js").read_text(encoding="utf-8")
        self.assertIn("CLIPBOARD_DIGIT_GROUPING", copy_source)
        self.assertIn("replace(CLIPBOARD_DIGIT_GROUPING, '')", copy_source)

    def test_clipboard_grouping_has_persisted_user_toggle(self):
        html = app_renderer.render_document(RENDERER)
        self.assertIn("copyTextWithDigitGroupingPreference", html)
        self.assertIn("clipboardDigitText", html)
        self.assertIn("state.ui.group_copied_digits === false", html)
        self.assertIn("Группировать разряды при копировании", html)
        self.assertIn("group_copied_digits: enabled", html)
        self.assertIn("await copyText(text, 'Вычисление скопировано')", html)
        self.assertIn("await copyText(text, 'Результат скопирован')", html)

    def test_editor_and_result_share_windows_ui_typeface(self):
        utility = (RENDERER / "app-shell-utility.css").read_text(encoding="utf-8")
        self.assertIn(".expression-input,\n.bracket-color-overlay", utility)
        self.assertIn("font-family: inherit;", utility)
        self.assertIn("font-weight: 500;", utility)


if __name__ == "__main__":
    unittest.main()
