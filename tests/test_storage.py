import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

if 'webview' not in sys.modules:
    sys.modules['webview'] = types.SimpleNamespace(Window=object)

import app
from app import Storage, build_html


class StorageTests(unittest.TestCase):
    def test_round_trip_and_remove(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'data.json'
            storage = Storage(path)
            self.assertTrue(storage.set('theme', 'dark'))
            self.assertEqual(Storage(path).get('theme'), 'dark')
            self.assertTrue(storage.remove('theme'))
            self.assertIsNone(Storage(path).get('theme'))
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')), {})

    def test_html_contains_editable_expression_and_inlined_assets(self):
        html = build_html()
        self.assertIn('window.__NUMLOCK_PYWEBVIEW__ = true', html)
        self.assertIn('class CalculatorEngine', html)
        self.assertIn('id="exprInput"', html)
        self.assertNotIn('src="calc-core.js"', html)
        self.assertNotIn('src="script.js"', html)


class FakeWindow:
    def __init__(self):
        self.hide_calls = 0
        self.show_calls = 0
        self.restore_calls = 0

    def hide(self):
        self.hide_calls += 1

    def show(self):
        self.show_calls += 1

    def restore(self):
        self.restore_calls += 1


class NumLockHookTests(unittest.TestCase):
    def setUp(self):
        self.old_window = app._window
        self.old_visible = app._visible
        self.old_quitting = app._quitting
        self.old_numlock_down = app._numlock_down
        self.old_keyboard = app._keyboard_module

        self.window = FakeWindow()
        app._window = self.window
        app._visible = True
        app._quitting = False
        app._numlock_down = False
        app._keyboard_module = None

    def tearDown(self):
        app._window = self.old_window
        app._visible = self.old_visible
        app._quitting = self.old_quitting
        app._numlock_down = self.old_numlock_down
        app._keyboard_module = self.old_keyboard

    def test_one_toggle_per_physical_numlock_press(self):
        app.on_numlock_press()
        app.on_numlock_press()
        self.assertEqual(self.window.hide_calls, 1)
        self.assertEqual(self.window.show_calls, 0)

        app.on_numlock_release()
        app.on_numlock_press()
        self.assertEqual(self.window.hide_calls, 1)
        self.assertEqual(self.window.show_calls, 1)
        self.assertEqual(self.window.restore_calls, 1)

    def test_numlock_hook_is_suppressed(self):
        calls = []

        class FakeKeyboard:
            @staticmethod
            def hook_key(key, callback, suppress=False):
                calls.append(('hook', key, suppress, callback))

            @staticmethod
            def add_hotkey(key, callback, **kwargs):
                calls.append(('hotkey', key, kwargs, callback))

        with patch.dict(sys.modules, {'keyboard': FakeKeyboard}), patch.object(app, 'ensure_numlock_on', return_value=True):
            app.register_hotkeys()

        self.assertEqual(calls[0][0:3], ('hook', 'num lock', True))


class FakeUser32:
    def __init__(self, enabled=False):
        self.enabled = enabled
        self.events = []

    def GetKeyState(self, key):
        self.events.append(('state', key))
        return 1 if self.enabled else 0

    def keybd_event(self, key, scan, flags, extra):
        self.events.append(('event', key, scan, flags, extra))
        if flags & app.KEYEVENTF_KEYUP:
            self.enabled = not self.enabled


class NumLockStateTests(unittest.TestCase):
    def test_numlock_is_enabled_when_initially_off(self):
        user32 = FakeUser32(enabled=False)
        self.assertTrue(app.ensure_numlock_on(user32))
        self.assertTrue(user32.enabled)
        key_events = [item for item in user32.events if item[0] == 'event']
        self.assertEqual(len(key_events), 2)

    def test_enabled_numlock_is_not_toggled(self):
        user32 = FakeUser32(enabled=True)
        self.assertTrue(app.ensure_numlock_on(user32))
        key_events = [item for item in user32.events if item[0] == 'event']
        self.assertEqual(key_events, [])


if __name__ == '__main__':
    unittest.main()
