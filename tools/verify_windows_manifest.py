"""Verify that a Windows executable embeds the NumCalc common-controls manifest."""

from __future__ import annotations

import argparse
from pathlib import Path

import pefile


RT_MANIFEST = 24
REQUIRED_MARKERS = (
    "Microsoft.Windows.Common-Controls",
    'version="6.0.0.0"',
    'requestedExecutionLevel level="asInvoker"',
)


def manifest_blobs(executable: Path) -> list[bytes]:
    pe = pefile.PE(str(executable), fast_load=False)
    try:
        directory = getattr(pe, "DIRECTORY_ENTRY_RESOURCE", None)
        if directory is None:
            return []
        result: list[bytes] = []
        for type_entry in directory.entries:
            if type_entry.id != RT_MANIFEST or not hasattr(type_entry, "directory"):
                continue
            for name_entry in type_entry.directory.entries:
                if not hasattr(name_entry, "directory"):
                    continue
                for language_entry in name_entry.directory.entries:
                    data = language_entry.data.struct
                    result.append(pe.get_data(data.OffsetToData, data.Size))
        return result
    finally:
        pe.close()


def decode_manifest(blob: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "utf-16-le"):
        try:
            return blob.decode(encoding)
        except UnicodeDecodeError:
            continue
    return blob.decode("latin-1", errors="replace")


def verify(executable: Path) -> None:
    if not executable.is_file():
        raise SystemExit(f"Executable not found: {executable}")
    manifests = [decode_manifest(blob) for blob in manifest_blobs(executable)]
    if not manifests:
        raise SystemExit("No RT_MANIFEST resource found")
    combined = "\n".join(manifests)
    missing = [marker for marker in REQUIRED_MARKERS if marker not in combined]
    if missing:
        raise SystemExit("Embedded manifest is missing: " + ", ".join(missing))
    print(f"Verified common-controls manifest in {executable}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    args = parser.parse_args()
    verify(args.executable)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
