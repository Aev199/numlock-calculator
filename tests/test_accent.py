import re
import sys
import tempfile
import types
import unittest
from pathlib import Path

sys.modules.setdefault("webview", types.SimpleNamespace(
    Window=object,
    create_window=lambda *args, **kwargs: object(),
    start=lambda *args, **kwargs: None,
))

import app
import app_renderer

ROOT = Path(__file__).resolve().parents[1]


class AccentTests(unittest.TestCase):
    def make_api(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        return app.AppApi(app.Storage(Path(directory.name) / "data.json"))

    def test_only_known_accents_are_saved(self):
        api = self.make_api()
        self.assertEqual(api.set_ui_settings({"accent": "green"})["accent"], "green")
        self.assertEqual(api.set_ui_settings({"accent": "<script>"})["accent"], "blue")

    def test_every_accent_has_styles_and_a_swatch(self):
        css = (ROOT / "renderer/app-shell-accent.css").read_text(encoding="utf-8")
        script = (ROOT / "renderer/app-shell-v2.accent.js").read_text(encoding="utf-8")
        for accent in app.ACCENTS:
            with self.subTest(accent=accent):
                self.assertIn(f"id: '{accent}'", script)
                if accent != "blue":
                    self.assertIn(f'body[data-accent="{accent}"]', css)
                    self.assertIn(f'body[data-theme="dark"][data-accent="{accent}"]', css)

    def test_saved_theme_and_accent_are_in_the_first_paint(self):
        fake = types.SimpleNamespace(
            RENDERER_DIR=ROOT / "renderer",
            webview=types.SimpleNamespace(create_window=lambda *a, **k: None),
            ACCENTS=app.ACCENTS,
            _api=types.SimpleNamespace(_ui_settings={"theme": "light", "accent": "teal"}),
        )
        app_renderer.install(fake)
        body = re.search(r"<body[^>]*>", fake.build_html()).group(0)
        self.assertIn('data-theme="light"', body)
        self.assertIn('data-accent="teal"', body)

        fake._api._ui_settings = {"accent": "unknown"}
        body = re.search(r"<body[^>]*>", fake.build_html()).group(0)
        self.assertIn('data-theme="dark"', body)
        self.assertNotIn("data-accent", body)


if __name__ == "__main__":
    unittest.main()
