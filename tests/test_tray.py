import types
import unittest
from pathlib import Path
from unittest.mock import patch

import app_product
import app_tray


ROOT = Path(__file__).resolve().parents[1]


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
            copy_diagnostics=lambda: True,
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
        self.assertTrue(callable(app.copy_diagnostics_from_tray))
        self.assertFalse(hasattr(app, "open_repository"))

    def test_help_and_menu_document_public_product(self):
        source = (ROOT / "app_tray.py").read_text(encoding="utf-8")
        self.assertIn("Ctrl+C", app_tray.HELP_TEXT)
        self.assertIn("Alt+← / Alt+→", app_tray.HELP_TEXT)
        self.assertIn("не содержит телеметрии", app_tray.HELP_TEXT)
        self.assertNotIn('pystray.MenuItem("Репозиторий"', source)
        self.assertIn('pystray.MenuItem("Копировать диагностику"', source)

    def test_product_metadata_adds_attribution_and_trusted_links(self):
        app, _, _ = self.make_app()
        tray_module = types.SimpleNamespace()
        app_product.install(app, tray_module)

        self.assertIn(
            "Калькулятор - идеологическое продолжение NumLock Calculator "
            "от Владимира Потапова",
            tray_module.ABOUT_TEXT,
        )
        self.assertIn("https://nlcalc.narod.ru/", tray_module.ABOUT_TEXT)
        self.assertIn("https://github.com/Aev199/numlock-calculator", tray_module.ABOUT_TEXT)
        self.assertEqual(
            tray_module.ABOUT_LINKS,
            (
                (
                    "NumLock Calculator — сайт Владимира Потапова",
                    "https://nlcalc.narod.ru/",
                ),
                (
                    "Репозиторий NumCalc",
                    "https://github.com/Aev199/numlock-calculator",
                ),
            ),
        )
        self.assertNotIn("<A HREF=", tray_module.ABOUT_DIALOG_CONTENT)

    def test_install_is_idempotent(self):
        app, _, _ = self.make_app()
        app_tray.install(app)
        first_main = app.main
        app_tray.install(app)
        self.assertIs(first_main, app.main)


if __name__ == "__main__":
    unittest.main()

