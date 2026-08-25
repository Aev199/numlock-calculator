import unittest
from email.message import Message
from pathlib import Path
from types import SimpleNamespace

import collect_third_party_licenses
import product_info


ROOT = Path(__file__).resolve().parents[1]


class PublicReleaseTests(unittest.TestCase):
    def test_required_public_files_exist(self):
        for relative in (
            "LICENSE",
            "LICENSING.md",
            "THIRD_PARTY_NOTICES.md",
            "SECURITY.md",
            "CONTRIBUTING.md",
            "RELEASE_NOTES.md",
            "docs/WINDOWS_ACCEPTANCE.md",
            "docs/RELEASE_CHECKLIST.md",
            "NumCalc.spec",
            "NumCalc-folder.spec",
            "NumCalc.manifest",
            ".github/workflows/release.yml",
        ):
            self.assertTrue((ROOT / relative).is_file(), relative)

        self.assertFalse((ROOT / "NumLockCalc.spec").exists())
        self.assertFalse((ROOT / "NumLockCalc-folder.spec").exists())
        self.assertFalse((ROOT / "WINDOWS_ACCEPTANCE.md").exists())
        self.assertFalse((ROOT / "RELEASE_CHECKLIST.md").exists())

    def test_windows_builds_embed_common_controls_manifest(self):
        manifest = (ROOT / "NumCalc.manifest").read_text(encoding="utf-8")
        self.assertIn("Microsoft.Windows.Common-Controls", manifest)
        self.assertIn('version="6.0.0.0"', manifest)
        expected_identity = ".".join(map(str, product_info.version_tuple()))
        self.assertIn(f'version="{expected_identity}"', manifest)
        for relative in ("NumCalc.spec", "NumCalc-folder.spec"):
            spec = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn("manifest='NumCalc.manifest'", spec)

    def test_product_links_and_license_are_centralized(self):
        self.assertEqual(product_info.LICENSE_NAME, "MIT")
        self.assertEqual(
            product_info.REPOSITORY_URL,
            "https://github.com/Aev199/numlock-calculator",
        )
        self.assertEqual(product_info.INSPIRATION_URL, "https://nlcalc.narod.ru/")

    def test_release_documents_match_product_version(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        notes = (ROOT / "RELEASE_NOTES.md").read_text(encoding="utf-8")
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        acceptance = (ROOT / "docs/WINDOWS_ACCEPTANCE.md").read_text(
            encoding="utf-8"
        )
        checklist = (ROOT / "docs/RELEASE_CHECKLIST.md").read_text(
            encoding="utf-8"
        )
        version_info = (ROOT / "version_info.txt").read_text(encoding="utf-8")
        version = product_info.APP_VERSION

        self.assertIn(f"**NumCalc {version}**", readme)
        self.assertTrue(notes.startswith(f"# NumCalc {version}\n"))
        self.assertIn(f"## {version} —", changelog)
        self.assertIn(f"Версия для проверки: **{version}**", acceptance)
        self.assertIn(f"# NumCalc {version} — чек-лист релиза", checklist)
        self.assertIn(f"StringStruct('FileVersion', '{version}')", version_info)
        self.assertIn(f"StringStruct('ProductVersion', '{version}')", version_info)

    def test_readme_contains_attribution_and_public_links(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("идеологическое продолжение", readme)
        self.assertIn("Владимира Потапова", readme)
        self.assertIn(product_info.INSPIRATION_URL, readme)
        self.assertIn(product_info.REPOSITORY_URL, readme)
        self.assertIn("THIRD_PARTY_NOTICES.md", readme)
        self.assertIn("docs/WINDOWS_ACCEPTANCE.md", readme)

    def test_runtime_dependencies_are_separate_from_builder(self):
        runtime = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        build = (ROOT / "requirements-build.txt").read_text(encoding="utf-8")
        self.assertIn("pywebview==6.2.1", runtime)
        self.assertIn("pystray==0.19.5", runtime)
        self.assertNotIn("pyinstaller", runtime.lower())
        self.assertIn("-r requirements.txt", build)
        self.assertIn("pyinstaller==6.21.0", build.lower())

    def test_license_requirement_parser_ignores_extras(self):
        self.assertEqual(
            collect_third_party_licenses.requirement_name("six>=1.16"),
            "six",
        )
        self.assertEqual(
            collect_third_party_licenses.requirement_name(
                'pythonnet; platform_system == "Windows"'
            ),
            "pythonnet",
        )
        self.assertIsNone(
            collect_third_party_licenses.requirement_name(
                'pytest; extra == "test"'
            )
        )

    def test_long_license_text_falls_back_to_classifier(self):
        package_metadata = Message()
        package_metadata["License"] = "Long license text " * 20
        package_metadata["Classifier"] = "License :: OSI Approved :: BSD License"
        distribution = SimpleNamespace(metadata=package_metadata)
        self.assertEqual(
            collect_third_party_licenses.concise_license_label(distribution),
            "BSD License",
        )

    def test_release_workflow_publishes_only_on_matching_tag(self):
        workflow = (ROOT / ".github/workflows/release.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("workflow_dispatch", workflow)
        self.assertNotIn("pull_request", workflow)
        self.assertIn("tags:", workflow)
        self.assertIn("gh release create", workflow)
        self.assertIn("if: startsWith(github.ref, 'refs/tags/')", workflow)
        self.assertIn("from product_info import APP_VERSION", workflow)
        self.assertIn("does not match product version", workflow)
        self.assertIn("pystray==0.19.5", workflow)
        self.assertNotIn("--no-binary=:all:", workflow)
        self.assertIn("THIRD_PARTY_NOTICES.md", workflow)


if __name__ == "__main__":
    unittest.main()
