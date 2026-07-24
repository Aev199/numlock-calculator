import types
import unittest
from pathlib import Path

import app_polish


class RendererPolishTests(unittest.TestCase):
    def make_app(self):
        source = """<!doctype html>
<html>
<head><style>base</style></head>
<body>
<script>
(function () {
  'use strict';
  function schedulePreview(delay = 90) {}
})();
</script>
</body>
</html>
"""
        return types.SimpleNamespace(
            RENDERER_DIR=Path(__file__).resolve().parents[1] / "renderer",
            build_html=lambda: source,
        )

    def test_polish_is_inlined_before_main_renderer(self):
        fake_app = self.make_app()
        app_polish.install(fake_app)
        html = fake_app.build_html()

        self.assertIn("nlcalc-polish-v3", html)
        self.assertIn("wrapTypedFunction", html)
        self.assertIn("function schedulePreview(delay = 18)", html)
        self.assertIn("nlcalc-pending-pulse", html)
        self.assertLess(
            html.index("const POLISH_MARKER"),
            html.index("function schedulePreview(delay = 18)"),
        )

    def test_install_is_idempotent(self):
        fake_app = self.make_app()
        app_polish.install(fake_app)
        first_builder = fake_app.build_html
        app_polish.install(fake_app)
        self.assertIs(first_builder, fake_app.build_html)
        self.assertEqual(fake_app.build_html().count("nlcalc-polish-v3"), 1)


if __name__ == "__main__":
    unittest.main()
