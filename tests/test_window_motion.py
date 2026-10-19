import types
import unittest

import app_window
import app_window_motion as motion


class WindowMotionTests(unittest.TestCase):
    def test_window_background_follows_the_theme(self):
        css = open("renderer/app-shell.css", encoding="utf-8").read()
        self.assertIn(f"--panel: {motion.background_for('light')};", css)
        self.assertIn(f"--panel: {motion.background_for('dark')};", css)
        self.assertEqual(motion.background_for(None), motion.background_for("dark"))

    def test_height_moves_in_one_eased_motion(self):
        steps = motion.eased_heights(432, 188)
        self.assertEqual(len(steps), motion.RESIZE_FRAMES)
        self.assertEqual(steps[-1], 188)
        self.assertEqual(steps, sorted(steps, reverse=True))
        # Ease-out: most of the distance is covered in the first half.
        self.assertLess(steps[len(steps) // 2], 432 - (432 - 188) * 0.75)
        self.assertEqual(motion.eased_heights(300, 300), [300])

    def test_target_matches_the_compact_window_rules(self):
        self.assertEqual(motion.target_height(False, 200), app_window.DEFAULT_WINDOW_HEIGHT)
        self.assertEqual(motion.target_height(True, 10), app_window.COMPACT_MIN_SIZE[1])
        self.assertEqual(motion.target_height(True, 9999), app_window.COMPACT_MAX_CONTENT_HEIGHT)
        self.assertEqual(motion.target_height(True, None), app_window.COMPACT_WINDOW_HEIGHT)

    def make_app(self, theme="light"):
        calls = []

        class Api:
            def __init__(self):
                self._ui_settings = {"theme": theme}

            def set_ui_settings(self, settings):
                calls.append(("settings", settings))
                return dict(settings)

            def set_compact_window(self, compact, content_height=None):
                calls.append(("compact", compact, content_height))
                return {"ok": True}

        app = types.SimpleNamespace(
            AppApi=Api,
            webview=types.SimpleNamespace(create_window=lambda *a, **k: calls.append(("create", k))),
            _window=None,
            _quitting=False,
            _coerce_bool=lambda value, default: bool(value),
        )
        app._api = Api()
        return app, calls

    def test_window_is_created_with_the_theme_background(self):
        app, calls = self.make_app("light")
        motion.install(app)
        app.webview.create_window("NumCalc", html="")
        self.assertEqual(calls[-1][1]["background_color"], "#fafafa")

    def test_resize_and_theme_changes_still_reach_the_original_api(self):
        app, calls = self.make_app()
        motion.install(app)
        api = app.AppApi()
        self.assertEqual(api.set_compact_window(True, 200), {"ok": True})
        api.set_ui_settings({"theme": "dark"})
        self.assertIn(("compact", True, 200), calls)
        self.assertIn(("settings", {"theme": "dark"}), calls)


if __name__ == "__main__":
    unittest.main()
