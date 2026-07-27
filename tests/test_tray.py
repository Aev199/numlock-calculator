import types
import unittest
from unittest.mock import patch

import app_tray


class TrayShellTests(unittest.TestCase):
    def make_app(self):
        create_calls = []
        start_calls = []

        def create_window(*args, **kwargs):
            create_calls.append((args, kwargs))
            return object()

        def start(*args, **kwargs):
            start_calls.append((args, kwargs))
            return None

        webview = types.SimpleNamespace(create_window=create_window, start=start)
        app = types.SimpleNamespace(
            build_html=lambda: "renderer-owned",
            webview=webview,
            main=lambda: None,
            _window=None,
            _visible=False,
            _quitting=False,
            show_window=lambda: None,
            refocus_window=lambda: None,
            hide_window=lambda: None,
            toggle_window=lambda: None,
            request_quit=lambda: None,
        )
        return app, create_calls, start_calls

    def test_window_defaults_are_frameless_and_shadowed(self):
        app, calls, _ = self.make_app()
        app_tray.install(app)

        app.webview.create_window("test", html="x")

        self.assertEqual(len(calls), 1)
        kwargs = calls[0][1]
        self.assertTrue(kwargs["frameless"])
        self.assertFalse(kwargs["easy_drag"])
        self.assertTrue(kwargs["shadow"])

    def test_tray_does_not_patch_renderer_markup(self):
        app, _, _ = self.make_app()
        original_builder = app.build_html
        app_tray.install(app)

        self.assertIs(app.build_html, original_builder)
        self.assertEqual(app.build_html(), "renderer-owned")

    def test_tray_starts_when_webview_loop_starts(self):
        app, _, start_calls = self.make_app()
        app_tray.install(app)

        with patch.object(app, "start_tray", return_value=True) as start_tray:
            app.webview.start(private_mode=True)

        start_tray.assert_called_once_with()
        self.assertEqual(start_calls, [((), {"private_mode": True})])

    def test_tray_entry_points_are_exposed(self):
        app, _, _ = self.make_app()
        app_tray.install(app)

        self.assertTrue(callable(app.start_tray))
        self.assertTrue(callable(app.stop_tray))
        self.assertTrue(callable(app.show_from_tray))
        self.assertTrue(callable(app.hide_from_tray))
        self.assertTrue(callable(app.quit_from_tray))

    def test_install_is_idempotent(self):
        app, _, _ = self.make_app()
        app_tray.install(app)
        first_main = app.main
        app_tray.install(app)
        self.assertIs(first_main, app.main)


if __name__ == "__main__":
    unittest.main()
