"""Collect license files for the runtime dependency closure.

Run this after installing ``requirements.txt`` on the target build platform.
The generated directory is shipped next to NumCalc.exe in public releases.
"""

from __future__ import annotations

import argparse
import re
import shutil
from collections import deque
from importlib import metadata
from pathlib import Path


ROOT_DISTRIBUTIONS = ("pywebview", "keyboard", "pystray", "Pillow")
LICENSE_PREFIXES = (
    "LICENSE",
    "LICENCE",
    "COPYING",
    "COPYRIGHT",
    "NOTICE",
    "AUTHORS",
)
_REQUIREMENT_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9_.-]*)")


def normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def requirement_name(requirement: str) -> str | None:
    """Extract an installed distribution name, ignoring optional extras."""
    if "extra ==" in requirement or "extra==" in requirement:
        return None
    match = _REQUIREMENT_NAME.match(requirement)
    return match.group(1) if match else None


def runtime_distributions() -> list[metadata.Distribution]:
    queue = deque(ROOT_DISTRIBUTIONS)
    seen: set[str] = set()
    result: list[metadata.Distribution] = []

    while queue:
        requested = queue.popleft()
        key = normalize_name(requested)
        if key in seen:
            continue
        seen.add(key)

        try:
            distribution = metadata.distribution(requested)
        except metadata.PackageNotFoundError:
            continue

        result.append(distribution)
        for requirement in distribution.requires or ():
            dependency = requirement_name(requirement)
            if dependency and normalize_name(dependency) not in seen:
                queue.append(dependency)

    return sorted(
        result,
        key=lambda item: normalize_name(item.metadata.get("Name", "")),
    )


def is_license_file(path: Path) -> bool:
    name = path.name.upper()
    return any(name.startswith(prefix) for prefix in LICENSE_PREFIXES)


def concise_license_label(distribution: metadata.Distribution) -> str:
    """Return a short label without embedding an entire license in the table."""

    expression = distribution.metadata.get("License-Expression")
    if expression and expression.strip():
        return " ".join(expression.split())

    declared = distribution.metadata.get("License")
    if declared:
        normalized = " ".join(declared.split())
        if len(normalized) <= 120:
            return normalized

    classifiers = distribution.metadata.get_all("Classifier") or ()
    labels: list[str] = []
    for classifier in classifiers:
        if not classifier.startswith("License ::"):
            continue
        label = classifier.rsplit("::", 1)[-1].strip()
        if label and label not in labels:
            labels.append(label)
    return ", ".join(labels) or "см. вложенные файлы"


def project_urls(distribution: metadata.Distribution) -> list[str]:
    urls: list[str] = []
    homepage = (distribution.metadata.get("Home-page") or "").strip()
    if homepage:
        urls.append(homepage)
    for item in distribution.metadata.get_all("Project-URL") or ():
        _, separator, value = item.partition(",")
        url = (value if separator else item).strip()
        if url and url not in urls:
            urls.append(url)
    return urls


def write_package_metadata(
    target: Path,
    distribution: metadata.Distribution,
    license_name: str,
    copied: int,
) -> None:
    name = distribution.metadata.get("Name", "unknown")
    lines = [
        f"Package: {name}",
        f"Version: {distribution.version}",
        f"License metadata: {license_name}",
        f"Copied license/notice files: {copied}",
    ]
    urls = project_urls(distribution)
    if urls:
        lines.append("Project URLs:")
        lines.extend(f"- {url}" for url in urls)
    if copied == 0:
        lines.extend(
            [
                "",
                "The installed distribution did not expose a separate LICENSE,",
                "COPYING or NOTICE file through package metadata. Consult the",
                "declared license and the upstream project for complete terms.",
            ]
        )
    (target / "PACKAGE_METADATA.txt").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def collect(output_dir: Path) -> list[tuple[str, str, str, int]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[tuple[str, str, str, int]] = []

    for distribution in runtime_distributions():
        name = distribution.metadata.get("Name", "unknown")
        version = distribution.version
        license_name = concise_license_label(distribution)
        target = output_dir / f"{normalize_name(name)}-{version}"
        target.mkdir(parents=True, exist_ok=True)

        copied = 0
        for relative in distribution.files or ():
            relative_path = Path(str(relative))
            if not is_license_file(relative_path):
                continue
            source = Path(distribution.locate_file(relative))
            if not source.is_file():
                continue
            destination = target / relative_path.name
            if destination.exists():
                suffix = 2
                while destination.with_name(
                    f"{destination.stem}-{suffix}{destination.suffix}"
                ).exists():
                    suffix += 1
                destination = destination.with_name(
                    f"{destination.stem}-{suffix}{destination.suffix}"
                )
            shutil.copy2(source, destination)
            copied += 1

        write_package_metadata(target, distribution, license_name, copied)
        rows.append((name, version, license_name, copied))

    report = [
        "# Лицензии фактически включённых runtime-пакетов",
        "",
        "Файл сформирован автоматически на Windows при сборке релиза.",
        "",
        "| Пакет | Версия | Метаданные лицензии | Файлов лицензий/уведомлений |",
        "|---|---:|---|---:|",
    ]
    for name, version, license_name, copied in rows:
        clean_license = " ".join(license_name.split()).replace("|", "\\|")
        report.append(f"| {name} | {version} | {clean_license} | {copied} |")
    report.extend(
        [
            "",
            "Если метаданные пакета неполны, условия определяются текстами лицензий",
            "в соответствующем подкаталоге и материалами upstream-проекта.",
        ]
    )
    (output_dir / "DEPENDENCIES.md").write_text(
        "\n".join(report) + "\n",
        encoding="utf-8",
    )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("release") / "licenses",
    )
    args = parser.parse_args()

    if args.output.exists():
        shutil.rmtree(args.output)
    rows = collect(args.output)
    if not rows:
        raise SystemExit("Runtime distributions were not found")
    if not any(normalize_name(name) == "pystray" for name, *_ in rows):
        raise SystemExit("pystray license data is missing")
    print(f"Collected license data for {len(rows)} distributions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
