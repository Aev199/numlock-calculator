import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

fake_webview = types.SimpleNamespace(
    Window=object,
    create_window=lambda *args, **kwargs: object(),
    start=lambda *args, **kwargs: None,
)
sys.modules.setdefault('webview', fake_webview)

import calc_engine
from calc_engine_runtime import CalculatorSession

calc_engine.CalculatorSession = CalculatorSession

import app
import app_renderer
import app_window

app_window.install(app)


class FakeNativeWindow:
    def __init__(self):
        self.MinimumSize = None
        self.InvokeRequired = False
        self._scale = 1.0


class FakeResizableWindow:
    def __init__(self, width=420, height=500):
        self.width = width
        self.height = height
        self.min_size = app_window.FULL_MIN_SIZE
        self.native = FakeNativeWindow()
        self.resize_calls = []

    def resize(self, width, height):
        self.width = width
        self.height = height
        self.resize_calls.append((width, height))


class CompactModeTests(unittest.TestCase):
    def test_compact_setting_defaults_off_and_survives_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = app.Storage(Path(directory) / 'state.json')
            api = app.AppApi(storage)
            self.assertFalse(api.bootstrap()['ui_settings']['compact_mode'])

            updated = api.set_ui_settings({'compact_mode': True})
            self.assertTrue(updated['compact_mode'])
            restored = app.AppApi(storage).bootstrap()
            self.assertTrue(restored['ui_settings']['compact_mode'])

            app.AppApi(storage).set_ui_settings({'compact_mode': False})
            self.assertFalse(
                app.AppApi(storage).bootstrap()['ui_settings']['compact_mode']
            )

    def test_native_window_uses_measured_compact_height_and_restores_full_height(self):
        saved_window = app._window
        saved_quitting = app._quitting
        saved_full_height = getattr(app, '_full_window_height', 432)
        try:
            window = FakeResizableWindow(width=420, height=500)
            app._window = window
            app._quitting = False
            api = app.AppApi(app.Storage(None))

            compact = api.set_compact_window(True, 176)
            self.assertTrue(compact['ok'])
            self.assertEqual(compact['height'], 176)
            self.assertEqual(window.min_size, (app_window.COMPACT_MIN_SIZE[0], 176))
            self.assertEqual(window.resize_calls[-1], (420, 176))
            if os.name == 'nt' and window.native.MinimumSize is not None:
                self.assertEqual(window.native.MinimumSize.Width, app_window.COMPACT_MIN_SIZE[0])
                self.assertEqual(window.native.MinimumSize.Height, 176)

            overlay = api.set_compact_window(True, 340)
            self.assertTrue(overlay['ok'])
            self.assertEqual(window.resize_calls[-1], (420, 340))
            self.assertEqual(window.min_size, (app_window.COMPACT_MIN_SIZE[0], 340))

            full = api.set_compact_window(False)
            self.assertTrue(full['ok'])
            self.assertEqual(window.min_size, app_window.FULL_MIN_SIZE)
            self.assertEqual(window.resize_calls[-1], (420, 500))
            if os.name == 'nt' and window.native.MinimumSize is not None:
                self.assertEqual(window.native.MinimumSize.Width, app_window.FULL_MIN_SIZE[0])
                self.assertEqual(window.native.MinimumSize.Height, app_window.FULL_MIN_SIZE[1])
        finally:
            app._window = saved_window
            app._quitting = saved_quitting
            app._full_window_height = saved_full_height

    def test_compact_height_is_bounded(self):
        saved_window = app._window
        saved_quitting = app._quitting
        try:
            window = FakeResizableWindow(width=420, height=500)
            app._window = window
            app._quitting = False
            api = app.AppApi(app.Storage(None))

            too_small = api.set_compact_window(True, 20)
            self.assertEqual(too_small['height'], app_window.COMPACT_MIN_SIZE[1])
            too_large = api.set_compact_window(True, 9999)
            self.assertEqual(too_large['height'], app_window.COMPACT_MAX_CONTENT_HEIGHT)
        finally:
            app._window = saved_window
            app._quitting = saved_quitting

    def test_renderer_contains_fitted_compact_layout_history_and_shortcuts(self):
        html = app_renderer.render_document(Path(app.RENDERER_DIR))
        self.assertIn('Компактный режим', html)
        self.assertIn('Ctrl+Shift+M — переключить, Ctrl+H — история.', html)
        self.assertIn('data-compact-mode="true"', html)
        self.assertIn("mode !== 'calculator'", html)
        self.assertIn('compactVisibleContentHeight', html)
        self.assertIn('openCompactHistory', html)
        self.assertIn("event.code === 'KeyM'", html)
        self.assertIn("event.code === 'KeyH'", html)
        self.assertIn('COMPACT_OVERLAY_HEIGHT = 340', html)
        self.assertIn('compact-history-search', html)
        self.assertIn('set_compact_window', html)


if __name__ == '__main__':
    unittest.main()
