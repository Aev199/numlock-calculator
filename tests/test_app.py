import json
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch

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
import app_numlock_compat
import app_renderer
import app_units_backend
import app_variables
import app_window

app_window.install(app)
app_numlock_compat.install(app)
app_units_backend.install(app)
app_variables.install(app)
app_renderer.install(app)


class StorageAndApiTests(unittest.TestCase):
    def test_storage_atomic_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            storage = app.Storage(path)
            storage.set('theme', 'dark')
            self.assertEqual(app.Storage(path).get('theme'), 'dark')
            self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['theme'], 'dark')

    def test_api_preview_commit_and_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = app.Storage(Path(directory) / 'state.json')
            api = app.AppApi(storage)
            preview = api.preview('250 kPa to MPa')
            self.assertTrue(preview['ok'], preview['error'])
            self.assertEqual(preview['result'], '0.25 MPa')
            self.assertTrue(api.preview('span := 6 m')['ok'])
            self.assertNotIn('span', api.bootstrap()['variables'])
            committed = api.commit('span := 6 m')
            self.assertTrue(committed['ok'], committed['error'])
            self.assertIn('history_entry', committed)
            restored = app.AppApi(storage).bootstrap()
            self.assertEqual(restored['variables']['span'], '6 m')
            self.assertEqual(len(restored['history']), 1)

    def test_delete_variable_persists_and_refreshes_suggestions(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = app.Storage(Path(directory) / 'state.json')
            api = app.AppApi(storage)
            self.assertTrue(api.commit('span := 6 m')['ok'])
            self.assertIn('span', api.bootstrap()['variables'])

            response = api.delete_variable('SPAN')
            self.assertTrue(response['ok'])
            self.assertEqual(response['deleted'], 'span')
            self.assertNotIn('span', response['variables'])
            self.assertFalse(any(item.get('label') == 'span' for item in response['suggestions']))
            self.assertNotIn('span', app.AppApi(storage).bootstrap()['variables'])

            missing = api.delete_variable('span')
            self.assertFalse(missing['ok'])
            self.assertEqual(missing['error'], 'Переменная не найдена')

    def test_legacy_history_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = app.Storage(Path(directory) / 'state.json')
            storage.set('nlcalc_history', json.dumps([{'expr': '2+3', 'res': '5'}]))
            data = app.AppApi(storage).bootstrap()
            self.assertEqual(data['history'][0]['expression'], '2+3')
            self.assertEqual(data['history'][0]['result'], '5')

    def test_memory_and_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            api = app.AppApi(app.Storage(Path(directory) / 'state.json'))
            response = api.set_memory(2, '12 + 4')
            self.assertTrue(response['ok'], response['error'])
            self.assertEqual(api.get_memory(2), '16')
            settings = api.set_settings({'angle_mode': 'RAD', 'number_base': 'HEX'})
            self.assertEqual(settings['angle_mode'], 'RAD')
            self.assertEqual(settings['number_base'], 'HEX')

    def test_html_is_keyboard_first(self):
        html = app.build_html()
        self.assertIn('id="expressionInput"', html)
        self.assertIn('id="historyList"', html)
        self.assertNotIn('id="keypad"', html)
        self.assertNotIn('src="script-v2.js"', html)
        self.assertIn('window.__NUMLOCK_PYWEBVIEW__ = true', html)


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


class HotkeyTests(unittest.TestCase):
    def setUp(self):
        self.saved = (
            app._window,
            app._visible,
            getattr(app, '_renderer_focused', True),
            app._quitting,
            app._numlock_down,
            app._keyboard_module,
            app._restoring_numlock,
            app._numlock_cycle_active,
            app._numlock_hook_mode,
        )
        app._window = FakeWindow()
        app._visible = True
        app._renderer_focused = True
        app._quitting = False
        app._numlock_down = False
        app._keyboard_module = None
        app._restoring_numlock = False
        app._numlock_cycle_active = False
        # Prevent platform-specific injection in unit tests. The fallback still
        # exercises the physical key latch and window state machine.
        app._numlock_hook_mode = 'fallback-suppressed'

    def tearDown(self):
        time.sleep(0.08)
        (
            app._window,
            app._visible,
            app._renderer_focused,
            app._quitting,
            app._numlock_down,
            app._keyboard_module,
            app._restoring_numlock,
            app._numlock_cycle_active,
            app._numlock_hook_mode,
        ) = self.saved

    def test_one_window_toggle_per_physical_press(self):
        app.on_numlock_press(was_on_before=True)
        app.on_numlock_press(was_on_before=True)
        time.sleep(0.03)
        self.assertEqual(app._window.hide_calls, 1)

        app.on_numlock_release()
        app.on_numlock_press(was_on_before=True)
        time.sleep(0.08)
        self.assertEqual(app._window.show_calls, 1)
        self.assertEqual(app._window.restore_calls, 1)

    def test_native_blink_entry_points_are_exposed(self):
        self.assertTrue(callable(app.send_numlock_toggle))
        self.assertTrue(callable(app.start_numlock_blink))
        self.assertGreater(app_numlock_compat.NUMLOCK_BLINK_SECONDS, 0)
        self.assertEqual(
            app_numlock_compat.INJECTED_MASK,
            app_numlock_compat.LLKHF_INJECTED
            | app_numlock_compat.LLKHF_LOWER_IL_INJECTED,
        )

    def test_fallback_suppresses_physical_toggle(self):
        calls = []

        class FakeKeyboard:
            @staticmethod
            def hook_key(key, callback, suppress=False):
                calls.append(('hook', key, suppress, callback))

            @staticmethod
            def add_hotkey(key, callback, **kwargs):
                calls.append(('hotkey', key, kwargs))

            @staticmethod
            def unhook_all():
                calls.append(('unhook',))

        with (
            patch.dict(sys.modules, {'keyboard': FakeKeyboard}),
            patch.object(app, 'ensure_numlock_on', return_value=True),
        ):
            try:
                app.register_hotkeys()
            finally:
                app.unregister_hotkeys()

        emergency = next(call for call in calls if call[0] == 'hotkey')
        self.assertEqual(emergency[1], 'ctrl+shift+q')

        fallback_hooks = [call for call in calls if call[0] == 'hook']
        for hook in fallback_hooks:
            self.assertEqual(hook[1:3], ('num lock', True))


if __name__ == '__main__':
    unittest.main()
