import types
import unittest
from pathlib import Path
from unittest.mock import patch

import app_native_titlebar
import app_renderer


ROOT = Path(__file__).resolve().parents[1]


class FakeUser32:
    def __init__(self, *, cursor=(640, 480), send_result=0):
        self.cursor = cursor
        self.send_result = send_result
        self.release_calls = 0
        self.messages = []

    def GetCursorPos(self, pointer):
        pointer._obj.x, pointer._obj.y = self.cursor
        return 1

    def ReleaseCapture(self):
        self.release_calls += 1
        return 1

    def SendMessageW(self, hwnd, message, wparam, lparam):
        self.messages.append((hwnd, message, wparam, lparam))
        return self.send_result


class NativeTitlebarTests(unittest.TestCase):
    def test_caption_drag_sends_synchronous_native_move_message(self):
        user32 = FakeUser32(cursor=(640, 480), send_result=0)
        self.assertTrue(app_native_titlebar.begin_windows_caption_drag(user32, 321))
        self.assertEqual(user32.release_calls, 1)
        self.assertEqual(
            user32.messages,
            [(
                321,
                app_native_titlebar.WM_NCLBUTTONDOWN,
                app_native_titlebar.HTCAPTION,
                app_native_titlebar._mouse_lparam(640, 480),
            )],
        )

    def test_zero_sendmessage_lresult_is_not_treated_as_drag_failure(self):
        user32 = FakeUser32(send_result=0)
        self.assertTrue(app_native_titlebar.begin_windows_caption_drag(user32, 321))
        self.assertEqual(len(user32.messages), 1)

    def test_signed_multi_monitor_coordinates_are_packed_without_css_scaling(self):
        self.assertEqual(
            app_native_titlebar._mouse_lparam(-120, -40),
            ((-40 & 0xFFFF) << 16) | (-120 & 0xFFFF),
        )

    def test_install_exposes_caption_drag_api(self):
        user32 = FakeUser32(cursor=(100, 200))

        class Api:
            pass

        fake_app = types.SimpleNamespace(
            AppApi=Api,
            _quitting=False,
            window_handle=lambda: 777,
            _user32=lambda: user32,
        )
        app_native_titlebar.install(fake_app)
        with patch.object(app_native_titlebar.os, 'name', 'nt'):
            self.assertTrue(Api().begin_window_drag())
        self.assertEqual(user32.messages[0][:3], (777, 0x00A1, 2))

    def test_renderer_disables_pywebview_drag_and_excludes_titlebar_controls(self):
        source = (ROOT / 'renderer' / 'app-shell-v2.restore-behavior.js').read_text(
            encoding='utf-8'
        )
        html = app_renderer.render_document(ROOT / 'renderer')

        self.assertIn("classList.remove('pywebview-drag-region')", source)
        self.assertIn('NATIVE_TITLEBAR_INTERACTIVE_SELECTOR', source)
        self.assertIn("'.pywebview-no-drag'", source)
        self.assertIn("'button'", source)
        self.assertIn('begin_window_drag', html)
        self.assertNotIn('screenX', source)
        self.assertNotIn('clientX', source)

    def test_keyboard_entry_point_installs_native_titlebar_before_renderer(self):
        source = (ROOT / 'app_keyboard.py').read_text(encoding='utf-8')
        native = source.index('app_native_titlebar.install(app)')
        renderer = source.index('app_renderer.install(app)')
        self.assertLess(native, renderer)


if __name__ == '__main__':
    unittest.main()
