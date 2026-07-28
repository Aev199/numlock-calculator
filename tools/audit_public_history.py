"""Scan reachable Git history for high-confidence secrets and risky filenames.

This is a release gate, not a replacement for GitHub secret scanning or a
professional security review. It intentionally uses conservative patterns to
avoid treating ordinary source-code words such as ``token`` as credentials.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path


MAX_BLOB_SIZE = 2 * 1024 * 1024
SECRET_PATTERNS = {
    "private key": re.compile(
        rb"-----BEGIN (?:RSA |OPENSSH |EC |DSA |PGP )?PRIVATE KEY-----"
    ),
    "GitHub token": re.compile(rb"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b"),
    "AWS access key": re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "OpenAI-style secret": re.compile(rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b"),
    "Slack token": re.compile(rb"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
}
SENSITIVE_NAMES = {
    ".env",
    ".env.local",
    "id_rsa",
    "id_ed25519",
    "credentials.json",
    "service-account.json",
}
SENSITIVE_SUFFIXES = {".pem", ".p12", ".pfx", ".key", ".kdbx"}
BINARY_ARTIFACT_SUFFIXES = {".exe", ".dll", ".zip", ".7z", ".rar", ".msi"}


def git(*args: str, input_text: str | None = None) -> str:
    result = subprocess.run(
        ("git", *args),
        input=input_text,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout


def reachable_objects() -> list[tuple[str, str]]:
    objects: list[tuple[str, str]] = []
    for line in git("rev-list", "--objects", "--all").splitlines():
        sha, separator, path = line.partition(" ")
        objects.append((sha, path if separator else ""))
    return objects


def blob_metadata(objects: list[tuple[str, str]]) -> list[tuple[str, int, str]]:
    query = "".join(f"{sha} {path}\n" for sha, path in objects)
    output = git(
        "cat-file",
        "--batch-check=%(objectname) %(objecttype) %(objectsize) %(rest)",
        input_text=query,
    )
    blobs: list[tuple[str, int, str]] = []
    for line in output.splitlines():
        sha, object_type, size_text, _, path = line.split(" ", 4)
        if object_type == "blob":
            blobs.append((sha, int(size_text), path))
    return blobs


def read_blob(sha: str) -> bytes:
    result = subprocess.run(
        ("git", "cat-file", "blob", sha),
        capture_output=True,
        check=True,
    )
    return result.stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--strict-artifacts",
        action="store_true",
        help="also fail if binary build artifacts occur anywhere in history",
    )
    args = parser.parse_args()

    objects = reachable_objects()
    blobs = blob_metadata(objects)
    findings: list[str] = []
    artifact_paths: set[str] = set()
    scanned = 0

    for sha, size, path_text in blobs:
        path = Path(path_text) if path_text else Path("<unknown>")
        lower_name = path.name.lower()
        lower_suffix = path.suffix.lower()

        if lower_name in SENSITIVE_NAMES or lower_suffix in SENSITIVE_SUFFIXES:
            findings.append(f"sensitive historical path: {path_text} ({sha})")
        if lower_suffix in BINARY_ARTIFACT_SUFFIXES:
            artifact_paths.add(path_text)

        if size > MAX_BLOB_SIZE:
            continue
        content = read_blob(sha)
        if b"\x00" in content[:4096]:
            continue
        scanned += 1
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(content):
                findings.append(f"{label}: {path_text or '<unknown>'} ({sha})")

    print(f"History audit: {len(objects)} objects, {scanned} text blobs scanned")
    if artifact_paths:
        print("Historical build/archive paths (review before publication):")
        for path in sorted(artifact_paths):
            print(f"  - {path}")

    if findings:
        print("Blocking findings:")
        for finding in sorted(set(findings)):
            print(f"  - {finding}")
        return 1
    if args.strict_artifacts and artifact_paths:
        print("Binary artifacts are blocking in strict mode.")
        return 1

    print("No high-confidence secrets or sensitive credential files found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
