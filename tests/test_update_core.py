import json
import tempfile
import unittest
from pathlib import Path

import update_core as core


LISTING = json.dumps([
    {"tag_name": "v1.6.0", "html_url": "h160", "draft": True, "prerelease": False,
     "assets": [{"name": "NumCalc.exe", "browser_download_url": "e160"},
                {"name": "latest.json", "browser_download_url": "m160"}]},
    {"tag_name": "v1.5.0-beta.1", "html_url": "h150", "draft": False, "prerelease": True,
     "assets": [{"name": "NumCalc.exe", "browser_download_url": "e150"},
                {"name": "latest.json", "browser_download_url": "m150"}]},
    {"tag_name": "v1.4.0", "html_url": "h140", "draft": False, "prerelease": False,
     "assets": [{"name": "NumCalc.exe", "browser_download_url": "e140"},
                {"name": "latest.json", "browser_download_url": "m140"}]},
    {"tag_name": "v1.9.0", "html_url": "h190", "draft": False, "prerelease": False,
     "assets": [{"name": "NumCalc-1.9.0-windows-x64.zip", "browser_download_url": "z190"}]},
]).encode()


def stub(manifest):
    def fetch(url, _progress):
        return LISTING if url == core.releases_url() else json.dumps(manifest).encode()
    return fetch


