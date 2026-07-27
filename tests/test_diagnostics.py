import logging
import tempfile
import types
import unittest
from pathlib import Path

import app_diagnostics


class DiagnosticsTests(unittest.TestCase):
    def make_app(self, clipboard):
        class AppApi:
            pass

        return types.SimpleNamespace(
            AppApi=AppApi,
            main=lambda: None,
            copy_text_to_clipboard=lambda text: clipboard.append(text) or True,
            _numlock_hook_mode="native",
            _quitting=False,
        )

    def test_frontend_error_is_written_and_copyable(self):
        clipboard = []
        with tempfile.TemporaryDirectory() as directory:
            app = self.make_app(clipboard)
            app_diagnostics.install(app, log_dir=Path(directory))
            api = app.AppApi()

            self.assertTrue(api.report_diagnostic("renderer", "boom", "stack line"))
            for handler in app.logger.handlers:
                handler.flush()

            diagnostics = app.diagnostic_text()
            self.assertIn("NumCalc diagnostics", diagnostics)
            self.assertIn("NumLock hook: native", diagnostics)
            self.assertIn("renderer: boom", diagnostics)
            self.assertIn("stack line", diagnostics)
            self.assertTrue(api.copy_diagnostics())
            self.assertEqual(clipboard[-1], app.diagnostic_text())

            # Release the file before TemporaryDirectory removes it on Windows.
            for handler in list(app.logger.handlers):
                handler.close()
                app.logger.removeHandler(handler)

    def test_install_is_idempotent(self):
        clipboard = []
        with tempfile.TemporaryDirectory() as directory:
            app = self.make_app(clipboard)
            app_diagnostics.install(app, log_dir=Path(directory))
            first_main = app.main
            app_diagnostics.install(app, log_dir=Path(directory))
            self.assertIs(app.main, first_main)
            for handler in list(logging.getLogger(app_diagnostics.LOGGER_NAME).handlers):
                handler.close()
                logging.getLogger(app_diagnostics.LOGGER_NAME).removeHandler(handler)


if __name__ == "__main__":
    unittest.main()
