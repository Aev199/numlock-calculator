import json
import tempfile
import unittest
from unittest import mock
from pathlib import Path

import app_updates
import update_core as core
from product_info import APP_VERSION


class MemoryStorage:
    def __init__(self):
        self.data = {}

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value


NEXT = "99.0.0"


class UpdaterTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.exe = self.root / "NumCalc.exe"
        self.exe.write_bytes(b"MZ current")
        self.new = b"MZ next"
        self.storage = MemoryStorage()
        self.states = []
        self.online = True

    def fetch(self, url, progress):
        if not self.online:
            raise core.UpdateError("Нет связи с GitHub: timed out")
        if url == core.releases_url():
            return json.dumps([{
                "tag_name": f"v{NEXT}", "html_url": "page", "prerelease": False,
                "assets": [{"name": "NumCalc.exe", "browser_download_url": "https://x/NumCalc.exe"},
                           {"name": "latest.json", "browser_download_url": "https://x/latest.json"}],
            }]).encode()
        if url.endswith("latest.json"):
            return json.dumps({"version": NEXT, "sha256": core.sha256_hex(self.new), "notes": ["Обновления"]}).encode()
        progress(len(self.new), len(self.new))
        return self.new

    def updater(self, installable=True):
        return app_updates.Updater(
            self.storage, self.states.append, fetch=self.fetch, exe=self.exe,
            downloads=lambda: None, version_of=lambda _path: None, installable=installable,
        )

    def test_manual_check_offers_and_installs_the_newer_release(self):
        updater = self.updater()
        updater.check(manual=True, wait=True)
        self.assertEqual(updater.phase, "available")
        self.assertEqual(updater.snapshot()["update"]["notes"], ["Обновления"])
        updater.download(wait=True)
        self.assertEqual(updater.phase, "ready")
        self.assertEqual(self.exe.read_bytes(), self.new)
        self.assertTrue(updater.snapshot()["previous"])
        updater.rollback()
        self.assertEqual((updater.phase, self.exe.read_bytes()), ("rolled_back", b"MZ current"))
        self.assertIn("checking", [state["phase"] for state in self.states])

    def test_skipped_version_is_not_offered_quietly(self):
        updater = self.updater()
        updater.check(manual=True, wait=True)
        updater.skip()
        self.assertEqual(self.storage.data["updates"]["skipped"], NEXT)
        again = self.updater()
        again.check(manual=False, wait=True)
        self.assertEqual(again.phase, "idle")
        again.check(manual=True, wait=True)
        self.assertEqual(again.phase, "available")

    def test_unreachable_github_suggests_the_browser(self):
        self.online = False
        updater = self.updater()
        updater.check(manual=True, wait=True)
        self.assertEqual(updater.phase, "blocked")
        self.assertIn("Нет связи", updater.message)
        quiet = self.updater()
        quiet.check(manual=False, wait=True)
        self.assertEqual(quiet.phase, "idle")

    def test_up_to_date_shared_folder_answers_for_the_network(self):
        self.online = False
        (self.root / "share").mkdir()
        (self.root / "share" / core.MANIFEST_ASSET).write_text(
            json.dumps({"version": APP_VERSION, "sha256": "a" * 64}), encoding="utf-8")
        updater = self.updater()
        updater.set_preferences({"folder": str(self.root / "share")})
        updater.check(manual=True, wait=True)
        self.assertEqual(updater.phase, "idle")
        self.assertIn("последняя версия", updater.note)

    def test_installed_version_is_shared_with_colleagues(self):
        share = self.root / "share"
        share.mkdir()
        updater = self.updater()
        updater.set_preferences({"folder": str(share), "share": True, "channel": "beta", "auto": False})
        self.assertEqual(self.storage.data["updates"]["channel"], "beta")
        updater.check(manual=True, wait=True)
        updater.download(wait=True)
        self.assertEqual(core.check_folder(share, APP_VERSION).version, NEXT)
        self.assertIn("выложена", updater.note)

    def test_source_runs_check_but_do_not_install(self):
        updater = self.updater(installable=False)
        updater.check(manual=True, wait=True)
        updater.download()
        self.assertEqual(updater.phase, "failed")
        self.assertEqual(self.exe.read_bytes(), b"MZ current")
        self.assertIsNone(updater.start_background_checks(lambda: True))

    def updater_with_download(self, version):
        downloads = self.root / "Downloads"
        downloads.mkdir()
        (downloads / "NumCalc (2).exe").write_bytes(b"MZ beta")
        return app_updates.Updater(
            self.storage, self.states.append, fetch=self.fetch, exe=self.exe,
            downloads=lambda: downloads, version_of=lambda _path: version, installable=True,
        )

    def test_a_beta_in_downloads_does_not_hide_the_release(self):
        updater = self.updater_with_download(f"{NEXT}-beta.2")
        updater.check(manual=True, wait=True)
        self.assertEqual(updater.update.version, NEXT)
        self.assertTrue(updater.update.exe_url.startswith("https://"))

    def test_the_release_wins_over_the_same_version_in_downloads(self):
        updater = self.updater_with_download(NEXT)
        updater.check(manual=True, wait=True)
        self.assertTrue(updater.update.exe_url.startswith("https://"))

    def test_a_newer_file_in_downloads_is_still_offered(self):
        updater = self.updater_with_download("100.0.0")
        updater.check(manual=True, wait=True)
        self.assertEqual(updater.update.version, "100.0.0")

    def test_the_installed_build_in_downloads_is_not_offered_again(self):
        self.online = False
        updater = self.updater_with_download(APP_VERSION)
        updater.check(manual=True, wait=True)
        self.assertEqual(updater.phase, "blocked")
        self.assertIsNone(updater.update)

    def test_restart_command_names_the_old_process(self):
        command = self.updater().restart_command()
        self.assertEqual(command[0], str(self.exe))
        self.assertTrue(command[1].startswith(app_updates.RESTART_ARGUMENT))



