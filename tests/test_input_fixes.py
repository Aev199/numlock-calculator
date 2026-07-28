import unittest
from pathlib import Path

import app_renderer


ROOT = Path(__file__).resolve().parents[1]


class InputFixesTests(unittest.TestCase):
    def test_input_fixes_follow_the_typing_runtime(self):
        self.assertEqual(len(app_renderer.SCRIPT_PARTS), 14)
        self.assertLess(
            app_renderer.SCRIPT_PARTS.index("app-shell-v2.typing.js"),
            app_renderer.SCRIPT_PARTS.index("app-shell-v2.part08.js"),
        )

    def test_animation_uses_timer_watchdog_instead_of_microtask_cancellation(self):
        source = (ROOT / "renderer" / "app-shell-v2.part08.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("beginCaretGlyphMotion = function (event)", source)
        self.assertIn("window.setTimeout", source)
        self.assertIn("CARET_INPUT_WATCHDOG_MS", source)
        self.assertNotIn("queueMicrotask", source)

    def test_implicit_multiplication_is_rendered_explicitly(self):
        source = (ROOT / "renderer" / "app-shell-v2.part08.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("displayExpression = function (value)", source)
        self.assertIn(r"/([0-9)])\s*(?=\()/g", source)
        self.assertIn("150(5) -> 150⋅(5)", source)


if __name__ == "__main__":
    unittest.main()
