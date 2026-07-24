import sys
import time
import types
import unittest

fake_webview = types.SimpleNamespace(Window=object)
sys.modules.setdefault("webview", fake_webview)

import calc_engine
from calc_engine_runtime import CalculatorSession

calc_engine.CalculatorSession = CalculatorSession

import app
import app_stability

app_stability.install(app)


class FakeWindow:
    def __init__(self):
        self.hide_calls = 0
        self.show_calls = 0
        self.restore_calls = 0
        self.evaluate_calls = 0

    def hide(self):
        self.hide_calls += 1

    def show(self):
        self.show_calls += 1

    def restore(self):
        self.restore_calls += 1

    def evaluate_js(self, _script):
        self.evaluate_calls += 1


class StabilityTests(unittest.TestCase):
    def setUp(self):
        self.saved = (
            app._window,
            app._visible,
            app._renderer_focused,
            app._quitting,
            app._numlock_down,
        )
        app._window = FakeWindow()
        app._visible = True
        app._renderer_focused = True
        app._quitting = False
        app._numlock_down = False

    def tearDown(self):
        (
            app._window,
            app._visible,
            app._renderer_focused,
            app._quitting,
            app._numlock_down,
        ) = self.saved

    def test_active_window_hides_once_per_physical_press(self):
        app.on_numlock_press()
        app.on_numlock_press()
        self.assertEqual(app._window.hide_calls, 1)

    def test_visible_unfocused_window_is_refocused(self):
        app._renderer_focused = False
        app.on_numlock_press()
        time.sleep(0.06)
        self.assertEqual(app._window.hide_calls, 0)
        self.assertEqual(app._window.show_calls, 1)
        self.assertEqual(app._window.restore_calls, 1)
        self.assertEqual(app._window.evaluate_calls, 1)

    def test_focus_state_is_exposed_through_api(self):
        app._api.window_focus_changed(False)
        self.assertFalse(app._renderer_focused)
        app._api.window_focus_changed(True)
        self.assertTrue(app._renderer_focused)

    def test_native_hook_is_installed_as_primary_handler(self):
        self.assertTrue(callable(app.register_numlock_hook))
        self.assertTrue(callable(app.stop_numlock_hook))

    def test_v2_html_contains_layout_independent_shortcut_and_groups(self):
        html = app.build_html()
        self.assertIn('id="paletteGroups"', html)
        self.assertIn("event.code === 'KeyK'", html)
        self.assertIn("__nlcalcRestoreEditorFocus", html)


if __name__ == "__main__":
    unittest.main()
