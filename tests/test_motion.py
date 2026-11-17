import unittest
from pathlib import Path

import app_renderer

ROOT = Path(__file__).resolve().parents[1]


class MotionTests(unittest.TestCase):
    def setUp(self):
        self.html = app_renderer.render_document(ROOT / "renderer")

    def test_feedback_motion_is_wired(self):
        for marker in (
            "commitCalculatorWithMotion",
            "copyCurrentCalculationWithMotion",
            "insertHistoryResultWithMotion",
            "colour-blend",
            "allow-discrete",
            "@starting-style",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.html)

    def test_own_setting_decides_and_windows_preference_is_ignored(self):
        self.assertNotIn("prefers-reduced-motion", self.html)
        self.assertNotIn("matchMedia", self.html)
        self.assertIn('body[data-motion="off"]', self.html)
        self.assertIn("dataset.motion === 'off'", self.html)
        self.assertIn("motionEnabled", self.html)

    def test_saved_setting_is_in_the_first_paint(self):
        import re
        import sys
        import types

        sys.modules.setdefault("webview", types.SimpleNamespace(
            Window=object,
            create_window=lambda *args, **kwargs: object(),
            start=lambda *args, **kwargs: None,
        ))
        import app

        for compact in (False, True):
            fake = types.SimpleNamespace(
                RENDERER_DIR=ROOT / "renderer",
                webview=types.SimpleNamespace(create_window=lambda *a, **k: None),
                ACCENTS=app.ACCENTS,
                compact_mode_enabled=lambda compact=compact: compact,
                _api=types.SimpleNamespace(_ui_settings={"motion": False}),
            )
            app_renderer.install(fake)
            body = re.search(r"<body[^>]*>", fake.build_html()).group(0)
            with self.subTest(compact=compact):
                self.assertIn('data-motion="off"', body)
                self.assertEqual('data-compact-mode="true"' in body, compact)

    def test_motion_setting_is_saved_as_a_boolean(self):
        import sys
        import tempfile
        import types

        sys.modules.setdefault("webview", types.SimpleNamespace(
            Window=object,
            create_window=lambda *args, **kwargs: object(),
            start=lambda *args, **kwargs: None,
        ))
        import app

        with tempfile.TemporaryDirectory() as directory:
            api = app.AppApi(app.Storage(Path(directory) / "data.json"))
            self.assertIs(api.set_ui_settings({"motion": "false"})["motion"], False)
            self.assertIs(api.set_ui_settings({"motion": True})["motion"], True)

    def test_effects_stay_short(self):
        css = (ROOT / "renderer/app-shell-motion-ui.css").read_text(encoding="utf-8")
        script = (ROOT / "renderer/app-shell-v2.motion.js").read_text(encoding="utf-8")
        import re

        durations = [int(value) for value in re.findall(r"(\d+)ms", css)]
        durations += [int(value) for value in re.findall(r"\], (\d+)\)", script)]
        self.assertTrue(durations)
        self.assertLessEqual(max(durations), 360)


if __name__ == "__main__":
    unittest.main()
