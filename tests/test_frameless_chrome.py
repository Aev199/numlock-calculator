import types
import unittest
from pathlib import Path

import app_frameless_chrome


ROOT = Path(__file__).resolve().parents[1]


class FramelessChromeTests(unittest.TestCase):
    def test_final_layer_forces_shadow_off(self):
        calls = []

        def create_window(*args, **kwargs):
            calls.append((args, kwargs))
            return object()

        app = types.SimpleNamespace(
            webview=types.SimpleNamespace(create_window=create_window),
        )
        app_frameless_chrome.install(app)

        app.webview.create_window("NumCalc", shadow=True)
        self.assertFalse(calls[0][1]["shadow"])

    def test_keyboard_installs_chrome_after_tray_before_renderer(self):
        source = (ROOT / "app_keyboard.py").read_text(encoding="utf-8")
        self.assertIn("import app_frameless_chrome", source)
        self.assertIn("app_frameless_chrome.install(app)", source)
        self.assertLess(
            source.index("app_tray.install(app)"),
            source.index("app_frameless_chrome.install(app)"),
        )
        self.assertLess(
            source.index("app_frameless_chrome.install(app)"),
            source.index("app_renderer.install(app)"),
        )

    def test_layer_documents_pywebview_dwm_frame_source(self):
        source = (ROOT / "app_frameless_chrome.py").read_text(encoding="utf-8")
        compile(source, "app_frameless_chrome.py", "exec")
        self.assertIn("DwmExtendFrameIntoClientArea", source)
        self.assertIn('kwargs["shadow"] = False', source)


if __name__ == "__main__":
    unittest.main()
