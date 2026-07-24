import types
import unittest
from pathlib import Path

import app_compact


class CompactShellTests(unittest.TestCase):
    def make_app(self):
        calls = []

        def create_window(*args, **kwargs):
            calls.append((args, kwargs))
            return object()

        app = types.SimpleNamespace(
            webview=types.SimpleNamespace(create_window=create_window),
        )
        return app, calls

    def test_window_size_overrides_prototype_dimensions(self):
        app, calls = self.make_app()
        app_compact.install(app)

        app.webview.create_window(
            "NumLock Calc",
            width=540,
            height=650,
            min_size=(420, 430),
        )

        self.assertEqual(len(calls), 1)
        kwargs = calls[0][1]
        self.assertEqual(kwargs["width"], app_compact.DEFAULT_WIDTH)
        self.assertEqual(kwargs["height"], app_compact.DEFAULT_HEIGHT)
        self.assertEqual(kwargs["min_size"], app_compact.MIN_SIZE)

    def test_compact_visual_rows_are_hidden(self):
        css = (
            Path(__file__).resolve().parents[1]
            / "renderer"
            / "polish-v3.css"
        ).read_text(encoding="utf-8")

        self.assertIn(".hint-row,", css)
        self.assertIn(".statusbar", css)
        self.assertIn("display: none !important", css)
        self.assertIn("grid-template-rows: auto minmax(0, 1fr)", css)

    def test_install_is_idempotent(self):
        app, _ = self.make_app()
        app_compact.install(app)
        first_create_window = app.webview.create_window
        app_compact.install(app)
        self.assertIs(first_create_window, app.webview.create_window)


if __name__ == "__main__":
    unittest.main()
