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

    def test_windows_reduced_motion_is_respected(self):
        # The page used to force full motion and ignore the system setting.
        self.assertNotIn("dataset.motion === 'full') return false", self.html)
        self.assertIn("prefers-reduced-motion: reduce", self.html)

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