class VersionTests(unittest.TestCase):
    def test_versions_compare_numerically(self):
        self.assertEqual(core.compare_versions("1.10.0", "1.9.9"), 1)
        self.assertEqual(core.compare_versions("v1.4.0", "1.4.0"), 0)
        self.assertEqual(core.compare_versions("1.4", "1.3.99"), 1)
        self.assertEqual(core.compare_versions("1.4.0-beta.1", "1.4.1"), -1)
        self.assertEqual(core.compare_versions("1.4.2-beta.1", "1.4.2"), -1)
        self.assertEqual(core.compare_versions("1.4.2", "1.4.2-beta.1"), 1)
        self.assertEqual(core.compare_versions("1.4.2-beta.1", "1.4.1"), 1)
        self.assertEqual(core.compare_versions("1.4.2-beta.2", "1.4.2-beta.1"), 1)
        self.assertEqual(core.compare_versions("1.4.2-beta.10", "1.4.2-beta.9"), 1)
        self.assertEqual(core.compare_versions("1.4.2-rc.1", "1.4.2-beta.9"), 1)
        self.assertEqual(core.compare_versions("1.4.2-beta.2", "1.4.2-beta.2"), 0)

    def test_channel_picks_newest_complete_release(self):
        beta = core.pick_release(LISTING, core.BETA)
        self.assertEqual((beta["version"], beta["exe_url"], beta["prerelease"]), ("1.5.0-beta.1", "e150", True))
        stable = core.pick_release(LISTING, core.STABLE)
        self.assertEqual((stable["version"], stable["manifest_url"]), ("1.4.0", "m140"))
        self.assertIsNone(core.pick_release(b"[]", core.BETA))

    def test_check_reads_the_manifest_of_a_newer_release(self):
        manifest = {"version": "1.4.0", "commit": "abc", "sha256": "a" * 64, "notes": ["Обновления"]}
        found = core.check("1.3.0", core.STABLE, stub(manifest))
        self.assertEqual((found.version, found.notes, found.exe_url, found.page), ("1.4.0", ["Обновления"], "e140", "h140"))
        self.assertIsNone(core.check("1.4.0", core.STABLE, stub(manifest)))

    def test_manifest_of_another_version_is_refused(self):
        manifest = {"version": "1.5.0-beta.1", "sha256": "a" * 64}
        with self.assertRaises(core.UpdateError):
            core.check("1.3.0", core.STABLE, stub(manifest))
        with self.assertRaises(core.UpdateError):
            core.check("1.3.0", core.STABLE, stub({"version": "1.4.0", "sha256": "short"}))


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.addCleanup(self.directory.cleanup)

    def test_install_swaps_files_and_rollback_swaps_back(self):
        exe = self.root / "NumCalc.exe"
        exe.write_bytes(b"MZ old")
        new = b"MZ new"
        with self.assertRaises(core.UpdateError):
            core.install(exe, new, "0" * 64)
        with self.assertRaises(core.UpdateError):
            core.install(exe, b"not an exe", core.sha256_hex(b"not an exe"))
        self.assertEqual(exe.read_bytes(), b"MZ old")
        core.install(exe, new, core.sha256_hex(new).upper())
        self.assertEqual(exe.read_bytes(), b"MZ new")
        self.assertEqual(core.previous_path(exe).read_bytes(), b"MZ old")
        core.rollback(exe)
        self.assertEqual(exe.read_bytes(), b"MZ old")
        self.assertEqual(core.previous_path(exe).read_bytes(), b"MZ new")
        self.assertFalse(core.staged_path(exe).exists())

    def test_rollback_without_previous_version_fails_cleanly(self):
        exe = self.root / "NumCalc.exe"
        exe.write_bytes(b"MZ")
        with self.assertRaises(core.UpdateError):
            core.rollback(exe)
        self.assertEqual(exe.read_bytes(), b"MZ")

    def test_side_file_names_the_update_folder(self):
        exe = self.root / "NumCalc.exe"
        self.assertIsNone(core.folder_from_side_file(exe))
        (self.root / core.SOURCE_FILE).write_text('# папка обновлений\n"\\\\server\\soft\\NumCalc"\n', encoding="utf-8")
        self.assertEqual(core.folder_from_side_file(exe), Path(r"\\server\soft\NumCalc"))

    def test_shared_folder_offers_a_newer_version(self):
        data = b"MZ new"
        (self.root / core.EXE_ASSET).write_bytes(data)
        (self.root / core.MANIFEST_ASSET).write_text(json.dumps({
            "version": "1.4.0", "commit": "abc", "channel": "stable",
            "sha256": core.sha256_hex(data), "notes": ["Сеть"],
        }), encoding="utf-8")
        found = core.check_folder(self.root, "1.3.0")
        self.assertEqual((found.version, found.prerelease), ("1.4.0", False))
        self.assertEqual(core.get(found.exe_url, lambda *_: None), data)
        self.assertIsNone(core.check_folder(self.root, "1.4.0"))
        with self.assertRaisesRegex(core.UpdateError, "недоступна"):
            core.check_folder(self.root / "нет", "1.0.0")
        (self.root / core.EXE_ASSET).unlink()
        with self.assertRaises(core.UpdateError):
            core.check_folder(self.root, "1.0.0")

    def test_publishing_fills_the_shared_folder_once(self):
        data = b"MZ release"
        update = core.Update(version="1.4.0", sha256=core.sha256_hex(data), exe_url="", page="",
                             commit="abc", notes=["Сеть"], prerelease=True)
        self.assertTrue(core.publish_to_folder(self.root, update, data))
        self.assertIsNone(core.check_folder(self.root, "1.3.0"))
        found = core.check_folder(self.root, "1.3.0", core.BETA)
        self.assertEqual((found.version, found.notes, found.prerelease), ("1.4.0", ["Сеть"], True))
        self.assertFalse(core.publish_to_folder(self.root, update, data))
        self.assertFalse((self.root / "NumCalc.exe.part").exists())

    def test_a_beta_in_the_shared_folder_is_offered_on_the_beta_channel_only(self):
        data = b"MZ beta"
        (self.root / core.EXE_ASSET).write_bytes(data)
        (self.root / core.MANIFEST_ASSET).write_text(json.dumps({
            "version": "1.5.0-beta.1", "sha256": core.sha256_hex(data),
        }), encoding="utf-8")
        self.assertIsNone(core.check_folder(self.root, "1.4.0"))
        self.assertEqual(core.check_folder(self.root, "1.4.0", core.BETA).version, "1.5.0-beta.1")

    def test_newest_downloaded_numcalc_is_found(self):
        for name in ["NumCalc.exe", "NumCalc (1).exe", "numcalc (2).exe", "Other.exe", "NumCalc.zip"]:
            (self.root / name).write_bytes(b"MZ")
        versions = {"NumCalc.exe": "1.3.0", "NumCalc (1).exe": "1.5.0", "numcalc (2).exe": "1.4.0"}
        version_of = lambda path: versions.get(path.name, "9.9.9")
        path, version = core.find_downloaded(self.root, "1.3.5", version_of)
        self.assertEqual((path.name, version), ("NumCalc (1).exe", "1.5.0"))
        self.assertIsNone(core.find_downloaded(self.root, "1.5.0", version_of))
        self.assertEqual(core.downloaded_update(path, version).sha256, core.sha256_hex(b"MZ"))


