import math
import threading
import unittest
from types import SimpleNamespace

import calc_engine
from input_normalization import install_calculator_normalization

install_calculator_normalization(calc_engine)

from calc_engine_runtime import CalculatorSession as BaseCalculatorSession
import app_user_functions


class CalculatorSession(BaseCalculatorSession):
    pass


class MemoryStorage:
    def __init__(self, data=None):
        self.data = dict(data or {})

    def get(self, key, default=None):
        return self.data.get(key, default)

    def update(self, values):
        self.data.update(values)


class DummyApi:
    def __init__(self, storage):
        self._storage = storage
        state = storage.get("engine_state", {})
        self._session = CalculatorSession(
            variables=state.get("variables", {}) if isinstance(state, dict) else {},
            memories=state.get("memories", []) if isinstance(state, dict) else [],
        )
        self._lock = threading.RLock()

    def bootstrap(self):
        return {
            "variables": {
                key: self._session.format_quantity(value)
                for key, value in sorted(self._session.variables.items())
            },
            "suggestions": self._session.suggestions(),
        }

    def _persist(self):
        self._storage.update({"engine_state": self._session.export_state()})


fake_app = SimpleNamespace(CalculatorSession=CalculatorSession, AppApi=DummyApi)
app_user_functions.install(fake_app)


class UserFunctionTests(unittest.TestCase):
    def setUp(self):
        self.engine = CalculatorSession()

    def define(self, expression):
        result = self.engine.evaluate(expression, commit=True)
        self.assertTrue(result.ok, result.error)
        return result

    def evaluate(self, expression):
        result = self.engine.evaluate(expression, commit=False)
        self.assertTrue(result.ok, result.error)
        return result

    def test_single_parameter_circle_formula(self):
        preview = self.engine.evaluate("c(d)=pi*d^2/4", commit=False)
        self.assertTrue(preview.ok, preview.error)
        self.assertNotIn("c", self.engine.user_functions)

        self.define("c(d)=pi*d^2/4")
        result = self.evaluate("c(20)")
        self.assertAlmostEqual(result.raw_value, math.pi * 20**2 / 4)
        self.assertEqual(result.result, "314.159265")

    def test_multiple_parameters_and_normal_comma_separator(self):
        self.define("r(a,b)=a*b")
        self.assertEqual(self.evaluate("r(2,3)").result, "6")
        self.assertEqual(self.evaluate("1+r(2,3)").result, "7")

    def test_decimal_comma_disambiguation_uses_function_arity(self):
        self.define("c(d)=pi*d^2/4")
        self.define("r(a,b)=a*b")

        one_argument = self.evaluate("c(2,5)")
        self.assertAlmostEqual(one_argument.raw_value, math.pi * 2.5**2 / 4)

        two_decimal_arguments = self.evaluate("r(2,5;3,5)")
        self.assertEqual(two_decimal_arguments.result, "8.75")

    def test_parameters_can_have_units_and_result_can_be_converted(self):
        self.define("c(d)=pi*d^2/4")
        result = self.evaluate("c(20 mm) to mm2")
        self.assertEqual(result.result, "314.159265 mm2")
        self.assertEqual(result.unit, "mm2")

    def test_function_uses_current_variables_and_restores_parameter_shadowing(self):
        assigned = self.engine.evaluate("coef:=2", commit=True)
        self.assertTrue(assigned.ok, assigned.error)
        original = self.engine.evaluate("x:=100", commit=True)
        self.assertTrue(original.ok, original.error)
        self.define("f(x)=coef*x+1")

        self.assertEqual(self.evaluate("f(3)").result, "7")
        self.assertEqual(self.evaluate("x").result, "100")

    def test_functions_can_call_other_user_functions(self):
        self.define("double(x)=2*x")
        self.define("quad(x)=double(double(x))")
        self.assertEqual(self.evaluate("quad(3)").result, "12")

    def test_arity_and_recursion_errors_are_user_facing(self):
        self.define("r(a,b)=a+b")
        wrong_arity = self.engine.evaluate("r(2)")
        self.assertFalse(wrong_arity.ok)
        self.assertIn("аргументов: 2", wrong_arity.error)

        self.define("loop(x)=loop(x)")
        recursive = self.engine.evaluate("loop(1)")
        self.assertFalse(recursive.ok)
        self.assertIn("Рекурсив", recursive.error)

    def test_reserved_names_and_duplicate_parameters_are_rejected(self):
        reserved = self.engine.evaluate("sin(x)=x", commit=True)
        self.assertFalse(reserved.ok)
        self.assertIn("зарезервировано", reserved.error)

        duplicate = self.engine.evaluate("f(x,x)=x", commit=True)
        self.assertFalse(duplicate.ok)
        self.assertIn("повторяется", duplicate.error)

    def test_export_restore_suggestions_and_delete(self):
        self.define("c(d)=pi*d^2/4")
        state = self.engine.export_state()
        self.assertIn("c", state["user_functions"])

        storage = MemoryStorage({"engine_state": state})
        api = DummyApi(storage)
        self.assertEqual(api._session.evaluate("c(10)").result, "78.539816")

        bootstrap = api.bootstrap()
        self.assertEqual(bootstrap["user_functions"]["c"]["parameters"], ["d"])
        custom = [
            item
            for item in bootstrap["suggestions"]
            if item.get("group") == "Пользовательские функции"
        ]
        self.assertEqual(custom[0]["insert"], "c()")

        deleted = api.delete_user_function("c")
        self.assertTrue(deleted["ok"])
        self.assertNotIn("c", deleted["user_functions"])
        self.assertNotIn("c", storage.data["engine_state"]["user_functions"])


if __name__ == "__main__":
    unittest.main()
