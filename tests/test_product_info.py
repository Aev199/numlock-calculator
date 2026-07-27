import types
import unittest

import app_product
import product_info


class ProductInfoTests(unittest.TestCase):
    def test_release_candidate_identity_is_consistent(self):
        self.assertEqual(product_info.APP_NAME, "NumCalc")
        self.assertEqual(product_info.APP_VERSION, "1.0.0-rc.1")
        self.assertEqual(product_info.APP_ID, "Aev199.NumCalc")
        self.assertEqual(product_info.EXECUTABLE_NAME, "NumCalc")
        self.assertEqual(product_info.version_tuple(), (1, 0, 0, 0))

    def test_product_identity_updates_runtime_and_tray(self):
        app = types.SimpleNamespace(APP_NAME="legacy")
        tray = types.SimpleNamespace(
            TRAY_TITLE="legacy",
            AUTOSTART_VALUE="legacy",
            ABOUT_TEXT="legacy",
        )

        app_product.install(app, tray)

        self.assertEqual(app.APP_NAME, product_info.APP_NAME)
        self.assertEqual(app.APP_VERSION, product_info.APP_VERSION)
        self.assertEqual(tray.TRAY_TITLE, product_info.APP_NAME)
        self.assertEqual(tray.AUTOSTART_VALUE, product_info.APP_NAME)
        self.assertIn(product_info.APP_VERSION, tray.ABOUT_TEXT)

    def test_install_is_idempotent(self):
        app = types.SimpleNamespace(APP_NAME="legacy")
        tray = types.SimpleNamespace(
            TRAY_TITLE="legacy",
            AUTOSTART_VALUE="legacy",
            ABOUT_TEXT="legacy",
        )
        app_product.install(app, tray)
        first_about = tray.ABOUT_TEXT
        tray.ABOUT_TEXT = "changed externally"
        app_product.install(app, tray)
        self.assertEqual(tray.ABOUT_TEXT, "changed externally")
        self.assertNotEqual(first_about, tray.ABOUT_TEXT)


if __name__ == "__main__":
    unittest.main()
