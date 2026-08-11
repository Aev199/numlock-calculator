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
import app_clipboard_settings

app_clipboard_settings.install(app)


class ClipboardSettingsTests(unittest.TestCase):
    def test_group_copied_digits_defaults_on_and_survives_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = app.Storage(Path(directory) / 'state.json')
            api = app.AppApi(storage)
            self.assertTrue(api.bootstrap()['ui_settings']['group_copied_digits'])

            disabled = api.set_ui_settings({'group_copied_digits': False})
            self.assertFalse(disabled['group_copied_digits'])
            self.assertFalse(
                app.AppApi(storage).bootstrap()['ui_settings']['group_copied_digits']
            )

            enabled = app.AppApi(storage).set_ui_settings(
                {'group_copied_digits': True}
            )
            self.assertTrue(enabled['group_copied_digits'])

    def test_string_false_is_not_coerced_to_true(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = app.Storage(Path(directory) / 'state.json')
            api = app.AppApi(storage)
            updated = api.set_ui_settings({'group_copied_digits': 'false'})
            self.assertFalse(updated['group_copied_digits'])


if __name__ == '__main__':
    unittest.main()
