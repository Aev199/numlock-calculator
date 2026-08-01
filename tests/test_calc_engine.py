import unittest

import calc_engine
from calculation_limits import install_calculator_limits
from input_normalization import install_calculator_normalization

install_calculator_normalization(calc_engine)
install_calculator_limits(calc_engine)

from calc_engine import prepare_for_ast
from calc_engine_runtime import CalculatorSession


class CalculatorEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = CalculatorSession()

    def assertResult(self, expression, expected):
        result = self.engine.evaluate(expression, commit=True)
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.result, expected)
        return result

    def test_arithmetic_and_precedence(self):
        self.assertResult('2 + 3 * 4', '14')
        self.assertResult('(2 + 3) * 4', '20')
        self.assertResult('2^3^2', '512')

    def test_functions_and_angles(self):
        self.assertResult('sin(30)', '0.5')
        self.assertResult('sin(30 deg)', '0.5')
        self.engine.set_settings({'angle_mode': 'RAD'})
        result = self.engine.evaluate('sin(pi / 2)')
        self.assertTrue(result.ok, result.error)
        self.assertAlmostEqual(result.raw_value, 1.0)

    def test_factorial_and_percent(self):
        self.assertResult('9!', '362880')
        self.assertResult('200 + 10%', '220')
        self.assertResult('50%', '0.5')
        self.assertResult('2^3%', '0.08')

    def test_units_and_conversion(self):
        self.assertResult('250 kPa to MPa', '0.25 MPa')
        self.assertResult('2 m + 30 cm to m', '2.3 m')
        self.assertResult('10 kN / 2 m2 to kPa', '5 kPa')
        self.assertResult('2 m / 2 s', '1 m/s')
        self.assertResult('20 degC to K', '293.15 K')

    def test_derived_units_share_the_dimensional_engine(self):
        self.assertResult('2 m * 3 m', '6 m2')
        self.assertResult('2 kPa + 300 Pa', '2.3 kPa')
        self.assertResult('1 tf/m2 to kPa', '9.80665 kPa')
        self.assertResult('4 tf/m to kgf/m', '4000 kgf/m')

    def test_result_exposes_common_quantity_shape(self):
        result = self.engine.evaluate('2 m * 3 m')
        self.assertTrue(result.ok, result.error)
        payload = result.as_dict()
        self.assertEqual(payload['quantity']['value'], 6.0)
        self.assertEqual(payload['quantity']['unit'], 'm2')
        self.assertEqual(payload['quantity']['dimension'], 'L^2')
        self.assertEqual(payload['dimensions'], ['2/1', '0/1', '0/1', '0/1'])

    def test_variables_and_ans(self):
        preview = self.engine.evaluate('span := 6 m', commit=False)
        self.assertTrue(preview.ok, preview.error)
        self.assertNotIn('span', self.engine.variables)
        result = self.engine.evaluate('span := 6 m', commit=True)
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.assigned_variable, 'span')
        self.assertResult('span / 2 to m', '3 m')
        self.assertResult('ans + 1 m to m', '4 m')

    def test_number_bases(self):
        self.engine.set_settings({'number_base': 'HEX'})
        self.assertResult('255', '0xFF')
        self.assertFalse(self.engine.evaluate('1 / 2').ok)

    def test_engineering_format_and_decimal_separator(self):
        settings = self.engine.set_settings(
            {
                'number_format': 'engineering',
                'precision': 4,
                'decimal_separator': ',',
            }
        )
        self.assertEqual(settings.number_format, 'engineering')
        self.assertEqual(settings.decimal_separator, ',')
        self.assertEqual(self.engine.evaluate('1234').result, '1,234e+3')
        self.assertEqual(self.engine.evaluate('0,0012').result, '1,2e-3')

    def test_history_contains_source_and_normalized_expression(self):
        result = self.engine.evaluate('3100*.,1', commit=True)
        entry = calc_engine.make_history_entry(result, self.engine.settings, 1).as_dict()
        self.assertEqual(entry['expression'], '3100*.,1')
        self.assertEqual(entry['source_expression'], '3100*.,1')
        self.assertEqual(entry['normalized_expression'], '3100*0.1')
        self.assertEqual(entry['result'], '310')
        self.assertIn('created_at', entry)

    def test_memory(self):
        result = self.engine.set_memory(3, '12 + 4')
        self.assertTrue(result.ok, result.error)
        self.assertEqual(self.engine.memory_expression(3), '16')

    def test_errors(self):
        result = self.engine.evaluate('2 +')
        self.assertFalse(result.ok)
        self.assertTrue(result.incomplete)
        result = self.engine.evaluate('1 / 0')
        self.assertFalse(result.ok)
        self.assertIn('ноль', result.error)
        result = self.engine.evaluate('2 m + 3 s')
        self.assertFalse(result.ok)
        self.assertIn('размерност', result.error)

    def test_prepare_expression(self):
        self.assertEqual(prepare_for_ast('250 kPa'), '250*kPa')
        self.assertEqual(prepare_for_ast('2 × (3 + 4)').replace(' ', ''), '2*(3+4)')
        self.assertEqual(prepare_for_ast('5!'), 'factorial(5)')
        self.assertEqual(prepare_for_ast('150(5)'), '150*(5)')
        self.assertEqual(prepare_for_ast('(2)(3)'), '(2)*(3)')

    def test_forgiving_decimal_and_visual_multiply_input(self):
        cases = {
            '3100*.,1': '310',
            '3100*,1': '310',
            '3100⋅,1': '310',
            '3100⋅.1': '310',
            '.1': '0.1',
            ',1': '0.1',
            '2*-0,5': '-1',
            '1e-3': '0.001',
            '150(5)': '750',
            '(2)(3)': '6',
        }
        for expression, expected in cases.items():
            with self.subTest(expression=expression):
                self.assertResult(expression, expected)
        self.assertEqual(prepare_for_ast('3100*.,1'), '3100*0.1')
        self.assertEqual(prepare_for_ast('3100⋅,1'), '3100*0.1')

    def test_resource_limits_return_user_facing_errors(self):
        too_long = self.engine.evaluate('1+' * 1100 + '1')
        self.assertFalse(too_long.ok)
        self.assertIn('длин', too_long.error.lower())

        too_deep = self.engine.evaluate('-' * 80 + '1')
        self.assertFalse(too_deep.ok)
        self.assertIn('глубин', too_deep.error.lower())

        exponent = self.engine.evaluate('2^1001')
        self.assertFalse(exponent.ok)
        self.assertIn('показатель', exponent.error.lower())


if __name__ == '__main__':
    unittest.main()
