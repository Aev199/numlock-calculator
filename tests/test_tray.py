import types
import unittest

import app_tray


class TrayShellTests(unittest.TestCase):
    def make_app(self):
        create_calls = []

        def create_window(*args, **kwargs):
            create_calls.append((args, kwargs))
            return object()

        webview = types.SimpleNamespace(create_window=create_window)
        app = types.SimpleNamespace(
            build_html=lambda: (
                '<html><head><style>base</style></head><body>'
                '<div class="brand-block">NumLock Calc</div>'
                '</body></html>'
            ),
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
        return app, create_calls

    def test_window_defaults_are_frameless_and_shadowed(self):
        app, calls = self.make_app()
        app_tray.install(app)

        app.webview.create_window('test', html='x')

        self.assertEqual(len(calls), 1)
        kwargs = calls[0][1]
        self.assertTrue(kwargs['frameless'])
        self.assertFalse(kwargs['easy_drag'])
        self.assertTrue(kwargs['shadow'])

    def test_drag_region_is_added_to_custom_header(self):
        app, _ = self.make_app()
        app_tray.install(app)

        html = app.build_html()

        self.assertIn('brand-block pywebview-drag-region', html)
        self.assertIn('Перетащить окно', html)

    def test_tray_entry_points_are_exposed(self):
        app, _ = self.make_app()
        app_tray.install(app)

        self.assertTrue(callable(app.start_tray))
        self.assertTrue(callable(app.stop_tray))
        self.assertTrue(callable(app.show_from_tray))
        self.assertTrue(callable(app.hide_from_tray))
        self.assertTrue(callable(app.quit_from_tray))

    def test_install_is_idempotent(self):
        app, _ = self.make_app()
        app_tray.install(app)
        first_main = app.main
        app_tray.install(app)
        self.assertIs(first_main, app.main)


if __name__ == '__main__':
    unittest.main()
