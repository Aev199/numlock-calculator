import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import release_manifest  # noqa: E402
import update_core  # noqa: E402
from product_info import APP_VERSION  # noqa: E402

CHANGELOG = """# Changelog

## Unreleased

- не попадает в выпуск;

## 1.4.0 — 2026-10-18

### Добавлено

- обновление из приложения;
- единицы `кН·м` и **см²**.

## 1.3.0 — 2026-08-25

- старое.
"""


class ReleaseManifestTests(unittest.TestCase):
    def test_notes_come_from_the_version_section(self):
        self.assertEqual(
            release_manifest.changelog_notes(CHANGELOG, "1.4.0"),
            ["Обновление из приложения", "Единицы кН·м и см²"],
        )
        self.assertEqual(release_manifest.changelog_notes(CHANGELOG, "1.5.0"), [])

    def test_suffixed_versions_are_beta(self):
        self.assertEqual(release_manifest.channel_for("1.5.0-beta.1"), "beta")
        self.assertEqual(release_manifest.channel_for("1.4.0"), "stable")

    def test_manifest_is_accepted_by_the_shared_folder_check(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            exe = folder / update_core.EXE_ASSET
            exe.write_bytes(b"MZ release")
            manifest = release_manifest.build_manifest(exe, "99.0.0", "abc", CHANGELOG)
            import json
            (folder / update_core.MANIFEST_ASSET).write_text(json.dumps(manifest), encoding="utf-8")
            found = update_core.check_folder(folder, APP_VERSION)
            self.assertEqual((found.version, found.sha256), ("99.0.0", update_core.sha256_hex(b"MZ release")))

    def test_current_changelog_describes_the_product_version(self):
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertTrue(release_manifest.changelog_notes(changelog, APP_VERSION))


if __name__ == "__main__":
    unittest.main()