def version_resource(product_version, fixed=(1, 4, 2)):
    """A minimal VS_VERSION_INFO laid out like the one PyInstaller embeds."""

    data = bytearray(b"MZ" + b"\x00" * 62)
    data += "VS_VERSION_INFO".encode("utf-16-le") + b"\x00\x00"
    while len(data) % 4:
        data += b"\x00"
    data += b"\xbd\x04\xef\xfe" + (0x10000).to_bytes(4, "little")
    data += ((fixed[0] << 16) | fixed[1]).to_bytes(4, "little")
    data += (fixed[2] << 16).to_bytes(4, "little")
    data += b"\x00" * 64
    if product_version is not None:
        data += "ProductVersion".encode("utf-16-le") + b"\x00\x00"
        while len(data) % 4:
            data += b"\x00"
        data += product_version.encode("utf-16-le") + b"\x00\x00"
    return bytes(data + b"\x00" * 32)


class ExeVersionTests(unittest.TestCase):
    def test_prerelease_suffix_is_read_from_the_version_string(self):
        self.assertEqual(core.version_from_resource(version_resource("1.4.2-beta.2")), "1.4.2-beta.2")
        self.assertEqual(core.version_from_resource(version_resource("1.4.2")), "1.4.2")

    def test_numbers_are_the_fallback(self):
        self.assertEqual(core.version_from_resource(version_resource(None, (1, 3, 0))), "1.3.0")
        self.assertIsNone(core.version_from_resource(b"MZ not a versioned exe"))

    def test_exe_file_is_read_from_disk(self):
        with tempfile.TemporaryDirectory() as directory:
            exe = Path(directory) / "NumCalc (2).exe"
            exe.write_bytes(version_resource("1.4.2-beta.2"))
            self.assertEqual(core.exe_version(exe), "1.4.2-beta.2")
            self.assertIsNone(core.exe_version(Path(directory) / "missing.exe"))


class TransportTests(unittest.TestCase):
    def test_powershell_route_is_encoded_safely(self):
        self.assertEqual(core.encode_command("abc"), "YQBiAGMA")
        self.assertEqual(core.encode_command("a"), "YQA=")
        script = core.powershell_script("https://x/y?a='b'", Path(r"C:\Temp\O'Neil.tmp"))
        self.assertIn("'https://x/y?a=''b'''", script)
        self.assertIn("O''Neil.tmp'", script)

    def test_clixml_errors_become_plain_text(self):
        raw = ('#< CLIXML\r\n<Objs Version="1.1.0.1"><S S="Error">Exception calling "DownloadFile": _x000D__x000A_</S>'
               '<S S="Error">Unable to connect &lt;remote&gt;_x000D__x000A_</S></Objs>')
        self.assertEqual(core.clixml_text(raw), 'Exception calling "DownloadFile": Unable to connect <remote>')
        self.assertEqual(core.clixml_text("  plain error \n"), "plain error")

    def test_http_errors_read_in_russian(self):
        self.assertIn("ограничил", core.http_message(403))
        self.assertIn("закрыт", core.http_message(404))
        self.assertTrue(core.browser_url().endswith("/releases/latest/download/NumCalc.exe"))


if __name__ == "__main__":
    unittest.main()
