import types
import unittest
from pathlib import Path

import app_native_titlebar
import app_renderer


ROOT = Path(__file__).resolve().parents[1]


class NativeTitlebarTests(unittest.TestCase):
    def test_settings_enable_webview2_non_client_regions(self):
        settings = types.SimpleNamespace(IsNonClientRegionSupportEnabled=False)
        self.assertTrue(app_native_titlebar.enable_non_client_region_support(settings))
        self.assertTrue(settings.IsNonClientRegionSupportEnabled)

    def test_explicit_dotnet_setter_is_supported(self):
        class Settings:
            def __setattr__(self, name, value):
                if name == "IsNonClientRegionSupportEnabled":
                    raise AttributeError(name)
                super().__setattr__(name, value)

            def set_IsNonClientRegionSupportEnabled(self, value):
                self.enabled = bool(value)

        settings = Settings()
        self.assertTrue(app_native_titlebar.enable_non_client_region_support(settings))
        self.assertTrue(settings.enabled)

    def test_edge_callback_enables_regions_before_first_navigation(self):
        order = []

        class EdgeChrome:
            def on_webview_ready(self, sender, args):
                order.append(("original", sender.CoreWebView2.Settings.IsNonClientRegionSupportEnabled))
                return "ready"

        module = types.SimpleNamespace(EdgeChrome=EdgeChrome)
        self.assertTrue(app_native_titlebar.patch_edgechromium(module))
        self.assertTrue(app_native_titlebar.patch_edgechromium(module))

        settings = types.SimpleNamespace(IsNonClientRegionSupportEnabled=False)
        sender = types.SimpleNamespace(CoreWebView2=types.SimpleNamespace(Settings=settings))
        args = types.SimpleNamespace(IsSuccess=True)

        self.assertEqual(EdgeChrome().on_webview_ready(sender, args), "ready")
        self.assertEqual(order, [("original", True)])

    def test_failed_webview_initialization_still_delegates_to_pywebview(self):
        calls = []

        class EdgeChrome:
            def on_webview_ready(self, sender, args):
                calls.append(args.IsSuccess)

        module = types.SimpleNamespace(EdgeChrome=EdgeChrome)
        self.assertTrue(app_native_titlebar.patch_edgechromium(module))
        sender = types.SimpleNamespace(CoreWebView2=None)
        EdgeChrome().on_webview_ready(sender, types.SimpleNamespace(IsSuccess=False))
        self.assertEqual(calls, [False])

    def test_renderer_uses_native_app_regions_without_mouse_bridge(self):
        html = app_renderer.render_document(ROOT / "renderer")
        restore_source = (
            ROOT / "renderer" / "app-shell-v2.restore-behavior.js"
        ).read_text(encoding="utf-8")

        self.assertIn('<header class="topbar">', html)
        self.assertNotIn('class="topbar pywebview-drag-region"', html)
        self.assertIn("app-region: drag", html)
        self.assertIn("app-region: no-drag", html)
        self.assertNotIn("begin_window_drag", html)
        self.assertNotIn("NATIVE_TITLEBAR_INTERACTIVE_SELECTOR", restore_source)
        self.assertNotIn("addEventListener('mousedown'", restore_source)
        self.assertNotIn("screenX", restore_source)
        self.assertNotIn("clientX", restore_source)

    def test_keyboard_entry_point_installs_native_titlebar_before_renderer(self):
        source = (ROOT / "app_keyboard.py").read_text(encoding="utf-8")
        native = source.index("app_native_titlebar.install(app)")
        renderer = source.index("app_renderer.install(app)")
        self.assertLess(native, renderer)


if __name__ == "__main__":
    unittest.main()
