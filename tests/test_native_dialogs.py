import unittest
from unittest.mock import patch

import app_native_dialogs


class NativeDialogTests(unittest.TestCase):
    def test_external_url_rejects_non_web_protocols(self):
        for url in ("file:///tmp/test", "javascript:alert(1)", "", "example.com"):
            self.assertFalse(app_native_dialogs.open_external_url(url))

    def test_external_url_respects_exact_allowlist(self):
        allowed = "https://github.com/Aev199/numlock-calculator"
        with patch("app_native_dialogs.webbrowser.open", return_value=True) as opener:
            self.assertFalse(
                app_native_dialogs.open_external_url(
                    "https://github.com/Aev199/other",
                    (allowed,),
                )
            )
            self.assertTrue(app_native_dialogs.open_external_url(allowed, (allowed,)))
        opener.assert_called_once_with(allowed, new=2)

    def test_message_box_is_safe_off_windows(self):
        if app_native_dialogs.os.name != "nt":
            self.assertFalse(app_native_dialogs.show_message("Title", "Text"))
            self.assertFalse(
                app_native_dialogs.show_link_dialog(
                    "Title",
                    "Instruction",
                    '<A HREF="https://example.com">Example</A>',
                    ("https://example.com",),
                )
            )


if __name__ == "__main__":
    unittest.main()
