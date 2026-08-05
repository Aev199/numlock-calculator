import sys
import tempfile
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

import app
import app_numlock_compat
import app_renderer
import app_window
from hotkey_config import DEFAULT_HOTKEY, validate_hotkey

if not hasattr(app, 'configure_global_hotkey'):
    app_window.install(app)
    app_numlock_compat.install(app)
if not getattr(app, '_consolidated_renderer_installed', False):
    app_renderer.install(app)


class HotkeyConfigurationTests(unittest.TestCase):
    def test_canonicalizes_modifiers_and_display(self):
        result = validate_hotkey('Shift + Control + Space')
        self.assertTrue(result.ok)
        self.assertEqual(result.hotkey, 'ctrl+shift+space')
        self.assertEqual(result.display, 'Ctrl + Shift + Space')

    def test_rejects_internal_and_windows_conflicts(self):
        for value in ('ctrl+space', 'alt+left', 'ctrl+alt+delete', 'windows+l'):
            result = validate_hotkey(value)
            self.assertFalse(result.ok, value)
            self.assertTrue(result.error)

    def test_allows_numlock_and_function_key_defaults(self):
        self.assertEqual(validate_hotkey(DEFAULT_HOTKEY).hotkey, 'num lock')
        self.assertEqual(validate_hotkey('F12').display, 'F12')

    def test_requires_modifier_for_plain_character(self):
        result = validate_hotkey('a')
        self.assertFalse(result.ok)
        self.assertIn('модификатор', result.error)


class HotkeyRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.saved = {
            key: getattr(app, key, None)
            for key in (
                '_global_hotkey', '_global_hotkey_display', '_keyboard_module',
                '_hotkeys_started', '_hotkey_registration_ok',
                '_hotkey_registration_error', '_global_hotkey_handle',
                '_numlock_hook_mode', '_quitting',
            )
        }

    def tearDown(self):
        for key, value in self.saved.items():
            setattr(app, key, value)

    def test_custom_hotkey_uses_global_registration_without_numlock_hook(self):
        calls = []

        class FakeKeyboard:
            @staticmethod
            def add_hotkey(key, callback, **kwargs):
                calls.append(('hotkey', key, callback, kwargs))
                return f'handle:{key}'

            @staticmethod
            def hook_key(key, callback, suppress=False):
                calls.append(('hook', key, callback, suppress))

            @staticmethod
            def unhook_all():
                calls.append(('unhook',))

        app._global_hotkey = 'ctrl+alt+space'
        app._quitting = False
        with patch.dict(sys.modules, {'keyboard': FakeKeyboard}):
            app.register_hotkeys()
            try:
                self.assertTrue(app._hotkey_registration_ok)
                self.assertEqual(app._global_hotkey_handle, 'handle:ctrl+alt+space')
                self.assertFalse(any(call[0] == 'hook' for call in calls))
                self.assertEqual(
                    [call[1] for call in calls if call[0] == 'hotkey'],
                    ['ctrl+alt+space', 'ctrl+shift+q'],
                )
                custom = calls[0]
                self.assertTrue(custom[3]['suppress'])
                self.assertTrue(custom[3]['trigger_on_release'])
            finally:
                app.unregister_hotkeys()

    def test_navigation_hotkey_ignores_keypad_alias(self):
        calls = []
        hooks = []
        toggles = []

        class Event:
            def __init__(self, event_type, name, is_keypad):
                self.event_type = event_type
                self.name = name
                self.is_keypad = is_keypad

        class ImmediateThread:
            def __init__(self, target, args=(), kwargs=None, **_options):
                self.target = target
                self.args = args
                self.kwargs = kwargs or {}

            def start(self):
                self.target(*self.args, **self.kwargs)

        class FakeKeyboard:
            @staticmethod
            def hook(callback, suppress=False):
                hooks.append((callback, suppress))
                return callback

            @staticmethod
            def add_hotkey(key, callback, **kwargs):
                calls.append(('hotkey', key, callback, kwargs))
                return f'handle:{key}'

            @staticmethod
            def unhook_all():
                calls.append(('unhook',))

        app._global_hotkey = 'page down'
        app._quitting = False
        with (
            patch.object(app_numlock_compat.os, 'name', 'nt'),
            patch.object(app_numlock_compat.threading, 'Thread', ImmediateThread),
            patch.object(app, 'toggle_window', lambda: toggles.append('toggle')),
            patch.dict(sys.modules, {'keyboard': FakeKeyboard}),
        ):
            app.register_hotkeys()
            try:
                self.assertTrue(app._hotkey_registration_ok)
                self.assertEqual(len(hooks), 1)
                handler, suppress = hooks[0]
                self.assertTrue(suppress)

                self.assertTrue(handler(Event('down', 'page down', True)))
                self.assertTrue(handler(Event('up', 'page down', True)))
                self.assertEqual(toggles, [])

                self.assertFalse(handler(Event('down', 'page down', False)))
                self.assertFalse(handler(Event('up', 'page down', False)))
                self.assertEqual(toggles, ['toggle'])
            finally:
                app.unregister_hotkeys()

    def test_api_persists_only_after_successful_registration(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = app.Storage(Path(directory) / 'state.json')
            api = app.AppApi(storage)
            with patch.object(
                app,
                'configure_global_hotkey',
                return_value={
                    'ok': True,
                    'hotkey': 'ctrl+alt+space',
                    'display': 'Ctrl + Alt + Space',
                },
            ):
                result = api.set_global_hotkey('ctrl+alt+space')
            self.assertTrue(result['ok'])
            self.assertEqual(
                app.AppApi(storage).get_global_hotkey()['hotkey'],
                'ctrl+alt+space',
            )

            with patch.object(
                app,
                'configure_global_hotkey',
                return_value={'ok': False, 'error': 'занято'},
            ):
                rejected = api.set_global_hotkey('ctrl+alt+f12')
            self.assertFalse(rejected['ok'])
            self.assertEqual(
                app.AppApi(storage).get_global_hotkey()['hotkey'],
                'ctrl+alt+space',
            )

    def test_renderer_exposes_settings_capture(self):
        html = app.build_html()
        self.assertIn('id="settingsButton"', html)
        self.assertIn('id="globalHotkeyCapture"', html)
        self.assertIn('set_global_hotkey', html)
        self.assertIn('KEYPAD_NAVIGATION_ALIASES', html)
        self.assertIn('Number(event.location) === 3', html)


if __name__ == '__main__':
    unittest.main()
