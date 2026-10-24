import sys
import tempfile
import types
import unittest
from pathlib import Path

sys.modules.setdefault("webview", types.SimpleNamespace(
    Window=object,
    create_window=lambda *args, **kwargs: object(),
    start=lambda *args, **kwargs: None,
))

import app
from history_rules import history_worthy


class HistoryRuleTests(unittest.TestCase):
    def test_bare_numbers_and_repeats_are_not_recorded(self):
        self.assertFalse(history_worthy("1 500", []))
        self.assertFalse(history_worthy("-2,5", []))
        self.assertFalse(history_worthy("  ", []))
        self.assertTrue(history_worthy("1250*1.2", []))
        latest = [{"expression": "1250⋅1.2"}]
        self.assertFalse(history_worthy("1250 * 1.2", latest))
        self.assertTrue(history_worthy("1250*1.3", latest))


class HistoryApiTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "data.json"
        self.api = app.AppApi(app.Storage(self.path))

    def expressions(self):
        return [item["expression"] for item in self.api.bootstrap()["history"]]

    def test_enter_on_a_result_adds_nothing(self):
        self.assertIn("history_entry", self.api.commit("1250*1.2"))
        response = self.api.commit("1500")
        self.assertTrue(response["ok"])
        self.assertNotIn("history_entry", response)
        self.api.commit("1250*1.2")
        self.assertEqual(self.expressions(), ["1250*1.2"])

    def test_a_copied_calculation_is_remembered_without_side_effects(self):
        self.api.commit("2+2")
        self.assertIn("history_entry", self.api.remember_calculation("17*3"))
        self.assertEqual(self.expressions(), ["17*3", "2+2"])
        # ans still holds the last Enter, not the remembered value.
        self.assertEqual(self.api.preview("ans")["result"], "4")
        self.assertNotIn("history_entry", self.api.remember_calculation("17*3"))
        self.assertNotIn("history_entry", self.api.remember_calculation("17*"))

    def test_assignments_are_never_remembered_implicitly(self):
        self.assertNotIn("history_entry", self.api.remember_calculation("span := 6"))
        self.assertNotIn("history_entry", self.api.remember_calculation("c(d) := pi*d^2/4"))
        self.assertEqual(self.expressions(), [])
        self.assertNotIn("span", self.api.bootstrap()["variables"])

    def test_deleted_entries_come_back_in_order(self):
        for expression in ("1+1", "2+2", "3+3"):
            self.api.commit(expression)
        history = self.api.bootstrap()["history"]
        middle = history[1]
        self.api.delete_history(middle["id"])
        self.assertEqual(self.expressions(), ["3+3", "1+1"])
        self.api.restore_history([middle])
        self.assertEqual(self.expressions(), ["3+3", "2+2", "1+1"])
        self.api.restore_history([middle])
        self.assertEqual(len(self.expressions()), 3)

        self.api.clear_history()
        self.api.restore_history(history)
        self.assertEqual(self.expressions(), ["3+3", "2+2", "1+1"])
        reopened = app.AppApi(app.Storage(self.path))
        self.assertEqual([item["expression"] for item in reopened.bootstrap()["history"]], ["3+3", "2+2", "1+1"])



class HistoryRendererTests(unittest.TestCase):
    def test_renderer_records_inserts_and_undoes(self):
        import app_renderer

        html = app_renderer.render_document(Path(__file__).resolve().parents[1] / "renderer")
        for marker in (
            "remember_calculation",
            "restore_history",
            "insertHistoryResult",
            "historyDayLabel",
            "'Вернуть'",
            "window.addEventListener('blur'",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, html)
        self.assertNotIn("Нажмите ещё раз, чтобы очистить историю", html)


if __name__ == "__main__":
    unittest.main()
