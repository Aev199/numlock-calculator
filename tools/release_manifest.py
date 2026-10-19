"""Write latest.json for a release: version, commit, channel, SHA-256 and notes.

The in-app updater reads this file next to NumCalc.exe in a GitHub Release or a
shared folder. Notes are the bullet points of the version's CHANGELOG section.

    python tools/release_manifest.py dist/NumCalc.exe --output dist/latest.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from product_info import APP_VERSION  # noqa: E402


def changelog_notes(text: str, version: str) -> list[str]:
    """Bullet points of ``## <version>`` up to the next second-level heading."""

    notes: list[str] = []
    inside = False
    for line in text.splitlines():
        if line.startswith("## "):
            if inside:
                break
            inside = re.match(rf"## {re.escape(version)}(\s|$)", line) is not None
            continue
        if inside and line.startswith("- "):
            note = line[2:].strip().rstrip(";.")
            note = note.replace("**", "").replace("`", "")
            if note:
                notes.append(note[0].upper() + note[1:])
    return notes


def channel_for(version: str) -> str:
    """A version with a suffix (1.5.0-beta.1) is a beta build."""

    return "beta" if "-" in version else "stable"


def build_manifest(exe: Path, version: str, commit: str, changelog: str) -> dict[str, object]:
    return {
        "version": version,
        "commit": commit,
        "channel": channel_for(version),
        "sha256": hashlib.sha256(exe.read_bytes()).hexdigest(),
        "notes": changelog_notes(changelog, version),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("exe", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", default=APP_VERSION)
    parser.add_argument("--commit", default="")
    arguments = parser.parse_args()
    # Windows runners print through cp1252; the notes are Cyrillic.
    sys.stdout.reconfigure(encoding="utf-8")
    commit = arguments.commit or subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT,
    ).stdout.strip()
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    manifest = build_manifest(arguments.exe, arguments.version, commit, changelog)
    if not manifest["notes"]:
        print(f"CHANGELOG.md has no bullet points for {arguments.version}", file=sys.stderr)
        return 1
    arguments.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