class InstallabilityTests(unittest.TestCase):
    def test_only_the_one_file_windows_build_updates_itself(self):
        exe = Path("/apps/NumCalc/NumCalc.exe")
        self.assertTrue(app_updates.is_one_file_bundle(exe, "/tmp/_MEI1234"))
        self.assertFalse(app_updates.is_one_file_bundle(exe, "/apps/NumCalc/_internal"))
        self.assertFalse(app_updates.is_one_file_bundle(exe, ""))
        self.assertFalse(app_updates.can_self_update())

    def test_exe_and_temp_on_different_windows_drives(self):
        import ntpath

        exe = Path("D:/Tools/NumCalc.exe")
        temp = r"C:\Users\me\AppData\Local\Temp\_MEI1234"
        self.assertTrue(app_updates.is_one_file_bundle(exe, temp, ntpath))
        self.assertFalse(app_updates.is_one_file_bundle(exe, r"D:\Tools\_internal", ntpath))

    def test_calculator_starts_when_updates_fail(self):
        import types

        started = []
        app = types.SimpleNamespace(main=lambda: started.append(True), AppApi=type("AppApi", (), {}))
        app_updates.install(app)
        app_updates.install_restart_wait(app)
        broken = mock.Mock(side_effect=RuntimeError("broken"))
        with mock.patch.object(app_updates, "Updater", broken), \
                mock.patch.object(app_updates, "wait_for_previous_process", broken):
            app.main()
        self.assertEqual(started, [True])


class RendererWiringTests(unittest.TestCase):
    def test_renderer_receives_update_state_and_settings(self):
        import app_renderer

        html = app_renderer.render_document(Path(__file__).resolve().parents[1] / "renderer")
        self.assertIn("window.__numcalcUpdates", html)
        self.assertIn("update_check", html)
        self.assertIn("settings-updates", html)
        self.assertIn(".update-overlay", html)


if __name__ == "__main__":
    unittest.main()
