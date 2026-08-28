import types
import unittest
from pathlib import Path

import app_vertical_resize


ROOT = Path(__file__).resolve().parents[1]


class DummyApi:
    def set_compact_window(self, compact, content_height=None):
        return {
            "ok": True,
            "compact_mode": bool(compact),
            "width": app_vertical_resize.FULL_WINDOW_WIDTH,
            "height": content_height or app_vertical_resize.FULL_WINDOW_MIN_HEIGHT,
        }


class VerticalResizeTests(unittest.TestCase):
    def make_app(self, compact=False):
        calls = []

        def create_window(*args, **kwargs):
            calls.append((args, kwargs))
            return object()

        app = types.SimpleNamespace(
            webview=types.SimpleNamespace(create_window=create_window),
            AppApi=type("Api", (DummyApi,), {}),
            compact_mode_enabled=lambda: compact,
            on_loaded=lambda: None,
            on_shown=lambda: None,
            _window=None,
        )
        return app, calls

    def test_full_mode_is_fixed_width_and_practically_unbounded_vertically(self):
        minimum, maximum = app_vertical_resize.resize_bounds(False)
        self.assertEqual(minimum, (384, 432))
        self.assertEqual(
            maximum,
            (384, app_vertical_resize.FULL_WINDOW_MAX_HEIGHT),
        )
        self.assertGreater(app_vertical_resize.FULL_WINDOW_MAX_HEIGHT, 10_000)

    def test_compact_mode_remains_locked_to_measured_size(self):
        minimum, maximum = app_vertical_resize.resize_bounds(True, 188)
        self.assertEqual(minimum, (384, 188))
        self.assertEqual(maximum, (384, 188))

    def test_full_window_creation_enables_only_useful_resize_axis(self):
        app, calls = self.make_app(compact=False)
        app_vertical_resize.install(app)

        app.webview.create_window(
            "NumCalc",
            width=999,
            height=432,
            min_size=(360, 380),
            resizable=False,
        )
        kwargs = calls[0][1]
        self.assertTrue(kwargs["resizable"])
        self.assertEqual(kwargs["width"], 384)
        self.assertEqual(kwargs["min_size"], (384, 432))

    def test_compact_creation_keeps_width_fixed_without_changing_height_floor(self):
        app, calls = self.make_app(compact=True)
        app_vertical_resize.install(app)

        app.webview.create_window(
            "NumCalc",
            width=999,
            height=188,
            min_size=(360, 160),
        )
        kwargs = calls[0][1]
        self.assertEqual(kwargs["width"], 384)
        self.assertEqual(kwargs["min_size"], (384, 160))

    def test_keyboard_entry_point_installs_resize_layer_after_window_controller(self):
        source = (ROOT / "app_keyboard.py").read_text(encoding="utf-8")
        self.assertIn("import app_vertical_resize", source)
        self.assertIn("app_vertical_resize.install(app)", source)
        self.assertLess(
            source.index("app_window.install(app)"),
            source.index("app_vertical_resize.install(app)"),
        )
        self.assertLess(
            source.index("app_vertical_resize.install(app)"),
            source.index("app_renderer.install(app)"),
        )


if __name__ == "__main__":
    unittest.main()
