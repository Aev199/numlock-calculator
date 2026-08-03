import json
import os
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
import app_storage
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
    def test_import_time_api_is_memory_only(self):
        self.assertIsNone(app.DATA_FILE)
        self.assertIsNone(app._api._storage._filepath)

    def test_portable_storage_uses_the_same_filename_and_migrates_legacy_data(self):
        with tempfile.TemporaryDirectory() as directory:
            app_dir = Path(directory) / "app"
            app_dir.mkdir()
            legacy = app_dir / "numlock-calc-data.json"
            legacy.write_text("{}", encoding="utf-8")
            fake_app = types.SimpleNamespace(
                application_dir=lambda: app_dir,
                DATA_FILENAME="numlock-calc-data.json",
            )
            with patch.dict(
                os.environ,
                {"LOCALAPPDATA": str(Path(directory) / "local")},
                clear=False,
            ):
                target, mode, warning = app_storage.resolve_storage(
                    fake_app,
                    ["app_keyboard.py", "--portable"],
                )
            self.assertEqual(target, app_dir / "data.json")
            self.assertEqual(mode, "portable")
            self.assertIsNone(warning)
            self.assertTrue(app_storage.migrate_legacy_data(legacy, target))
            self.assertTrue(target.exists())

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

    def test_format_settings_and_history_survive_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = app.Storage(Path(directory) / 'state.json')
            api = app.AppApi(storage)
            settings = api.set_settings(
                {
                    'number_format': 'engineering',
                    'precision': 4,
                    'decimal_separator': ',',
                }
            )
            self.assertEqual(settings['number_format'], 'engineering')
            self.assertEqual(settings['decimal_separator'], ',')
            committed = api.commit('1234')
            self.assertEqual(committed['result'], '1,234e+3')
            entry = committed['history_entry']
            self.assertEqual(entry['normalized_expression'], '1234')
            self.assertEqual(entry['precision'], 4)
            self.assertEqual(entry['number_format'], 'engineering')
            self.assertEqual(entry['decimal_separator'], ',')

            restored = app.AppApi(storage).bootstrap()
            self.assertEqual(restored['settings']['number_format'], 'engineering')
            self.assertEqual(restored['settings']['decimal_separator'], ',')
            self.assertEqual(restored['history'][0]['normalized_expression'], '1234')

    def test_enter_selection_ui_setting_defaults_on_and_survives_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = app.Storage(Path(directory) / 'state.json')
            api = app.AppApi(storage)
            self.assertTrue(api.bootstrap()['ui_settings']['select_result_on_enter'])

            disabled = api.set_ui_settings({'select_result_on_enter': False})
            self.assertFalse(disabled['select_result_on_enter'])
            self.assertFalse(
                app.AppApi(storage).bootstrap()['ui_settings']['select_result_on_enter']
            )

            enabled = app.AppApi(storage).set_ui_settings(
                {'select_result_on_enter': True}
            )
            self.assertTrue(enabled['select_result_on_enter'])

    def test_onboarding_and_interpolation_state_survive_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = app.Storage(Path(directory) / 'state.json')
            api = app.AppApi(storage)
            self.assertFalse(api.bootstrap()['ui_settings']['onboarding_seen'])

            result = api.interpolate(
                {
                    'mode': '1d',
                    'values': {'x0': '0', 'y0': '0', 'x1': '10', 'y1': '100', 'x': '2,5'},
                }
            )
            self.assertTrue(result['ok'], result.get('error'))
            self.assertEqual(result['result'], '25')

            api.set_settings(
                {'number_format': 'engineering', 'precision': 4, 'decimal_separator': ','}
            )
            formatted = api.interpolate(
                {
                    'mode': '1d',
                    'values': {'x0': '0', 'y0': '0', 'x1': '1', 'y1': '1234', 'x': '1'},
                }
            )
            self.assertEqual(formatted['result'], '1,234e+3')

            saved = api.save_interpolation_state(
                {'mode': '2d', 'two_d': {'z11': '30,5'}, 'one_d': {'x': '2'}}
            )
            self.assertEqual(saved['mode'], '2d')
            api.set_ui_settings({'onboarding_seen': True})
            restored = app.AppApi(storage).bootstrap()
            self.assertTrue(restored['ui_settings']['onboarding_seen'])
            self.assertEqual(restored['interpolation']['mode'], '2d')
            self.assertEqual(restored['interpolation']['two_d']['z11'], '30,5')
            self.assertEqual(restored['interpolation']['one_d']['x'], '2')

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
