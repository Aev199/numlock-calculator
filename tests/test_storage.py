import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import app_storage


class StorageLocationTests(unittest.TestCase):
    def make_app(self, app_dir):
        class Storage:
            def __init__(self, path):
                self.path = Path(path)

        class AppApi:
            def __init__(self, storage):
                self._storage = storage

            def bootstrap(self):
                return {"ok": True}

        return types.SimpleNamespace(
            application_dir=lambda: Path(app_dir),
            DATA_FILENAME="numlock-calc-data.json",
            DATA_FILE=Path(app_dir) / "numlock-calc-data.json",
            Storage=Storage,
            AppApi=AppApi,
            _api=AppApi(Storage(Path(app_dir) / "old.json")),
        )

    def test_normal_mode_uses_localappdata_and_migrates_legacy_file(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            app_dir = root / "app"
            local = root / "local"
            app_dir.mkdir()
            legacy = app_dir / "numlock-calc-data.json"
            legacy.write_text(json.dumps({"history": [1]}), encoding="utf-8")
            app = self.make_app(app_dir)

            with patch.dict("os.environ", {"LOCALAPPDATA": str(local)}, clear=False):
                app_storage.install(app, argv=["numcalc"])

            expected = local / "NumCalc" / "data.json"
            self.assertEqual(app.DATA_FILE, expected)
            self.assertEqual(app._storage_mode, "normal")
            self.assertTrue(app._storage_migrated)
            self.assertEqual(expected.read_text(encoding="utf-8"), legacy.read_text(encoding="utf-8"))
            payload = app._api.bootstrap()
            self.assertEqual(payload["storage"]["path"], str(expected))
            self.assertEqual(payload["storage"]["mode"], "normal")

    def test_portable_marker_keeps_data_next_to_application(self):
        with tempfile.TemporaryDirectory() as root:
            app_dir = Path(root)
            (app_dir / app_storage.PORTABLE_MARKER).write_text("", encoding="utf-8")
            app = self.make_app(app_dir)

            app_storage.install(app, argv=["numcalc"])

            self.assertEqual(app.DATA_FILE, app_dir / "data.json")
            self.assertEqual(app._storage_mode, "portable")
            self.assertIsNone(app._storage_warning)

    def test_unwritable_portable_folder_falls_back_with_warning(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            app_dir = root / "app"
            local = root / "local"
            app_dir.mkdir()
            app = self.make_app(app_dir)

            with (
                patch.dict("os.environ", {"LOCALAPPDATA": str(local)}, clear=False),
                patch.object(app_storage, "directory_is_writable", side_effect=[False, True]),
            ):
                app_storage.install(app, argv=["numcalc", "--portable"])

            self.assertEqual(app.DATA_FILE, local / "NumCalc" / "data.json")
            self.assertEqual(app._storage_mode, "normal-fallback")
            self.assertIn("portable", app._storage_warning)
            self.assertIn("storage_warning", app._api.bootstrap())

    def test_install_is_idempotent(self):
        with tempfile.TemporaryDirectory() as root:
            app = self.make_app(Path(root))
            app_storage.install(app, argv=["numcalc", "--portable"])
            first_api = app._api
            app_storage.install(app, argv=["numcalc"])
            self.assertIs(app._api, first_api)


if __name__ == "__main__":
    unittest.main()
