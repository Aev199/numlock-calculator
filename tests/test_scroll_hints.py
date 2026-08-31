import unittest
from pathlib import Path

import app_renderer


ROOT = Path(__file__).resolve().parents[1]


class LongExpressionScrollHintTests(unittest.TestCase):
    def test_scroll_hint_assets_are_wired_after_keyboard_ux(self):
        self.assertIn("app-shell-scroll-hints.css", app_renderer.STYLE_PARTS)
        self.assertIn("app-shell-v2.scroll-hints.js", app_renderer.SCRIPT_PARTS)
        self.assertLess(
            app_renderer.STYLE_PARTS.index("app-shell-ux.css"),
            app_renderer.STYLE_PARTS.index("app-shell-scroll-hints.css"),
        )
        self.assertLess(
            app_renderer.SCRIPT_PARTS.index("app-shell-v2.ux.js"),
            app_renderer.SCRIPT_PARTS.index("app-shell-v2.scroll-hints.js"),
        )

    def test_rendered_editor_exposes_dynamic_left_and_right_cues(self):
        html = app_renderer.render_document(ROOT / "renderer")

        for marker in (
            "function updateExpressionScrollHints()",
            "dom.input.scrollWidth - dom.input.clientWidth",
            "classList.toggle('has-scroll-left', hasLeft)",
            "classList.toggle('has-scroll-right', hasRight)",
            "requestAnimationFrame(updateExpressionScrollHints)",
            ".expression-field-shell.has-scroll-left::before",
            ".expression-field-shell.has-scroll-right::after",
            "linear-gradient(to right, var(--panel-raised), transparent)",
            "linear-gradient(to left, var(--panel-raised), transparent)",
        ):
            self.assertIn(marker, html)

    def test_cues_are_visual_only_and_calculator_scoped(self):
        css = (ROOT / "renderer" / "app-shell-scroll-hints.css").read_text(
            encoding="utf-8"
        )
        js = (ROOT / "renderer" / "app-shell-v2.scroll-hints.js").read_text(
            encoding="utf-8"
        )

        self.assertIn('body[data-app-mode="calculator"]', css)
        self.assertIn("pointer-events: none", css)
        self.assertNotIn("button", css)
        self.assertNotIn("insertAtSelection", js)
        self.assertNotIn("setRangeText", js)


if __name__ == "__main__":
    unittest.main()
