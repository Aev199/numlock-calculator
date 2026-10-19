"""Self-update of the portable NumCalc.exe from GitHub Releases.

A release carries ``NumCalc.exe`` and ``latest.json`` (version, commit,
SHA-256, change list). The app picks the newest release of its channel,
downloads the EXE, checks its hash and swaps files by renaming: Windows lets a
running EXE be renamed, not overwritten. The previous EXE stays beside it as
``<name>.old.exe`` for one-click rollback.

When the program itself has no way out, two offline sources work as well: a
shared folder with the same two files, and the browser's Downloads folder.
Nothing here touches the UI; the network call is injected so tests stay local.
"""

from __future__ import annotations

import base64
import hashlib
import html
import json
import os
import re
import subprocess
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from product_info import APP_VERSION

REPOSITORY = "Aev199/numlock-calculator"
EXE_ASSET = "NumCalc.exe"
MANIFEST_ASSET = "latest.json"
SOURCE_FILE = "numcalc-update.txt"
USER_AGENT = f"NumCalc/{APP_VERSION}"

STABLE = "stable"
BETA = "beta"
CHANNEL_LABELS = {STABLE: "Стабильные", BETA: "Все сборки (бета)"}

Progress = Callable[[int, int | None], None]
Fetch = Callable[[str, Progress], bytes]


class UpdateError(Exception):
    """A failed step with a message fit for the user.

    ``answered`` means a server replied (with an error or bad data): another
    network route would get the same answer, so the caller does not fall back.
    """

    def __init__(self, message: str, *, answered: bool = False) -> None:
        super().__init__(message)
        self.answered = answered


@dataclass
class Update:
    version: str
    sha256: str
    exe_url: str
    page: str
    commit: str = ""
    notes: list[str] = field(default_factory=list)
    prerelease: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "commit": self.commit,
            "notes": list(self.notes),
            "page": self.page,
            "prerelease": self.prerelease,
            "local": not self.exe_url.startswith("https://"),
            "source": self.exe_url,
        }


def channel_key(value: object) -> str:
    return STABLE if value == STABLE else BETA if value == BETA else STABLE


def parse_version(text: str) -> list[int]:
    """``v1.4.0`` / ``1.4.0-beta.1`` → ``[1, 4, 0]``."""

    numbers: list[int] = []
    for part in re.split(r"[.\-+]", str(text).strip().lstrip("vV")):
        if not part.isdigit():
            break
        numbers.append(int(part))
    return numbers


def is_prerelease(text: str) -> bool:
    return "-" in str(text).strip()


def compare_versions(left: str, right: str) -> int:
    """Numeric comparison; with equal numbers ``1.4.2-beta.1`` precedes ``1.4.2``."""

    a, b = parse_version(left), parse_version(right)
    for index in range(max(len(a), len(b))):
        x = a[index] if index < len(a) else 0
        y = b[index] if index < len(b) else 0
        if x != y:
            return 1 if x > y else -1
    pre_a, pre_b = is_prerelease(left), is_prerelease(right)
    if pre_a != pre_b:
        return -1 if pre_a else 1
    if pre_a:
        return _compare_suffixes(_suffix(left), _suffix(right))
    return 0


def _suffix(text: str) -> list[str]:
    return str(text).strip().split("-", 1)[1].split(".")


def _compare_suffixes(a: list[str], b: list[str]) -> int:
    """``beta.2`` > ``beta.1``, ``rc.1`` > ``beta.9``: numbers numerically, words by name."""

    for x, y in zip(a, b):
        if x == y:
            continue
        if x.isdigit() and y.isdigit():
            return 1 if int(x) > int(y) else -1
        if x.isdigit() != y.isdigit():
            return -1 if x.isdigit() else 1
        return 1 if x > y else -1
    return (len(a) > len(b)) - (len(a) < len(b))


def releases_url() -> str:
    return f"https://api.github.com/repos/{REPOSITORY}/releases?per_page=20"


def browser_url() -> str:
    """The newest final release's EXE; GitHub serves "latest" for final releases only."""

    return f"https://github.com/{REPOSITORY}/releases/latest/download/{EXE_ASSET}"


def pick_release(listing: bytes, channel: str) -> dict[str, object] | None:
    """The newest complete release of ``channel`` in GitHub's release list."""

    try:
        releases = json.loads(listing)
    except ValueError as error:
        raise UpdateError(f"GitHub вернул непонятный ответ: {error}", answered=True) from error
    best: dict[str, object] | None = None
    for release in releases if isinstance(releases, list) else []:
        if not isinstance(release, dict) or release.get("draft"):
            continue
        prerelease = bool(release.get("prerelease"))
        if prerelease and channel != BETA:
            continue
        assets = {
            asset.get("name"): asset.get("browser_download_url")
            for asset in release.get("assets") or []
            if isinstance(asset, dict)
        }
        if not assets.get(EXE_ASSET) or not assets.get(MANIFEST_ASSET):
            continue
        candidate = {
            "version": str(release.get("tag_name", "")).lstrip("vV"),
            "page": str(release.get("html_url", "")),
            "exe_url": str(assets[EXE_ASSET]),
            "manifest_url": str(assets[MANIFEST_ASSET]),
            "prerelease": prerelease,
        }
        if best is None or compare_versions(candidate["version"], best["version"]) > 0:
            best = candidate
    return best


def _manifest(data: bytes, origin: str) -> dict[str, object]:
    try:
        manifest = json.loads(data.decode("utf-8-sig"))
    except (ValueError, UnicodeDecodeError) as error:
        raise UpdateError(f"{MANIFEST_ASSET} {origin} повреждён: {error}", answered=True) from error
    if not isinstance(manifest, dict) or not manifest.get("version"):
        raise UpdateError(f"{MANIFEST_ASSET} {origin} не содержит версии", answered=True)
    sha = str(manifest.get("sha256", "")).strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", sha):
        raise UpdateError(f"{MANIFEST_ASSET} {origin} не содержит контрольной суммы", answered=True)
    notes = manifest.get("notes") or []
    manifest["sha256"] = sha
    manifest["notes"] = [str(note) for note in notes if str(note).strip()] if isinstance(notes, list) else []
    return manifest


def check(current: str, channel: str, fetch: Fetch) -> Update | None:
    """A newer version than ``current`` on ``channel``, if there is one."""

    candidate = pick_release(fetch(releases_url(), _ignore), channel)
    if candidate is None or compare_versions(str(candidate["version"]), current) <= 0:
        return None
    manifest = _manifest(fetch(str(candidate["manifest_url"]), _ignore), "выпуска")
    if compare_versions(str(manifest["version"]), str(candidate["version"])) != 0:
        raise UpdateError("Описание выпуска не совпадает с самим выпуском", answered=True)
    return Update(
        version=str(candidate["version"]),
        sha256=str(manifest["sha256"]),
        exe_url=str(candidate["exe_url"]),
        page=str(candidate["page"]),
        commit=str(manifest.get("commit", "")),
        notes=list(manifest["notes"]),
        prerelease=bool(candidate["prerelease"]),
    )


def _ignore(_done: int, _total: int | None) -> None:
    return None


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def previous_path(exe: Path) -> Path:
    """Where the replaced EXE is kept for rollback."""

    return exe.with_name(f"{exe.stem}.old.exe")


def staged_path(exe: Path) -> Path:
    return exe.with_name(f"{exe.stem}.new.exe")


def install(exe: Path, data: bytes, sha256: str) -> None:
    """Put ``data`` in place of ``exe`` after checking the hash.

    The old EXE becomes ``previous_path(exe)``. Nothing changes if any step fails.
    """

    if sha256_hex(data) != sha256.strip().lower():
        raise UpdateError("Контрольная сумма загруженного файла не совпала")
    if not data.startswith(b"MZ"):
        raise UpdateError("Загруженный файл не является программой Windows")
    staged = staged_path(exe)
    previous = previous_path(exe)
    try:
        with open(staged, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError:
        staged.unlink(missing_ok=True)
        raise
    try:
        previous.unlink(missing_ok=True)
        os.replace(exe, previous)
    except OSError:
        staged.unlink(missing_ok=True)
        raise
    try:
        os.replace(staged, exe)
    except OSError:
        try:
            os.replace(previous, exe)
        finally:
            staged.unlink(missing_ok=True)
        raise


def rollback(exe: Path) -> None:
    """Swap ``exe`` with the kept previous version, so the rollback can be undone too."""

    previous = previous_path(exe)
    if not previous.exists():
        raise UpdateError("Предыдущей версии нет")
    swap = staged_path(exe)
    swap.unlink(missing_ok=True)
    os.replace(exe, swap)
    try:
        os.replace(previous, exe)
    except OSError:
        os.replace(swap, exe)
        raise
    # The previous version runs either way; only the copy to undo can be lost.
    os.replace(swap, previous)


def remove_leftovers(exe: Path) -> None:
    """Drop a staged file from an install that stopped half way."""

    try:
        staged_path(exe).unlink(missing_ok=True)
    except OSError:
        pass


def folder_from_side_file(exe: Path) -> Path | None:
    """The folder named in ``numcalc-update.txt`` beside ``exe``.

    An administrator sets it once for everybody who runs NumCalc from there.
    """

    try:
        text = (exe.parent / SOURCE_FILE).read_text(encoding="utf-8-sig")
    except OSError:
        return None
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return Path(line.strip('"'))
    return None


def check_folder(folder: Path, current: str) -> Update | None:
    """An update kept in a shared folder: ``latest.json`` and ``NumCalc.exe``."""

    try:
        data = (folder / MANIFEST_ASSET).read_bytes()
    except OSError as error:
        raise UpdateError(f"Папка обновлений «{folder}» недоступна: {error.strerror or error}") from error
    manifest = _manifest(data, "в папке обновлений")
    if compare_versions(str(manifest["version"]), current) <= 0:
        return None
    exe = folder / EXE_ASSET
    if not exe.is_file():
        raise UpdateError(f"В папке обновлений нет {EXE_ASSET}")
    return Update(
        version=str(manifest["version"]),
        sha256=str(manifest["sha256"]),
        exe_url=str(exe),
        page=str(folder),
        commit=str(manifest.get("commit", "")),
        notes=list(manifest["notes"]),
        prerelease=manifest.get("channel") == BETA,
    )


def publish_to_folder(folder: Path, update: Update, data: bytes) -> bool:
    """Put an installed version into the shared folder for colleagues.

    Skipped when the folder already has it or a newer one. The EXE goes first
    and the manifest last, so the folder never announces a file that is not there.
    """

    manifest_path = folder / MANIFEST_ASSET
    try:
        existing = _manifest(manifest_path.read_bytes(), "")
        if compare_versions(str(existing["version"]), update.version) >= 0:
            return False
    except (OSError, UpdateError):
        pass
    staged = folder / f"{EXE_ASSET}.part"
    staged.write_bytes(data)
    # A colleague may be copying the old EXE right now; replace, not truncate.
    os.replace(staged, folder / EXE_ASSET)
    manifest = {
        "version": update.version,
        "commit": update.commit,
        "channel": BETA if update.prerelease else STABLE,
        "sha256": sha256_hex(data),
        "notes": update.notes,
    }
    staged = folder / f"{MANIFEST_ASSET}.part"
    staged.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(staged, manifest_path)
    return True


def downloads_dir() -> Path | None:
    """The user's Downloads folder, wherever it was moved."""

    if os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
            ) as key:
                value, _ = winreg.QueryValueEx(key, "{374DE290-123F-4565-9164-39C4925E467B}")
            return Path(os.path.expandvars(value))
        except OSError:
            pass
    home = Path.home()
    return home / "Downloads" if home else None


_VERSION_KEY = "ProductVersion".encode("utf-16-le") + b"\x00\x00"
_VERSION_INFO = "VS_VERSION_INFO".encode("utf-16-le")
_FIXED_INFO_SIGNATURE = b"\xbd\x04\xef\xfe"
# The version resource sits in the bootloader part of the EXE, well inside this.
_VERSION_SCAN_BYTES = 4 * 1024 * 1024


def version_from_resource(data: bytes) -> str | None:
    """The ProductVersion string of a version resource, suffix included.

    The numeric file version drops prerelease suffixes, so 1.4.2-beta.1 and
    1.4.2 would look the same; the string keeps them apart. The numbers are
    the fallback for an EXE without the string.
    """

    start = data.find(_VERSION_INFO)
    if start < 0:
        return None
    key = data.find(_VERSION_KEY, start, start + 16384)
    if key >= 0:
        position = key + len(_VERSION_KEY)
        position += (-position) % 4
        end = position
        while end + 1 < len(data) and data[end:end + 2] != b"\x00\x00":
            end += 2
        value = data[position:end].decode("utf-16-le", "replace").strip()
        if parse_version(value):
            return value
    fixed = data.find(_FIXED_INFO_SIGNATURE, start, start + 16384)
    if fixed < 0 or fixed + 16 > len(data):
        return None
    ms = int.from_bytes(data[fixed + 8:fixed + 12], "little")
    ls = int.from_bytes(data[fixed + 12:fixed + 16], "little")
    return f"{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}"


def exe_version(path: Path) -> str | None:
    """The version in an EXE's file properties ("1.4.2-beta.1")."""

    try:
        with open(path, "rb") as handle:
            return version_from_resource(handle.read(_VERSION_SCAN_BYTES))
    except OSError:
        return None


def find_downloaded(
    folder: Path,
    current: str,
    version_of: Callable[[Path], str | None] = exe_version,
) -> tuple[Path, str] | None:
    """The newest ``NumCalc*.exe`` in ``folder`` that is newer than ``current``.

    Browsers add " (1)" to repeated downloads, so any suffix is accepted.
    """

    try:
        entries: Iterable[Path] = list(folder.iterdir())
    except OSError:
        return None
    best: tuple[Path, str] | None = None
    for path in entries:
        name = path.name.lower()
        if not (name.startswith("numcalc") and name.endswith(".exe")) or not path.is_file():
            continue
        try:
            version = version_of(path)
        except OSError:
            version = None
        if not version or compare_versions(version, current) <= 0:
            continue
        if best is None or compare_versions(version, best[1]) > 0:
            best = (path, version)
    return best


def downloaded_update(path: Path, version: str) -> Update:
    """An update offered from a file the browser downloaded."""

    return Update(
        version=version,
        sha256=sha256_hex(path.read_bytes()),
        exe_url=str(path),
        page=str(path.parent),
    )


def get(location: str, progress: Progress, fetch: Fetch | None = None) -> bytes:
    """The update's EXE: downloaded for a release, read for a local file."""

    if location.startswith("https://"):
        return (fetch or https_get)(location, progress)
    path = Path(location)
    total = path.stat().st_size
    chunks: list[bytes] = []
    done = 0
    with open(path, "rb") as handle:
        while chunk := handle.read(256 * 1024):
            chunks.append(chunk)
            done += len(chunk)
            progress(done, total)
    return b"".join(chunks)


def https_get(url: str, progress: Progress) -> bytes:
    """GET over HTTPS with the system proxy; PowerShell when the route itself fails.

    PowerShell's web client sends the Windows login to a proxy that asks for
    it and follows PAC scripts, which corporate filters often let through.
    """

    try:
        return _urllib_get(url, progress)
    except UpdateError as first:
        if first.answered or os.name != "nt":
            raise
        try:
            data = _powershell_get(url)
        except UpdateError as second:
            raise UpdateError(f"{first}. Запасной способ (PowerShell) тоже не сработал: {second}") from second
        progress(len(data), len(data))
        return data


def _urllib_get(url: str, progress: Progress) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json, application/octet-stream",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            length = response.headers.get("Content-Length")
            total = int(length) if length and length.isdigit() else None
            chunks: list[bytes] = []
            done = 0
            while chunk := response.read(64 * 1024):
                chunks.append(chunk)
                done += len(chunk)
                progress(done, total)
            return b"".join(chunks)
    except urllib.error.HTTPError as error:
        raise UpdateError(http_message(error.code), answered=error.code != 407) from error
    except (urllib.error.URLError, OSError) as error:
        reason = getattr(error, "reason", error)
        raise UpdateError(f"Нет связи с GitHub: {reason}") from error


def http_message(status: int) -> str:
    if status in (403, 429):
        return "GitHub временно ограничил запросы, попробуйте через час"
    if status == 404:
        return "Выпуски не найдены: репозиторий закрыт или выпусков ещё нет"
    if status == 407:
        return "Прокси требует входа (407)"
    return f"Сервер ответил {status}"


def powershell_script(url: str, target: Path) -> str:
    def quote(text: str) -> str:
        return "'" + text.replace("'", "''") + "'"

    return (
        "$ErrorActionPreference='Stop'; "
        "[Net.ServicePointManager]::SecurityProtocol = "
        "[Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12; "
        "$c = New-Object Net.WebClient; "
        f"$c.Headers.Add('User-Agent', {quote(USER_AGENT)}); "
        "$c.Headers.Add('Accept', 'application/vnd.github+json, application/octet-stream'); "
        "$c.Proxy = [Net.WebRequest]::GetSystemWebProxy(); "
        "$c.Proxy.Credentials = [Net.CredentialCache]::DefaultNetworkCredentials; "
        f"$c.DownloadFile({quote(url)}, {quote(str(target))})"
    )


def encode_command(script: str) -> str:
    """``-EncodedCommand`` text: Base64 of UTF-16LE, so no quoting can break it."""

    return base64.b64encode(script.encode("utf-16-le")).decode("ascii")


def clixml_text(output: str) -> str:
    """The readable text inside PowerShell's CLIXML error stream."""

    if not output.lstrip().startswith("#< CLIXML"):
        return output.strip()
    parts = re.findall(r'<S S="Error">(.*?)</S>', output, flags=re.DOTALL)
    text = "".join(parts).replace("_x000D_", "").replace("_x000A_", " ")
    return " ".join(html.unescape(text).split())


def _powershell_get(url: str) -> bytes:
    handle, name = tempfile.mkstemp(prefix="numcalc-download-", suffix=".tmp")
    os.close(handle)
    target = Path(name)
    try:
        completed = subprocess.run(
            [
                "powershell.exe", "-NoProfile", "-NonInteractive",
                "-ExecutionPolicy", "Bypass",
                "-EncodedCommand", encode_command(powershell_script(url, target)),
            ],
            capture_output=True,
            timeout=600,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if completed.returncode != 0:
            text = clixml_text(completed.stderr.decode("utf-8", "replace")) or "неизвестная ошибка"
            raise UpdateError(text[:300])
        return target.read_bytes()
    except (OSError, subprocess.SubprocessError) as error:
        raise UpdateError(str(error)) from error
    finally:
        target.unlink(missing_ok=True)
